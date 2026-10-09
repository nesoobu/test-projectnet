"""v8: про-сцена — матчи с PandaScore/Liquipedia, прогнозы на несо, подписки на матчи и команды, обсуждение."""
import asyncio
import json
import logging
import time
from datetime import timedelta

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import config, db, notify
from . import esports as E
from .main import Me, _h, add_balance, add_xp, people, spend, sqlts, utcnow

log = logging.getLogger("lera.v8")
router = APIRouter(prefix="/api")

SCHEMA = """
CREATE TABLE IF NOT EXISTS pro_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ext TEXT NOT NULL UNIQUE, source TEXT NOT NULL, game TEXT, game_name TEXT,
    league TEXT, league_img TEXT, tournament TEXT, best_of INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL,
    begin_at TEXT, team_a TEXT NOT NULL, team_b TEXT NOT NULL, acr_a TEXT, acr_b TEXT, logo_a TEXT, logo_b TEXT,
    flag_a TEXT, flag_b TEXT, score_a INTEGER, score_b INTEGER, winner TEXT, streams TEXT NOT NULL DEFAULT '[]',
    seen_at TEXT, settled INTEGER NOT NULL DEFAULT 0, notified INTEGER NOT NULL DEFAULT 0, manual INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS pro_m_st ON pro_matches(status, begin_at);
CREATE INDEX IF NOT EXISTS pro_m_g ON pro_matches(game, begin_at);
CREATE TABLE IF NOT EXISTS pro_follow (tg_id INTEGER NOT NULL, match_id INTEGER NOT NULL, PRIMARY KEY (tg_id, match_id));
CREATE TABLE IF NOT EXISTS pro_team_follow (tg_id INTEGER NOT NULL, team TEXT NOT NULL, PRIMARY KEY (tg_id, team));
CREATE TABLE IF NOT EXISTS pro_preds (match_id INTEGER NOT NULL, tg_id INTEGER NOT NULL, pick TEXT NOT NULL, stake INTEGER NOT NULL,
    payout INTEGER, created_at TEXT NOT NULL DEFAULT (datetime('now')), PRIMARY KEY (match_id, tg_id));
CREATE TABLE IF NOT EXISTS pro_comments (id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER NOT NULL, tg_id INTEGER NOT NULL,
    text TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS pro_c_m ON pro_comments(match_id, id);
CREATE TABLE IF NOT EXISTS pro_sources (name TEXT PRIMARY KEY, ok_at TEXT, count INTEGER, err TEXT, err_at TEXT);
"""
FIELDS = ["source", "game", "game_name", "league", "league_img", "tournament", "best_of", "status", "begin_at", "team_a", "team_b",
          "acr_a", "acr_b", "logo_a", "logo_b", "flag_a", "flag_b", "score_a", "score_b", "winner"]
STATUS_RANK = {"upcoming": 0, "live": 1, "done": 2, "cancelled": 2}


async def init():
    await db._conn.executescript(SCHEMA)
    await db._conn.commit()


# ── загрузка ─────────────────────────────────────────────────────────────

async def upsert(rows: list[dict]) -> int:
    n = 0
    now = sqlts(utcnow())
    for r in rows:
        if not r.get("begin_at"):
            continue
        old = await db.one("SELECT * FROM pro_matches WHERE ext=?", r["id"])
        vals = [r.get(f) for f in FIELDS]
        streams = json.dumps(r.get("streams") or [], ensure_ascii=False)
        if not old:
            await db.run(f"INSERT INTO pro_matches (ext, {', '.join(FIELDS)}, streams, seen_at) VALUES (?{', ?' * len(FIELDS)}, ?, ?)",
                         r["id"], *vals, streams, now)
            n += 1
            continue
        if old["manual"]:
            continue
        # статус не откатываем назад (Liquipedia иногда отдаёт «скоро» уже начавшемуся матчу)
        if STATUS_RANK.get(r["status"], 0) < STATUS_RANK.get(old["status"], 0):
            r = {**r, "status": old["status"], "score_a": old["score_a"], "score_b": old["score_b"], "winner": old["winner"]}
            vals = [r.get(f) for f in FIELDS]
        await db.run(f"UPDATE pro_matches SET {', '.join(f + '=?' for f in FIELDS)}, streams=?, seen_at=? WHERE id=?",
                     *vals, streams, now, old["id"])
        if r["status"] != old["status"]:
            await on_status(old["id"])
        n += 1
    return n


