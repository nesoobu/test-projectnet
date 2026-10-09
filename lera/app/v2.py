"""Лера v2: мультиигры, «Готов играть», отзывы, ачивки, вики, турниры, опрос дня, Лерадл, автопостинг."""
import asyncio
import hashlib
import html as htmllib
import json
import logging
import math
import random
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import content as C, db, notify, wiki_content as W
from .main import (MSK, Me, _h, add_balance, add_xp, bump_quest, get_or_create_match, is_online, jl, people,
                   spend, sqlts, today, utcnow, yday)

router = APIRouter(prefix="/api")
log = logging.getLogger("lera.v2")


def need_admin(me: dict):
    if not me["is_admin"]:
        raise HTTPException(403, "Только для админа")


def need_game(game: str) -> dict:
    g = C.GAMES.get(game)
    if not g:
        raise HTTPException(400, "Неизвестная игра")
    return g


def msk_to_utc(s: str) -> str:
    """'2026-10-12T19:00' (МСК) → '2026-10-12 16:00:00' (UTC, как в базе)."""
    try:
        dt = datetime.fromisoformat(s.replace(" ", "T")[:16])
    except ValueError:
        raise HTTPException(400, "Дата в формате ГГГГ-ММ-ДДTЧЧ:ММ")
    return sqlts(dt - timedelta(hours=3))


# ── автопостинг ──────────────────────────────────────────────────────────

async def autopost(text: str, game: str | None = None, kind: str = "event", link: str | None = None,
                   publish_at: str | None = None, image: str | None = None) -> int | None:
    """Пост от имени Леры. События режем по частоте, чтобы не заспамить ленту."""
    if kind == "event":
        recent = await db.val("SELECT COUNT(*) FROM posts WHERE author=0 AND kind='event' "
                              "AND created_at > datetime('now','-1 hour')")
        if recent >= 6:
            return None
    if await db.one("SELECT 1 FROM posts WHERE author=0 AND text=? AND created_at > datetime('now','-1 day')", text):
        return None
    return await db.run("INSERT INTO posts (author, text, game, kind, link, publish_at, image) VALUES (0,?,?,?,?,?,?)",
                        text[:1500], game, kind, link, publish_at, image)


def _strip(s: str | None) -> str:
    s = htmllib.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


ATOM = "{http://www.w3.org/2005/Atom}"


def parse_feed(raw: bytes) -> list[dict]:
    root = ET.fromstring(raw)
    out = []
    for it in root.iter("item"):
        out.append({"id": (it.findtext("guid") or it.findtext("link") or it.findtext("title") or "").strip(),
                    "title": _strip(it.findtext("title")), "link": (it.findtext("link") or "").strip(),
                    "text": _strip(it.findtext("description"))})
    for it in root.iter(f"{ATOM}entry"):
        ln = it.find(f"{ATOM}link")
        out.append({"id": (it.findtext(f"{ATOM}id") or "").strip(), "title": _strip(it.findtext(f"{ATOM}title")),
                    "link": ln.get("href", "") if ln is not None else "",
                    "text": _strip(it.findtext(f"{ATOM}summary") or it.findtext(f"{ATOM}content"))})
    return [x for x in out if x["id"]]


async def poll_feed(f: dict, client: httpx.AsyncClient):
    try:
        r = await client.get(f["url"])
        items = parse_feed(r.content)
    except Exception as e:  # noqa: BLE001 — кривой фид не должен ронять цикл
        await db.run("UPDATE feeds SET last_error=? WHERE id=?", str(e)[:200], f["id"])
        return
    seen = jl(f["seen"])
    first_run = not seen
    fresh = [x for x in items if x["id"] not in seen]
    if first_run:
        fresh = fresh[:1]           # при подключении — только самая свежая новость
    for x in reversed(fresh[:3]):
        text = f"📰 {x['title']}" + (f"\n\n{x['text'][:500]}{'…' if len(x['text']) > 500 else ''}" if x["text"] else "")
        link = x["link"] if x["link"].startswith("https://") else None
        await autopost(text, f["game"], "news", link)
    seen = ([x["id"] for x in items] + seen)[:300]
    await db.run("UPDATE feeds SET seen=?, last_error=NULL WHERE id=?", json.dumps(seen), f["id"])


async def weekly_digest():
    key = "weekly_" + datetime.now(MSK).strftime("%G-%V")
    if await db.one("SELECT 1 FROM meta WHERE key=?", key):
        return
    await db.run("INSERT INTO meta (key, val) VALUES (?, '1')", key)
    rows = await db.all_("SELECT tg_id, xp FROM users WHERE tg_id != 0 ORDER BY xp DESC LIMIT 3")
    if not rows:
        return
    ppl = await people([r["tg_id"] for r in rows])
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"{medals[i]} {ppl[r['tg_id']]['name']} — {r['xp']} xp" for i, r in enumerate(rows) if r["tg_id"] in ppl]
    squads = await db.val("SELECT COUNT(*) FROM squads WHERE created_at > datetime('now','-7 days')")
    matches = await db.val("SELECT COUNT(*) FROM matches WHERE created_at > datetime('now','-7 days')")
    await autopost("📊 Итоги недели от Леры\n\n" + "\n".join(lines)
                   + f"\n\nЗа неделю собрано {squads} отрядов и {matches} мэтчей. Новая неделя — новый топ.", None, "news")


async def background_loop():
    """Фоновые задачи веб-процесса: RSS каждые 15 мин, итоги недели по понедельникам, уборка."""
    tick = 0
    async with httpx.AsyncClient(timeout=15, follow_redirects=True,
                                 headers={"User-Agent": "LeraBot/2.0 (+https://t.me)"}) as client:
        while True:
            try:
                if tick % 15 == 0:
                    for f in await db.all_("SELECT * FROM feeds WHERE active=1"):
                        await poll_feed(f, client)
                now = datetime.now(MSK)
                if now.weekday() == 0 and now.hour >= 12:
                    await weekly_digest()
                    from .v4 import weekly_clip
                    await weekly_clip()
                await db.run("DELETE FROM ready WHERE until < datetime('now')")
                await db.run("DELETE FROM notify_log WHERE kind != 'ready_self' AND at < datetime('now','-2 days')")
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("background tick failed")
            tick += 1
            await asyncio.sleep(60)


# ── игры в профиле ───────────────────────────────────────────────────────

class GameIn(BaseModel):
    rank: int | None = Field(None, ge=0, le=20)
    roles: list[str] = []
    heroes: list[str] = []
    uid: str | None = Field(None, max_length=40)


