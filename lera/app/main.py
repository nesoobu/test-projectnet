import asyncio
import json
import math
import random
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, content as C, db, notify
from .auth import validate_init_data

MSK = timezone(timedelta(hours=3))
ONLINE_WINDOW = 5 * 60


@asynccontextmanager
async def lifespan(_app):
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    await db.connect()
    from .v2 import background_loop
    task = asyncio.create_task(background_loop())
    yield
    task.cancel()
    await db.close()


app = FastAPI(title="Лера", lifespan=lifespan, docs_url=None, redoc_url=None)


@app.middleware("http")
async def no_stale_static(request: Request, call_next):
    # Telegram WebView агрессивно кэширует — заставляем ревалидировать фронт
    resp = await call_next(request)
    if request.url.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


# ── helpers ──────────────────────────────────────────────────────────────

def today() -> str:
    return datetime.now(MSK).date().isoformat()


def yday() -> str:
    return (datetime.now(MSK).date() - timedelta(days=1)).isoformat()


def is_weekend() -> bool:
    return datetime.now(MSK).weekday() >= 5


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def sqlts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_ts(s: str | None) -> datetime | None:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S") if s else None


def is_premium(u: dict) -> bool:
    p = parse_ts(u.get("premium_until"))
    return bool(p and p > utcnow())


def is_online(u: dict) -> bool:
    s = parse_ts(u.get("last_seen"))
    return bool(s and (utcnow() - s).total_seconds() < ONLINE_WINDOW)


def level_of(xp: int) -> dict:
    lvl = int(math.sqrt(max(xp, 0) / 40)) + 1
    cur, nxt = 40 * (lvl - 1) ** 2, 40 * lvl ** 2
    return {"level": lvl, "xp": xp, "from": cur, "to": nxt}


def jl(s, default=None):
    try:
        return json.loads(s) if s else (default if default is not None else [])
    except ValueError:
        return default if default is not None else []


async def add_balance(tg_id: int, amount: int, reason: str):
    await db.run("UPDATE users SET balance = balance + ? WHERE tg_id=?", amount, tg_id)
    await db.run("INSERT INTO transactions (tg_id, amount, reason) VALUES (?,?,?)", tg_id, amount, reason)


async def spend(tg_id: int, amount: int, reason: str):
    ok = await db.change("UPDATE users SET balance = balance - ? WHERE tg_id=? AND balance >= ?", amount, tg_id, amount)
    if not ok:
        raise HTTPException(402, "Не хватает несо")
    await db.run("INSERT INTO transactions (tg_id, amount, reason) VALUES (?,?,?)", tg_id, -amount, reason)


async def add_xp(tg_id: int, amount: int):
    await db.run("UPDATE users SET xp = xp + ? WHERE tg_id=?", amount, tg_id)


async def bump_quest(tg_id: int, quest_id: str, n: int = 1):
    goal = C.QUESTS[quest_id][1]
    await db.run(
        "INSERT INTO quest_progress (tg_id, day, quest_id, progress) VALUES (?,?,?,MIN(?,?)) "
        "ON CONFLICT(tg_id, day, quest_id) DO UPDATE SET progress = MIN(progress + ?, ?)",
        tg_id, today(), quest_id, n, goal, n, goal)


PCOLS = ("p.nickname, p.age, p.city, p.gender, p.about, p.rank, p.roles, p.heroes, p.play_times, "
         "p.voice, p.photos, p.accent, p.duet_visible")
UCOLS = "u.tg_id, u.username, u.first_name, u.photo_url, u.premium_until, u.last_seen, u.xp, u.streak"


async def cosmetics(ids: list[int]) -> dict[int, dict]:
    if not ids:
        return {}
    q = ",".join("?" * len(ids))
    rows = await db.all_(f"SELECT tg_id, item_id FROM inventory WHERE equipped=1 AND tg_id IN ({q})", *ids)
    out: dict[int, dict] = {}
    for r in rows:
        kind = C.ITEMS.get(r["item_id"], (None, None))[1]
        if kind:
            out.setdefault(r["tg_id"], {})[kind] = r["item_id"]
    return out


def card(r: dict, cos: dict | None = None, games: list | None = None, rep: dict | None = None,
         game: str | None = None) -> dict:
    """game — какая игра «главная» в карточке: её ранг/роли/мейны идут в rank/roles/heroes."""
    photos = jl(r.get("photos"))
    cos = cos or {}
    title = cos.get("title")
    games = games or []
    g = next((x for x in games if x["game"] == game), games[0] if games else None)
    rep = rep or {}
    return {
        "tg_id": r["tg_id"],
        "name": r.get("nickname") or r.get("first_name") or "Игрок",
        "username": r.get("username"),
        "age": r.get("age"), "city": r.get("city"), "gender": r.get("gender"),
        "about": r.get("about") or "",
        "game": g["game"] if g else None,
        "rank": g["rank"] if g else None,
        "roles": g["roles"] if g else [], "heroes": g["heroes"] if g else [],
        "games": games, "rep": rep.get("score", 0), "rep_tags": rep.get("tags", []),
        "play_times": jl(r.get("play_times")),
        "voice": bool(r.get("voice")),
        "photos": photos,
        "avatar": photos[0] if photos else (r.get("photo_url") or ""),
        "accent": r.get("accent"),
        "online": is_online(r),
        "premium": is_premium(r),
        "level": level_of(r.get("xp") or 0)["level"],
        "frame": cos.get("frame"), "color": cos.get("color"), "banner": cos.get("banner"),
        "title": C.ITEMS[title][0] if title in C.ITEMS else None,
    }


async def user_games(ids: list[int]) -> dict[int, list]:
    if not ids:
        return {}
    q = ",".join("?" * len(ids))
    out: dict[int, list] = {}
    for r in await db.all_(f"SELECT * FROM user_games WHERE tg_id IN ({q}) ORDER BY pos, rowid", *ids):
        if r["game"] in C.GAMES:
            out.setdefault(r["tg_id"], []).append({"game": r["game"], "rank": r["rank"], "roles": jl(r["roles"]),
                                                   "heroes": jl(r["heroes"]), "uid": r["game_uid"]})
    return out


async def reputation(ids: list[int]) -> dict[int, dict]:
    if not ids:
        return {}
    q = ",".join("?" * len(ids))
    out: dict[int, dict] = {}
    for r in await db.all_(f"SELECT to_id, thumb, tags FROM reviews WHERE to_id IN ({q})", *ids):
        d = out.setdefault(r["to_id"], {"score": 0, "cnt": {}})
        d["score"] += r["thumb"]
        for t in jl(r["tags"]):
            d["cnt"][t] = d["cnt"].get(t, 0) + 1
    for d in out.values():
        d["tags"] = [t for t, _ in sorted(d.pop("cnt").items(), key=lambda x: -x[1])
                     if t in C.REVIEW_TAGS and t not in C.NEGATIVE_TAGS][:3]
    return out


