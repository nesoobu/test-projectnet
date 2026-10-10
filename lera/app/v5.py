"""Лера v5: реалтайм (WebSocket), входящие, друзья и подарки, быстрый поиск пати, бэкапы."""
import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from . import config, content as C, db, notify
from .auth import validate_init_data
from .main import (MSK, Me, _h, add_balance, add_xp, get_or_create_match, people, spend, sqlts, utcnow)
from .realtime import hub

router = APIRouter()
log = logging.getLogger("lera.v5")


# ── WebSocket ────────────────────────────────────────────────────────────

async def chat_members(key: str, uid: int) -> list[int] | None:
    """Кто состоит в чате (и есть ли там uid). key: m12 / s5 / c3."""
    kind, _, num = key[:1], None, key[1:]
    if not num.isdigit():
        return None
    i = int(num)
    if kind == "m":
        m = await db.one("SELECT u1, u2 FROM matches WHERE id=?", i)
        ids = [m["u1"], m["u2"]] if m else []
    elif kind == "s":
        ids = [r["tg_id"] for r in await db.all_("SELECT tg_id FROM squad_members WHERE squad_id=?", i)]
    elif kind == "c":
        ids = [r["tg_id"] for r in await db.all_("SELECT tg_id FROM clan_members WHERE clan_id=?", i)]
    elif kind == "t":
        from .v6 import t_chat_ids
        ids = await t_chat_ids(i)
    else:
        return None
    return ids if uid in ids else None


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    init = ws.query_params.get("init", "")
    tg = validate_init_data(init)
    if not tg and config.DEV_USER_ID:
        dev = ws.query_params.get("dev")
        tg = {"id": int(dev) if dev and dev.isdigit() else config.DEV_USER_ID}
    if not tg:
        await ws.close(code=4401)
        return
    uid = int(tg["id"])
    u = await db.one("SELECT banned FROM users WHERE tg_id=?", uid)
    if not u or u["banned"]:
        await ws.close(code=4403)
        return
    await ws.accept()
    hub.add(uid, ws)
    await db.run("UPDATE users SET last_seen=datetime('now') WHERE tg_id=?", uid)
    last_typing: dict[str, float] = {}
    try:
        while True:
            raw = await ws.receive_text()
            try:
                ev = json.loads(raw)
            except ValueError:
                continue
            t = ev.get("type")
            if t == "ping":
                await ws.send_text('{"type":"pong"}')
            elif t == "typing":
                key = str(ev.get("chat", ""))[:12]
                now = asyncio.get_event_loop().time()
                if now - last_typing.get(key, 0) < 2.5:
                    continue
                last_typing[key] = now
                ids = await chat_members(key, uid)
                if ids:
                    name = (await people([uid]))[uid]["name"]
                    hub.push([i for i in ids if i != uid], {"type": "typing", "chat": key, "from": uid, "name": name})
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        log.exception("ws error")
    finally:
        hub.remove(uid, ws)
        await db.run("UPDATE users SET last_seen=datetime('now') WHERE tg_id=?", uid)


# ── входящие ─────────────────────────────────────────────────────────────

@router.get("/api/inbox")
async def inbox(me=Me):
    rows = await db.all_("SELECT id, text, link, read, created_at FROM notifications WHERE tg_id=? ORDER BY id DESC LIMIT 60", me["tg_id"])
    unread = await db.val("SELECT COUNT(*) FROM notifications WHERE tg_id=? AND read=0", me["tg_id"])
    return {"items": rows, "unread": unread}


@router.post("/api/inbox/read")
async def inbox_read(me=Me):
    await db.run("UPDATE notifications SET read=1 WHERE tg_id=? AND read=0", me["tg_id"])
    return {"ok": True}


# ── друзья ───────────────────────────────────────────────────────────────

def pair(x: int, y: int) -> tuple[int, int]:
    return (x, y) if x < y else (y, x)


async def friendship(x: int, y: int) -> dict | None:
    a, b = pair(x, y)
    return await db.one("SELECT * FROM friends WHERE a=? AND b=?", a, b)


async def are_friends(x: int, y: int) -> bool:
    f = await friendship(x, y)
    return bool(f and f["status"] == "accepted")