@router.put("/games/{game}")
async def game_save(game: str, body: GameIn, me=Me):
    g = need_game(game)
    if body.rank is not None and body.rank >= len(g["ranks"]):
        raise HTTPException(400, "Неизвестный ранг")
    roles = [r for r in body.roles if r in g["roles"]][:3]
    names = {h[0] for h in g.get("heroes") or []}
    heroes = [h for h in body.heroes if h in names][:5]
    pos = await db.val("SELECT pos FROM user_games WHERE tg_id=? AND game=?", me["tg_id"], game)
    if pos is None:
        pos = await db.val("SELECT COUNT(*) FROM user_games WHERE tg_id=?", me["tg_id"])
    await db.run("INSERT INTO user_games (tg_id, game, rank, roles, heroes, game_uid, pos) VALUES (?,?,?,?,?,?,?) "
                 "ON CONFLICT(tg_id, game) DO UPDATE SET rank=excluded.rank, roles=excluded.roles, "
                 "heroes=excluded.heroes, game_uid=excluded.game_uid",
                 me["tg_id"], game, body.rank, json.dumps(roles), json.dumps(heroes, ensure_ascii=False),
                 (body.uid or "").strip() or None, pos)
    return (await people([me["tg_id"]]))[me["tg_id"]]


@router.delete("/games/{game}")
async def game_delete(game: str, me=Me):
    await db.run("DELETE FROM user_games WHERE tg_id=? AND game=?", me["tg_id"], game)
    return {"ok": True}


class OrderIn(BaseModel):
    games: list[str]


@router.post("/games/order")
async def games_order(body: OrderIn, me=Me):
    for i, g in enumerate(body.games):
        await db.run("UPDATE user_games SET pos=? WHERE tg_id=? AND game=?", i, me["tg_id"], g)
    return {"ok": True}


@router.get("/games/stats")
async def games_stats(me=Me):
    rows = await db.all_(
        "SELECT ug.game, COUNT(*) n, SUM(CASE WHEN u.last_seen > datetime('now','-5 minutes') THEN 1 ELSE 0 END) online "
        "FROM user_games ug JOIN users u ON u.tg_id=ug.tg_id GROUP BY ug.game")
    ready = {r["game"]: r["n"] for r in await db.all_(
        "SELECT game, COUNT(*) n FROM ready WHERE until > datetime('now') GROUP BY game")}
    return {r["game"]: {"players": r["n"], "online": r["online"] or 0, "ready": ready.get(r["game"], 0)} for r in rows}


# ── «Готов играть» ───────────────────────────────────────────────────────

class ReadyIn(BaseModel):
    game: str
    minutes: int = Field(60, ge=15, le=240)
    note: str = Field("", max_length=80)


@router.get("/ready")
async def ready_list(game: str, me=Me):
    rows = await db.all_("SELECT * FROM ready WHERE game=? AND until > datetime('now') ORDER BY created_at DESC LIMIT 50", game)
    blocked = {r["to_id"] for r in await db.all_("SELECT to_id FROM blocks WHERE from_id=?", me["tg_id"])}
    rows = [r for r in rows if r["tg_id"] not in blocked]
    ppl = await people([r["tg_id"] for r in rows], game)
    mine = next((r for r in rows if r["tg_id"] == me["tg_id"]), None)
    if not mine:
        mine = await db.one("SELECT * FROM ready WHERE tg_id=? AND until > datetime('now')", me["tg_id"])
    return {"mine": mine,
            "players": [{**ppl[r["tg_id"]], "note": r["note"], "until": r["until"]}
                        for r in rows if r["tg_id"] in ppl and r["tg_id"] != me["tg_id"]]}


@router.post("/ready")
async def ready_set(body: ReadyIn, me=Me):
    g = need_game(body.game)
    uid = me["tg_id"]
    if not await db.one("SELECT 1 FROM user_games WHERE tg_id=? AND game=?", uid, body.game):
        raise HTTPException(400, f"Сначала добавь {g['short']} в профиль")
    until = sqlts(utcnow() + timedelta(minutes=body.minutes))
    await db.run("INSERT INTO ready (tg_id, game, note, until) VALUES (?,?,?,?) "
                 "ON CONFLICT(tg_id) DO UPDATE SET game=excluded.game, note=excluded.note, until=excluded.until, "
                 "created_at=datetime('now')", uid, body.game, body.note.strip(), until)
    await bump_quest(uid, "ready")
    # рассылка — не чаще раза в 30 минут от одного игрока
    sent = 0
    if not await db.one("SELECT 1 FROM notify_log WHERE tg_id=? AND kind='ready_self' AND at > datetime('now','-30 minutes')", uid):
        await db.run("INSERT INTO notify_log (tg_id, kind) VALUES (?, 'ready_self')", uid)
        p = (await people([uid], body.game))[uid]
        bits = [x for x in [g["ranks"][p["rank"]] if p["rank"] is not None else None,
                            ", ".join(g["roles"][r] for r in p["roles"])] if x]
        note = f"\n«{_h(body.note.strip())}»" if body.note.strip() else ""
        text = (f"🎮 <b>{_h(p['name'])}</b> готов(а) играть в <b>{g['short']}</b> ближайшие {body.minutes} мин"
                + (f"\n{_h(' · '.join(bits))}" if bits else "") + note)
        rows = await db.all_(
            "SELECT ug.tg_id FROM user_games ug JOIN users u ON u.tg_id=ug.tg_id "
            "WHERE ug.game=? AND ug.tg_id NOT IN (?, 0) AND u.mute_ready=0 AND u.banned=0 AND u.last_seen > datetime('now','-14 days') "
            "AND NOT EXISTS (SELECT 1 FROM blocks b WHERE (b.from_id=ug.tg_id AND b.to_id=?) OR (b.from_id=? AND b.to_id=ug.tg_id)) "
            "AND NOT EXISTS (SELECT 1 FROM notify_log n WHERE n.tg_id=ug.tg_id AND n.kind='ready' AND n.at > datetime('now','-3 hours')) "
            "ORDER BY u.last_seen DESC LIMIT 40", body.game, uid, uid, uid)
        for r in rows:
            notify.send(r["tg_id"], text, "home")
            await db.run("INSERT INTO notify_log (tg_id, kind) VALUES (?, 'ready')", r["tg_id"])
            sent += 1
    return {"ok": True, "notified": sent, "until": until}


@router.delete("/ready")
async def ready_off(me=Me):
    await db.run("DELETE FROM ready WHERE tg_id=?", me["tg_id"])
    return {"ok": True}


@router.post("/ready/{to}/invite")
async def ready_invite(to: int, me=Me):
    r = await db.one("SELECT * FROM ready WHERE tg_id=? AND until > datetime('now')", to)
    if not r or to == me["tg_id"]:
        raise HTTPException(404, "Игрок уже не ищет пати")
    if await db.one("SELECT 1 FROM blocks WHERE (from_id=? AND to_id=?) OR (from_id=? AND to_id=?)", to, me["tg_id"], me["tg_id"], to):
        raise HTTPException(403, "Недоступно")
    mid, _ = await get_or_create_match(me["tg_id"], to)
    p = (await people([me["tg_id"]], r["game"]))[me["tg_id"]]
    notify.send(to, f"🔥 <b>{_h(p['name'])}</b> откликнулся(ась) на твоё «Готов играть» в {C.GAMES[r['game']]['short']}. "
                    "Чат уже открыт!", f"m{mid}")
    return {"match_id": mid}