async def people(ids, game: str | None = None) -> dict[int, dict]:
    ids = list({int(i) for i in ids})
    if not ids:
        return {}
    q = ",".join("?" * len(ids))
    rows = await db.all_(f"SELECT {UCOLS}, {PCOLS} FROM users u LEFT JOIN profiles p ON p.tg_id=u.tg_id "
                         f"WHERE u.tg_id IN ({q})", *ids)
    cos, games, reps = await cosmetics(ids), await user_games(ids), await reputation(ids)
    out = {r["tg_id"]: card(r, cos.get(r["tg_id"]), games.get(r["tg_id"]), reps.get(r["tg_id"]), game) for r in rows}
    if 0 in out:
        out[0].update(name="Лера", avatar="/static/img/lera.svg", lera=True)
    return out


async def ensure_user(tg: dict, start_param: str | None = None) -> dict:
    """Создать пользователя при первом входе (из мини-аппа или /start в боте). Реферал засчитывается один раз."""
    uid = int(tg["id"])
    u = await db.one("SELECT * FROM users WHERE tg_id=?", uid)
    if u:
        return u
    await db.run("INSERT OR IGNORE INTO users (tg_id, username, first_name, photo_url, lang) VALUES (?,?,?,?,?)",
                 uid, tg.get("username"), tg.get("first_name"), tg.get("photo_url"), tg.get("language_code"))
    await db.run("INSERT OR IGNORE INTO profiles (tg_id, nickname) VALUES (?,?)", uid, tg.get("first_name"))
    sp = start_param or ""
    if sp.startswith("ref_") and sp[4:].isdigit() and int(sp[4:]) != uid:
        ref = int(sp[4:])
        if await db.one("SELECT 1 FROM users WHERE tg_id=?", ref):
            await db.run("UPDATE users SET referrer=? WHERE tg_id=?", ref, uid)
            await add_balance(uid, 100, "referral_new")
            await add_balance(ref, 150, "referral")
            notify.send(ref, f"🎁 По твоей ссылке пришёл <b>{_h(tg.get('first_name') or 'игрок')}</b>. +150 несо!")
    return await db.one("SELECT * FROM users WHERE tg_id=?", uid)


# ── auth ─────────────────────────────────────────────────────────────────

async def current_user(request: Request) -> dict:
    tg = validate_init_data(request.headers.get("X-Init-Data", ""))
    if not tg and config.DEV_USER_ID:
        dev_id = int(request.headers.get("X-Dev-User") or config.DEV_USER_ID)
        tg = {"id": dev_id, "first_name": f"Dev{dev_id % 1000}", "username": None, "start_param": None}
    if not tg:
        raise HTTPException(401, "Открой Леру через Telegram")

    uid = int(tg["id"])
    u = await db.one("SELECT * FROM users WHERE tg_id=?", uid)
    if not u:
        u = await ensure_user(tg, tg.get("start_param"))
    elif (utcnow() - (parse_ts(u["last_seen"]) or utcnow())).total_seconds() > 60:
        await db.run("UPDATE users SET last_seen=datetime('now'), username=?, first_name=?, "
                     "photo_url=COALESCE(?, photo_url) WHERE tg_id=?",
                     tg.get("username"), tg.get("first_name"), tg.get("photo_url"), uid)
    u["is_admin"] = uid in config.ADMIN_IDS
    return u


def _h(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


Me = Depends(current_user)


# ── bootstrap / profile ──────────────────────────────────────────────────

async def unread_counts(uid: int) -> dict:
    chats = await db.val(
        "SELECT COUNT(*) FROM match_messages mm JOIN matches m ON m.id=mm.match_id "
        "LEFT JOIN match_reads r ON r.match_id=m.id AND r.tg_id=? "
        "WHERE (m.u1=? OR m.u2=?) AND mm.sender != ? AND mm.id > COALESCE(r.last_id, 0)", uid, uid, uid, uid)
    likes = await db.val(
        "SELECT COUNT(*) FROM swipes s WHERE s.to_id=? AND s.action IN ('like','super') "
        "AND NOT EXISTS (SELECT 1 FROM swipes x WHERE x.from_id=? AND x.to_id=s.from_id)", uid, uid)
    return {"chats": chats or 0, "likes": likes or 0}


@app.get("/api/bootstrap")
async def bootstrap(me=Me):
    uid = me["tg_id"]
    person = (await people([uid]))[uid]
    prof = await db.one("SELECT * FROM profiles WHERE tg_id=?", uid) or {}
    return {
        "me": {
            **person,
            "balance": me["balance"], "tickets": me["tickets"],
            "streak": me["streak"] if me["last_checkin"] in (today(), yday()) else 0,
            "checked_today": me["last_checkin"] == today(),
            "level": level_of(me["xp"]), "pity": me["pity"],
            "premium_until": me["premium_until"] if is_premium(me) else None,
            "is_admin": me["is_admin"], "duet_visible": bool(prof.get("duet_visible", 1)),
            "profile_done": bool(prof.get("nickname") and person["games"]),
            "mute_ready": bool(me.get("mute_ready")),
        },
        "unread": await unread_counts(uid),
        "dict": {
            "ranks": C.RANKS, "roles": C.ROLES, "play_times": C.PLAY_TIMES, "modes": C.SQUAD_MODES,
            "icebreakers": C.ICEBREAKERS, "premium_stars": config.PREMIUM_STARS, "bot": config.BOT_USERNAME,
            "items": {k: {"name": v[0], "kind": v[1], "rarity": v[2]} for k, v in C.ITEMS.items()},
            "games": {k: {"name": g["name"], "short": g["short"], "color": g["color"], "ranks": g["ranks"],
                          "roles": g["roles"], "modes": g["modes"], "heroes": bool(g.get("heroes"))}
                      for k, g in C.GAMES.items()},
            "review_tags": C.REVIEW_TAGS, "weekend": is_weekend(),
        },
    }


@app.post("/api/ping")
async def ping(me=Me):
    await db.run("UPDATE users SET last_seen=datetime('now') WHERE tg_id=?", me["tg_id"])
    return await unread_counts(me["tg_id"])


class ProfileIn(BaseModel):
    nickname: str = Field(min_length=1, max_length=24)
    age: int | None = Field(None, ge=14, le=80)
    city: str | None = Field(None, max_length=40)
    gender: str | None = None
    about: str | None = Field(None, max_length=300)
    rank: int | None = Field(None, ge=0, le=len(C.RANKS) - 1)
    roles: list[str] = []
    heroes: list[str] = []
    play_times: list[str] = []
    voice: bool = False
    photos: list[str] = []
    accent: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    duet_visible: bool = True


@app.put("/api/profile")
async def save_profile(p: ProfileIn, me=Me):
    hero_names = {h[0] for h in C.HEROES}
    roles = [r for r in p.roles if r in C.ROLES][:3]
    heroes = [h for h in p.heroes if h in hero_names][:5]
    times = [t for t in p.play_times if t in C.PLAY_TIMES]
    photos = [ph for ph in p.photos if ph.startswith("/uploads/") and ".." not in ph][:4]
    gender = p.gender if p.gender in ("m", "f") else None
    await db.run(
        "INSERT INTO profiles (tg_id, nickname, age, city, gender, about, rank, roles, heroes, play_times, voice, "
        "photos, accent, duet_visible, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now')) "
        "ON CONFLICT(tg_id) DO UPDATE SET nickname=excluded.nickname, age=excluded.age, city=excluded.city, "
        "gender=excluded.gender, about=excluded.about, rank=excluded.rank, roles=excluded.roles, "
        "heroes=excluded.heroes, play_times=excluded.play_times, voice=excluded.voice, photos=excluded.photos, "
        "accent=excluded.accent, duet_visible=excluded.duet_visible, updated_at=excluded.updated_at",
        me["tg_id"], p.nickname.strip(), p.age, (p.city or "").strip() or None, gender, (p.about or "").strip(),
        p.rank, json.dumps(roles), json.dumps(heroes, ensure_ascii=False), json.dumps(times), int(p.voice),
        json.dumps(photos), p.accent, int(p.duet_visible))
    return (await people([me["tg_id"]]))[me["tg_id"]]


MAGIC = {b"\xff\xd8\xff": ".jpg", b"\x89PNG": ".png", b"RIFF": ".webp", b"GIF8": ".gif"}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), me=Me):
    data = await file.read(6 * 1024 * 1024 + 1)
    if len(data) > 6 * 1024 * 1024:
        raise HTTPException(413, "Файл больше 6 МБ")
    ext = next((e for m, e in MAGIC.items() if data.startswith(m)), None)
    if not ext or (ext == ".webp" and data[8:12] != b"WEBP"):
        raise HTTPException(415, "Нужна картинка: jpg, png, webp или gif")
    name = f"{me['tg_id']}_{secrets.token_hex(8)}{ext}"
    (config.UPLOAD_DIR / name).write_bytes(data)
    return {"url": f"/uploads/{name}"}