@router.get("/api/friends")
async def friends(me=Me):
    uid = me["tg_id"]
    rows = await db.all_("SELECT * FROM friends WHERE a=? OR b=?", uid, uid)
    other = lambda r: r["b"] if r["a"] == uid else r["a"]  # noqa: E731
    ppl = await people([other(r) for r in rows])
    ready = {r["tg_id"]: r for r in await db.all_("SELECT tg_id, game, note FROM ready WHERE until > datetime('now')")}
    acc = [{**ppl[other(r)], "ready": ready.get(other(r))} for r in rows if r["status"] == "accepted" and other(r) in ppl]
    acc.sort(key=lambda p: (not p["ready"], not p["online"], p["name"]))
    return {"friends": acc,
            "incoming": [ppl[other(r)] for r in rows if r["status"] == "pending" and r["requester"] != uid and other(r) in ppl],
            "outgoing": [ppl[other(r)] for r in rows if r["status"] == "pending" and r["requester"] == uid and other(r) in ppl]}


@router.get("/api/friends/status/{to}")
async def friend_status(to: int, me=Me):
    f = await friendship(me["tg_id"], to)
    if not f:
        return {"status": "none"}
    if f["status"] == "accepted":
        return {"status": "friends"}
    return {"status": "outgoing" if f["requester"] == me["tg_id"] else "incoming"}


@router.post("/api/friends/{to}")
async def friend_add(to: int, me=Me):
    uid = me["tg_id"]
    if to == uid or to == 0 or not await db.one("SELECT 1 FROM users WHERE tg_id=? AND banned=0", to):
        raise HTTPException(400, "Нельзя")
    if await db.one("SELECT 1 FROM blocks WHERE (from_id=? AND to_id=?) OR (from_id=? AND to_id=?)", uid, to, to, uid):
        raise HTTPException(403, "Недоступно")
    a, b = pair(uid, to)
    f = await friendship(uid, to)
    name = _h((await people([uid]))[uid]["name"])
    if f and f["status"] == "accepted":
        return {"status": "friends"}
    if f and f["requester"] != uid:          # встречная заявка → дружба
        await db.run("UPDATE friends SET status='accepted' WHERE a=? AND b=?", a, b)
        mid, _ = await get_or_create_match(uid, to)
        notify.send(to, f"🤝 <b>{name}</b> принял(а) заявку в друзья", f"m{mid}")
        await add_xp(uid, 5); await add_xp(to, 5)
        return {"status": "friends", "match_id": mid}
    if not f:
        if await db.val("SELECT COUNT(*) FROM friends WHERE requester=? AND status='pending' AND created_at > datetime('now','-1 day')", uid) >= 30:
            raise HTTPException(429, "Слишком много заявок за сутки")
        await db.run("INSERT INTO friends (a, b, requester) VALUES (?,?,?)", a, b, uid)
        notify.send(to, f"👋 <b>{name}</b> хочет добавить тебя в друзья", "friends")
    return {"status": "outgoing"}


@router.delete("/api/friends/{to}")
async def friend_remove(to: int, me=Me):
    a, b = pair(me["tg_id"], to)
    await db.run("DELETE FROM friends WHERE a=? AND b=?", a, b)
    return {"status": "none"}


@router.post("/api/friends/{to}/chat")
async def friend_chat(to: int, me=Me):
    if not await are_friends(me["tg_id"], to):
        raise HTTPException(403, "Сначала добавьтесь в друзья")
    mid, _ = await get_or_create_match(me["tg_id"], to)
    await db.run("DELETE FROM blocks WHERE from_id=? AND to_id=? AND reason='unmatch'", me["tg_id"], to)
    return {"match_id": mid}


class GiftIn(BaseModel):
    to: int
    kind: str = Field(pattern="^(nesso|item)$")
    value: str = Field(min_length=1, max_length=40)
    note: str = Field("", max_length=120)


