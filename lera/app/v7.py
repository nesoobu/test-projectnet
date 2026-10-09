"""v7: вики — страница героя, тир-лист игроков, советы, лайки гайдов."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import db, wiki_content as W
from .main import Me, add_xp, people
from .v2 import guide_rows, need_game, tier_map

router = APIRouter(prefix="/api")


def need_hero(game: str, name: str) -> tuple:
    g = need_game(game)
    h = next((h for h in g.get("heroes") or [] if h[0] == name), None)
    if not h:
        raise HTTPException(404, "Нет такого в вики")
    return g, h


@router.get("/wiki/hero")
async def hero(game: str, name: str, me=Me):
    g, h = need_hero(game, name)
    uid = me["tg_id"]
    dist = [0] * 5
    for r in await db.all_("SELECT tier, COUNT(*) n FROM wiki_tier WHERE game=? AND hero=? GROUP BY tier", game, name):
        dist[r["tier"]] = r["n"]
    t = (await tier_map(game)).get(name, {"tier": None, "score": None, "votes": 0})
    tips = await db.all_("SELECT t.id, t.author, t.text, t.created_at, "
                         "(SELECT COUNT(*) FROM wiki_tip_likes l WHERE l.tip_id=t.id) AS likes, "
                         "EXISTS(SELECT 1 FROM wiki_tip_likes l WHERE l.tip_id=t.id AND l.tg_id=?) AS liked "
                         "FROM wiki_tips t WHERE t.game=? AND t.hero=? ORDER BY likes DESC, t.id DESC LIMIT 50", uid, game, name)
    ppl = await people({x["author"] for x in tips})
    mains_ids = [r["tg_id"] for r in await db.all_(
        "SELECT ug.tg_id FROM user_games ug JOIN users u ON u.tg_id=ug.tg_id WHERE ug.game=? AND ug.heroes LIKE ? "
        "AND u.banned=0 ORDER BY u.last_seen DESC LIMIT 12", game, f'%"{name}"%')]
    mp = await people(mains_ids, game)
    mains = sorted([mp[i] for i in mains_ids if i in mp], key=lambda p: not p.get("online"))
    info = W.WIKI.get(game, {})
    return {"name": h[0], "cls": h[1], "lane": h[2], "lane_name": g["roles"].get(h[2]) if h[2] else None,
            "role_desc": info.get("roles", {}).get(h[2], "") if h[2] else "", **t, "dist": dist,
            "my_tier": await db.val("SELECT tier FROM wiki_tier WHERE game=? AND hero=? AND tg_id=?", game, name, uid),
            "tips": [{**x, "author": ppl.get(x["author"]), "liked": bool(x["liked"]), "mine": x["author"] == uid} for x in tips],
            "guides": await guide_rows(uid, "g.game=? AND g.hero=?", game, name),
            "mains": mains, "mains_total": await db.val("SELECT COUNT(*) FROM user_games WHERE game=? AND heroes LIKE ?", game, f'%"{name}"%'),
            "similar": [x[0] for x in g["heroes"] if x[1] == h[1] and x[0] != name][:10]}


class TierIn(BaseModel):
    game: str
    hero: str
    tier: int = Field(ge=-1, le=4)


@router.post("/wiki/tier")
async def vote_tier(body: TierIn, me=Me):
    need_hero(body.game, body.hero)
    if body.tier < 0:
        await db.run("DELETE FROM wiki_tier WHERE game=? AND hero=? AND tg_id=?", body.game, body.hero, me["tg_id"])
    else:
        new = await db.change("INSERT OR IGNORE INTO wiki_tier (game, hero, tg_id, tier) VALUES (?,?,?,?)",
                              body.game, body.hero, me["tg_id"], body.tier)
        if new:
            await add_xp(me["tg_id"], 1)
        else:
            await db.run("UPDATE wiki_tier SET tier=? WHERE game=? AND hero=? AND tg_id=?", body.tier, body.game, body.hero, me["tg_id"])
    return {"ok": True}


class TipIn(BaseModel):
    game: str
    hero: str
    text: str = Field(min_length=8, max_length=280)


@router.post("/wiki/tips")
async def tip_add(body: TipIn, me=Me):
    need_hero(body.game, body.hero)
    if await db.val("SELECT COUNT(*) FROM wiki_tips WHERE author=? AND created_at > datetime('now','-1 day')", me["tg_id"]) >= 10:
        raise HTTPException(429, "Хватит на сегодня — максимум 10 советов в день")
    tid = await db.run("INSERT INTO wiki_tips (game, hero, author, text) VALUES (?,?,?,?)",
                       body.game, body.hero, me["tg_id"], " ".join(body.text.split()))
    await add_xp(me["tg_id"], 3)
    return {"id": tid}


@router.post("/wiki/tips/{tid}/like")
async def tip_like(tid: int, me=Me):
    t = await db.one("SELECT author FROM wiki_tips WHERE id=?", tid)
    if not t:
        raise HTTPException(404, "Совет не найден")
    if t["author"] == me["tg_id"]:
        raise HTTPException(409, "Свой совет лайкать нельзя")
    if not await db.change("INSERT OR IGNORE INTO wiki_tip_likes (tip_id, tg_id) VALUES (?,?)", tid, me["tg_id"]):
        await db.run("DELETE FROM wiki_tip_likes WHERE tip_id=? AND tg_id=?", tid, me["tg_id"])
        return {"liked": False}
    await add_xp(t["author"], 2)
    return {"liked": True}


@router.delete("/wiki/tips/{tid}")
async def tip_del(tid: int, me=Me):
    t = await db.one("SELECT author FROM wiki_tips WHERE id=?", tid)
    if not t:
        raise HTTPException(404, "Совет не найден")
    if t["author"] != me["tg_id"] and not me["is_admin"]:
        raise HTTPException(403, "Не твой совет")
    await db.run("DELETE FROM wiki_tip_likes WHERE tip_id=?", tid)
    await db.run("DELETE FROM wiki_tips WHERE id=?", tid)
    return {"ok": True}


@router.post("/wiki/guides/{gid}/like")
async def guide_like(gid: int, me=Me):
    g = await db.one("SELECT author FROM guides WHERE id=? AND status='approved'", gid)
    if not g:
        raise HTTPException(404, "Гайд не найден")
    if not await db.change("INSERT OR IGNORE INTO guide_likes (guide_id, tg_id) VALUES (?,?)", gid, me["tg_id"]):
        await db.run("DELETE FROM guide_likes WHERE guide_id=? AND tg_id=?", gid, me["tg_id"])
        return {"liked": False}
    if g["author"] != me["tg_id"]:
        await add_xp(g["author"], 2)
    return {"liked": True}