@app.get("/api/user/{tg_id}")
async def user_card(tg_id: int, me=Me):
    p = (await people([tg_id])).get(tg_id)
    if not p:
        raise HTTPException(404, "Нет такого игрока")
    return p


# ── duet ─────────────────────────────────────────────────────────────────

def vibe(me: dict, o: dict) -> tuple[int, list[str]]:
    score, why = 46, []
    mr, orr = set(me["roles"]), set(o["roles"])
    if mr and orr:
        if not mr & orr:
            score += 18; why.append("Роли закрывают друг друга")
        else:
            score += 5
    if me["rank"] is not None and o["rank"] is not None:
        d = abs(me["rank"] - o["rank"])
        if d == 0:
            score += 15; why.append("Один ранг")
        elif d == 1:
            score += 9; why.append("Близкий ранг")
        elif d >= 3:
            score -= 12
    common_t = set(me["play_times"]) & set(o["play_times"])
    if common_t:
        score += 12; why.append("Играете в одно время")
    if me["voice"] and o["voice"]:
        score += 7; why.append("Оба с микро")
    if me["city"] and o["city"] and me["city"].lower() == o["city"].lower():
        score += 7; why.append("Один город")
    if set(me["heroes"]) & set(o["heroes"]):
        score += 4; why.append("Общие мейны")
    shared = {g["game"] for g in me.get("games", [])} & {g["game"] for g in o.get("games", [])}
    if len(shared) > 1:
        score += min(9, 3 * (len(shared) - 1)); why.append(f"{len(shared)} общие игры")
    rv = o.get("rep", 0)
    if rv >= 3:
        score += 4; why.append("Хорошие отзывы")
    elif rv <= -3:
        score -= 10
    if o["online"]:
        score += 4
    return max(12, min(99, score)), why[:3]


@app.get("/api/duet/feed")
async def duet_feed(game: str = C.DEFAULT_GAME, gender: str = "", age_min: int = 14, age_max: int = 80,
                    rank_min: int = 0, rank_max: int = 99, role: str = "", online: int = 0, me=Me):
    uid = me["tg_id"]
    if game not in C.GAMES:
        game = C.DEFAULT_GAME
    rows = await db.all_(
        f"SELECT {UCOLS}, {PCOLS} FROM profiles p JOIN users u ON u.tg_id=p.tg_id "
        "WHERE p.duet_visible=1 AND p.tg_id != ? AND p.tg_id != 0 AND p.nickname IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM user_games ug WHERE ug.tg_id=p.tg_id AND ug.game=?) "
        "AND NOT EXISTS (SELECT 1 FROM swipes s WHERE s.from_id=? AND s.to_id=p.tg_id) "
        "AND NOT EXISTS (SELECT 1 FROM blocks b WHERE (b.from_id=? AND b.to_id=p.tg_id) OR (b.from_id=p.tg_id AND b.to_id=?)) "
        "ORDER BY u.last_seen DESC LIMIT 300", uid, game, uid, uid, uid)
    liked_me = {r["from_id"]: r["action"] for r in await db.all_(
        "SELECT from_id, action FROM swipes WHERE to_id=? AND action IN ('like','super')", uid)}
    mine = (await people([uid], game))[uid]
    ids = [r["tg_id"] for r in rows]
    cos, games, reps = await cosmetics(ids), await user_games(ids), await reputation(ids)
    out = []
    for r in rows:
        c = card(r, cos.get(r["tg_id"]), games.get(r["tg_id"]), reps.get(r["tg_id"]), game)
        if gender in ("m", "f") and c["gender"] != gender:
            continue
        if c["age"] and not (age_min <= c["age"] <= age_max):
            continue
        if c["rank"] is not None and not (rank_min <= c["rank"] <= rank_max):
            continue
        if role and role not in c["roles"]:
            continue
        if online and not c["online"]:
            continue
        c["vibe"], c["vibe_why"] = vibe(mine, c)
        c["super_liked_me"] = liked_me.get(c["tg_id"]) == "super"
        out.append(c)
    out.sort(key=lambda c: (c["super_liked_me"], c["online"], c["vibe"] + random.random() * 8), reverse=True)
    return {"cards": out[:25]}


class SwipeIn(BaseModel):
    to: int
    action: str = Field(pattern="^(like|super|pass)$")


async def super_left(me: dict) -> int:
    limit = 5 if is_premium(me) else 1
    used = await db.val("SELECT COUNT(*) FROM swipes WHERE from_id=? AND action='super' "
                        "AND created_at >= datetime('now','-1 day')", me["tg_id"])
    return max(0, limit - (used or 0))


@app.get("/api/duet/status")
async def duet_status(me=Me):
    return {"super_left": await super_left(me), "premium": is_premium(me)}


async def get_or_create_match(a: int, b: int) -> tuple[int, bool]:
    u1, u2 = sorted((a, b))
    row = await db.one("SELECT id FROM matches WHERE u1=? AND u2=?", u1, u2)
    if row:
        return row["id"], False
    return await db.run("INSERT INTO matches (u1, u2) VALUES (?,?)", u1, u2), True