@router.post("/api/gift")
async def gift(body: GiftIn, me=Me):
    uid = me["tg_id"]
    if not await are_friends(uid, body.to):
        raise HTTPException(403, "Подарки — только друзьям")
    name = _h((await people([uid]))[uid]["name"])
    if body.kind == "nesso":
        if not body.value.isdigit() or not 10 <= int(body.value) <= 5000:
            raise HTTPException(400, "От 10 до 5000 несо")
        n = int(body.value)
        sent = await db.val("SELECT COALESCE(-SUM(amount),0) FROM transactions WHERE tg_id=? AND reason LIKE 'gift_to:%' "
                            "AND created_at > datetime('now','-1 day')", uid)
        if sent + n > 10000:
            raise HTTPException(429, "Не больше 10 000 несо подарков в сутки")
        await spend(uid, n, f"gift_to:{body.to}")
        await add_balance(body.to, n, f"gift_from:{uid}")
        what = f"{n} несо"
    else:
        iid = body.value
        if iid not in C.ITEMS:
            raise HTTPException(404, "Нет такого предмета")
        if await db.one("SELECT 1 FROM inventory WHERE tg_id=? AND item_id=?", body.to, iid):
            raise HTTPException(409, "У друга это уже есть")
        if not await db.change("DELETE FROM inventory WHERE tg_id=? AND item_id=?", uid, iid):
            raise HTTPException(403, "Этого предмета у тебя нет")
        await db.run("INSERT INTO inventory (tg_id, item_id) VALUES (?,?)", body.to, iid)
        what = C.ITEMS[iid][0]
    note = f"\n«{_h(body.note.strip())}»" if body.note.strip() else ""
    notify.send(body.to, f"🎁 <b>{name}</b> подарил(а) тебе: <b>{_h(what)}</b>{note}", "home")
    await add_xp(uid, 5)
    return {"ok": True, "what": what}


# ── быстрый поиск пати ───────────────────────────────────────────────────

class MMIn(BaseModel):
    game: str
    mode: str
    size: int = Field(ge=2, le=5)
    role: str | None = None
    voice: bool = False


@router.get("/api/mm")
async def mm_status(game: str, me=Me):
    mine = await db.one("SELECT * FROM mm_queue WHERE tg_id=?", me["tg_id"])
    counts = await db.all_("SELECT mode, size, COUNT(*) n FROM mm_queue WHERE game=? GROUP BY mode, size", game)
    return {"mine": mine, "queue": counts, "total": sum(c["n"] for c in counts)}


@router.post("/api/mm")
async def mm_join(body: MMIn, me=Me):
    uid = me["tg_id"]
    g = C.GAMES.get(body.game)
    if not g or body.mode not in g["modes"]:
        raise HTTPException(400, "Неизвестный режим")
    ug = await db.one("SELECT rank, roles FROM user_games WHERE tg_id=? AND game=?", uid, body.game)
    if not ug:
        raise HTTPException(400, f"Сначала добавь {g['short']} в профиль")
    role = body.role if body.role in g["roles"] else (json.loads(ug["roles"] or "[]") or [None])[0]
    await db.run("INSERT OR REPLACE INTO mm_queue (tg_id, game, mode, size, role, rank, voice) VALUES (?,?,?,?,?,?,?)",
                 uid, body.game, body.mode, body.size, role, ug["rank"], int(body.voice))
    asyncio.create_task(run_matcher())
    return await mm_status(body.game, me)


@router.delete("/api/mm")
async def mm_leave(me=Me):
    await db.run("DELETE FROM mm_queue WHERE tg_id=?", me["tg_id"])
    return {"ok": True}


_mm_lock = asyncio.Lock()


