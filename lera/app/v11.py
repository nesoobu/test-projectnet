"""v11: портреты героев вместо букв.

Автозагрузка с открытых источников (раз при старте и по кнопке модератора), картинки сохраняются у нас
в data/uploads/heroes/<игра>/ и ужимаются до 256px. Ручная загрузка модератором (source='manual') не перезаписывается.
"""
import asyncio
import io
import json
import logging
import re

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import config, content as C, db
from .main import Me

log = logging.getLogger("lera.v11")
router = APIRouter(prefix="/api")
UA = "LeraBot/8.2 (Telegram mini app lera.lerarubot.ru; hero icons, cached locally)"
DIR = config.UPLOAD_DIR / "heroes"
_running: dict = {}

FANDOM = {"hok": "honor-of-kings", "mlbb": "mobile-legends", "genshin": "genshin-impact", "dota2": "dota2",
          "valorant": "valorant", "brawl": "brawlstars"}
DOTA_SLUG = {"Anti-Mage": "antimage", "Shadow Fiend": "nevermore", "Queen of Pain": "queenofpain", "Centaur Warrunner": "centaur",
             "Underlord": "abyssal_underlord", "Timbersaw": "shredder", "Io": "wisp", "Zeus": "zuus", "Magnus": "magnataur",
             "Necrophos": "necrolyte", "Outworld Destroyer": "obsidian_destroyer", "Treant Protector": "treant", "Vengeful Spirit": "vengefulspirit",
             "Wraith King": "skeleton_king", "Clockwerk": "rattletrap", "Lifestealer": "life_stealer", "Doom": "doom_bringer"}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


async def imgs(game: str) -> dict:
    return {r["hero"]: r["url"] for r in await db.all_("SELECT hero, url FROM hero_img WHERE game=?", game)}


def heroes_of(game: str) -> list[str]:
    return [h[0] for h in C.GAMES.get(game, {}).get("heroes") or [] if h[1] != "Карта"]


def shrink(data: bytes) -> bytes | None:
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        im.thumbnail((256, 256))
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA")
        out = io.BytesIO()
        im.save(out, "WEBP", quality=85)
        return out.getvalue()
    except Exception:  # noqa: BLE001
        return None


async def save(client, game: str, hero: str, url: str, source: str) -> bool:
    if await db.one("SELECT 1 FROM hero_img WHERE game=? AND hero=? AND source='manual'", game, hero):
        return False
    try:
        r = await client.get(url)
        r.raise_for_status()
    except Exception:  # noqa: BLE001
        return False
    data = shrink(r.content)
    if not data:
        return False
    (DIR / game).mkdir(parents=True, exist_ok=True)
    name = f"{slug(hero) or 'x'}.webp"
    (DIR / game / name).write_bytes(data)
    await db.run("INSERT INTO hero_img (game, hero, url, source) VALUES (?,?,?,?) ON CONFLICT(game, hero) DO UPDATE SET "
                 "url=excluded.url, source=excluded.source, updated_at=datetime('now')", game, hero, f"/uploads/heroes/{game}/{name}", source)
    return True


# ── источники: возвращают {герой: url картинки} ─────────────────────────

async def src_dota(client, names):
    return {n: f"https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/"
               f"{DOTA_SLUG.get(n) or re.sub(r'[^a-z0-9]+', '_', n.lower()).strip('_')}.png" for n in names}


async def src_valorant(client, names):
    r = await client.get("https://valorant-api.com/v1/agents", params={"isPlayableCharacter": "true"})
    by = {norm(a["displayName"]): a.get("displayIcon") for a in r.json().get("data", [])}
    return {n: by[norm(n)] for n in names if by.get(norm(n))}


async def src_brawl(client, names):
    r = await client.get("https://api.brawlapi.com/v1/brawlers")
    by = {}
    for b in r.json().get("list", []):
        by[norm(b.get("name"))] = b.get("imageUrl2") or b.get("imageUrl")
    return {n: by[norm(n)] for n in names if by.get(norm(n))}


