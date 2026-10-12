"""v9: то, о чём просят на форумах LFG — подтверждённый ранг, надёжность (не пришёл), сбор на время,
голосовые в чатах, контрпики от игроков, наставники."""
import asyncio
import logging
import secrets

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from . import config, content as C, db, notify
from .main import Me, _h, add_balance, add_xp, people
from .v2 import need_admin, need_game

log = logging.getLogger("lera.v9")
router = APIRouter(prefix="/api")


# ── подтверждение ранга скрином ──────────────────────────────────────────

class VerifyIn(BaseModel):
    game: str
    image: str = Field(pattern=r"^/uploads/[\w.-]+$")


@router.post("/verify")
async def verify_request(body: VerifyIn, me=Me):
    g = need_game(body.game)
    ug = await db.one("SELECT rank, verified FROM user_games WHERE tg_id=? AND game=?", me["tg_id"], body.game)
    if not ug or ug["rank"] is None:
        raise HTTPException(400, "Сначала укажи ранг в профиле игры")
    if ug["verified"]:
        raise HTTPException(409, "Ранг уже подтверждён")
    if await db.one("SELECT 1 FROM rank_verify WHERE tg_id=? AND game=? AND status='pending'", me["tg_id"], body.game):
        raise HTTPException(409, "Заявка уже на проверке")
    await db.run("INSERT INTO rank_verify (tg_id, game, rank, image) VALUES (?,?,?,?)", me["tg_id"], body.game, ug["rank"], body.image)
    for a in config.ADMIN_IDS:
        notify.send(a, f"✅ Заявка на подтверждение ранга: {g['short']} · {_h(g['ranks'][ug['rank']])}", "admin")
    return {"ok": True}


@router.get("/verify")
async def verify_status(me=Me):
    rows = await db.all_("SELECT game, status FROM rank_verify WHERE tg_id=? ORDER BY id", me["tg_id"])
    return {"status": {r["game"]: r["status"] for r in rows}}


@router.get("/admin/verify")
async def verify_list(me=Me):
    need_admin(me)
    rows = await db.all_("SELECT * FROM rank_verify WHERE status='pending' ORDER BY id LIMIT 50")
    ppl = await people({r["tg_id"] for r in rows})
    return {"items": [{**r, "user": ppl.get(r["tg_id"]), "rank_name": C.GAMES[r["game"]]["ranks"][r["rank"]]
                       if r["game"] in C.GAMES and r["rank"] is not None and r["rank"] < len(C.GAMES[r["game"]]["ranks"]) else "?"}
                      for r in rows]}


class ModIn(BaseModel):
    ok: bool


@router.post("/admin/verify/{vid}")
async def verify_moderate(vid: int, body: ModIn, me=Me):
    need_admin(me)
    r = await db.one("SELECT * FROM rank_verify WHERE id=? AND status='pending'", vid)
    if not r:
        raise HTTPException(404, "Заявка не найдена")
    await db.run("UPDATE rank_verify SET status=? WHERE id=?", "ok" if body.ok else "rejected", vid)
    g = C.GAMES.get(r["game"], {"short": r["game"]})
    if body.ok:
        await db.run("UPDATE user_games SET verified=1 WHERE tg_id=? AND game=? AND rank IS ?", r["tg_id"], r["game"], r["rank"])
        await add_balance(r["tg_id"], 50, "verify")
        notify.send(r["tg_id"], f"✅ Ранг в {g['short']} подтверждён — у тебя галочка в анкете. +50 несо", "home")
    else:
        notify.send(r["tg_id"], f"Ранг в {g['short']} не подтвердили: на скрине не видно ник и ранг. Попробуй ещё раз.", "home")
    return {"ok": True}


# ── контрпики от игроков ─────────────────────────────────────────────────

def hero_names(game: str) -> set:
    return {h[0] for h in need_game(game).get("heroes") or []}