@app.post("/api/duet/swipe")
async def swipe(s: SwipeIn, me=Me):
    uid = me["tg_id"]
    if s.to == uid or not await db.one("SELECT 1 FROM users WHERE tg_id=?", s.to):
        raise HTTPException(400, "Некого свайпать")
    if s.action == "super" and await super_left(me) <= 0:
        raise HTTPException(429, "Суперлайки на сегодня кончились")
    await db.run("INSERT OR REPLACE INTO swipes (from_id, to_id, action) VALUES (?,?,?)", uid, s.to, s.action)
    await add_xp(uid, 1)
    await bump_quest(uid, "swipe")
    if s.action == "pass":
        return {"match": None}
    name = _h((await people([uid]))[uid]["name"])
    back = await db.one("SELECT action FROM swipes WHERE from_id=? AND to_id=? AND action IN ('like','super')", s.to, uid)
    if back:
        mid, new = await get_or_create_match(uid, s.to)
        if new:
            await add_xp(uid, 20); await add_xp(s.to, 20)
            notify.send(s.to, f"💥 <b>Мэтч с {name}!</b>\nЛера уже открыла вам чат.", f"m{mid}")
        return {"match": {"id": mid, "with": (await people([s.to]))[s.to],
                          "lera": random.choice(C.LERA_LINES["match"])}}
    if s.action == "super":
        notify.send(s.to, f"⭐️ <b>{name}</b> поставил(а) тебе суперлайк. Глянь анкету — она уже первая в ленте.", "duet")
    else:
        notify.send(s.to, f"❤️ Кто-то лайкнул твою анкету в дуэте. Загляни во вкладку «Лайки».", "likes")
    return {"match": None}