async def source_ok(name: str, count: int):
    await db.run("INSERT INTO pro_sources (name, ok_at, count) VALUES (?,?,?) ON CONFLICT(name) DO UPDATE SET ok_at=excluded.ok_at, "
                 "count=excluded.count", name, sqlts(utcnow()), count)


async def source_err(name: str, err: str):
    await db.run("INSERT INTO pro_sources (name, err, err_at) VALUES (?,?,?) ON CONFLICT(name) DO UPDATE SET err=excluded.err, "
                 "err_at=excluded.err_at", name, err[:300], sqlts(utcnow()))


async def ps_games() -> set:
    rows = await db.all_("SELECT DISTINCT game FROM pro_matches WHERE source='pandascore' AND game IS NOT NULL "
                         "AND seen_at > datetime('now','-1 day')")
    return {r["game"] for r in rows}


async def refresh_pandascore(client):
    try:
        rows = await E.fetch_pandascore(client, config.PANDASCORE_TOKEN)
        await source_ok("pandascore", await upsert(rows))
    except Exception as e:  # noqa: BLE001
        log.warning("pandascore: %s", e)
        await source_err("pandascore", repr(e))


async def refresh_wiki(client, wiki: str):
    if E.LQ_WIKI.get(wiki) and E.LQ_WIKI[wiki] in await ps_games():
        return   # эту игру уже покрывает PandaScore — без дублей
    try:
        rows = await E.fetch_liquipedia(client, wiki)
        await source_ok(f"liquipedia:{wiki}", await upsert(rows))
    except Exception as e:  # noqa: BLE001
        log.warning("liquipedia %s: %s", wiki, e)
        await source_err(f"liquipedia:{wiki}", repr(e))


# ── события матча: старт, результат, расчёт прогнозов ───────────────────

async def watchers(m: dict) -> set:
    ids = {r["tg_id"] for r in await db.all_("SELECT tg_id FROM pro_follow WHERE match_id=?", m["id"])}
    ids |= {r["tg_id"] for r in await db.all_("SELECT tg_id FROM pro_team_follow WHERE team IN (?,?)", m["team_a"], m["team_b"])}
    ids |= {r["tg_id"] for r in await db.all_("SELECT tg_id FROM pro_preds WHERE match_id=?", m["id"])}
    return ids


async def on_status(mid: int):
    m = await db.one("SELECT * FROM pro_matches WHERE id=?", mid)
    if m["status"] in ("done", "cancelled") and not m["settled"]:
        await settle(m)


