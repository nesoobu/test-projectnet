"""Лера v3: кланы, боевой пропуск, промокоды, расширенная админка."""
import asyncio
import calendar
import json
import logging
import re
import secrets
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import config, content as C, db, notify
from .main import (MSK, Me, _h, add_balance, add_xp, is_premium, jl, parse_ts, people, season, sqlts, today, utcnow)
from .v2 import autopost, need_admin

router = APIRouter(prefix="/api")
log = logging.getLogger("lera.v3")


async def grant(uid: int, kind: str, value, reason: str) -> str:
    """Выдать награду. Возвращает человекочитаемое описание."""
    if kind == "nesso":
        await add_balance(uid, int(value), reason)
        return f"{int(value)} несо"
    if kind == "ticket":
        await db.run("UPDATE users SET tickets = tickets + ? WHERE tg_id=?", int(value), uid)
        return f"{int(value)} тикет(ов)"
    if kind == "item":
        if value not in C.ITEMS:
            raise HTTPException(400, "Нет такого предмета")
        if not await db.change("INSERT OR IGNORE INTO inventory (tg_id, item_id) VALUES (?,?)", uid, value):
            await add_balance(uid, 100, reason + ":dup")
            return f"{C.ITEMS[value][0]} (дубль → 100 несо)"
        return C.ITEMS[value][0]
    if kind == "premium":
        u = await db.one("SELECT premium_until FROM users WHERE tg_id=?", uid) or {}
        base = max(utcnow(), parse_ts(u.get("premium_until")) or utcnow())
        await db.run("UPDATE users SET premium_until=? WHERE tg_id=?", sqlts(base + timedelta(days=int(value))), uid)
        return f"Premium на {int(value)} дн."
    if kind == "xp":
        await add_xp(uid, int(value))
        return f"{int(value)} xp"
    raise HTTPException(400, "Неизвестный тип награды")


async def admin_log(admin: int, action: str, target: int | None = None, details: str = ""):
    await db.run("INSERT INTO admin_log (admin, action, target, details) VALUES (?,?,?,?)", admin, action, target, details[:500])


# ── кланы ────────────────────────────────────────────────────────────────

TAG_RE = re.compile(r"^[A-ZА-ЯЁ0-9]{2,5}$")


async def clan_get(cid: int) -> dict:
    c = await db.one("SELECT * FROM clans WHERE id=?", cid)
    if not c:
        raise HTTPException(404, "Клан не найден")
    return c


async def my_clan_role(uid: int, cid: int | None = None) -> tuple[int | None, str | None]:
    r = await db.one("SELECT clan_id, role FROM clan_members WHERE tg_id=?", uid)
    if not r or (cid and r["clan_id"] != cid):
        return (r["clan_id"] if r else None), None
    return r["clan_id"], r["role"]