class SettingsIn(BaseModel):
    mute_ready: bool


@router.post("/settings")
async def settings(body: SettingsIn, me=Me):
    await db.run("UPDATE users SET mute_ready=? WHERE tg_id=?", int(body.mute_ready), me["tg_id"])
    return {"ok": True}


# ── отзывы и репутация ───────────────────────────────────────────────────

async def can_review(a: int, b: int) -> bool:
    u1, u2 = sorted((a, b))
    if await db.one("SELECT 1 FROM matches WHERE u1=? AND u2=?", u1, u2):
        return True
    return bool(await db.one(
        "SELECT 1 FROM squad_members x JOIN squad_members y ON x.squad_id=y.squad_id WHERE x.tg_id=? AND y.tg_id=?", a, b))


@router.get("/review/candidates")
async def review_candidates(me=Me):
    uid = me["tg_id"]
    ids = [r["o"] for r in await db.all_(
        "SELECT CASE WHEN u1=? THEN u2 ELSE u1 END o FROM matches WHERE (u1=? OR u2=?) "
        "AND created_at > datetime('now','-30 days') "
        "UNION SELECT y.tg_id FROM squad_members x JOIN squad_members y ON x.squad_id=y.squad_id "
        "WHERE x.tg_id=? AND y.tg_id != ? AND y.joined_at > datetime('now','-14 days')", uid, uid, uid, uid, uid)]
    done = {r["to_id"] for r in await db.all_(
        "SELECT to_id FROM reviews WHERE from_id=? AND created_at > datetime('now','-7 days')", uid)}
    ppl = await people([i for i in ids if i not in done and i != 0][:20])
    return {"people": list(ppl.values())}


class ReviewIn(BaseModel):
    to: int
    thumb: int = Field(ge=-1, le=1)
    tags: list[str] = []


@router.post("/review")
async def review(body: ReviewIn, me=Me):
    uid = me["tg_id"]
    if body.to == uid or body.thumb == 0:
        raise HTTPException(400, "Так нельзя")
    if not await can_review(uid, body.to):
        raise HTTPException(403, "Оценить можно только тех, с кем был мэтч или отряд")
    if await db.one("SELECT 1 FROM reviews WHERE from_id=? AND to_id=? AND created_at > datetime('now','-7 days')", uid, body.to):
        raise HTTPException(409, "Ты уже оценивал(а) этого игрока на этой неделе")
    allowed = {k for k in C.REVIEW_TAGS if (k in C.NEGATIVE_TAGS) == (body.thumb < 0)}
    tags = [t for t in body.tags if t in allowed][:3]
    await db.run("INSERT INTO reviews (from_id, to_id, thumb, tags) VALUES (?,?,?,?)", uid, body.to, body.thumb, json.dumps(tags))
    await add_xp(uid, 3)
    if body.thumb > 0:
        tg = ", ".join(C.REVIEW_TAGS[t] for t in tags)
        notify.send(body.to, "👍 Тиммейт оставил тебе хороший отзыв" + (f": <b>{tg}</b>" if tg else "") + ". Репутация растёт!")
    return {"ok": True}


# ── ачивки ───────────────────────────────────────────────────────────────

async def user_stats(uid: int) -> dict:
    legendary = [k for k, v in C.ITEMS.items() if v[2] == "legendary"]
    q = ",".join("?" * len(legendary))
    v = db.val
    return {
        "matches": await v("SELECT COUNT(*) FROM matches WHERE u1=? OR u2=?", uid, uid),
        "squads": await v("SELECT COUNT(*) FROM squads WHERE creator=?", uid),
        "messages": (await v("SELECT COUNT(*) FROM match_messages WHERE sender=?", uid))
                    + (await v("SELECT COUNT(*) FROM squad_messages WHERE sender=?", uid)),
        "posts": await v("SELECT COUNT(*) FROM posts WHERE author=?", uid),
        "post_likes": await v("SELECT COUNT(*) FROM post_likes l JOIN posts p ON p.id=l.post_id WHERE p.author=?", uid),
        "streak": await v("SELECT streak FROM users WHERE tg_id=?", uid) or 0,
        "rep": await v("SELECT COUNT(*) FROM reviews WHERE to_id=? AND thumb>0", uid),
        "legendaries": await v(f"SELECT COUNT(*) FROM inventory WHERE tg_id=? AND item_id IN ({q})", uid, *legendary),
        "items": await v("SELECT COUNT(*) FROM inventory WHERE tg_id=?", uid),
        "games": await v("SELECT COUNT(*) FROM user_games WHERE tg_id=?", uid),
        "leradle": await v("SELECT COUNT(*) FROM leradle2 WHERE tg_id=? AND solved=1", uid),
        "t_wins": await v("SELECT COUNT(*) FROM tournaments t JOIN t_members m ON m.team_id=t.winner WHERE m.tg_id=?", uid),
        "ready": await v("SELECT COUNT(*) FROM notify_log WHERE tg_id=? AND kind='ready_self'", uid),
    }


@router.get("/achievements")
async def achievements(user: int = 0, me=Me):
    uid = user or me["tg_id"]
    st = await user_stats(uid)
    have = {r["ach_id"]: r["at"] for r in await db.all_("SELECT * FROM achievements WHERE tg_id=?", uid)}
    out, new = [], []
    for aid, name, desc, reward, metric, goal in C.ACHIEVEMENTS:
        done = st[metric] >= goal
        if done and aid not in have and uid == me["tg_id"]:
            if await db.change("INSERT OR IGNORE INTO achievements (tg_id, ach_id) VALUES (?,?)", uid, aid):
                await add_balance(uid, reward, f"ach:{aid}")
                await add_xp(uid, 20)
                new.append(name)
                have[aid] = "now"
        out.append({"id": aid, "name": name, "desc": desc, "reward": reward, "goal": goal,
                    "progress": min(st[metric], goal), "done": aid in have})
    return {"achievements": out, "new": new, "count": len(have), "total": len(C.ACHIEVEMENTS)}


# ── вики ─────────────────────────────────────────────────────────────────

async def tier_map(game: str) -> dict:
    out = {}
    for r in await db.all_("SELECT hero, AVG(tier) a, COUNT(*) n FROM wiki_tier WHERE game=? GROUP BY hero", game):
        out[r["hero"]] = {"tier": W.TIERS[min(4, int(r["a"] + 0.5))], "score": round(r["a"], 2), "votes": r["n"]}
    return out