async def settle(m: dict):
    await db.run("UPDATE pro_matches SET settled=1 WHERE id=?", m["id"])
    preds = await db.all_("SELECT * FROM pro_preds WHERE match_id=?", m["id"])
    title = f"{_h(m['team_a'])} — {_h(m['team_b'])}"
    score = f" {m['score_a']}:{m['score_b']}" if m["score_a"] is not None else ""
    if m["status"] == "cancelled" or not m["winner"]:
        for p in preds:
            await add_balance(p["tg_id"], p["stake"], f"pro_refund:{m['id']}")
            await db.run("UPDATE pro_preds SET payout=? WHERE match_id=? AND tg_id=?", p["stake"], m["id"], p["tg_id"])
    else:
        win = [p for p in preds if p["pick"] == m["winner"]]
        lose_pool = sum(p["stake"] for p in preds if p["pick"] != m["winner"])
        win_pool = sum(p["stake"] for p in win)
        for p in preds:
            pay = 0
            if p["pick"] == m["winner"]:
                pay = p["stake"] + (lose_pool * p["stake"] // win_pool if win_pool else 0) + max(5, p["stake"] // 10)  # +10% бонус от Леры
                await add_balance(p["tg_id"], pay, f"pro_win:{m['id']}")
                await add_xp(p["tg_id"], 10)
            await db.run("UPDATE pro_preds SET payout=? WHERE match_id=? AND tg_id=?", pay, m["id"], p["tg_id"])
            notify.send(p["tg_id"], f"🔮 {title}{score}: " + (f"прогноз зашёл! +{pay} несо" if pay else "прогноз не зашёл"), f"x{m['id']}")
    wname = m["team_a"] if m["winner"] == "a" else m["team_b"] if m["winner"] == "b" else None
    predicted = {p["tg_id"] for p in preds}
    for uid in await watchers(m) - predicted:
        if wname:
            notify.send(uid, f"🏁 {title}{score} — победа <b>{_h(wname)}</b>", f"x{m['id']}")


async def tick_events():
    now = utcnow()
    soon = await db.all_("SELECT * FROM pro_matches WHERE notified=0 AND status IN ('upcoming','live') AND begin_at <= ? AND begin_at > ?",
                         sqlts(now + timedelta(minutes=10)), sqlts(now - timedelta(hours=1)))
    for m in soon:
        await db.run("UPDATE pro_matches SET notified=1 WHERE id=?", m["id"])
        for uid in await watchers(m):
            notify.send(uid, f"🔴 Скоро начало: <b>{_h(m['team_a'])}</b> vs <b>{_h(m['team_b'])}</b> · {_h(m['league'] or m['game_name'] or '')}",
                        f"x{m['id']}")
    # Liquipedia убирает сыгранные матчи со страницы: если «идёт» давно пропал — закрываем с последним счётом
    for m in await db.all_("SELECT * FROM pro_matches WHERE status='live' AND manual=0 AND seen_at < datetime('now','-3 hours')"):
        st = "done" if m["score_a"] is not None and m["score_a"] != m["score_b"] else "cancelled"
        win = ("a" if m["score_a"] > m["score_b"] else "b") if st == "done" else None
        await db.run("UPDATE pro_matches SET status=?, winner=? WHERE id=?", st, win, m["id"])
        await on_status(m["id"])
    for m in await db.all_("SELECT * FROM pro_matches WHERE status IN ('done','cancelled') AND settled=0"):
        await settle(m)


async def loop():
    await init()
    wikis = list(E.LQ_WIKI)
    last_ps, last_lq, i = 0.0, 0.0, 0
    async with httpx.AsyncClient(timeout=25, follow_redirects=True, headers={"User-Agent": E.UA}) as client:
        while True:
            try:
                now = time.monotonic()
                if config.PANDASCORE_TOKEN and now - last_ps > 180:
                    last_ps = now
                    await refresh_pandascore(client)
                if config.LIQUIPEDIA and now - last_lq > 120:   # одна вики раз в 2 мин → каждая игра раз в ~14 мин
                    last_lq = now
                    await refresh_wiki(client, wikis[i % len(wikis)])
                    i += 1
                await tick_events()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("v8 tick failed")
            await asyncio.sleep(30)


# ── API ──────────────────────────────────────────────────────────────────

def view(m: dict) -> dict:
    out = {k: m[k] for k in m if k not in ("seen_at", "settled", "notified", "ext")}
    out["streams"] = json.loads(m["streams"] or "[]")
    return out


@router.get("/pro")
async def pro_list(tab: str = "live", game: str = "all", me=Me):
    where, args, order = [], [], "begin_at"
    if tab == "live":
        where.append("status='live' AND begin_at > datetime('now','-12 hours')")
    elif tab == "past":
        where.append("status='done' AND begin_at > datetime('now','-14 days')"); order = "begin_at DESC"
    else:
        where.append("status='upcoming' AND begin_at > datetime('now','-2 hours') AND begin_at < datetime('now','+21 days')")
    gw, gargs = "", []
    if game == "other":
        gw = " AND game IS NULL"
    elif game == "mine":
        gw = " AND game IN (SELECT game FROM user_games WHERE tg_id=?)"; gargs = [me["tg_id"]]
    elif game == "teams":
        gw = " AND (team_a IN (SELECT team FROM pro_team_follow WHERE tg_id=?) OR team_b IN (SELECT team FROM pro_team_follow WHERE tg_id=?))"
        gargs = [me["tg_id"], me["tg_id"]]
    elif game != "all":
        gw = " AND game=?"; gargs = [game]
    rows = await db.all_(f"SELECT * FROM pro_matches WHERE {' AND '.join(where)}{gw} ORDER BY {order} LIMIT 200", *args, *gargs)
    ids = [r["id"] for r in rows]
    picks, follows = {}, set()
    if ids:
        q = ",".join("?" * len(ids))
        picks = {r["match_id"]: r for r in await db.all_(f"SELECT * FROM pro_preds WHERE tg_id=? AND match_id IN ({q})", me["tg_id"], *ids)}
        follows = {r["match_id"] for r in await db.all_(f"SELECT match_id FROM pro_follow WHERE tg_id=? AND match_id IN ({q})", me["tg_id"], *ids)}
    counts = {}
    for t, cond in (("live", "status='live' AND begin_at > datetime('now','-12 hours')"),
                    ("soon", "status='upcoming' AND begin_at > datetime('now','-2 hours') AND begin_at < datetime('now','+21 days')")):
        counts[t] = await db.val(f"SELECT COUNT(*) FROM pro_matches WHERE {cond}{gw}", *gargs)
    games = await db.all_("SELECT game, COUNT(*) n FROM pro_matches WHERE game IS NOT NULL AND begin_at > datetime('now','-14 days') "
                          "GROUP BY game ORDER BY n DESC")
    other = await db.val("SELECT COUNT(*) FROM pro_matches WHERE game IS NULL AND begin_at > datetime('now','-14 days')")
    my_teams = [r["team"] for r in await db.all_("SELECT team FROM pro_team_follow WHERE tg_id=?", me["tg_id"])]
    return {"matches": [{**view(r), "my_pick": picks.get(r["id"], {}).get("pick"), "followed": r["id"] in follows} for r in rows],
            "counts": counts, "games": [g["game"] for g in games], "other": bool(other), "my_teams": my_teams,
            "sources": await sources_short()}


async def sources_short() -> list:
    return [r["name"].split(":")[0] for r in await db.all_("SELECT name FROM pro_sources WHERE ok_at > datetime('now','-1 day')")]


async def get_m(mid: int) -> dict:
    m = await db.one("SELECT * FROM pro_matches WHERE id=?", mid)
    if not m:
        raise HTTPException(404, "Матч не найден")
    return m


@router.get("/pro/m/{mid}")
async def pro_match(mid: int, me=Me):
    m = await get_m(mid)
    uid = me["tg_id"]
    pool = {"a": 0, "b": 0, "na": 0, "nb": 0}
    for r in await db.all_("SELECT pick, SUM(stake) s, COUNT(*) n FROM pro_preds WHERE match_id=? GROUP BY pick", mid):
        pool[r["pick"]] = r["s"]; pool["n" + r["pick"]] = r["n"]
    my_teams = {r["team"] for r in await db.all_("SELECT team FROM pro_team_follow WHERE tg_id=?", uid)}
    h2h = await db.all_("SELECT id, begin_at, team_a, team_b, score_a, score_b, winner, league FROM pro_matches WHERE status='done' AND id<>? "
                        "AND ((team_a=? AND team_b=?) OR (team_a=? AND team_b=?)) ORDER BY begin_at DESC LIMIT 5",
                        mid, m["team_a"], m["team_b"], m["team_b"], m["team_a"])
    form = {}
    for side in ("a", "b"):
        t = m[f"team_{side}"]
        rs = await db.all_("SELECT team_a, winner FROM pro_matches WHERE status='done' AND winner IS NOT NULL AND id<>? "
                           "AND (team_a=? OR team_b=?) ORDER BY begin_at DESC LIMIT 5", mid, t, t)
        form[side] = ["W" if (r["winner"] == "a") == (r["team_a"] == t) else "L" for r in rs]
    return {**view(m), "pool": pool, "my": await db.one("SELECT pick, stake, payout FROM pro_preds WHERE match_id=? AND tg_id=?", mid, uid),
            "followed": bool(await db.one("SELECT 1 FROM pro_follow WHERE tg_id=? AND match_id=?", uid, mid)),
            "team_followed": {"a": m["team_a"] in my_teams, "b": m["team_b"] in my_teams},
            "can_predict": m["status"] == "upcoming" and m["begin_at"] > sqlts(utcnow()),
            "comments": await db.val("SELECT COUNT(*) FROM pro_comments WHERE match_id=?", mid), "h2h": h2h, "form": form}


@router.post("/pro/m/{mid}/follow")
async def pro_follow(mid: int, me=Me):
    await get_m(mid)
    if await db.change("INSERT OR IGNORE INTO pro_follow (tg_id, match_id) VALUES (?,?)", me["tg_id"], mid):
        return {"followed": True}
    await db.run("DELETE FROM pro_follow WHERE tg_id=? AND match_id=?", me["tg_id"], mid)
    return {"followed": False}


class TeamIn(BaseModel):
    team: str = Field(min_length=1, max_length=80)


@router.post("/pro/team")
async def team_follow(body: TeamIn, me=Me):
    if await db.change("INSERT OR IGNORE INTO pro_team_follow (tg_id, team) VALUES (?,?)", me["tg_id"], body.team):
        if await db.val("SELECT COUNT(*) FROM pro_team_follow WHERE tg_id=?", me["tg_id"]) > 30:
            await db.run("DELETE FROM pro_team_follow WHERE tg_id=? AND team=?", me["tg_id"], body.team)
            raise HTTPException(409, "Максимум 30 команд")
        return {"followed": True}
    await db.run("DELETE FROM pro_team_follow WHERE tg_id=? AND team=?", me["tg_id"], body.team)
    return {"followed": False}


class PredIn(BaseModel):
    pick: str = Field(pattern="^[ab]$")
    stake: int = Field(ge=10, le=1000)


@router.post("/pro/m/{mid}/predict")
async def pro_predict(mid: int, body: PredIn, me=Me):
    m = await get_m(mid)
    if m["status"] != "upcoming" or m["begin_at"] <= sqlts(utcnow()):
        raise HTTPException(409, "Матч уже начался — прогнозы закрыты")
    if await db.one("SELECT 1 FROM pro_preds WHERE match_id=? AND tg_id=?", mid, me["tg_id"]):
        raise HTTPException(409, "Ты уже сделал прогноз")
    await spend(me["tg_id"], body.stake, f"pro_bet:{mid}")
    await db.run("INSERT INTO pro_preds (match_id, tg_id, pick, stake) VALUES (?,?,?,?)", mid, me["tg_id"], body.pick, body.stake)
    await add_xp(me["tg_id"], 3)
    return {"ok": True}


class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@router.get("/pro/m/{mid}/comments")
async def pro_comments(mid: int, after: int = 0, me=Me):
    msgs = await db.all_("SELECT id, tg_id AS sender, text, created_at FROM pro_comments WHERE match_id=? AND id > ? ORDER BY id DESC LIMIT 200",
                         mid, after)
    msgs.reverse()
    ppl = await people({m["sender"] for m in msgs})
    for m in msgs:
        p = ppl.get(m["sender"]) or {}
        m["name"], m["avatar"], m["frame"], m["color"] = p.get("name"), p.get("avatar"), p.get("frame"), p.get("color")
    return {"messages": msgs}


@router.post("/pro/m/{mid}/comments")
async def pro_comment(mid: int, body: CommentIn, me=Me):
    await get_m(mid)
    if await db.val("SELECT COUNT(*) FROM pro_comments WHERE tg_id=? AND created_at > datetime('now','-1 minute')", me["tg_id"]) >= 6:
        raise HTTPException(429, "Помедленнее :)")
    cid = await db.run("INSERT INTO pro_comments (match_id, tg_id, text) VALUES (?,?,?)", mid, me["tg_id"], body.text.strip())
    return {"id": cid}


@router.get("/pro/top")
async def pro_top(me=Me):
    """Топ прогнозистов за 30 дней."""
    rows = await db.all_("SELECT tg_id, SUM(CASE WHEN payout > stake THEN 1 ELSE 0 END) wins, COUNT(*) n, SUM(COALESCE(payout,0) - stake) profit "
                         "FROM pro_preds WHERE payout IS NOT NULL AND created_at > datetime('now','-30 days') GROUP BY tg_id "
                         "HAVING n >= 3 ORDER BY profit DESC LIMIT 20")
    ppl = await people({r["tg_id"] for r in rows})
    return {"top": [{**r, "user": ppl.get(r["tg_id"])} for r in rows if r["tg_id"] in ppl]}


# ── админ ────────────────────────────────────────────────────────────────

@router.get("/admin/pro")
async def admin_pro(me=Me):
    from .v2 import need_admin
    need_admin(me)
    return {"sources": await db.all_("SELECT * FROM pro_sources ORDER BY name"), "pandascore": bool(config.PANDASCORE_TOKEN),
            "liquipedia": config.LIQUIPEDIA, "total": await db.val("SELECT COUNT(*) FROM pro_matches")}


class ManualIn(BaseModel):
    game: str | None = None
    league: str = Field(min_length=2, max_length=80)
    team_a: str = Field(min_length=1, max_length=60)
    team_b: str = Field(min_length=1, max_length=60)
    begin_at: str
    best_of: int = Field(1, ge=1, le=7)
    stream: str = Field("", max_length=300)


@router.post("/admin/pro")
async def admin_pro_add(body: ManualIn, me=Me):
    """Ручной матч — если источник не знает о нужной лиге (например, СНГ-квалы)."""
    from .v2 import msk_to_utc, need_admin
    need_admin(me)
    import secrets
    mid = await db.run("INSERT INTO pro_matches (ext, source, game, game_name, league, tournament, best_of, status, begin_at, team_a, team_b, "
                       "acr_a, acr_b, streams, seen_at, manual) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
                       f"man:{secrets.token_hex(6)}", "lera", body.game, "", body.league.strip(), body.league.strip(), body.best_of,
                       "upcoming", msk_to_utc(body.begin_at), body.team_a.strip(), body.team_b.strip(), E.acronym(body.team_a),
                       E.acronym(body.team_b), json.dumps([{"url": body.stream, "lang": "ru", "main": True}] if body.stream else []),
                       sqlts(utcnow()))
    return {"id": mid}


class ResultIn(BaseModel):
    score_a: int = Field(ge=0, le=9)
    score_b: int = Field(ge=0, le=9)
    status: str = Field("done", pattern="^(live|done|cancelled)$")


@router.post("/admin/pro/{mid}")
async def admin_pro_result(mid: int, body: ResultIn, me=Me):
    from .v2 import need_admin
    need_admin(me)
    await get_m(mid)
    win = None if body.status != "done" or body.score_a == body.score_b else ("a" if body.score_a > body.score_b else "b")
    await db.run("UPDATE pro_matches SET score_a=?, score_b=?, status=?, winner=?, manual=1 WHERE id=?",
                 body.score_a, body.score_b, body.status, win, mid)
    await on_status(mid)
    return {"ok": True}