async def src_fandom(client, game, names):
    """MediaWiki pageimages: главная картинка страницы героя на фан-вики."""
    out = {}
    api = f"https://{FANDOM[game]}.fandom.com/api.php"
    for i in range(0, len(names), 40):
        chunk = names[i:i + 40]
        r = await client.get(api, params={"action": "query", "titles": "|".join(chunk), "prop": "pageimages", "piprop": "thumbnail",
                                          "pithumbsize": 256, "redirects": 1, "format": "json"})
        q = r.json().get("query", {})
        back = {x["to"]: x["from"] for x in q.get("redirects", [])} | {x["to"]: x["from"] for x in q.get("normalized", [])}
        for p in q.get("pages", {}).values():
            th = (p.get("thumbnail") or {}).get("source")
            if not th:
                continue
            title = p.get("title", "")
            orig = back.get(title, title)
            orig = back.get(orig, orig)
            match = next((n for n in chunk if norm(n) in (norm(orig), norm(title))), None)
            if match:
                out[match] = th
        await asyncio.sleep(1)
    return out


SOURCES = {"dota2": [src_dota], "valorant": [src_valorant], "brawl": [src_brawl]}


async def import_game(game: str) -> dict:
    names = heroes_of(game)
    if not names:
        return {"game": game, "ok": 0, "total": 0}
    have = await db.all_("SELECT hero FROM hero_img WHERE game=?", game)
    todo = [n for n in names if n not in {h["hero"] for h in have}]
    got, errors = 0, []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": UA}) as client:
        for src in SOURCES.get(game, []) + ([lambda c, n: src_fandom(c, game, n)] if game in FANDOM else []):
            if not todo:
                break
            try:
                found = await src(client, todo)
            except Exception as e:  # noqa: BLE001
                errors.append(repr(e)[:120])
                continue
            for n, url in found.items():
                if url and await save(client, game, n, url, "auto"):
                    got += 1
                    todo.remove(n)
    log.info("hero icons %s: +%s, missing %s", game, got, len(todo))
    return {"game": game, "ok": len(names) - len(todo), "total": len(names), "added": got, "missing": todo[:20], "errors": errors}


async def import_all() -> list:
    res = []
    for g in C.GAMES:
        if heroes_of(g):
            res.append(await import_game(g))
    await db.run("INSERT INTO meta (key, val) VALUES ('hero_icons', ?) ON CONFLICT(key) DO UPDATE SET val=excluded.val",
                 json.dumps(res, ensure_ascii=False))
    return res


async def startup():
    """Один раз после обновления — подтянуть портреты в фоне."""
    await asyncio.sleep(20)
    if not await db.val("SELECT 1 FROM meta WHERE key='hero_icons'"):
        try:
            await import_all()
        except Exception:  # noqa: BLE001
            log.exception("hero icons import failed")


# ── API ──────────────────────────────────────────────────────────────────

@router.post("/admin/hero-icons")
async def run_import(me=Me):
    if not me.get("is_mod"):
        raise HTTPException(403, "Только для модераторов")
    if _running.get("t") and not _running["t"].done():
        raise HTTPException(409, "Уже загружаю — подожди пару минут")
    _running["t"] = asyncio.create_task(import_all())
    return {"ok": True}


@router.get("/admin/hero-icons")
async def import_status(me=Me):
    if not me.get("is_mod"):
        raise HTTPException(403, "Только для модераторов")
    v = await db.val("SELECT val FROM meta WHERE key='hero_icons'")
    return {"running": bool(_running.get("t") and not _running["t"].done()), "last": json.loads(v) if v else None,
            "count": await db.val("SELECT COUNT(*) FROM hero_img")}


class IconIn(BaseModel):
    game: str
    hero: str
    image: str = Field(pattern=r"^/uploads/[\w.-]+$")


@router.post("/wiki/icon")
async def set_icon(body: IconIn, me=Me):
    if not me.get("is_mod"):
        raise HTTPException(403, "Только для модераторов")
    if body.hero not in {h[0] for h in C.GAMES.get(body.game, {}).get("heroes") or []}:
        raise HTTPException(404, "Нет такого героя")
    src = config.UPLOAD_DIR / body.image.removeprefix("/uploads/")
    data = shrink(src.read_bytes()) if src.exists() else None
    if not data:
        raise HTTPException(400, "Не получилось прочитать картинку")
    (DIR / body.game).mkdir(parents=True, exist_ok=True)
    name = f"{slug(body.hero) or 'x'}-m.webp"
    (DIR / body.game / name).write_bytes(data)
    await db.run("INSERT INTO hero_img (game, hero, url, source) VALUES (?,?,?,'manual') ON CONFLICT(game, hero) DO UPDATE SET "
                 "url=excluded.url, source='manual', updated_at=datetime('now')", body.game, body.hero, f"/uploads/heroes/{body.game}/{name}")
    return {"ok": True}