async def guide_rows(uid: int, where: str, *args) -> list:
    rows = await db.all_("SELECT g.id, g.game, g.title, g.author, g.views, g.created_at, g.hero, g.cat, substr(g.body,1,140) AS preview, "
                         "(SELECT COUNT(*) FROM guide_likes l WHERE l.guide_id=g.id) AS likes, "
                         "EXISTS(SELECT 1 FROM guide_likes l WHERE l.guide_id=g.id AND l.tg_id=?) AS liked "
                         f"FROM guides g WHERE g.status='approved' AND {where} ORDER BY likes DESC, g.views DESC, g.id DESC LIMIT 100", uid, *args)
    ppl = await people({r["author"] for r in rows})
    return [{**r, "author": ppl.get(r["author"]), "liked": bool(r["liked"])} for r in rows]


@router.get("/wiki")
async def wiki(game: str, me=Me):
    g = need_game(game)
    info = W.WIKI.get(game, {})
    heroes = None
    if g.get("heroes"):
        pop: dict = {}
        for r in await db.all_("SELECT heroes FROM user_games WHERE game=? AND heroes != '[]'", game):
            for h in jl(r["heroes"]):
                pop[h] = pop.get(h, 0) + 1
        tiers = await tier_map(game)
        heroes = [{"name": n, "cls": c, "lane": l, "lane_name": g["roles"].get(l) if l else None, "mains": pop.get(n, 0),
                   **tiers.get(n, {"tier": None, "score": None, "votes": 0})} for n, c, l in g["heroes"]]
    roles = [{"key": k, "name": v, "desc": info.get("roles", {}).get(k, ""),
              "players": await db.val("SELECT COUNT(*) FROM user_games WHERE game=? AND roles LIKE ?", game, f'%"{k}"%')}
             for k, v in g["roles"].items()]
    return {"game": game, "entity": C.ENTITY.get(game, "Герои"), "about": info.get("about", ""), "roles": roles,
            "ranks": g["ranks"], "modes": list(g["modes"].values()), "glossary": info.get("glossary", []),
            "basics": info.get("basics", []), "cats": W.GUIDE_CATS, "heroes": heroes,
            "guides": await guide_rows(me["tg_id"], "g.game=?", game),
            "stats": {"players": await db.val("SELECT COUNT(*) FROM user_games WHERE game=?", game),
                      "tips": await db.val("SELECT COUNT(*) FROM wiki_tips WHERE game=?", game),
                      "voters": await db.val("SELECT COUNT(DISTINCT tg_id) FROM wiki_tier WHERE game=?", game)}}


@router.get("/wiki/guides/{gid}")
async def guide(gid: int, me=Me):
    r = await db.one("SELECT * FROM guides WHERE id=?", gid)
    if not r or (r["status"] != "approved" and r["author"] != me["tg_id"] and not me["is_admin"]):
        raise HTTPException(404, "Гайд не найден")
    await db.run("UPDATE guides SET views = views + 1 WHERE id=?", gid)
    likes = await db.val("SELECT COUNT(*) FROM guide_likes WHERE guide_id=?", gid)
    liked = bool(await db.one("SELECT 1 FROM guide_likes WHERE guide_id=? AND tg_id=?", gid, me["tg_id"]))
    return {**r, "author": (await people([r["author"]])).get(r["author"]), "likes": likes, "liked": liked,
            "cat_name": W.GUIDE_CATS.get(r.get("cat") or "other")}


class GuideIn(BaseModel):
    game: str
    title: str = Field(min_length=4, max_length=80)
    body: str = Field(min_length=40, max_length=8000)
    hero: str | None = None
    cat: str = "other"


@router.post("/wiki/guides")
async def guide_add(body: GuideIn, me=Me):
    g = need_game(body.game)
    status = "approved" if me["is_admin"] else "pending"
    hero = body.hero if body.hero in {h[0] for h in g.get("heroes") or []} else None
    cat = body.cat if body.cat in W.GUIDE_CATS else "other"
    gid = await db.run("INSERT INTO guides (game, author, title, body, status, hero, cat) VALUES (?,?,?,?,?,?,?)",
                       body.game, me["tg_id"], body.title.strip(), body.body.strip(), status, hero, cat)
    if status == "pending":
        from . import config
        for a in config.ADMIN_IDS:
            notify.send(a, f"📚 Новый гайд на модерации ({g['short']}): <b>{_h(body.title)}</b>", "admin")
    return {"id": gid, "status": status}


@router.delete("/wiki/guides/{gid}")
async def guide_del(gid: int, me=Me):
    r = await db.one("SELECT author FROM guides WHERE id=?", gid)
    if not r:
        raise HTTPException(404, "Гайд не найден")
    if r["author"] != me["tg_id"] and not me["is_admin"]:
        raise HTTPException(403, "Не твой гайд")
    await db.run("DELETE FROM guides WHERE id=?", gid)
    return {"ok": True}


@router.get("/admin/guides")
async def guides_pending(me=Me):
    need_admin(me)
    rows = await db.all_("SELECT * FROM guides WHERE status='pending' ORDER BY id")
    ppl = await people({r["author"] for r in rows})
    return {"guides": [{**r, "author": ppl.get(r["author"])} for r in rows]}


class ModerateIn(BaseModel):
    approve: bool


@router.post("/admin/guides/{gid}")
async def guide_moderate(gid: int, body: ModerateIn, me=Me):
    need_admin(me)
    r = await db.one("SELECT * FROM guides WHERE id=? AND status='pending'", gid)
    if not r:
        raise HTTPException(404, "Нет такого гайда на модерации")
    if body.approve:
        await db.run("UPDATE guides SET status='approved' WHERE id=?", gid)
        await add_balance(r["author"], 100, "guide")
        notify.send(r["author"], f"📚 Твой гайд «{_h(r['title'])}» опубликован! +100 несо", "home")
        await autopost(f"📚 Новый гайд по {C.GAMES[r['game']]['short']}: «{r['title']}». Ищи во вкладке «Вики».", r["game"], "event")
    else:
        await db.run("UPDATE guides SET status='rejected' WHERE id=?", gid)
        notify.send(r["author"], f"Гайд «{_h(r['title'])}» не прошёл модерацию. Попробуй дополнить и отправить снова.")
    return {"ok": True}


# ── турниры ──────────────────────────────────────────────────────────────

class TourIn(BaseModel):
    game: str
    title: str = Field(min_length=3, max_length=60)
    about: str = Field("", max_length=1000)
    team_size: int = Field(1, ge=1, le=5)
    max_teams: int = Field(8, ge=2, le=64)
    prize: int = Field(0, ge=0, le=100000)
    starts_at: str
    best_of: int = Field(1, ge=1, le=5)
    entry_fee: int = Field(0, ge=0, le=5000)
    checkin: bool = True
    auto_start: bool = True
    prize_split: list[int] = [70, 30]
    rules: str = Field("", max_length=2000)