@app.post("/api/duet/undo")
async def undo(me=Me):
    if not is_premium(me):
        raise HTTPException(403, "Отмена свайпа — фича Premium")
    last = await db.one("SELECT to_id, action FROM swipes WHERE from_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                        me["tg_id"])
    if not last:
        raise HTTPException(404, "Нечего отменять")
    u1, u2 = sorted((me["tg_id"], last["to_id"]))
    if await db.one("SELECT 1 FROM matches WHERE u1=? AND u2=?", u1, u2):
        raise HTTPException(409, "Это уже мэтч — отменить нельзя")
    await db.run("DELETE FROM swipes WHERE from_id=? AND to_id=?", me["tg_id"], last["to_id"])
    return (await people([last["to_id"]])).get(last["to_id"])


@app.get("/api/duet/likes")
async def likes_me(me=Me):
    uid = me["tg_id"]
    rows = await db.all_(
        "SELECT s.from_id, s.action, s.created_at FROM swipes s WHERE s.to_id=? AND s.action IN ('like','super') "
        "AND NOT EXISTS (SELECT 1 FROM swipes x WHERE x.from_id=? AND x.to_id=s.from_id) "
        "AND NOT EXISTS (SELECT 1 FROM blocks b WHERE b.from_id=? AND b.to_id=s.from_id) "
        "ORDER BY s.created_at DESC LIMIT 100", uid, uid, uid)
    ppl = await people([r["from_id"] for r in rows])
    return {"likes": [{**ppl[r["from_id"]], "super": r["action"] == "super", "at": r["created_at"]}
                      for r in rows if r["from_id"] in ppl]}


# ── matches / chats ──────────────────────────────────────────────────────

async def my_match(mid: int, uid: int) -> dict:
    m = await db.one("SELECT * FROM matches WHERE id=? AND (u1=? OR u2=?)", mid, uid, uid)
    if not m:
        raise HTTPException(404, "Чат не найден")
    m["other"] = m["u2"] if m["u1"] == uid else m["u1"]
    return m


@app.get("/api/chats")
async def chats(me=Me):
    uid = me["tg_id"]
    ms = await db.all_(
        "SELECT m.id, m.u1, m.u2, m.created_at, "
        "(SELECT text FROM match_messages WHERE match_id=m.id ORDER BY id DESC LIMIT 1) AS last_text, "
        "(SELECT sender FROM match_messages WHERE match_id=m.id ORDER BY id DESC LIMIT 1) AS last_sender, "
        "(SELECT created_at FROM match_messages WHERE match_id=m.id ORDER BY id DESC LIMIT 1) AS last_at, "
        "(SELECT COUNT(*) FROM match_messages mm WHERE mm.match_id=m.id AND mm.sender != ? AND mm.id > "
        "  COALESCE((SELECT last_id FROM match_reads WHERE match_id=m.id AND tg_id=?),0)) AS unread "
        "FROM matches m WHERE (m.u1=? OR m.u2=?) "
        "AND NOT EXISTS (SELECT 1 FROM blocks b WHERE (b.from_id=m.u1 AND b.to_id=m.u2) OR (b.from_id=m.u2 AND b.to_id=m.u1))",
        uid, uid, uid, uid)
    ppl = await people([m["u2"] if m["u1"] == uid else m["u1"] for m in ms])
    out = [{"id": m["id"], "with": ppl.get(m["u2"] if m["u1"] == uid else m["u1"]), "last_text": m["last_text"],
            "mine": m["last_sender"] == uid, "at": m["last_at"] or m["created_at"], "unread": m["unread"]}
           for m in ms]
    out.sort(key=lambda x: x["at"], reverse=True)
    sq = await db.all_(
        "SELECT s.id, s.title, s.game, s.mode, s.status, "
        "(SELECT text FROM squad_messages WHERE squad_id=s.id ORDER BY id DESC LIMIT 1) AS last_text, "
        "(SELECT COUNT(*) FROM squad_members WHERE squad_id=s.id) AS members, s.max_players "
        "FROM squads s JOIN squad_members sm ON sm.squad_id=s.id AND sm.tg_id=? "
        "WHERE s.status != 'closed' AND s.expires_at > datetime('now') ORDER BY s.created_at DESC", uid)
    return {"matches": out, "squads": sq}


@app.get("/api/chats/{mid}")
async def chat_messages(mid: int, after: int = 0, me=Me):
    m = await my_match(mid, me["tg_id"])
    msgs = await db.all_("SELECT id, sender, text, created_at FROM match_messages WHERE match_id=? AND id > ? "
                         "ORDER BY id LIMIT 200", mid, after)
    if msgs:
        await db.run("INSERT INTO match_reads (match_id, tg_id, last_id) VALUES (?,?,?) "
                     "ON CONFLICT(match_id, tg_id) DO UPDATE SET last_id=MAX(last_id, excluded.last_id)",
                     mid, me["tg_id"], msgs[-1]["id"])
    other_read = await db.val("SELECT last_id FROM match_reads WHERE match_id=? AND tg_id=?", mid, m["other"]) or 0
    res = {"messages": msgs, "other_read": other_read}
    if not after:
        res["with"] = (await people([m["other"]])).get(m["other"])
    return res


class MsgIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@app.post("/api/chats/{mid}")
async def chat_send(mid: int, body: MsgIn, me=Me):
    m = await my_match(mid, me["tg_id"])
    if await db.one("SELECT 1 FROM blocks WHERE (from_id=? AND to_id=?) OR (from_id=? AND to_id=?)",
                    me["tg_id"], m["other"], m["other"], me["tg_id"]):
        raise HTTPException(403, "Чат недоступен")
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Пустое сообщение")
    first = not await db.one("SELECT 1 FROM match_messages WHERE match_id=? AND sender=?", mid, me["tg_id"])
    msg_id = await db.run("INSERT INTO match_messages (match_id, sender, text) VALUES (?,?,?)", mid, me["tg_id"], text)
    await db.run("INSERT INTO match_reads (match_id, tg_id, last_id) VALUES (?,?,?) "
                 "ON CONFLICT(match_id, tg_id) DO UPDATE SET last_id=excluded.last_id", mid, me["tg_id"], msg_id)
    other = await db.one("SELECT last_seen FROM users WHERE tg_id=?", m["other"])
    if first or not is_online(other or {}):
        name = _h((await people([me["tg_id"]]))[me["tg_id"]]["name"])
        notify.send(m["other"], f"💬 <b>{name}</b>: {_h(text[:120])}", f"m{mid}")
    return await db.one("SELECT id, sender, text, created_at FROM match_messages WHERE id=?", msg_id)


@app.post("/api/chats/{mid}/unmatch")
async def unmatch(mid: int, me=Me):
    m = await my_match(mid, me["tg_id"])
    await db.run("INSERT OR REPLACE INTO blocks (from_id, to_id, reason) VALUES (?,?, 'unmatch')", me["tg_id"], m["other"])
    return {"ok": True}


class BlockIn(BaseModel):
    to: int
    reason: str = Field("", max_length=200)


@app.post("/api/block")
async def block(b: BlockIn, me=Me):
    await db.run("INSERT OR REPLACE INTO blocks (from_id, to_id, reason) VALUES (?,?,?)", me["tg_id"], b.to, b.reason)
    if b.reason and b.reason != "unmatch":
        for admin in config.ADMIN_IDS:
            notify.send(admin, f"🚩 Жалоба от <code>{me['tg_id']}</code> на <code>{b.to}</code>: {_h(b.reason)}")
    return {"ok": True}


# ── squads ───────────────────────────────────────────────────────────────

class SquadIn(BaseModel):
    title: str = Field(min_length=2, max_length=48)
    game: str = C.DEFAULT_GAME
    mode: str
    rank: int | None = Field(None, ge=0, le=20)
    roles_needed: list[str] = []
    max_players: int = Field(5, ge=2, le=5)
    voice: bool = False
    hours: int = Field(2, ge=1, le=12)


async def squad_view(sid: int, uid: int, with_members=True) -> dict:
    s = await db.one("SELECT * FROM squads WHERE id=?", sid)
    if not s:
        raise HTTPException(404, "Отряд не найден")
    mem = await db.all_("SELECT tg_id FROM squad_members WHERE squad_id=? ORDER BY joined_at", sid)
    ids = [m["tg_id"] for m in mem]
    s["roles_needed"] = jl(s["roles_needed"])
    s["count"] = len(ids)
    s["joined"] = uid in ids
    s["is_owner"] = s["creator"] == uid
    s["expired"] = parse_ts(s["expires_at"]) < utcnow()
    if with_members:
        ppl = await people(ids + [s["creator"]], s["game"])
        s["members"] = [ppl[i] for i in ids if i in ppl]
        s["creator_card"] = ppl.get(s["creator"])
    return s


@app.get("/api/squads")
async def squads(game: str = "", mode: str = "", mine: int = 0, me=Me):
    uid = me["tg_id"]
    q = ("SELECT s.id FROM squads s WHERE s.status IN ('open','full') AND s.expires_at > datetime('now') "
         + ("AND s.game=? " if game in C.GAMES and not mine else "")
         + ("AND s.mode=? " if mode else "")
         + ("AND EXISTS (SELECT 1 FROM squad_members m WHERE m.squad_id=s.id AND m.tg_id=?) " if mine
            else "AND s.status='open' ")
         + "ORDER BY s.created_at DESC LIMIT 60")
    args = ([game] if game in C.GAMES and not mine else []) + ([mode] if mode else []) + ([uid] if mine else [])
    ids = [r["id"] for r in await db.all_(q, *args)]
    return {"squads": [await squad_view(i, uid) for i in ids]}


@app.post("/api/squads")
async def create_squad(s: SquadIn, me=Me):
    g = C.GAMES.get(s.game)
    if not g or s.mode not in g["modes"]:
        raise HTTPException(400, "Неизвестный режим")
    if s.rank is not None and s.rank >= len(g["ranks"]):
        raise HTTPException(400, "Неизвестный ранг")
    uid = me["tg_id"]
    active = await db.val("SELECT COUNT(*) FROM squads WHERE creator=? AND status='open' AND expires_at > datetime('now')", uid)
    if active >= 3:
        raise HTTPException(429, "У тебя уже 3 открытых отряда — закрой лишние")
    sid = await db.run(
        "INSERT INTO squads (creator, title, game, mode, rank, roles_needed, max_players, voice, expires_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)", uid, s.title.strip(), s.game, s.mode, s.rank,
        json.dumps([r for r in s.roles_needed if r in g["roles"]]), s.max_players, int(s.voice),
        sqlts(utcnow() + timedelta(hours=s.hours)))
    await db.run("INSERT INTO squad_members (squad_id, tg_id) VALUES (?,?)", sid, uid)
    await add_xp(uid, 10)
    return await squad_view(sid, uid)


@app.get("/api/squads/{sid}")
async def squad_get(sid: int, me=Me):
    return await squad_view(sid, me["tg_id"])


@app.post("/api/squads/{sid}/join")
async def squad_join(sid: int, me=Me):
    uid = me["tg_id"]
    s = await squad_view(sid, uid, with_members=False)
    if s["joined"]:
        return await squad_view(sid, uid)
    if s["status"] != "open" or s["expired"]:
        raise HTTPException(409, "Отряд уже не набирает")
    if s["count"] >= s["max_players"]:
        raise HTTPException(409, "Мест нет")
    if await db.one("SELECT 1 FROM blocks WHERE from_id=? AND to_id=?", s["creator"], uid):
        raise HTTPException(403, "Тебя сюда не пустят")
    await db.run("INSERT OR IGNORE INTO squad_members (squad_id, tg_id) VALUES (?,?)", sid, uid)
    name = _h((await people([uid]))[uid]["name"])
    count = s["count"] + 1
    notify.send(s["creator"], f"🛡 <b>{name}</b> вступил(а) в «{_h(s['title'])}» — {count}/{s['max_players']}", f"s{sid}")
    if count >= s["max_players"]:
        await db.run("UPDATE squads SET status='full' WHERE id=?", sid)
        for m in await db.all_("SELECT tg_id FROM squad_members WHERE squad_id=?", sid):
            notify.send(m["tg_id"], f"✅ Отряд «{_h(s['title'])}» собран! Заходите в игру.", f"s{sid}")
        from .v2 import autopost
        await autopost(f"🛡 Отряд «{s['title']}» собран — {s['max_players']} игроков уже в катке. "
                       "Тоже хочешь? Собери свой во вкладке «Тиммейты».", s["game"], "event")
    return await squad_view(sid, uid)


@app.post("/api/squads/{sid}/leave")
async def squad_leave(sid: int, me=Me):
    uid = me["tg_id"]
    s = await squad_view(sid, uid, with_members=False)
    await db.run("DELETE FROM squad_members WHERE squad_id=? AND tg_id=?", sid, uid)
    if s["is_owner"]:
        await db.run("UPDATE squads SET status='closed' WHERE id=?", sid)
    elif s["status"] == "full":
        await db.run("UPDATE squads SET status='open' WHERE id=?", sid)
    return {"ok": True}


@app.post("/api/squads/{sid}/close")
async def squad_close(sid: int, me=Me):
    s = await squad_view(sid, me["tg_id"], with_members=False)
    if not (s["is_owner"] or me["is_admin"]):
        raise HTTPException(403, "Закрыть может только создатель")
    await db.run("UPDATE squads SET status='closed' WHERE id=?", sid)
    return {"ok": True}


@app.get("/api/squads/{sid}/messages")
async def squad_msgs(sid: int, after: int = 0, me=Me):
    s = await squad_view(sid, me["tg_id"], with_members=False)
    if not s["joined"]:
        raise HTTPException(403, "Вступи в отряд, чтобы читать чат")
    msgs = await db.all_("SELECT id, sender, text, created_at FROM squad_messages WHERE squad_id=? AND id > ? "
                         "ORDER BY id DESC LIMIT 200", sid, after)
    msgs.reverse()
    ppl = await people({m["sender"] for m in msgs})
    for m in msgs:
        p = ppl.get(m["sender"]) or {}
        m["name"], m["avatar"], m["frame"], m["color"] = p.get("name"), p.get("avatar"), p.get("frame"), p.get("color")
    return {"messages": msgs}


@app.post("/api/squads/{sid}/messages")
async def squad_send(sid: int, body: MsgIn, me=Me):
    s = await squad_view(sid, me["tg_id"], with_members=False)
    if not s["joined"]:
        raise HTTPException(403, "Вступи в отряд")
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Пустое сообщение")
    mid = await db.run("INSERT INTO squad_messages (squad_id, sender, text) VALUES (?,?,?)", sid, me["tg_id"], text)
    await bump_quest(me["tg_id"], "squad_msg")
    return {"id": mid}


# ── feed ─────────────────────────────────────────────────────────────────

class PostIn(BaseModel):
    text: str = Field(min_length=1, max_length=1500)
    image: str | None = None
    game: str | None = None


async def posts_view(rows: list[dict], uid: int) -> list[dict]:
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    q = ",".join("?" * len(ids))
    likes = {r["post_id"]: r["n"] for r in await db.all_(
        f"SELECT post_id, COUNT(*) n FROM post_likes WHERE post_id IN ({q}) GROUP BY post_id", *ids)}
    mine = {r["post_id"] for r in await db.all_(
        f"SELECT post_id FROM post_likes WHERE tg_id=? AND post_id IN ({q})", uid, *ids)}
    comm = {r["post_id"]: r["n"] for r in await db.all_(
        f"SELECT post_id, COUNT(*) n FROM comments WHERE post_id IN ({q}) GROUP BY post_id", *ids)}
    ppl = await people({r["author"] for r in rows})
    return [{**r, "author": ppl.get(r["author"]), "likes": likes.get(r["id"], 0), "liked": r["id"] in mine,
             "comments": comm.get(r["id"], 0), "own": r["author"] == uid} for r in rows]


@app.get("/api/feed")
async def feed(before: int = 0, author: int = 0, top: int = 0, game: str = "", kind: str = "", me=Me):
    uid = me["tg_id"]
    where = ("WHERE NOT EXISTS (SELECT 1 FROM blocks b WHERE b.from_id=? AND b.to_id=p.author) "
             "AND (p.publish_at IS NULL OR p.publish_at <= datetime('now'))")
    args: list = [uid]
    if game in C.GAMES:
        where += " AND (p.game = ? OR p.game IS NULL)"; args.append(game)
    if kind in ("user", "news", "event"):
        where += " AND p.kind = ?"; args.append(kind)
    if before:
        where += " AND p.id < ?"; args.append(before)
    if author:
        where += " AND p.author = ?"; args.append(author)
    if top:
        where += " AND p.created_at > datetime('now','-7 days')"
        order = "ORDER BY (SELECT COUNT(*) FROM post_likes l WHERE l.post_id=p.id) DESC, p.id DESC"
    else:
        order = "ORDER BY p.id DESC"
    rows = await db.all_(f"SELECT p.* FROM posts p {where} {order} LIMIT 20", *args)
    return {"posts": await posts_view(rows, uid)}


@app.post("/api/feed")
async def post_create(p: PostIn, me=Me):
    img = p.image if p.image and p.image.startswith("/uploads/") and ".." not in p.image else None
    recent = await db.val("SELECT COUNT(*) FROM posts WHERE author=? AND created_at > datetime('now','-1 hour')", me["tg_id"])
    if recent >= 5:
        raise HTTPException(429, "Не больше 5 постов в час")
    game = p.game if p.game in C.GAMES else None
    pid = await db.run("INSERT INTO posts (author, text, image, game) VALUES (?,?,?,?)", me["tg_id"], p.text.strip(), img, game)
    await add_xp(me["tg_id"], 5)
    return (await posts_view([await db.one("SELECT * FROM posts WHERE id=?", pid)], me["tg_id"]))[0]


@app.delete("/api/feed/{pid}")
async def post_delete(pid: int, me=Me):
    p = await db.one("SELECT author FROM posts WHERE id=?", pid)
    if not p:
        raise HTTPException(404, "Пост не найден")
    if p["author"] != me["tg_id"] and not me["is_admin"]:
        raise HTTPException(403, "Это не твой пост")
    await db.run("DELETE FROM comments WHERE post_id=?", pid)
    await db.run("DELETE FROM post_likes WHERE post_id=?", pid)
    await db.run("DELETE FROM posts WHERE id=?", pid)
    return {"ok": True}


@app.post("/api/feed/{pid}/like")
async def post_like(pid: int, me=Me):
    p = await db.one("SELECT author FROM posts WHERE id=?", pid)
    if not p:
        raise HTTPException(404, "Пост не найден")
    if await db.change("DELETE FROM post_likes WHERE post_id=? AND tg_id=?", pid, me["tg_id"]):
        liked = False
    else:
        await db.run("INSERT INTO post_likes (post_id, tg_id) VALUES (?,?)", pid, me["tg_id"])
        await bump_quest(me["tg_id"], "post_like")
        if p["author"] != me["tg_id"]:
            await add_xp(p["author"], 2)
        liked = True
    return {"liked": liked, "likes": await db.val("SELECT COUNT(*) FROM post_likes WHERE post_id=?", pid)}


@app.get("/api/feed/{pid}/comments")
async def comments(pid: int, me=Me):
    rows = await db.all_("SELECT * FROM comments WHERE post_id=? ORDER BY id LIMIT 200", pid)
    ppl = await people({r["author"] for r in rows})
    return {"comments": [{**r, "author": ppl.get(r["author"])} for r in rows]}


@app.post("/api/feed/{pid}/comments")
async def comment_add(pid: int, body: MsgIn, me=Me):
    p = await db.one("SELECT author, text FROM posts WHERE id=?", pid)
    if not p:
        raise HTTPException(404, "Пост не найден")
    cid = await db.run("INSERT INTO comments (post_id, author, text) VALUES (?,?,?)", pid, me["tg_id"], body.text.strip())
    if p["author"] != me["tg_id"]:
        name = _h((await people([me["tg_id"]]))[me["tg_id"]]["name"])
        notify.send(p["author"], f"💬 <b>{name}</b> прокомментировал(а) твой пост: {_h(body.text[:100])}", f"p{pid}")
    r = await db.one("SELECT * FROM comments WHERE id=?", cid)
    return {**r, "author": (await people([me["tg_id"]]))[me["tg_id"]]}


# ── wiki / leaderboard ───────────────────────────────────────────────────

@app.get("/api/wiki/heroes")
async def heroes(me=Me):
    pop = {}
    for r in await db.all_("SELECT heroes FROM user_games WHERE game='hok' AND heroes != '[]'"):
        for h in jl(r["heroes"]):
            pop[h] = pop.get(h, 0) + 1
    return {"heroes": [{"name": n, "cls": c, "lane": l, "lane_name": C.ROLES[l], "mains": pop.get(n, 0)}
                       for n, c, l in C.HEROES]}


@app.get("/api/leaderboard")
async def leaderboard(by: str = "xp", me=Me):
    if by == "likes":
        rows = await db.all_("SELECT to_id AS tg_id, COUNT(*) AS score FROM swipes WHERE action IN ('like','super') "
                             "AND created_at > datetime('now','-30 days') GROUP BY to_id ORDER BY score DESC LIMIT 50")
    elif by == "streak":
        rows = await db.all_("SELECT tg_id, streak AS score FROM users WHERE streak > 0 AND last_checkin >= ? "
                             "ORDER BY streak DESC, xp DESC LIMIT 50", yday())
    else:
        rows = await db.all_("SELECT tg_id, xp AS score FROM users WHERE xp > 0 ORDER BY xp DESC LIMIT 50")
    ppl = await people([r["tg_id"] for r in rows])
    return {"top": [{**ppl[r["tg_id"]], "score": r["score"]} for r in rows if r["tg_id"] in ppl], "me": me["tg_id"]}


# ── economy: checkin / quests / shop / inventory / gacha ─────────────────

@app.post("/api/checkin")
async def checkin(me=Me):
    t = today()
    if me["last_checkin"] == t:
        raise HTTPException(409, "Уже забрано сегодня")
    streak = me["streak"] + 1 if me["last_checkin"] == yday() else 1
    ok = await db.change("UPDATE users SET last_checkin=?, streak=? WHERE tg_id=? AND (last_checkin IS NULL OR last_checkin != ?)",
                         t, streak, me["tg_id"], t)
    if not ok:
        raise HTTPException(409, "Уже забрано сегодня")
    reward = 20 + 10 * min(streak - 1, 6)
    if is_premium(me):
        reward *= 2
    if is_weekend():
        reward *= 2
    ticket = streak % 7 == 0
    await add_balance(me["tg_id"], reward, "checkin")
    if ticket:
        await db.run("UPDATE users SET tickets = tickets + 1 WHERE tg_id=?", me["tg_id"])
    await add_xp(me["tg_id"], 10)
    await bump_quest(me["tg_id"], "checkin")
    return {"reward": reward, "streak": streak, "ticket": ticket, "lera": random.choice(C.LERA_LINES["checkin"])}


@app.get("/api/quests")
async def quests(me=Me):
    rows = {r["quest_id"]: r for r in await db.all_(
        "SELECT * FROM quest_progress WHERE tg_id=? AND day=?", me["tg_id"], today())}
    k2 = 2 if is_weekend() else 1
    return {"weekend": k2 == 2, "quests": [{"id": k, "title": v[0], "goal": v[1], "reward": v[2] * k2,
                        "progress": rows.get(k, {}).get("progress", 0), "claimed": bool(rows.get(k, {}).get("claimed"))}
                       for k, v in C.QUESTS.items()]}


@app.post("/api/quests/{qid}/claim")
async def quest_claim(qid: str, me=Me):
    if qid not in C.QUESTS:
        raise HTTPException(404, "Нет такого квеста")
    _, goal, reward = C.QUESTS[qid]
    ok = await db.change("UPDATE quest_progress SET claimed=1 WHERE tg_id=? AND day=? AND quest_id=? AND progress>=? AND claimed=0",
                         me["tg_id"], today(), qid, goal)
    if not ok:
        raise HTTPException(409, "Квест ещё не выполнен")
    if is_weekend():
        reward *= 2
    await add_balance(me["tg_id"], reward, f"quest:{qid}")
    await add_xp(me["tg_id"], 5)
    return {"reward": reward}


def item_out(iid: str, owned: set, equipped: set) -> dict:
    name, kind, rarity, price = C.ITEMS[iid]
    return {"id": iid, "name": name, "kind": kind, "rarity": rarity, "price": price,
            "owned": iid in owned, "equipped": iid in equipped, "premium": iid in C.PREMIUM_ONLY}


async def inv_sets(uid: int) -> tuple[set, set]:
    rows = await db.all_("SELECT item_id, equipped FROM inventory WHERE tg_id=?", uid)
    return {r["item_id"] for r in rows}, {r["item_id"] for r in rows if r["equipped"]}


@app.get("/api/shop")
async def shop(me=Me):
    owned, eq = await inv_sets(me["tg_id"])
    items = [item_out(i, owned, eq) for i, v in C.ITEMS.items() if v[3] is not None]
    return {"items": items, "balance": me["balance"]}


@app.post("/api/shop/buy/{iid}")
async def buy(iid: str, me=Me):
    if iid not in C.ITEMS or C.ITEMS[iid][3] is None:
        raise HTTPException(404, "Этого нет в продаже")
    if await db.one("SELECT 1 FROM inventory WHERE tg_id=? AND item_id=?", me["tg_id"], iid):
        raise HTTPException(409, "Уже есть")
    await spend(me["tg_id"], C.ITEMS[iid][3], f"buy:{iid}")
    await db.run("INSERT INTO inventory (tg_id, item_id) VALUES (?,?)", me["tg_id"], iid)
    return {"ok": True, "balance": await db.val("SELECT balance FROM users WHERE tg_id=?", me["tg_id"])}


@app.get("/api/inventory")
async def inventory(me=Me):
    owned, eq = await inv_sets(me["tg_id"])
    if is_premium(me):
        owned.add("frame_crown")
    return {"items": [item_out(i, owned, eq) for i in C.ITEMS if i in owned]}


@app.post("/api/inventory/equip/{iid}")
async def equip(iid: str, me=Me):
    uid = me["tg_id"]
    if iid not in C.ITEMS:
        raise HTTPException(404, "Нет такого предмета")
    if iid in C.PREMIUM_ONLY and is_premium(me):
        await db.run("INSERT OR IGNORE INTO inventory (tg_id, item_id) VALUES (?,?)", uid, iid)
    row = await db.one("SELECT equipped FROM inventory WHERE tg_id=? AND item_id=?", uid, iid)
    if not row:
        raise HTTPException(403, "Этого предмета у тебя нет")
    kind = C.ITEMS[iid][1]
    same = [k for k, v in C.ITEMS.items() if v[1] == kind]
    q = ",".join("?" * len(same))
    await db.run(f"UPDATE inventory SET equipped=0 WHERE tg_id=? AND item_id IN ({q})", uid, *same)
    if not row["equipped"]:
        await db.run("UPDATE inventory SET equipped=1 WHERE tg_id=? AND item_id=?", uid, iid)
    return {"equipped": not row["equipped"]}


def roll_rarity(pity: int) -> str:
    if pity + 1 >= C.GACHA_PITY:
        return "legendary"
    r = random.uniform(0, sum(C.RARITY_WEIGHTS.values()))
    for rarity, w in C.RARITY_WEIGHTS.items():
        r -= w
        if r <= 0:
            return rarity
    return "common"


class RollIn(BaseModel):
    count: int = Field(1, ge=1, le=10)
    ticket: bool = False


@app.post("/api/gacha/roll")
async def gacha(body: RollIn, me=Me):
    uid = me["tg_id"]
    n = 10 if body.count >= 10 else 1
    if body.ticket and n == 1:
        if not await db.change("UPDATE users SET tickets = tickets - 1 WHERE tg_id=? AND tickets > 0", uid):
            raise HTTPException(402, "Нет тикетов")
    else:
        await spend(uid, C.GACHA_COST_X10 if n == 10 else C.GACHA_COST, f"gacha_x{n}")
    pity = await db.val("SELECT pity FROM users WHERE tg_id=?", uid)
    owned, _ = await inv_sets(uid)
    pool = {r: [i for i, v in C.ITEMS.items() if v[2] == r and i not in C.PREMIUM_ONLY] for r in C.RARITY_WEIGHTS}
    results, refund = [], 0
    for k in range(n):
        rarity = roll_rarity(pity)
        if n == 10 and k == 9 and all(x["rarity"] == "common" for x in results):
            rarity = "rare"   # гарант rare+ в десятке
        pity = 0 if rarity == "legendary" else pity + 1
        iid = random.choice(pool[rarity])
        dup = iid in owned
        if dup:
            refund += C.DUPLICATE_REFUND[rarity]
        else:
            owned.add(iid)
            await db.run("INSERT OR IGNORE INTO inventory (tg_id, item_id) VALUES (?,?)", uid, iid)
        results.append({"id": iid, "name": C.ITEMS[iid][0], "kind": C.ITEMS[iid][1], "rarity": rarity, "dup": dup})
    await db.run("UPDATE users SET pity=? WHERE tg_id=?", pity, uid)
    if refund:
        await add_balance(uid, refund, "gacha_dup")
    await bump_quest(uid, "gacha")
    u = await db.one("SELECT balance, tickets FROM users WHERE tg_id=?", uid)
    leg = any(r["rarity"] == "legendary" for r in results)
    if leg:
        from .v2 import autopost
        nm = (await people([uid]))[uid]["name"]
        it = next(r for r in results if r["rarity"] == "legendary")
        await autopost(f"✨ {nm} выбил(а) легендарку «{it['name']}» в гаче! Поздравляем — и завидуем.", None, "event")
    return {"results": results, "refund": refund, "pity": pity, "pity_max": C.GACHA_PITY, **u,
            "lera": random.choice(C.LERA_LINES["legendary"]) if leg else None}


@app.get("/api/gacha/info")
async def gacha_info(me=Me):
    total = sum(C.RARITY_WEIGHTS.values())
    return {"pity": me["pity"], "pity_max": C.GACHA_PITY, "tickets": me["tickets"], "balance": me["balance"],
            "cost": C.GACHA_COST, "cost10": C.GACHA_COST_X10,
            "rates": {k: round(v / total * 100, 1) for k, v in C.RARITY_WEIGHTS.items()}}


# ── premium / payments ───────────────────────────────────────────────────

PACKS = {"premium30": ("Lera Premium · 30 дней", "Суперлайки ×5, отмена свайпа, ×2 ежедневка, корона-рамка", None),
         "nesso1000": ("1000 несо", "Пополнение кошелька Леры", 49)}


class InvoiceIn(BaseModel):
    pack: str


@app.post("/api/pay/invoice")
async def invoice(body: InvoiceIn, me=Me):
    if body.pack not in PACKS:
        raise HTTPException(404, "Нет такого пакета")
    title, desc, stars = PACKS[body.pack]
    stars = stars or config.PREMIUM_STARS
    link = await notify.create_stars_invoice(title, desc, f"{body.pack}:{me['tg_id']}", stars)
    if not link:
        raise HTTPException(503, "Оплата сейчас недоступна")
    return {"link": link}


async def apply_payment(charge_id: str, tg_id: int, payload: str, stars: int) -> bool:
    """Вызывается ботом после successful_payment. Идемпотентно."""
    await db.connect()
    if await db.one("SELECT 1 FROM payments WHERE charge_id=?", charge_id):
        return False
    await db.run("INSERT INTO payments (charge_id, tg_id, payload, stars) VALUES (?,?,?,?)", charge_id, tg_id, payload, stars)
    pack = payload.split(":")[0]
    if pack == "premium30":
        u = await db.one("SELECT premium_until FROM users WHERE tg_id=?", tg_id) or {}
        base = max(utcnow(), parse_ts(u.get("premium_until")) or utcnow())
        await db.run("UPDATE users SET premium_until=? WHERE tg_id=?", sqlts(base + timedelta(days=30)), tg_id)
    elif pack == "nesso1000":
        await add_balance(tg_id, 1000, "stars")
    return True


# ── admin ────────────────────────────────────────────────────────────────

@app.get("/api/admin/stats")
async def admin_stats(me=Me):
    if not me["is_admin"]:
        raise HTTPException(403, "Только для админа")
    q = {
        "users": "SELECT COUNT(*) FROM users",
        "online": "SELECT COUNT(*) FROM users WHERE last_seen > datetime('now','-5 minutes')",
        "dau": "SELECT COUNT(*) FROM users WHERE last_seen > datetime('now','-1 day')",
        "matches": "SELECT COUNT(*) FROM matches",
        "squads_open": "SELECT COUNT(*) FROM squads WHERE status='open' AND expires_at > datetime('now')",
        "posts": "SELECT COUNT(*) FROM posts",
        "premium": "SELECT COUNT(*) FROM users WHERE premium_until > datetime('now')",
    }
    return {k: await db.val(v) for k, v in q.items()}


# ── v2: игры, турниры, вики, автопостинг, мини-игры ─────────────────────
from . import v2  # noqa: E402

app.include_router(v2.router)


# ── static ───────────────────────────────────────────────────────────────

config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory=config.WEB_DIR), name="static")


@app.get("/{path:path}", include_in_schema=False)
async def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404)
    return FileResponse(config.WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})
