"""v6: турниры уровнем выше — чек-ин, автостарт, отчёты капитанов, споры, лобби, чат турнира."""
import asyncio
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import config, db, notify
from .main import Me, _h, people, sqlts, utcnow
from .realtime import hub
from .v2 import advance, my_team, need_admin, refund_fee, start_tournament, t_get

log = logging.getLogger("lera.v6")
router = APIRouter(prefix="/api")
AUTO_ACCEPT = timedelta(minutes=30)   # если соперник молчит — отчёт принимается сам
CHECKIN_WINDOW = timedelta(minutes=30)


def ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


async def t_chat_ids(tid: int) -> list[int]:
    ids = [r["tg_id"] for r in await db.all_("SELECT tg_id FROM t_members WHERE tid=?", tid)]
    return ids + [a for a in config.ADMIN_IDS if a not in ids]


async def team_ids(team: int | None) -> list[int]:
    if not team:
        return []
    return [r["tg_id"] for r in await db.all_("SELECT tg_id FROM t_members WHERE team_id=?", team)]


async def get_match(tid: int, mid: int) -> tuple[dict, dict]:
    t = await t_get(tid)
    m = await db.one("SELECT * FROM t_matches WHERE id=? AND tid=?", mid, tid)
    if not m or t["status"] != "live":
        raise HTTPException(404, "Матч не найден")
    if m["winner"]:
        raise HTTPException(409, "Матч уже сыгран")
    if not (m["team_a"] and m["team_b"]):
        raise HTTPException(409, "Соперник ещё не определён")
    return t, m


async def side(m: dict, uid: int) -> str | None:
    """'a' / 'b' — капитан какой команды в матче."""
    for s in ("a", "b"):
        if await db.val("SELECT captain FROM t_teams WHERE id=?", m[f"team_{s}"]) == uid:
            return s
    return None


async def close_match(t: dict, m: dict, winner: int, score: str = ""):
    await db.run("UPDATE t_matches SET disputed=0, score=COALESCE(NULLIF(?,''), score) WHERE id=?", score, m["id"])
    await advance(t, m, winner)
    from .v4 import settle_predictions
    await settle_predictions(t, m["id"], winner)
    hub.push(await t_chat_ids(t["id"]), {"type": "tour", "tid": t["id"]})


# ── чек-ин ───────────────────────────────────────────────────────────────

@router.post("/tournaments/{tid}/checkin")
async def checkin(tid: int, me=Me):
    t = await t_get(tid)
    team = await my_team(tid, me["tg_id"])
    if not team:
        raise HTTPException(403, "Ты не участвуешь")
    if t["status"] != "reg" or not t["checkin"]:
        raise HTTPException(409, "Чек-ин закрыт")
    if utcnow() < ts(t["starts_at"]) - CHECKIN_WINDOW:
        raise HTTPException(409, "Чек-ин откроется за 30 минут до старта")
    await db.run("UPDATE t_teams SET checked_in=1 WHERE id=?", team)
    return {"ok": True}


# ── результат матча от капитанов ─────────────────────────────────────────

class ReportIn(BaseModel):
    team: int
    score: str = Field("", max_length=12)
    proof: str = Field("", max_length=300)


@router.post("/tournaments/{tid}/matches/{mid}/report")
async def report(tid: int, mid: int, body: ReportIn, me=Me):
    t, m = await get_match(tid, mid)
    s = await side(m, me["tg_id"])
    if not s:
        raise HTTPException(403, "Результат отправляет капитан команды")
    if body.team not in (m["team_a"], m["team_b"]):
        raise HTTPException(400, "Эта команда не играет в матче")
    await db.run(f"UPDATE t_matches SET report_{s}=?, reported_at=?, score=COALESCE(NULLIF(?,''), score), "
                 "proof=COALESCE(NULLIF(?,''), proof) WHERE id=?", body.team, sqlts(utcnow()), body.score.strip(),
                 body.proof.strip(), mid)
    m = await db.one("SELECT * FROM t_matches WHERE id=?", mid)
    other = "b" if s == "a" else "a"
    names = {r["id"]: r["name"] for r in await db.all_("SELECT id, name FROM t_teams WHERE id IN (?,?)", m["team_a"], m["team_b"])}
    if m[f"report_{other}"] is None:
        cap = await db.val("SELECT captain FROM t_teams WHERE id=?", m[f"team_{other}"])
        notify.send(cap, f"📝 «{_h(t['title'])}»: соперник сообщил, что победил <b>{_h(names[body.team])}</b>. "
                         "Подтверди или оспорь — через 30 минут результат примется сам.", f"t{tid}")
        hub.push(await t_chat_ids(tid), {"type": "tour", "tid": tid})
        return {"status": "waiting"}
    if m["report_a"] == m["report_b"]:
        await close_match(t, m, m["report_a"], body.score.strip())
        return {"status": "done"}
    await db.run("UPDATE t_matches SET disputed=1 WHERE id=?", mid)
    for a in config.ADMIN_IDS:
        notify.send(a, f"⚖️ Спор в «{_h(t['title'])}»: {_h(names[m['team_a']])} vs {_h(names[m['team_b']])} — "
                       "оба капитана заявили победу. Реши в сетке.", f"t{tid}")
    for u in await team_ids(m["team_a"]) + await team_ids(m["team_b"]):
        notify.send(u, f"⚖️ «{_h(t['title'])}»: результаты не совпали — матч проверит админ.", f"t{tid}")
    hub.push(await t_chat_ids(tid), {"type": "tour", "tid": tid})
    return {"status": "disputed"}