async def fees_total(tid: int, t: dict) -> int:
    return (t.get("entry_fee") or 0) * (await db.val("SELECT COUNT(*) FROM t_members WHERE tid=?", tid) or 0)


async def refund_fee(t: dict, uids):
    if t.get("entry_fee"):
        for u in uids:
            await add_balance(u, t["entry_fee"], f"t_refund:{t['id']}")


async def t_get(tid: int) -> dict:
    t = await db.one("SELECT * FROM tournaments WHERE id=?", tid)
    if not t:
        raise HTTPException(404, "Турнир не найден")
    return t


async def my_team(tid: int, uid: int) -> int | None:
    return await db.val("SELECT team_id FROM t_members WHERE tid=? AND tg_id=?", tid, uid)


@router.get("/tournaments")
async def tournaments(game: str = "", me=Me):
    q = "SELECT t.*, (SELECT COUNT(*) FROM t_teams x WHERE x.tid=t.id) AS teams FROM tournaments t WHERE t.status != 'cancelled' "
    args = []
    if game in C.GAMES:
        q += "AND t.game=? "; args.append(game)
    rows = await db.all_(q + "ORDER BY CASE t.status WHEN 'live' THEN 0 WHEN 'reg' THEN 1 ELSE 2 END, t.starts_at LIMIT 50", *args)
    mine = {r["tid"] for r in await db.all_("SELECT tid FROM t_members WHERE tg_id=?", me["tg_id"])}
    return {"tournaments": [{**r, "joined": r["id"] in mine} for r in rows]}


@router.post("/tournaments")
async def tour_create(body: TourIn, me=Me):
    need_admin(me)
    g = need_game(body.game)
    split = [x for x in body.prize_split if x > 0][:2] or [100]
    if sum(split) != 100:
        raise HTTPException(400, "Доли приза должны давать 100%")
    tid = await db.run("INSERT INTO tournaments (game, title, about, team_size, max_teams, prize, starts_at, created_by, "
                       "best_of, entry_fee, checkin, auto_start, prize_split, rules) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       body.game, body.title.strip(), body.about.strip(), body.team_size, body.max_teams, body.prize,
                       msk_to_utc(body.starts_at), me["tg_id"], body.best_of, body.entry_fee, int(body.checkin),
                       int(body.auto_start), json.dumps(split), body.rules.strip() or None)
    fmt = "соло" if body.team_size == 1 else f"{body.team_size}×{body.team_size}"
    await autopost(f"🏆 Новый турнир по {g['short']}: «{body.title}»\n{fmt} · Bo{body.best_of} · до {body.max_teams} участников"
                   + (f" · приз {body.prize} несо" if body.prize else "") + (f" · взнос {body.entry_fee}" if body.entry_fee else "")
                   + "\nРегистрация уже открыта — вкладка «Главная».", body.game, "news")
    return {"id": tid}