async def weekly_xp(ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    q = ",".join("?" * len(ids))
    return {r["clan_id"]: r["n"] for r in await db.all_(
        f"SELECT clan_id, SUM(amount) n FROM clan_xp_log WHERE at > datetime('now','-7 days') AND clan_id IN ({q}) GROUP BY clan_id", *ids)}


async def clans_view(rows: list[dict]) -> list[dict]:
    ids = [r["id"] for r in rows]
    if not ids:
        return []
    q = ",".join("?" * len(ids))
    cnt = {r["clan_id"]: r["n"] for r in await db.all_(f"SELECT clan_id, COUNT(*) n FROM clan_members WHERE clan_id IN ({q}) GROUP BY clan_id", *ids)}
    wk = await weekly_xp(ids)
    return [{**r, "members": cnt.get(r["id"], 0), "week_xp": wk.get(r["id"], 0), **{"lvl": C.clan_level(r["xp"])}} for r in rows]


@router.get("/clans")
async def clans(q: str = "", game: str = "", sort: str = "week", me=Me):
    where, args = "WHERE 1=1", []
    if q:
        where += " AND (name LIKE ? OR tag LIKE ?)"; args += [f"%{q}%", f"%{q.upper()}%"]
    if game in C.GAMES:
        where += " AND (game=? OR game IS NULL)"; args.append(game)
    rows = await db.all_(f"SELECT * FROM clans {where} ORDER BY xp DESC LIMIT 100", *args)
    out = await clans_view(rows)
    if sort == "week":
        out.sort(key=lambda c: (c["week_xp"], c["xp"]), reverse=True)
    mine, role = await my_clan_role(me["tg_id"])
    pending = [r["clan_id"] for r in await db.all_("SELECT clan_id FROM clan_requests WHERE tg_id=?", me["tg_id"])]
    return {"clans": out, "my_clan": mine, "pending": pending, "cost": C.CLAN_COST}


class ClanIn(BaseModel):
    name: str = Field(min_length=3, max_length=24)
    tag: str = Field(min_length=2, max_length=5)
    game: str | None = None
    about: str = Field("", max_length=300)
    color: str = Field("#d4ff3f", pattern=r"^#[0-9a-fA-F]{6}$")
    open: bool = True


@router.post("/clans")
async def clan_create(body: ClanIn, me=Me):
    uid = me["tg_id"]
    tag = body.tag.strip().upper()
    if not TAG_RE.match(tag):
        raise HTTPException(400, "Тег: 2–5 букв или цифр")
    if (await my_clan_role(uid))[0]:
        raise HTTPException(409, "Ты уже в клане — сначала выйди")
    if await db.one("SELECT 1 FROM clans WHERE tag=?", tag):
        raise HTTPException(409, "Такой тег уже занят")
    from .main import spend
    await spend(uid, C.CLAN_COST, "clan_create")
    cid = await db.run("INSERT INTO clans (name, tag, game, about, color, owner, open) VALUES (?,?,?,?,?,?,?)",
                       body.name.strip(), tag, body.game if body.game in C.GAMES else None, body.about.strip(),
                       body.color, uid, int(body.open))
    await db.run("INSERT INTO clan_members (clan_id, tg_id, role) VALUES (?,?,'owner')", cid, uid)
    await db.run("DELETE FROM clan_requests WHERE tg_id=?", uid)
    await autopost(f"🛡 Новый клан [{tag}] {body.name.strip()} — ищет бойцов. Загляни во вкладку «Тиммейты → кланы».",
                   body.game if body.game in C.GAMES else None, "event")
    return {"id": cid}


@router.get("/clans/{cid}")
async def clan_view(cid: int, me=Me):
    c = (await clans_view([await clan_get(cid)]))[0]
    mem = await db.all_("SELECT * FROM clan_members WHERE clan_id=? ORDER BY CASE role WHEN 'owner' THEN 0 WHEN 'officer' THEN 1 ELSE 2 END, xp DESC", cid)
    ppl = await people([m["tg_id"] for m in mem], c["game"])
    _, role = await my_clan_role(me["tg_id"], cid)
    reqs = []
    if role in ("owner", "officer"):
        rr = await db.all_("SELECT tg_id, created_at FROM clan_requests WHERE clan_id=? ORDER BY created_at", cid)
        rp = await people([r["tg_id"] for r in rr], c["game"])
        reqs = [rp[r["tg_id"]] for r in rr if r["tg_id"] in rp]
    pos = await db.val("SELECT COUNT(*) FROM clans WHERE xp > ?", c["xp"]) + 1
    return {**c, "rank_pos": pos, "my_role": role,
            "requested": bool(await db.one("SELECT 1 FROM clan_requests WHERE clan_id=? AND tg_id=?", cid, me["tg_id"])),
            "members_list": [{**ppl[m["tg_id"]], "role": m["role"], "clan_xp": m["xp"]} for m in mem if m["tg_id"] in ppl],
            "requests": reqs}


class ClanEditIn(BaseModel):
    about: str = Field("", max_length=300)
    color: str = Field("#d4ff3f", pattern=r"^#[0-9a-fA-F]{6}$")
    open: bool = True
    game: str | None = None


@router.put("/clans/{cid}")
async def clan_edit(cid: int, body: ClanEditIn, me=Me):
    _, role = await my_clan_role(me["tg_id"], cid)
    if role not in ("owner", "officer"):
        raise HTTPException(403, "Только лидер или офицер")
    await db.run("UPDATE clans SET about=?, color=?, open=?, game=? WHERE id=?", body.about.strip(), body.color,
                 int(body.open), body.game if body.game in C.GAMES else None, cid)
    return {"ok": True}


async def add_member(cid: int, uid: int):
    await db.run("INSERT INTO clan_members (clan_id, tg_id) VALUES (?,?)", cid, uid)
    await db.run("DELETE FROM clan_requests WHERE tg_id=?", uid)


@router.post("/clans/{cid}/join")
async def clan_join(cid: int, me=Me):
    uid = me["tg_id"]
    c = await clan_get(cid)
    if (await my_clan_role(uid))[0]:
        raise HTTPException(409, "Ты уже в клане")
    n = await db.val("SELECT COUNT(*) FROM clan_members WHERE clan_id=?", cid)
    if n >= C.clan_level(c["xp"])["max_members"]:
        raise HTTPException(409, "В клане нет мест")
    name = (await people([uid]))[uid]["name"]
    if c["open"]:
        await add_member(cid, uid)
        notify.send(c["owner"], f"🛡 <b>{_h(name)}</b> вступил(а) в клан [{c['tag']}]", f"c{cid}")
        return {"joined": True}
    await db.run("INSERT OR IGNORE INTO clan_requests (clan_id, tg_id) VALUES (?,?)", cid, uid)
    for r in await db.all_("SELECT tg_id FROM clan_members WHERE clan_id=? AND role IN ('owner','officer')", cid):
        notify.send(r["tg_id"], f"📨 <b>{_h(name)}</b> просится в клан [{c['tag']}]", f"c{cid}")
    return {"joined": False, "requested": True}


class DecideIn(BaseModel):
    accept: bool


@router.post("/clans/{cid}/requests/{uid}")
async def clan_request(cid: int, uid: int, body: DecideIn, me=Me):
    _, role = await my_clan_role(me["tg_id"], cid)
    if role not in ("owner", "officer"):
        raise HTTPException(403, "Только лидер или офицер")
    c = await clan_get(cid)
    if not await db.change("DELETE FROM clan_requests WHERE clan_id=? AND tg_id=?", cid, uid):
        raise HTTPException(404, "Заявка не найдена")
    if body.accept:
        if (await my_clan_role(uid))[0]:
            raise HTTPException(409, "Игрок уже в другом клане")
        await add_member(cid, uid)
        notify.send(uid, f"✅ Тебя приняли в клан [{c['tag']}] {_h(c['name'])}!", f"c{cid}")
    return {"ok": True}


@router.post("/clans/{cid}/leave")
async def clan_leave(cid: int, me=Me):
    uid = me["tg_id"]
    _, role = await my_clan_role(uid, cid)
    if not role:
        return {"ok": True}
    await db.run("DELETE FROM clan_members WHERE tg_id=?", uid)
    if role == "owner":
        heir = await db.one("SELECT tg_id FROM clan_members WHERE clan_id=? ORDER BY CASE role WHEN 'officer' THEN 0 ELSE 1 END, xp DESC LIMIT 1", cid)
        if heir:
            await db.run("UPDATE clan_members SET role='owner' WHERE tg_id=?", heir["tg_id"])
            await db.run("UPDATE clans SET owner=? WHERE id=?", heir["tg_id"], cid)
            notify.send(heir["tg_id"], "👑 Ты теперь лидер клана — прошлый лидер вышел.", f"c{cid}")
        else:
            await delete_clan(cid)
    return {"ok": True}


async def delete_clan(cid: int):
    for t in ("clan_members", "clan_requests", "clan_messages", "clan_xp_log"):
        await db.run(f"DELETE FROM {t} WHERE clan_id=?", cid)
    await db.run("DELETE FROM clans WHERE id=?", cid)


@router.post("/clans/{cid}/kick/{uid}")
async def clan_kick(cid: int, uid: int, me=Me):
    _, role = await my_clan_role(me["tg_id"], cid)
    _, trole = await my_clan_role(uid, cid)
    if not trole:
        raise HTTPException(404, "Игрок не в клане")
    if role != "owner" and not (role == "officer" and trole == "member"):
        raise HTTPException(403, "Недостаточно прав")
    await db.run("DELETE FROM clan_members WHERE tg_id=? AND clan_id=?", uid, cid)
    return {"ok": True}


class RoleIn(BaseModel):
    role: str = Field(pattern="^(owner|officer|member)$")


@router.post("/clans/{cid}/role/{uid}")
async def clan_role(cid: int, uid: int, body: RoleIn, me=Me):
    _, role = await my_clan_role(me["tg_id"], cid)
    if role != "owner":
        raise HTTPException(403, "Только лидер")
    if not (await my_clan_role(uid, cid))[1] or uid == me["tg_id"]:
        raise HTTPException(400, "Нельзя")
    if body.role == "owner":
        await db.run("UPDATE clan_members SET role='officer' WHERE tg_id=?", me["tg_id"])
        await db.run("UPDATE clans SET owner=? WHERE id=?", uid, cid)
    await db.run("UPDATE clan_members SET role=? WHERE tg_id=?", body.role, uid)
    notify.send(uid, f"🛡 Твоя роль в клане: <b>{C.CLAN_ROLES[body.role]}</b>", f"c{cid}")
    return {"ok": True}


@router.get("/clans/{cid}/messages")
async def clan_msgs(cid: int, after: int = 0, me=Me):
    if not (await my_clan_role(me["tg_id"], cid))[1]:
        raise HTTPException(403, "Чат только для бойцов клана")
    msgs = await db.all_("SELECT id, sender, text, created_at FROM clan_messages WHERE clan_id=? AND id > ? ORDER BY id DESC LIMIT 200", cid, after)
    msgs.reverse()
    ppl = await people({m["sender"] for m in msgs})
    for m in msgs:
        p = ppl.get(m["sender"]) or {}
        m["name"], m["avatar"], m["frame"], m["color"] = p.get("name"), p.get("avatar"), p.get("frame"), p.get("color")
    return {"messages": msgs}


class MsgIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@router.post("/clans/{cid}/messages")
async def clan_send(cid: int, body: MsgIn, me=Me):
    if not (await my_clan_role(me["tg_id"], cid))[1]:
        raise HTTPException(403, "Чат только для бойцов клана")
    mid = await db.run("INSERT INTO clan_messages (clan_id, sender, text) VALUES (?,?,?)", cid, me["tg_id"], body.text.strip())
    return {"id": mid}


# ── боевой пропуск ───────────────────────────────────────────────────────

def season_end() -> datetime:
    now = datetime.now(MSK)
    last = calendar.monthrange(now.year, now.month)[1]
    return now.replace(day=last, hour=23, minute=59, second=59, microsecond=0)


def reward_out(kind: str, value) -> dict:
    out = {"kind": kind, "value": value}
    if kind == "item":
        out.update(name=C.ITEMS[value][0], item_kind=C.ITEMS[value][1], rarity=C.ITEMS[value][2])
    return out


async def pass_unlocked(me: dict) -> bool:
    return is_premium(me) or bool(await db.one("SELECT 1 FROM bp_pass WHERE tg_id=? AND season=?", me["tg_id"], season()))


@router.get("/pass")
async def pass_view(me=Me):
    uid, s = me["tg_id"], season()
    xp = await db.val("SELECT xp FROM bp_progress WHERE tg_id=? AND season=?", uid, s) or 0
    level = min(C.BP_LEVELS, xp // C.BP_XP_PER_LEVEL)
    claimed = {(r["level"], r["track"]) for r in await db.all_("SELECT level, track FROM bp_claims WHERE tg_id=? AND season=?", uid, s)}
    unlocked = await pass_unlocked(me)
    levels = [{"level": lv,
               "free": {**reward_out(*C.bp_reward(lv, "free")), "claimed": (lv, "free") in claimed},
               "premium": {**reward_out(*C.bp_reward(lv, "premium")), "claimed": (lv, "premium") in claimed}}
              for lv in range(1, C.BP_LEVELS + 1)]
    ready = sum(1 for l in levels if l["level"] <= level and (not l["free"]["claimed"] or (unlocked and not l["premium"]["claimed"])))
    end = season_end()
    return {"season": s, "season_name": end.strftime("%m.%Y"), "ends_at": end.strftime("%Y-%m-%dT%H:%M:%S+03:00"),
            "xp": xp, "level": level, "per_level": C.BP_XP_PER_LEVEL, "max": C.BP_LEVELS,
            "unlocked": unlocked, "stars": C.BP_STARS, "ready": ready, "levels": levels}


class ClaimIn(BaseModel):
    level: int = Field(0, ge=0, le=100)
    track: str = Field("free", pattern="^(free|premium|all)$")


@router.post("/pass/claim")
async def pass_claim(body: ClaimIn, me=Me):
    uid, s = me["tg_id"], season()
    xp = await db.val("SELECT xp FROM bp_progress WHERE tg_id=? AND season=?", uid, s) or 0
    level = min(C.BP_LEVELS, xp // C.BP_XP_PER_LEVEL)
    unlocked = await pass_unlocked(me)
    todo = []
    if body.track == "all":
        for lv in range(1, level + 1):
            todo.append((lv, "free"))
            if unlocked:
                todo.append((lv, "premium"))
    else:
        if body.level < 1 or body.level > level:
            raise HTTPException(409, "Уровень ещё не открыт")
        if body.track == "premium" and not unlocked:
            raise HTTPException(403, "Премиум-линейка закрыта")
        todo.append((body.level, body.track))
    got = []
    for lv, tr in todo:
        if await db.change("INSERT OR IGNORE INTO bp_claims (tg_id, season, level, track) VALUES (?,?,?,?)", uid, s, lv, tr):
            got.append(await grant(uid, *C.bp_reward(lv, tr), f"pass:{s}:{lv}:{tr}"))
    if not got and body.track != "all":
        raise HTTPException(409, "Уже забрано")
    return {"got": got}


# ── промокоды ────────────────────────────────────────────────────────────

class PromoUseIn(BaseModel):
    code: str = Field(min_length=3, max_length=32)


@router.post("/promo")
async def promo_use(body: PromoUseIn, me=Me):
    code = body.code.strip().upper()
    p = await db.one("SELECT * FROM promos WHERE code=?", code)
    if not p or (p["expires_at"] and parse_ts(p["expires_at"]) < utcnow()):
        raise HTTPException(404, "Такого промокода нет или он истёк")
    if p["uses"] >= p["max_uses"]:
        raise HTTPException(409, "Промокод закончился")
    if not await db.change("INSERT OR IGNORE INTO promo_uses (code, tg_id) VALUES (?,?)", code, me["tg_id"]):
        raise HTTPException(409, "Ты уже активировал этот промокод")
    if not await db.change("UPDATE promos SET uses = uses + 1 WHERE code=? AND uses < max_uses", code):
        await db.run("DELETE FROM promo_uses WHERE code=? AND tg_id=?", code, me["tg_id"])
        raise HTTPException(409, "Промокод закончился")
    got = await grant(me["tg_id"], p["kind"], p["value"], f"promo:{code}")
    return {"got": got}


# ── админка ──────────────────────────────────────────────────────────────

@router.get("/admin/overview")
async def admin_overview(me=Me):
    need_admin(me)
    v = db.val
    days = [(datetime.now(MSK).date() - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    dau = {r["day"]: r["n"] for r in await db.all_("SELECT day, COUNT(*) n FROM daily_active WHERE day >= ? GROUP BY day", days[0])}
    reg = {r["d"]: r["n"] for r in await db.all_(
        "SELECT date(created_at, '+3 hours') d, COUNT(*) n FROM users WHERE created_at >= datetime('now','-15 days') AND tg_id != 0 GROUP BY d")}
    econ = await db.all_("SELECT CASE WHEN instr(reason, ':') > 0 THEN substr(reason, 1, instr(reason, ':') - 1) ELSE reason END r, "
                         "SUM(amount) s, COUNT(*) n FROM transactions WHERE created_at > datetime('now','-7 days') GROUP BY r ORDER BY ABS(SUM(amount)) DESC LIMIT 10")
    games = await db.all_("SELECT game, COUNT(*) n FROM user_games GROUP BY game ORDER BY n DESC")
    return {
        "cards": {
            "users": await v("SELECT COUNT(*) FROM users WHERE tg_id != 0"),
            "online": await v("SELECT COUNT(*) FROM users WHERE last_seen > datetime('now','-5 minutes')"),
            "dau": dau.get(days[-1], 0),
            "wau": await v("SELECT COUNT(DISTINCT tg_id) FROM daily_active WHERE day >= ?", days[-7]),
            "new_today": reg.get(days[-1], 0),
            "premium": await v("SELECT COUNT(*) FROM users WHERE premium_until > datetime('now')"),
            "stars_30d": await v("SELECT COALESCE(SUM(stars),0) FROM payments WHERE created_at > datetime('now','-30 days')"),
            "nesso_total": await v("SELECT COALESCE(SUM(balance),0) FROM users"),
            "matches": await v("SELECT COUNT(*) FROM matches"),
            "clans": await v("SELECT COUNT(*) FROM clans"),
            "reports": await v("SELECT COUNT(DISTINCT to_id) FROM blocks WHERE reason NOT IN ('', 'unmatch') AND reason IS NOT NULL AND resolved=0"),
            "banned": await v("SELECT COUNT(*) FROM users WHERE banned=1"),
        },
        "dau": [{"day": d, "n": dau.get(d, 0)} for d in days],
        "reg": [{"day": d, "n": reg.get(d, 0)} for d in days],
        "economy": econ, "games": games,
    }


@router.get("/admin/users")
async def admin_users(q: str = "", filter: str = "", sort: str = "recent", me=Me):
    need_admin(me)
    where, args = "WHERE u.tg_id != 0", []
    if q:
        qs = q.strip().lstrip("@")
        where += " AND (CAST(u.tg_id AS TEXT) = ? OR u.username LIKE ? OR u.first_name LIKE ? OR p.nickname LIKE ?)"
        args += [qs, f"%{qs}%", f"%{qs}%", f"%{qs}%"]
    if filter == "banned":
        where += " AND u.banned=1"
    elif filter == "premium":
        where += " AND u.premium_until > datetime('now')"
    elif filter == "reported":
        where += " AND EXISTS (SELECT 1 FROM blocks b WHERE b.to_id=u.tg_id AND b.reason NOT IN ('','unmatch') AND b.resolved=0)"
    order = {"xp": "u.xp DESC", "balance": "u.balance DESC", "new": "u.created_at DESC"}.get(sort, "u.last_seen DESC")
    rows = await db.all_(f"SELECT u.tg_id FROM users u LEFT JOIN profiles p ON p.tg_id=u.tg_id {where} ORDER BY {order} LIMIT 50", *args)
    ppl = await people([r["tg_id"] for r in rows])
    extra = {r["tg_id"]: r for r in await db.all_(
        f"SELECT tg_id, balance, xp, banned, last_seen FROM users WHERE tg_id IN ({','.join('?' * len(rows)) or 'NULL'})",
        *[r["tg_id"] for r in rows])}
    return {"users": [{**ppl[r["tg_id"]], **extra.get(r["tg_id"], {})} for r in rows if r["tg_id"] in ppl]}


@router.get("/admin/users/{uid}")
async def admin_user(uid: int, me=Me):
    need_admin(me)
    u = await db.one("SELECT * FROM users WHERE tg_id=?", uid)
    if not u:
        raise HTTPException(404, "Нет такого игрока")
    card = (await people([uid]))[uid]
    reports = await db.all_("SELECT from_id, reason, created_at, resolved FROM blocks WHERE to_id=? AND reason NOT IN ('','unmatch') "
                            "ORDER BY created_at DESC LIMIT 30", uid)
    tx = await db.all_("SELECT amount, reason, created_at FROM transactions WHERE tg_id=? ORDER BY id DESC LIMIT 25", uid)
    pays = await db.all_("SELECT payload, stars, created_at FROM payments WHERE tg_id=? ORDER BY created_at DESC LIMIT 10", uid)
    stats = {
        "posts": await db.val("SELECT COUNT(*) FROM posts WHERE author=?", uid),
        "matches": await db.val("SELECT COUNT(*) FROM matches WHERE u1=? OR u2=?", uid, uid),
        "squads": await db.val("SELECT COUNT(*) FROM squads WHERE creator=?", uid),
        "messages": await db.val("SELECT COUNT(*) FROM match_messages WHERE sender=?", uid),
        "days_active": await db.val("SELECT COUNT(*) FROM daily_active WHERE tg_id=?", uid),
    }
    return {"card": card, "user": {k: u[k] for k in ("tg_id", "username", "first_name", "balance", "tickets", "xp", "streak",
                                                     "premium_until", "created_at", "last_seen", "banned", "ban_reason", "referrer")},
            "reports": reports, "transactions": tx, "payments": pays, "stats": stats}


class GrantIn(BaseModel):
    kind: str = Field(pattern="^(nesso|ticket|item|premium|xp)$")
    value: str = Field(min_length=1, max_length=40)
    note: str = Field("", max_length=200)
    notify_user: bool = True


@router.post("/admin/users/{uid}/grant")
async def admin_grant(uid: int, body: GrantIn, me=Me):
    need_admin(me)
    if not await db.one("SELECT 1 FROM users WHERE tg_id=?", uid):
        raise HTTPException(404, "Нет такого игрока")
    val = body.value.strip()
    if body.kind != "item":
        try:
            n = int(val)
        except ValueError:
            raise HTTPException(400, "Нужно число")
        if body.kind == "nesso" and n < 0:
            await db.run("UPDATE users SET balance = MAX(0, balance + ?) WHERE tg_id=?", n, uid)
            await db.run("INSERT INTO transactions (tg_id, amount, reason) VALUES (?,?,?)", uid, n, "admin")
            await admin_log(me["tg_id"], "take_nesso", uid, f"{n} {body.note}")
            return {"got": f"списано {-n} несо"}
        if n <= 0 or n > 1_000_000:
            raise HTTPException(400, "Странное число")
    got = await grant(uid, body.kind, val, "admin")
    await admin_log(me["tg_id"], f"grant_{body.kind}", uid, f"{val} {body.note}")
    if body.notify_user:
        notify.send(uid, f"🎁 Тебе подарок от администрации: <b>{_h(got)}</b>" + (f"\n{_h(body.note)}" if body.note else ""), "home")
    return {"got": got}


class BanIn(BaseModel):
    reason: str = Field("", max_length=200)


@router.post("/admin/users/{uid}/ban")
async def admin_ban(uid: int, body: BanIn, me=Me):
    need_admin(me)
    if uid in config.ADMIN_IDS:
        raise HTTPException(400, "Админа не забанить")
    await db.run("UPDATE users SET banned=1, ban_reason=? WHERE tg_id=?", body.reason.strip() or None, uid)
    await db.run("UPDATE profiles SET duet_visible=0 WHERE tg_id=?", uid)
    await db.run("DELETE FROM ready WHERE tg_id=?", uid)
    await db.run("UPDATE blocks SET resolved=1 WHERE to_id=?", uid)
    await admin_log(me["tg_id"], "ban", uid, body.reason)
    return {"ok": True}


@router.post("/admin/users/{uid}/unban")
async def admin_unban(uid: int, me=Me):
    need_admin(me)
    await db.run("UPDATE users SET banned=0, ban_reason=NULL WHERE tg_id=?", uid)
    await db.run("UPDATE profiles SET duet_visible=1 WHERE tg_id=?", uid)
    await admin_log(me["tg_id"], "unban", uid)
    return {"ok": True}


class WipeIn(BaseModel):
    what: str = Field(pattern="^(photos|about|posts|nick)$")


@router.post("/admin/users/{uid}/wipe")
async def admin_wipe(uid: int, body: WipeIn, me=Me):
    need_admin(me)
    if body.what == "photos":
        await db.run("UPDATE profiles SET photos='[]' WHERE tg_id=?", uid)
    elif body.what == "about":
        await db.run("UPDATE profiles SET about='' WHERE tg_id=?", uid)
    elif body.what == "nick":
        await db.run("UPDATE profiles SET nickname='Игрок' WHERE tg_id=?", uid)
    else:
        ids = [r["id"] for r in await db.all_("SELECT id FROM posts WHERE author=?", uid)]
        for pid in ids:
            await db.run("DELETE FROM comments WHERE post_id=?", pid)
            await db.run("DELETE FROM post_likes WHERE post_id=?", pid)
        await db.run("DELETE FROM posts WHERE author=?", uid)
    await admin_log(me["tg_id"], f"wipe_{body.what}", uid)
    return {"ok": True}


@router.get("/admin/reports")
async def admin_reports(me=Me):
    need_admin(me)
    rows = await db.all_("SELECT to_id, COUNT(*) n, GROUP_CONCAT(reason, ' · ') reasons, MAX(created_at) last FROM blocks "
                         "WHERE reason NOT IN ('','unmatch') AND reason IS NOT NULL AND resolved=0 GROUP BY to_id ORDER BY n DESC, last DESC LIMIT 50")
    ppl = await people([r["to_id"] for r in rows])
    return {"reports": [{**r, "user": ppl.get(r["to_id"])} for r in rows]}


@router.post("/admin/reports/{uid}/dismiss")
async def admin_dismiss(uid: int, me=Me):
    need_admin(me)
    await db.run("UPDATE blocks SET resolved=1 WHERE to_id=?", uid)
    await admin_log(me["tg_id"], "dismiss_reports", uid)
    return {"ok": True}


class BroadcastIn(BaseModel):
    text: str = Field(min_length=1, max_length=3500)
    game: str | None = None
    days: int = Field(30, ge=1, le=3650)
    test: bool = False


async def run_broadcast(bid: int, ids: list[int], text: str):
    sent = failed = 0
    kb = {"inline_keyboard": [[{"text": "Открыть Леру", "web_app": {"url": config.WEBAPP_URL}}]]} if config.WEBAPP_URL else None
    async with httpx.AsyncClient(timeout=10) as c:
        for i, uid in enumerate(ids):
            body = {"chat_id": uid, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
            if kb:
                body["reply_markup"] = kb
            try:
                r = await c.post(f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage", json=body)
                if r.status_code == 429:
                    await asyncio.sleep(int(r.json().get("parameters", {}).get("retry_after", 5)) + 1)
                    r = await c.post(f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage", json=body)
                if r.status_code == 200:
                    sent += 1
                else:
                    failed += 1
            except Exception:  # noqa: BLE001
                failed += 1
            if i % 20 == 19:
                await db.run("UPDATE broadcasts SET sent=?, failed=? WHERE id=?", sent, failed, bid)
            await asyncio.sleep(0.05)   # ~20 сообщений в секунду, лимит Telegram — 30
    await db.run("UPDATE broadcasts SET sent=?, failed=?, status='done' WHERE id=?", sent, failed, bid)


_bg: set = set()


@router.post("/admin/broadcast")
async def admin_broadcast(body: BroadcastIn, me=Me):
    need_admin(me)
    if not config.BOT_TOKEN:
        raise HTTPException(503, "BOT_TOKEN не задан")
    if body.test:
        ids = [me["tg_id"]]
    elif body.game in C.GAMES:
        ids = [r["tg_id"] for r in await db.all_(
            "SELECT u.tg_id FROM users u JOIN user_games g ON g.tg_id=u.tg_id WHERE g.game=? AND u.banned=0 AND u.tg_id != 0 "
            "AND u.last_seen > datetime('now', ?)", body.game, f"-{body.days} days")]
    else:
        ids = [r["tg_id"] for r in await db.all_(
            "SELECT tg_id FROM users WHERE banned=0 AND tg_id != 0 AND last_seen > datetime('now', ?)", f"-{body.days} days")]
    bid = await db.run("INSERT INTO broadcasts (text, filter, total, created_by) VALUES (?,?,?,?)", body.text,
                       json.dumps({"game": body.game, "days": body.days, "test": body.test}), len(ids), me["tg_id"])
    t = asyncio.create_task(run_broadcast(bid, ids, body.text))
    _bg.add(t)
    t.add_done_callback(_bg.discard)
    await admin_log(me["tg_id"], "broadcast", None, f"{len(ids)} получателей")
    return {"id": bid, "total": len(ids)}


@router.get("/admin/broadcasts")
async def admin_broadcasts(me=Me):
    need_admin(me)
    return {"broadcasts": await db.all_("SELECT * FROM broadcasts ORDER BY id DESC LIMIT 20")}


class PromoIn(BaseModel):
    code: str = Field("", max_length=32)
    kind: str = Field(pattern="^(nesso|ticket|item|premium)$")
    value: str = Field(min_length=1, max_length=40)
    max_uses: int = Field(100, ge=1, le=1_000_000)
    days: int = Field(30, ge=0, le=3650)


@router.get("/admin/promos")
async def admin_promos(me=Me):
    need_admin(me)
    return {"promos": await db.all_("SELECT * FROM promos ORDER BY created_at DESC LIMIT 100")}


@router.post("/admin/promos")
async def admin_promo_create(body: PromoIn, me=Me):
    need_admin(me)
    code = (body.code.strip() or "LERA" + secrets.token_hex(3)).upper()
    if not re.match(r"^[A-Z0-9_-]{3,32}$", code):
        raise HTTPException(400, "Код: латиница, цифры, - и _")
    if body.kind == "item" and body.value not in C.ITEMS:
        raise HTTPException(400, "Нет такого предмета")
    if body.kind != "item" and not body.value.isdigit():
        raise HTTPException(400, "Нужно число")
    exp = sqlts(utcnow() + timedelta(days=body.days)) if body.days else None
    if not await db.change("INSERT OR IGNORE INTO promos (code, kind, value, max_uses, expires_at, created_by) VALUES (?,?,?,?,?,?)",
                           code, body.kind, body.value, body.max_uses, exp, me["tg_id"]):
        raise HTTPException(409, "Такой код уже есть")
    await admin_log(me["tg_id"], "promo_create", None, f"{code} {body.kind}={body.value} ×{body.max_uses}")
    return {"code": code}


@router.delete("/admin/promos/{code}")
async def admin_promo_del(code: str, me=Me):
    need_admin(me)
    await db.run("DELETE FROM promos WHERE code=?", code.upper())
    return {"ok": True}


@router.get("/admin/log")
async def admin_log_view(me=Me):
    need_admin(me)
    rows = await db.all_("SELECT * FROM admin_log ORDER BY id DESC LIMIT 100")
    ppl = await people({r["target"] for r in rows if r["target"]} | {r["admin"] for r in rows})
    return {"log": [{**r, "admin_name": ppl.get(r["admin"], {}).get("name"), "target_name": ppl.get(r["target"], {}).get("name")} for r in rows]}


@router.delete("/admin/clans/{cid}")
async def admin_clan_del(cid: int, me=Me):
    need_admin(me)
    c = await clan_get(cid)
    await delete_clan(cid)
    await admin_log(me["tg_id"], "clan_delete", c["owner"], f"[{c['tag']}] {c['name']}")
    return {"ok": True}


@router.get("/admin/items")
async def admin_items(me=Me):
    need_admin(me)
    return {"items": [{"id": k, "name": v[0], "kind": v[1], "rarity": v[2]} for k, v in C.ITEMS.items()]}