def age_s(row: dict) -> float:
    return (utcnow() - datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")).total_seconds()


def pick_party(cands: list[dict], size: int) -> list[dict] | None:
    """Жадно: от самого давнего, близкий ранг, разные роли. Чем дольше ждут — тем мягче требования."""
    anchor = cands[0]
    wait = age_s(anchor)
    rank_gap = 1 if wait < 60 else 2 if wait < 180 else 4
    strict_roles = wait < 120
    party, roles = [anchor], {anchor["role"]}
    for c in cands[1:]:
        if anchor["rank"] is not None and c["rank"] is not None and abs(anchor["rank"] - c["rank"]) > rank_gap:
            continue
        if strict_roles and c["role"] in roles and c["role"] is not None:
            continue
        party.append(c); roles.add(c["role"])
        if len(party) == size:
            return party
    return None


async def run_matcher():
    if _mm_lock.locked():
        return
    async with _mm_lock:
        # просроченные — домой
        for r in await db.all_("SELECT tg_id, game FROM mm_queue WHERE created_at < datetime('now','-20 minutes')"):
            await db.run("DELETE FROM mm_queue WHERE tg_id=?", r["tg_id"])
            notify.send(r["tg_id"], f"⌛ Быстрый поиск в {C.GAMES[r['game']]['short']}: за 20 минут пати не собралось. "
                                    "Попробуй другой режим или кинь клич «Готов играть».", "home")
        groups = await db.all_("SELECT game, mode, size FROM mm_queue GROUP BY game, mode, size HAVING COUNT(*) >= size")
        for grp in groups:
            while True:
                cands = await db.all_("SELECT * FROM mm_queue WHERE game=? AND mode=? AND size=? ORDER BY created_at",
                                      grp["game"], grp["mode"], grp["size"])
                party = None
                for i in range(len(cands)):
                    party = pick_party(cands[i:], grp["size"])
                    if party:
                        break
                if not party:
                    break
                await form_party(grp, party)


async def form_party(grp: dict, party: list[dict]):
    g = C.GAMES[grp["game"]]
    ids = [p["tg_id"] for p in party]
    leader = ids[0]
    title = f"Быстрый поиск · {g['modes'][grp['mode']]}"
    sid = await db.run("INSERT INTO squads (creator, title, game, mode, rank, roles_needed, max_players, voice, status, expires_at) "
                       "VALUES (?,?,?,?,?,'[]',?,?,'full',?)", leader, title, grp["game"], grp["mode"],
                       min((p["rank"] for p in party if p["rank"] is not None), default=None), grp["size"],
                       int(any(p["voice"] for p in party)), sqlts(utcnow() + timedelta(hours=2)))
    for uid in ids:
        await db.run("INSERT OR IGNORE INTO squad_members (squad_id, tg_id) VALUES (?,?)", sid, uid)
        await db.run("DELETE FROM mm_queue WHERE tg_id=?", uid)
        await add_xp(uid, 5)
    ppl = await people(ids, grp["game"])
    lineup = "\n".join(f"— {_h(ppl[u]['name'])}" + (f" · {g['roles'].get(p['role'], '')}" if p["role"] else "")
                       for u, p in zip(ids, party) if u in ppl)
    await db.run("INSERT INTO squad_messages (squad_id, sender, text) VALUES (?, 0, ?)", sid,
                 "Пати собрано! Познакомьтесь, договоритесь о ролях и киньте друг другу ID в игре. Удачной катки 🎮")
    for uid in ids:
        hub.push([uid], {"type": "mm_found", "squad": sid})
        notify.send(uid, f"⚡️ <b>Пати найдено!</b> {g['short']} · {g['modes'][grp['mode']]}\n{lineup}", f"s{sid}")


# ── фон: матчмейкер + бэкапы ─────────────────────────────────────────────

BACKUP_DIR = Path(config.DB_PATH).parent / "backups"


async def backup():
    now = datetime.now(MSK)
    if now.hour < 4:
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"lera-{now.date().isoformat()}.db"
    if target.exists():
        return
    import aiosqlite
    async with aiosqlite.connect(target) as dst:
        await db._conn.backup(dst)
    for old in sorted(BACKUP_DIR.glob("lera-*.db"))[:-7]:
        old.unlink(missing_ok=True)
    log.info("backup → %s", target)


async def loop():
    tick = 0
    while True:
        try:
            await run_matcher()
            if tick % 60 == 0:
                await backup()
                await db.run("DELETE FROM notifications WHERE created_at < datetime('now','-30 days')")
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("v5 tick failed")
        tick += 1
        await asyncio.sleep(5 + random.random())


@router.get("/api/admin/backups")
async def backups(me=Me):
    from .v2 import need_admin
    need_admin(me)
    files = sorted(BACKUP_DIR.glob("lera-*.db"), reverse=True) if BACKUP_DIR.exists() else []
    return {"backups": [{"name": f.name, "size": f.stat().st_size} for f in files]}