# ── лобби ────────────────────────────────────────────────────────────────

class LobbyIn(BaseModel):
    code: str = Field(min_length=1, max_length=80)


@router.post("/tournaments/{tid}/matches/{mid}/lobby")
async def lobby(tid: int, mid: int, body: LobbyIn, me=Me):
    t, m = await get_match(tid, mid)
    if not me["is_admin"] and not await side(m, me["tg_id"]):
        raise HTTPException(403, "Код лобби задаёт капитан или админ")
    await db.run("UPDATE t_matches SET lobby=? WHERE id=?", body.code.strip(), mid)
    for u in await team_ids(m["team_a"]) + await team_ids(m["team_b"]):
        if u != me["tg_id"]:
            notify.send(u, f"🎮 «{_h(t['title'])}»: лобби готово — <code>{_h(body.code.strip())}</code>", f"t{tid}")
    hub.push(await t_chat_ids(tid), {"type": "tour", "tid": tid})
    return {"ok": True}


# ── чат турнира ──────────────────────────────────────────────────────────

class MsgIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


async def chat_access(tid: int, me: dict):
    await t_get(tid)
    if not me["is_admin"] and not await my_team(tid, me["tg_id"]):
        raise HTTPException(403, "Чат только для участников")


@router.get("/tournaments/{tid}/chat")
async def chat_get(tid: int, after: int = 0, me=Me):
    await chat_access(tid, me)
    msgs = await db.all_("SELECT id, sender, text, created_at FROM t_messages WHERE tid=? AND id > ? ORDER BY id DESC LIMIT 200", tid, after)
    msgs.reverse()
    ppl = await people({m["sender"] for m in msgs})
    for m in msgs:
        p = ppl.get(m["sender"]) or {}
        m["name"], m["avatar"], m["frame"], m["color"] = p.get("name"), p.get("avatar"), p.get("frame"), p.get("color")
        if m["sender"] in config.ADMIN_IDS:
            m["name"] = f"{m['name']} · орг"
    return {"messages": msgs}


@router.post("/tournaments/{tid}/chat")
async def chat_send(tid: int, body: MsgIn, me=Me):
    await chat_access(tid, me)
    mid = await db.run("INSERT INTO t_messages (tid, sender, text) VALUES (?,?,?)", tid, me["tg_id"], body.text.strip())
    hub.push(await t_chat_ids(tid), {"type": "msg", "chat": f"t{tid}", "id": mid})
    return {"id": mid}


# ── админ: споры ─────────────────────────────────────────────────────────

@router.get("/admin/disputes")
async def disputes(me=Me):
    need_admin(me)
    rows = await db.all_("SELECT m.*, t.title, t.game FROM t_matches m JOIN tournaments t ON t.id=m.tid "
                         "WHERE m.disputed=1 AND m.winner IS NULL AND t.status='live' ORDER BY m.id")
    names = {r["id"]: r["name"] for r in await db.all_("SELECT id, name FROM t_teams WHERE tid IN (SELECT tid FROM t_matches WHERE disputed=1)")}
    for r in rows:
        r["a_name"], r["b_name"] = names.get(r["team_a"], "?"), names.get(r["team_b"], "?")
    return {"disputes": rows}


# ── фон: напоминания, автостарт, автоприём отчётов ───────────────────────

async def tick():
    now = utcnow()
    for t in await db.all_("SELECT * FROM tournaments WHERE status='reg' AND reminded=0 AND starts_at <= ?",
                           sqlts(now + CHECKIN_WINDOW)):
        await db.run("UPDATE tournaments SET reminded=1 WHERE id=?", t["id"])
        text = f"⏰ «{_h(t['title'])}» стартует через 30 минут." + (" Открыт чек-ин — отметься, иначе снимут с турнира!" if t["checkin"] else "")
        for r in await db.all_("SELECT tg_id FROM t_members WHERE tid=?", t["id"]):
            notify.send(r["tg_id"], text, f"t{t['id']}")
    for t in await db.all_("SELECT * FROM tournaments WHERE status='reg' AND auto_start=1 AND starts_at <= ?", sqlts(now)):
        try:
            await start_tournament(t)
        except HTTPException:
            await refund_fee(t, [r["tg_id"] for r in await db.all_("SELECT tg_id FROM t_members WHERE tid=?", t["id"])])
            await db.run("UPDATE tournaments SET status='cancelled' WHERE id=?", t["id"])
            for r in await db.all_("SELECT tg_id FROM t_members WHERE tid=?", t["id"]):
                notify.send(r["tg_id"], f"😔 «{_h(t['title'])}» отменён — не набралось участников. Взнос вернули.", f"t{t['id']}")
    for m in await db.all_("SELECT * FROM t_matches WHERE winner IS NULL AND disputed=0 AND reported_at IS NOT NULL "
                           "AND (report_a IS NULL) != (report_b IS NULL) AND reported_at <= ?", sqlts(now - AUTO_ACCEPT)):
        t = await db.one("SELECT * FROM tournaments WHERE id=?", m["tid"])
        if t and t["status"] == "live":
            await close_match(t, m, m["report_a"] or m["report_b"])


async def loop():
    while True:
        try:
            await tick()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("v6 tick failed")
        await asyncio.sleep(30)
