"""v10: настоящая вики — статьи героев (модераторы пишут, игроки предлагают правки), тир-лист Леры, русские имена."""
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import config, db, notify
from .hero_ru import RU
from .main import Me, _h, add_balance, add_xp, people
from .v2 import need_admin, need_game

router = APIRouter(prefix="/api")
TIERS = ["S", "A", "B", "C", "D"]


def need_mod(me: dict):
    if not me.get("is_mod"):
        raise HTTPException(403, "Только для модераторов")


async def lera_tiers(game: str) -> dict:
    return {r["hero"]: TIERS[r["tier"]] for r in await db.all_("SELECT hero, tier FROM lera_tier WHERE game=?", game)}


async def ru_names(game: str) -> dict:
    out = dict(RU.get(game, {}))
    for r in await db.all_("SELECT hero, data FROM hero_info WHERE game=?", game):
        n = (json.loads(r["data"]) or {}).get("ru_name")
        if n:
            out[r["hero"]] = n
    return out


async def hero_article(game: str, hero: str) -> dict | None:
    r = await db.one("SELECT data, updated_by, updated_at FROM hero_info WHERE game=? AND hero=?", game, hero)
    if not r:
        return None
    a = json.loads(r["data"])
    a["updated_at"] = r["updated_at"]
    a["editor"] = (await people([r["updated_by"]])).get(r["updated_by"], {}).get("name") if r["updated_by"] else None
    return a


def need_hero(game: str, hero: str):
    g = need_game(game)
    if hero not in {h[0] for h in g.get("heroes") or []}:
        raise HTTPException(404, "Нет такого в вики")
    return g


# ── тир-лист Леры ────────────────────────────────────────────────────────

class LeraTierIn(BaseModel):
    game: str
    hero: str
    tier: int = Field(ge=-1, le=4)


@router.post("/wiki/lera-tier")
async def set_lera_tier(body: LeraTierIn, me=Me):
    need_mod(me)
    need_hero(body.game, body.hero)
    if body.tier < 0:
        await db.run("DELETE FROM lera_tier WHERE game=? AND hero=?", body.game, body.hero)
    else:
        await db.run("INSERT INTO lera_tier (game, hero, tier, updated_by) VALUES (?,?,?,?) ON CONFLICT(game, hero) DO UPDATE SET "
                     "tier=excluded.tier, updated_by=excluded.updated_by, updated_at=datetime('now')", body.game, body.hero, body.tier, me["tg_id"])
    return {"ok": True}


# ── статьи героев ────────────────────────────────────────────────────────

class Skill(BaseModel):
    name: str = Field("", max_length=60)
    desc: str = Field("", max_length=600)


class ArticleIn(BaseModel):
    game: str
    hero: str
    ru_name: str = Field("", max_length=40)
    epithet: str = Field("", max_length=80)
    difficulty: int = Field(0, ge=0, le=3)
    about: str = Field("", max_length=1500)
    skills: list[Skill] = Field(default_factory=list, max_length=6)
    build: str = Field("", max_length=800)
    combos: str = Field("", max_length=800)
    strong: str = Field("", max_length=500)
    weak: str = Field("", max_length=500)
    note: str = Field("", max_length=200)   # комментарий к правке (для модератора)


def clean(body: ArticleIn) -> dict:
    d = body.model_dump(exclude={"game", "hero", "note"})
    d["skills"] = [s for s in d["skills"] if s["name"].strip() or s["desc"].strip()]
    for k, v in list(d.items()):
        if isinstance(v, str):
            d[k] = v.strip()
    return d


@router.put("/wiki/article")
async def save_article(body: ArticleIn, me=Me):
    g = need_hero(body.game, body.hero)
    data = clean(body)
    if me.get("is_mod"):
        await db.run("INSERT INTO hero_info (game, hero, data, updated_by) VALUES (?,?,?,?) ON CONFLICT(game, hero) DO UPDATE SET "
                     "data=excluded.data, updated_by=excluded.updated_by, updated_at=datetime('now')",
                     body.game, body.hero, json.dumps(data, ensure_ascii=False), me["tg_id"])
        return {"status": "saved"}
    if await db.val("SELECT COUNT(*) FROM hero_edits WHERE tg_id=? AND status='pending'", me["tg_id"]) >= 5:
        raise HTTPException(429, "У тебя уже 5 правок на проверке — подожди модераторов")
    data["note"] = body.note.strip()
    await db.run("INSERT INTO hero_edits (game, hero, tg_id, data) VALUES (?,?,?,?)", body.game, body.hero, me["tg_id"],
                 json.dumps(data, ensure_ascii=False))
    mods = set(config.ADMIN_IDS) | {r["tg_id"] for r in await db.all_("SELECT tg_id FROM users WHERE is_mod=1")}
    for m in mods:
        notify.send(m, f"📝 Правка вики: {g['short']} · {_h(body.hero)}", "admin")
    return {"status": "pending"}


@router.get("/admin/hero-edits")
async def edits_list(me=Me):
    need_mod(me)
    rows = await db.all_("SELECT * FROM hero_edits WHERE status='pending' ORDER BY id LIMIT 50")
    ppl = await people({r["tg_id"] for r in rows})
    return {"items": [{**r, "data": json.loads(r["data"]), "user": ppl.get(r["tg_id"]),
                       "current": await hero_article(r["game"], r["hero"])} for r in rows]}


class ModIn(BaseModel):
    ok: bool


@router.post("/admin/hero-edits/{eid}")
async def edit_moderate(eid: int, body: ModIn, me=Me):
    need_mod(me)
    r = await db.one("SELECT * FROM hero_edits WHERE id=? AND status='pending'", eid)
    if not r:
        raise HTTPException(404, "Правка не найдена")
    await db.run("UPDATE hero_edits SET status=? WHERE id=?", "ok" if body.ok else "rejected", eid)
    if body.ok:
        data = json.loads(r["data"])
        data.pop("note", None)
        await db.run("INSERT INTO hero_info (game, hero, data, updated_by) VALUES (?,?,?,?) ON CONFLICT(game, hero) DO UPDATE SET "
                     "data=excluded.data, updated_by=excluded.updated_by, updated_at=datetime('now')",
                     r["game"], r["hero"], json.dumps(data, ensure_ascii=False), r["tg_id"])
        await add_balance(r["tg_id"], 50, "wiki_edit")
        await add_xp(r["tg_id"], 20)
        notify.send(r["tg_id"], f"📚 Твою правку статьи «{_h(r['hero'])}» приняли! +50 несо", "home")
    return {"ok": True}


# ── назначение модераторов ───────────────────────────────────────────────

class ModSetIn(BaseModel):
    on: bool


@router.post("/admin/users/{uid}/mod")
async def set_mod(uid: int, body: ModSetIn, me=Me):
    need_admin(me)
    await db.run("UPDATE users SET is_mod=? WHERE tg_id=?", int(body.on), uid)
    if body.on:
        notify.send(uid, "🛡 Ты теперь модератор вики Леры: тир-лист Леры, статьи героев и проверка правок.", "home")
    return {"ok": True}
