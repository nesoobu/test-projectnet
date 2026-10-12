"""v12: драфт-помощник, глобальный поиск, личный рекап недели."""
import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from . import content as C, db, notify
from .main import MSK, Me, people
from .v2 import need_game

log = logging.getLogger("lera.v12")
router = APIRouter(prefix="/api")
TIER_BONUS = {"S": 3, "A": 2, "B": 1, "C": 0, "D": -1}


# ── драфт-помощник ───────────────────────────────────────────────────────

@router.get("/wiki/draft")
async def draft(game: str, enemies: str = "", allies: str = "", me=Me):
    """Кого взять против выбранных врагов: контрпики игроков + тир Леры/игроков + закрытие ролей команды."""
    g = need_game(game)
    heroes = [h for h in g.get("heroes") or [] if h[1] != "Карта"]
    if not heroes:
        raise HTTPException(400, "Для этой игры драфта нет")
    names = {h[0]: h for h in heroes}
    en = [x for x in enemies.split("|") if x in names][:5]
    al = [x for x in allies.split("|") if x in names][:4]
    if not en and not al:
        raise HTTPException(400, "Выбери хотя бы одного героя")
    from .v2 import tier_map
    from .v10 import lera_tiers, ru_names
    from .v11 import imgs
    pt, lt, rn, im = await tier_map(game), await lera_tiers(game), await ru_names(game), await imgs(game)
    votes: dict = {}   # (hero, counter) -> голоса
    for r in await db.all_("SELECT hero, counter, COUNT(*) n FROM hero_counters WHERE game=? GROUP BY hero, counter", game):
        votes[(r["hero"], r["counter"])] = r["n"]
    taken_roles = {names[a][2] for a in al if names[a][2]}
    out = []
    for name, cls, lane in heroes:
        if name in en or name in al:
            continue
        score, why = 0.0, []
        for e in en:
            good = votes.get((e, name), 0)      # name контрит e
            bad = votes.get((name, e), 0)       # e контрит name
            if good:
                score += 2 * good
                why.append(f"контрит {rn.get(e, e)} ×{good}")
            if bad:
                score -= 2 * bad
                why.append(f"боится {rn.get(e, e)}")
        tier = lt.get(name) or (pt.get(name) or {}).get("tier")
        if tier:
            score += TIER_BONUS[tier]
            if tier in ("S", "A"):
                why.append(f"тир {tier}" + (" по Лере" if lt.get(name) else ""))
        if lane and al:
            if lane in taken_roles:
                score -= 2
            else:
                score += 1
                why.append(f"закрывает роль «{g['roles'].get(lane, lane)}»")
        out.append({"name": name, "ru": rn.get(name), "img": im.get(name), "cls": cls, "lane": lane, "tier": tier,
                    "score": round(score, 1), "why": why[:3]})
    out.sort(key=lambda x: -x["score"])
    data_votes = sum(votes.get((e, h), 0) for e in en for h in names)
    return {"picks": out[:12], "avoid": sorted([x for x in out if any(w.startswith("боится") for w in x["why"])],
                                               key=lambda x: x["score"])[:5], "counter_votes": data_votes}


# ── глобальный поиск ─────────────────────────────────────────────────────