@router.get("/tournaments/{tid}")
async def tour_view(tid: int, me=Me):
    t = await t_get(tid)
    teams = await db.all_("SELECT * FROM t_teams WHERE tid=? ORDER BY id", tid)
    mem = await db.all_("SELECT * FROM t_members WHERE tid=?", tid)
    ppl = await people([m["tg_id"] for m in mem], t["game"])
    for tm in teams:
        tm["members"] = [ppl[m["tg_id"]] for m in mem if m["team_id"] == tm["id"] and m["tg_id"] in ppl]
    matches = await db.all_("SELECT * FROM t_matches WHERE tid=? ORDER BY round, pos", tid)
    mt = await my_team(tid, me["tg_id"])
    starts = datetime.strptime(t["starts_at"], "%Y-%m-%d %H:%M:%S")
    pool = t["prize"] + await fees_total(tid, t)
    split = jl(t["prize_split"]) or [100]
    return {**t, "teams": teams, "matches": matches, "my_team": mt,
            "my_captain": bool(mt and next((x for x in teams if x["id"] == mt), {}).get("captain") == me["tg_id"]),
            "rounds": max([m["round"] for m in matches], default=0), "pool": pool,
            "payouts": [pool * p // 100 for p in split], "checkin_open": bool(t["checkin"]) and t["status"] == "reg"
            and utcnow() >= starts - timedelta(minutes=30), "server_now": sqlts(utcnow())}


class RegIn(BaseModel):
    team_name: str = Field("", max_length=30)


@router.post("/tournaments/{tid}/register")
async def tour_register(tid: int, body: RegIn, me=Me):
    t = await t_get(tid)
    uid = me["tg_id"]
    if t["status"] != "reg":
        raise HTTPException(409, "Регистрация закрыта")
    if await my_team(tid, uid):
        raise HTTPException(409, "Ты уже участвуешь")
    if await db.val("SELECT COUNT(*) FROM t_teams WHERE tid=?", tid) >= t["max_teams"]:
        raise HTTPException(409, "Мест нет")
    if not await db.one("SELECT 1 FROM user_games WHERE tg_id=? AND game=?", uid, t["game"]):
        raise HTTPException(400, f"Сначала добавь {C.GAMES[t['game']]['short']} в профиль")
    if t["entry_fee"]:
        await spend(uid, t["entry_fee"], f"t_fee:{tid}")
    name = body.team_name.strip() or (await people([uid]))[uid]["name"]
    team = await db.run("INSERT INTO t_teams (tid, name, captain) VALUES (?,?,?)", tid, name, uid)
    await db.run("INSERT INTO t_members (team_id, tid, tg_id) VALUES (?,?,?)", team, tid, uid)
    return {"team_id": team}


@router.post("/tournaments/{tid}/teams/{team}/join")
async def tour_join_team(tid: int, team: int, me=Me):
    t = await t_get(tid)
    uid = me["tg_id"]
    if t["status"] != "reg":
        raise HTTPException(409, "Регистрация закрыта")
    if await my_team(tid, uid):
        raise HTTPException(409, "Ты уже в команде")
    tm = await db.one("SELECT * FROM t_teams WHERE id=? AND tid=?", team, tid)
    if not tm:
        raise HTTPException(404, "Команда не найдена")
    if await db.val("SELECT COUNT(*) FROM t_members WHERE team_id=?", team) >= t["team_size"]:
        raise HTTPException(409, "Команда уже полная")
    if t["entry_fee"]:
        await spend(uid, t["entry_fee"], f"t_fee:{tid}")
    await db.run("INSERT INTO t_members (team_id, tid, tg_id) VALUES (?,?,?)", team, tid, uid)
    nm = (await people([uid]))[uid]["name"]
    notify.send(tm["captain"], f"🏆 <b>{_h(nm)}</b> вступил(а) в твою команду «{_h(tm['name'])}» на «{_h(t['title'])}»", f"t{tid}")
    return {"ok": True}


@router.post("/tournaments/{tid}/leave")
async def tour_leave(tid: int, me=Me):
    t = await t_get(tid)
    uid = me["tg_id"]
    if t["status"] != "reg":
        raise HTTPException(409, "Турнир уже идёт — выйти нельзя")
    team = await my_team(tid, uid)
    if not team:
        return {"ok": True}
    await db.run("DELETE FROM t_members WHERE tid=? AND tg_id=?", tid, uid)
    await refund_fee(t, [uid])
    left = await db.one("SELECT tg_id FROM t_members WHERE team_id=? LIMIT 1", team)
    if left:
        await db.run("UPDATE t_teams SET captain=? WHERE id=? AND captain=?", left["tg_id"], team, uid)
    else:
        await db.run("DELETE FROM t_teams WHERE id=?", team)
    return {"ok": True}


async def advance(t: dict, m: dict, winner: int):
    await db.run("UPDATE t_matches SET winner=? WHERE id=?", winner, m["id"])
    rounds = await db.val("SELECT MAX(round) FROM t_matches WHERE tid=?", t["id"])
    if m["round"] >= rounds:
        await finish(t, winner)
        return
    col = "team_a" if m["pos"] % 2 == 0 else "team_b"
    await db.run(f"UPDATE t_matches SET {col}=? WHERE tid=? AND round=? AND pos=?", winner, t["id"], m["round"] + 1, m["pos"] // 2)
    nxt = await db.one("SELECT * FROM t_matches WHERE tid=? AND round=? AND pos=?", t["id"], m["round"] + 1, m["pos"] // 2)
    if nxt["team_a"] and nxt["team_b"]:
        names = {r["id"]: r["name"] for r in await db.all_("SELECT id, name FROM t_teams WHERE id IN (?,?)", nxt["team_a"], nxt["team_b"])}
        for r in await db.all_("SELECT tg_id FROM t_members WHERE team_id IN (?,?)", nxt["team_a"], nxt["team_b"]):
            notify.send(r["tg_id"], f"⚔️ «{_h(t['title'])}»: следующий матч — <b>{_h(names.get(nxt['team_a'], '?'))}</b> vs "
                                    f"<b>{_h(names.get(nxt['team_b'], '?'))}</b>", f"t{t['id']}")


async def finish(t: dict, winner: int):
    t = await db.one("SELECT * FROM tournaments WHERE id=?", t["id"])
    await db.run("UPDATE tournaments SET status='done', winner=? WHERE id=?", winner, t["id"])
    team = await db.one("SELECT * FROM t_teams WHERE id=?", winner)
    members = [r["tg_id"] for r in await db.all_("SELECT tg_id FROM t_members WHERE team_id=?", winner)]
    final = await db.one("SELECT * FROM t_matches WHERE tid=? ORDER BY round DESC LIMIT 1", t["id"])
    runner = (final["team_b"] if final["team_a"] == winner else final["team_a"]) if final else None
    pool = t["prize"] + await fees_total(t["id"], t)
    split = jl(t.get("prize_split")) or [100]
    places = [(winner, split[0], "🏆 Победа"), (runner, split[1] if len(split) > 1 else 0, "🥈 Второе место")]
    for team_id, pct, label in places:
        if not team_id:
            continue
        ids = [r["tg_id"] for r in await db.all_("SELECT tg_id FROM t_members WHERE team_id=?", team_id)]
        share = (pool * pct // 100) // max(1, len(ids))
        for uid in ids:
            if share:
                await add_balance(uid, share, f"tournament:{t['id']}")
            await add_xp(uid, 100 if team_id == winner else 50)
            notify.send(uid, f"{label} в «{_h(t['title'])}»!" + (f" +{share} несо" if share else ""), f"t{t['id']}")
    ppl = await people(members)
    names = ", ".join(ppl[u]["name"] for u in members if u in ppl)
    who = team["name"] if t["team_size"] > 1 else names
    await autopost(f"🏆 Турнир «{t['title']}» завершён! Победа — {who}"
                   + (f" ({names})" if t["team_size"] > 1 and names else "") + ". GG!", t["game"], "event")


@router.post("/tournaments/{tid}/start")
async def tour_start(tid: int, me=Me):
    need_admin(me)
    t = await t_get(tid)
    if t["status"] != "reg":
        raise HTTPException(409, "Турнир уже запущен")
    return await start_tournament(t)


async def start_tournament(t: dict) -> dict:
    tid = t["id"]
    if t["checkin"]:   # не отметившиеся вылетают, взнос возвращается
        for tm in await db.all_("SELECT id FROM t_teams WHERE tid=? AND checked_in=0", tid):
            ids = [r["tg_id"] for r in await db.all_("SELECT tg_id FROM t_members WHERE team_id=?", tm["id"])]
            await refund_fee(t, ids)
            for u in ids:
                notify.send(u, f"⌛ Ты не отметился на «{_h(t['title'])}» — участие снято" + (", взнос возвращён" if t["entry_fee"] else ""), f"t{tid}")
            await db.run("DELETE FROM t_members WHERE team_id=?", tm["id"])
            await db.run("DELETE FROM t_teams WHERE id=?", tm["id"])
    teams = [r["id"] for r in await db.all_("SELECT id FROM t_teams WHERE tid=?", tid)]
    if len(teams) < 2:
        raise HTTPException(409, "Нужно минимум 2 участника" + (" с чек-ином" if t["checkin"] else ""))
    random.shuffle(teams)
    size = 2 ** math.ceil(math.log2(len(teams)))
    rounds = int(math.log2(size))
    await db.run("DELETE FROM t_matches WHERE tid=?", tid)
    for r in range(1, rounds + 1):
        for pos in range(size >> r):
            await db.run("INSERT INTO t_matches (tid, round, pos) VALUES (?,?,?)", tid, r, pos)
    await db.run("UPDATE tournaments SET status='live' WHERE id=?", tid)
    t["status"] = "live"
    for i in range(size // 2):
        a = teams[i]
        b = teams[size - 1 - i] if size - 1 - i < len(teams) else None
        await db.run("UPDATE t_matches SET team_a=?, team_b=? WHERE tid=? AND round=1 AND pos=?", a, b, tid, i)
        if b is None:   # bye
            m = await db.one("SELECT * FROM t_matches WHERE tid=? AND round=1 AND pos=?", tid, i)
            await advance(t, m, a)
    for r in await db.all_("SELECT tg_id FROM t_members WHERE tid=?", tid):
        notify.send(r["tg_id"], f"⚔️ Турнир «{_h(t['title'])}» начался! Смотри сетку.", f"t{tid}")
    return {"ok": True}


class WinIn(BaseModel):
    team: int
    score: str = Field("", max_length=12)


@router.post("/tournaments/{tid}/matches/{mid}/winner")
async def tour_winner(tid: int, mid: int, body: WinIn, me=Me):
    need_admin(me)
    t = await t_get(tid)
    m = await db.one("SELECT * FROM t_matches WHERE id=? AND tid=?", mid, tid)
    if not m or t["status"] != "live":
        raise HTTPException(404, "Матч не найден")
    if m["winner"]:
        raise HTTPException(409, "Победитель уже выбран")
    if body.team not in (m["team_a"], m["team_b"]) or not (m["team_a"] and m["team_b"]):
        raise HTTPException(400, "Эта команда не играет в матче")
    await db.run("UPDATE t_matches SET disputed=0, score=COALESCE(NULLIF(?,''), score) WHERE id=?", body.score.strip(), mid)
    await advance(t, m, body.team)
    from .v4 import settle_predictions
    await settle_predictions(t, mid, body.team)
    return {"ok": True}


@router.delete("/tournaments/{tid}")
async def tour_cancel(tid: int, me=Me):
    need_admin(me)
    t = await t_get(tid)
    if t["status"] in ("reg", "live"):
        await refund_fee(t, [r["tg_id"] for r in await db.all_("SELECT tg_id FROM t_members WHERE tid=?", tid)])
    await db.run("UPDATE tournaments SET status='cancelled' WHERE id=?", tid)
    return {"ok": True}


# ── опрос дня ────────────────────────────────────────────────────────────

async def poll_view(p: dict, uid: int) -> dict:
    votes = await db.all_("SELECT option, COUNT(*) n FROM poll_votes WHERE poll_id=? GROUP BY option", p["id"])
    mine = await db.val("SELECT option FROM poll_votes WHERE poll_id=? AND tg_id=?", p["id"], uid)
    opts = jl(p["options"])
    counts = [0] * len(opts)
    for v in votes:
        if 0 <= v["option"] < len(opts):
            counts[v["option"]] = v["n"]
    return {"id": p["id"], "question": p["question"], "options": opts, "game": p["game"], "voted": mine,
            "counts": counts if mine is not None else None, "total": sum(counts)}


@router.get("/poll")
async def poll_today(game: str = "", me=Me):
    d = today()
    p = await db.one("SELECT * FROM polls WHERE day=? AND game=?", d, game) if game in C.GAMES else None
    if not p and game in C.GAMES and C.GAMES[game].get("heroes"):
        ordn = datetime.now(MSK).date().toordinal()
        if ordn % 2:   # через день — опрос про свою игру: мета, баны, любимые карты
            g = C.GAMES[game]
            rnd = random.Random(f"poll:{game}:{d}")
            opts = [h[0] for h in rnd.sample(g["heroes"], min(4, len(g["heroes"])))]
            ent = C.ENTITY.get(game, "Герои")
            q = rnd.choice([f"Лучшая карта в {g['short']}?", f"На какой карте {g['short']} ты сильнее?"]) if ent == "Карты" else \
                rnd.choice([f"Кто сильнее в текущей мете {g['short']}?", f"Кого бы ты забанил в {g['short']}?",
                            f"Кого тебе хочется взять в следующей катке {g['short']}?", f"Самый переоценённый в {g['short']}?"])
            await db.run("INSERT INTO polls (question, options, game, day) VALUES (?,?,?,?)", q, json.dumps(opts, ensure_ascii=False), game, d)
            p = await db.one("SELECT * FROM polls WHERE day=? AND game=?", d, game)
    p = p or await db.one("SELECT * FROM polls WHERE day=? AND game IS NULL", d)
    if not p:
        idx = datetime.now(MSK).date().toordinal() % len(C.POLL_POOL)
        q, opts = C.POLL_POOL[idx]
        await db.run("INSERT INTO polls (question, options, game, day) VALUES (?,?,NULL,?)", q, json.dumps(opts, ensure_ascii=False), d)
        p = await db.one("SELECT * FROM polls WHERE day=? AND game IS NULL", d)
    return await poll_view(p, me["tg_id"])


class VoteIn(BaseModel):
    option: int = Field(ge=0, le=9)


@router.post("/poll/{pid}/vote")
async def poll_vote(pid: int, body: VoteIn, me=Me):
    p = await db.one("SELECT * FROM polls WHERE id=?", pid)
    if not p or body.option >= len(jl(p["options"])):
        raise HTTPException(404, "Опрос не найден")
    if await db.change("INSERT OR IGNORE INTO poll_votes (poll_id, tg_id, option) VALUES (?,?,?)", pid, me["tg_id"], body.option):
        await add_xp(me["tg_id"], 2)
    return await poll_view(p, me["tg_id"])


class PollIn(BaseModel):
    question: str = Field(min_length=3, max_length=140)
    options: list[str] = Field(min_length=2, max_length=6)
    game: str | None = None
    day: str | None = None


@router.post("/admin/poll")
async def poll_create(body: PollIn, me=Me):
    need_admin(me)
    game = body.game if body.game in C.GAMES else None
    d = body.day or today()
    opts = [o.strip()[:40] for o in body.options if o.strip()]
    if game:
        await db.run("DELETE FROM polls WHERE day=? AND game=?", d, game)
    else:
        await db.run("DELETE FROM polls WHERE day=? AND game IS NULL AND id NOT IN (SELECT poll_id FROM poll_votes)", d)
    pid = await db.run("INSERT INTO polls (question, options, game, day, created_by) VALUES (?,?,?,?,?)",
                       body.question.strip(), json.dumps(opts, ensure_ascii=False), game, d, me["tg_id"])
    return {"id": pid}


# ── Лерадл: угадай персонажа дня (для каждой игры свой) ──────────────────

LERADLE_MAX = 6


def ldl_game(game: str) -> str:
    return game if game in C.LERADLE_GAMES else "hok"


def ldl_pool(game: str) -> list:
    return C.GAMES[ldl_game(game)]["heroes"]


def leradle_answer(day: str, game: str = "hok") -> tuple:
    pool = ldl_pool(game)
    seed = f"lera:{day}" if game == "hok" else f"lera:{game}:{day}"   # HoK — как раньше, чтобы не сбить сегодняшний ответ
    return pool[int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(pool)]


def leradle_feedback(guess: tuple, ans: tuple, game: str) -> dict:
    roles = C.GAMES[ldl_game(game)]["roles"]
    gl, al = len(guess[0].replace(" ", "")), len(ans[0].replace(" ", ""))
    gf, af = guess[0][0].upper(), ans[0][0].upper()
    return {"name": guess[0], "cls": guess[1], "cls_ok": guess[1] == ans[1],
            "lane": roles.get(guess[2], "—"), "lane_ok": guess[2] == ans[2],
            "len": gl, "len_hint": "eq" if gl == al else ("up" if al > gl else "down"),
            "letter": gf, "letter_hint": "eq" if gf == af else ("up" if af > gf else "down"),
            "win": guess[0] == ans[0]}


async def leradle_row(uid: int, d: str, game: str) -> dict | None:
    return await db.one("SELECT * FROM leradle2 WHERE tg_id=? AND day=? AND game=?", uid, d, game)


async def leradle_state(uid: int, game: str = "hok") -> dict:
    game = ldl_game(game)
    d = today()
    row = await leradle_row(uid, d, game) or {"guesses": "[]", "solved": 0}
    ans = leradle_answer(d, game)
    by_name = {h[0]: h for h in ldl_pool(game)}
    guesses = [leradle_feedback(by_name[n], ans, game) for n in jl(row["guesses"]) if n in by_name]
    over = bool(row["solved"]) or len(guesses) >= LERADLE_MAX
    u = await db.one("SELECT leradle_streak, last_leradle FROM users WHERE tg_id=?", uid)
    streak = u["leradle_streak"] if u and u["last_leradle"] in (d, yday()) else 0
    roles = C.GAMES[game]["roles"]
    return {"day": d, "game": game, "entity": C.ENTITY.get(game, "Герои"), "max": LERADLE_MAX, "guesses": guesses,
            "solved": bool(row["solved"]), "over": over,
            "answer": {"name": ans[0], "cls": ans[1], "lane": roles.get(ans[2], "—")} if over else None,
            "streak": streak, "names": sorted(by_name), "games": C.LERADLE_GAMES}


@router.get("/leradle")
async def leradle(game: str = "hok", me=Me):
    return await leradle_state(me["tg_id"], game)


class GuessIn(BaseModel):
    name: str
    game: str = "hok"


@router.post("/leradle/guess")
async def leradle_guess(body: GuessIn, me=Me):
    uid, d, game = me["tg_id"], today(), ldl_game(body.game)
    by_name = {h[0].lower(): h for h in ldl_pool(game)}
    hero = by_name.get(body.name.strip().lower())
    if not hero:
        raise HTTPException(400, "Нет такого варианта")
    row = await leradle_row(uid, d, game)
    guesses = jl(row["guesses"]) if row else []
    if (row and row["solved"]) or len(guesses) >= LERADLE_MAX:
        raise HTTPException(409, "На сегодня всё — приходи завтра или попробуй другую игру")
    if hero[0] in guesses:
        raise HTTPException(409, "Это уже было")
    guesses.append(hero[0])
    win = hero[0] == leradle_answer(d, game)[0]
    await db.run("INSERT INTO leradle2 (tg_id, day, game, guesses, solved) VALUES (?,?,?,?,?) "
                 "ON CONFLICT(tg_id, day, game) DO UPDATE SET guesses=excluded.guesses, solved=excluded.solved",
                 uid, d, game, json.dumps(guesses), int(win))
    reward = 0
    if win:
        u = await db.one("SELECT leradle_streak, last_leradle FROM users WHERE tg_id=?", uid)
        first_today = u["last_leradle"] != d
        streak = (u["leradle_streak"] + 1) if u["last_leradle"] == yday() else (u["leradle_streak"] if not first_today else 1)
        await db.run("UPDATE users SET leradle_streak=?, last_leradle=? WHERE tg_id=?", streak, d, uid)
        reward = 20 + 5 * (LERADLE_MAX - len(guesses)) + (5 * min(streak - 1, 6) if first_today else 0)
        await add_balance(uid, reward, f"leradle:{game}")
        await add_xp(uid, 15)
        await bump_quest(uid, "leradle")
    st = await leradle_state(uid, game)
    return {**st, "reward": reward}


# ── админ: посты, фиды ───────────────────────────────────────────────────

class AdminPostIn(BaseModel):
    text: str = Field(min_length=1, max_length=1500)
    game: str | None = None
    image: str | None = None
    link: str | None = None
    publish_at: str | None = None


@router.post("/admin/post")
async def admin_post(body: AdminPostIn, me=Me):
    need_admin(me)
    pid = await autopost(body.text.strip(), body.game if body.game in C.GAMES else None, "news",
                         body.link if body.link and body.link.startswith("https://") else None,
                         msk_to_utc(body.publish_at) if body.publish_at else None,
                         body.image if body.image and body.image.startswith("/uploads/") else None)
    return {"id": pid}


@router.get("/admin/scheduled")
async def admin_scheduled(me=Me):
    need_admin(me)
    return {"posts": await db.all_("SELECT id, text, game, publish_at FROM posts WHERE publish_at > datetime('now') ORDER BY publish_at")}


class FeedIn(BaseModel):
    url: str = Field(pattern=r"^https?://", max_length=400)
    game: str | None = None
    title: str = Field("", max_length=60)


@router.get("/admin/feeds")
async def feeds(me=Me):
    need_admin(me)
    return {"feeds": await db.all_("SELECT id, url, game, title, active, last_error FROM feeds ORDER BY id")}


@router.post("/admin/feeds")
async def feed_add(body: FeedIn, me=Me):
    need_admin(me)
    fid = await db.run("INSERT OR IGNORE INTO feeds (url, game, title) VALUES (?,?,?)", body.url.strip(),
                       body.game if body.game in C.GAMES else None, body.title.strip() or None)
    f = await db.one("SELECT * FROM feeds WHERE url=?", body.url.strip())
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers={"User-Agent": "LeraBot/2.0"}) as c:
        await poll_feed(f, c)
    f = await db.one("SELECT id, url, game, title, active, last_error FROM feeds WHERE url=?", body.url.strip())
    return {"feed": f, "id": fid}


@router.delete("/admin/feeds/{fid}")
async def feed_del(fid: int, me=Me):
    need_admin(me)
    await db.run("DELETE FROM feeds WHERE id=?", fid)
    return {"ok": True}


# ── главная: всё одним запросом ──────────────────────────────────────────

@router.get("/home")
async def home(game: str, me=Me):
    need_game(game)
    uid = me["tg_id"]
    t = await db.all_("SELECT t.*, (SELECT COUNT(*) FROM t_teams x WHERE x.tid=t.id) AS teams FROM tournaments t "
                      "WHERE t.game=? AND t.status IN ('reg','live') ORDER BY t.starts_at LIMIT 3", game)
    lera = await leradle_state(uid, game)
    q = await db.all_("SELECT quest_id, progress, claimed FROM quest_progress WHERE tg_id=? AND day=?", uid, today())
    claimable = sum(1 for r in q if r["progress"] >= C.QUESTS.get(r["quest_id"], ("", 99))[1] and not r["claimed"])
    squads = await db.val("SELECT COUNT(*) FROM squads WHERE game=? AND status='open' AND expires_at > datetime('now')", game)
    online = await db.val("SELECT COUNT(*) FROM user_games ug JOIN users u ON u.tg_id=ug.tg_id "
                          "WHERE ug.game=? AND u.last_seen > datetime('now','-5 minutes')", game)
    return {"tournaments": t, "leradle": {"solved": lera["solved"], "over": lera["over"], "tries": len(lera["guesses"]),
                                         "streak": lera["streak"], "game": lera["game"]},
            "quests_ready": claimable, "squads_open": squads, "online": online,
            "ready": await ready_list(game, me), "poll": await poll_today(game, me)}