@router.get("/wiki/counters")
async def counters(game: str, hero: str, me=Me):
    names = hero_names(game)
    if hero not in names:
        raise HTTPException(404, "Нет такого героя")
    q = ("SELECT {col} AS name, COUNT(*) n, MAX(tg_id=?) mine FROM hero_counters WHERE game=? AND {key}=? "
         "GROUP BY {col} ORDER BY n DESC LIMIT 8")
    return {"countered_by": await db.all_(q.format(col="counter", key="hero"), me["tg_id"], game, hero),
            "counters": await db.all_(q.format(col="hero", key="counter"), me["tg_id"], game, hero)}


class CounterIn(BaseModel):
    game: str
    hero: str
    counter: str


@router.post("/wiki/counters")
async def counter_vote(body: CounterIn, me=Me):
    names = hero_names(body.game)
    if body.hero not in names or body.counter not in names or body.hero == body.counter:
        raise HTTPException(400, "Выбери двух разных героев")
    if await db.change("INSERT OR IGNORE INTO hero_counters (game, hero, counter, tg_id) VALUES (?,?,?,?)",
                       body.game, body.hero, body.counter, me["tg_id"]):
        await add_xp(me["tg_id"], 1)
        return {"voted": True}
    await db.run("DELETE FROM hero_counters WHERE game=? AND hero=? AND counter=? AND tg_id=?", body.game, body.hero, body.counter, me["tg_id"])
    return {"voted": False}


# ── голосовые сообщения ──────────────────────────────────────────────────

VOICE_MAGIC = {b"\x1a\x45\xdf\xa3": ".webm", b"OggS": ".ogg"}


@router.post("/upload/voice")
async def upload_voice(file: UploadFile = File(...), me=Me):
    data = await file.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, "Голосовое длиннее минуты")
    ext = next((e for m, e in VOICE_MAGIC.items() if data.startswith(m)), None)
    if not ext and data[4:8] == b"ftyp":   # iOS пишет mp4/m4a
        ext = ".m4a"
    if not ext:
        raise HTTPException(415, "Неизвестный формат аудио")
    name = f"v{me['tg_id']}_{secrets.token_hex(8)}{ext}"
    (config.UPLOAD_DIR / name).write_bytes(data)
    return {"url": f"/uploads/{name}"}


# ── фон: сбор на время и «как сыграли?» ─────────────────────────────────

async def tick():
    # за 15 минут до сбора — напоминание всем в отряде
    for s in await db.all_("SELECT * FROM squads WHERE start_at IS NOT NULL AND reminded=0 AND status IN ('open','full') "
                           "AND start_at <= datetime('now','+15 minutes')"):
        await db.run("UPDATE squads SET reminded=1 WHERE id=?", s["id"])
        for m in await db.all_("SELECT tg_id FROM squad_members WHERE squad_id=?", s["id"]):
            notify.send(m["tg_id"], f"⏰ Через 15 минут сбор отряда «{_h(s['title'])}». Заходи в чат!", f"s{s['id']}")
    # через ~1.5 часа после старта отряда — попросить оценить тиммейтов (так считается надёжность)
    for s in await db.all_("SELECT * FROM squads WHERE rate_prompted=0 AND "
                           "COALESCE(start_at, created_at) <= datetime('now','-90 minutes') AND "
                           "COALESCE(start_at, created_at) > datetime('now','-1 day')"):
        await db.run("UPDATE squads SET rate_prompted=1 WHERE id=?", s["id"])
        ids = [m["tg_id"] for m in await db.all_("SELECT tg_id FROM squad_members WHERE squad_id=?", s["id"])]
        if len(ids) < 2:
            continue
        for uid in ids:
            notify.send(uid, f"🎮 Как сыграли с отрядом «{_h(s['title'])}»? Оцени тиммейтов — кто-то не пришёл? "
                             "Так в Лере считается надёжность.", "rate")


async def loop():
    while True:
        try:
            await tick()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("v9 tick failed")
        await asyncio.sleep(60)