@router.get("/search")
async def search(q: str, me=Me):
    q = q.strip()
    if len(q) < 2:
        return {"players": [], "heroes": [], "guides": [], "clans": [], "teams": []}
    like = f"%{q}%"
    ql = q.lower()
    ids = [r["tg_id"] for r in await db.all_(
        "SELECT p.tg_id FROM profiles p JOIN users u ON u.tg_id=p.tg_id WHERE u.banned=0 AND p.tg_id NOT IN (0, ?) "
        "AND (p.nickname LIKE ? OR u.username LIKE ?) ORDER BY u.last_seen DESC LIMIT 12", me["tg_id"], like, like)]
    ppl = await people(ids)
    from .v10 import ru_names
    from .v11 import imgs
    heroes = []
    for gk, g in C.GAMES.items():
        if not g.get("heroes") or len(heroes) >= 12:
            continue
        rn, im = await ru_names(gk), await imgs(gk)
        for n, cls, _ in g["heroes"]:
            ru = rn.get(n)
            if ql in n.lower() or (ru and ql in ru.lower()):
                heroes.append({"game": gk, "name": n, "ru": ru, "cls": cls, "img": im.get(n)})
    guides = await db.all_("SELECT id, game, title FROM guides WHERE status='approved' AND title LIKE ? ORDER BY views DESC LIMIT 8", like)
    clans = await db.all_("SELECT id, name, tag, color, game FROM clans WHERE name LIKE ? OR tag LIKE ? LIMIT 8", like, like)
    teams = [r["t"] for r in await db.all_(
        "SELECT t FROM (SELECT team_a t, begin_at FROM pro_matches UNION ALL SELECT team_b, begin_at FROM pro_matches) "
        "WHERE t LIKE ? GROUP BY t ORDER BY MAX(begin_at) DESC LIMIT 8", like)] if await db.one(
        "SELECT 1 FROM sqlite_master WHERE name='pro_matches'") else []
    return {"players": [ppl[i] for i in ids if i in ppl], "heroes": heroes[:12], "guides": guides, "clans": clans, "teams": teams}


# ── личный рекап недели ──────────────────────────────────────────────────

async def weekly_recap():
    key = "recap_" + datetime.now(MSK).strftime("%G-%V")
    if await db.one("SELECT 1 FROM meta WHERE key=?", key):
        return
    await db.run("INSERT INTO meta (key, val) VALUES (?, '1')", key)
    users = [r["tg_id"] for r in await db.all_(
        "SELECT DISTINCT tg_id FROM daily_active WHERE day >= date('now','-7 days') AND tg_id != 0")]
    for uid in users:
        v = lambda sql, *a: db.val(sql, *a)
        st = {
            "days": await v("SELECT COUNT(*) FROM daily_active WHERE tg_id=? AND day >= date('now','-7 days')", uid),
            "matches": await v("SELECT COUNT(*) FROM matches WHERE (u1=? OR u2=?) AND created_at > datetime('now','-7 days')", uid, uid),
            "squads": await v("SELECT COUNT(*) FROM squad_members WHERE tg_id=? AND joined_at > datetime('now','-7 days')", uid),
            "msgs": await v("SELECT COUNT(*) FROM match_messages WHERE sender=? AND created_at > datetime('now','-7 days')", uid),
            "nesso": await v("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE tg_id=? AND amount>0 AND created_at > datetime('now','-7 days')", uid),
            "likes": await v("SELECT COUNT(*) FROM swipes WHERE to_id=? AND action IN ('like','super') AND created_at > datetime('now','-7 days')", uid),
        }
        try:
            st["bets"] = await v("SELECT COUNT(*) FROM pro_preds WHERE tg_id=? AND payout > stake AND created_at > datetime('now','-7 days')", uid)
        except Exception:  # noqa: BLE001
            st["bets"] = 0
        lines = [f"📅 в Лере {st['days']} из 7 дней"]
        if st["likes"]:
            lines.append(f"💘 тебя лайкнули {st['likes']} " + ("раз" if st['likes'] % 10 in (0, 1, 5, 6, 7, 8, 9) or 11 <= st['likes'] % 100 <= 14 else "раза"))
        if st["matches"]:
            lines.append(f"🤝 новых мэтчей: {st['matches']}")
        if st["squads"]:
            lines.append(f"🎮 отрядов: {st['squads']}")
        if st["bets"]:
            lines.append(f"🔮 угаданных прогнозов: {st['bets']}")
        if st["nesso"]:
            lines.append(f"🪙 заработано несо: {st['nesso']}")
        tail = "Неделя была огонь — так держать!" if st["days"] >= 5 else "На этой неделе зайди почаще — в дуэте тебя ждут 😉"
        notify.send(uid, "🗓 <b>Твоя неделя в Лере</b>\n\n" + "\n".join(lines) + f"\n\n{tail}", "home")
        await asyncio.sleep(0.05)


async def loop():
    while True:
        try:
            now = datetime.now(MSK)
            if now.weekday() == 0 and now.hour >= 13:
                await weekly_recap()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("v12 tick failed")
        await asyncio.sleep(600)
