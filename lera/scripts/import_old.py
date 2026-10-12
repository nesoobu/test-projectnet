"""Перенос игроков из старой базы Леры (lera_bot.db) в новую.

    python -m scripts.import_old /root/ler/data/lera_bot.db

Безопасно: старую базу только читает, в новой ничего не перезаписывает (INSERT OR IGNORE).
Переносит: tg_id, username, баланс, аватар из Telegram, ник, возраст, город, пол, «о себе», видимость в дуэте.
"""
import asyncio
import json
import sqlite3
import sys

from app import db


def cols(con, table):
    try:
        return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    except sqlite3.DatabaseError:
        return set()


def pick(row, *names):
    for n in names:
        if n in row.keys() and row[n] not in (None, ""):
            return row[n]
    return None


async def main(path):
    old = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    old.row_factory = sqlite3.Row
    if "tg_id" not in cols(old, "users"):
        raise SystemExit("В старой базе нет таблицы users с tg_id")
    has_prof = "tg_id" in cols(old, "user_profiles")
    await db.connect()
    n_users = n_prof = 0
    for u in old.execute("SELECT * FROM users"):
        photo = pick(u, "tg_photo_url", "photo_url")
        photo = photo if isinstance(photo, str) and photo.startswith("https://") else None
        bal = pick(u, "balance", "nesso_balance")
        n_users += await db.change(
            "INSERT OR IGNORE INTO users (tg_id, username, first_name, photo_url, lang, balance) VALUES (?,?,?,?,?,?)",
            u["tg_id"], pick(u, "username"), pick(u, "first_name"), photo, pick(u, "lang"),
            max(300, int(bal)) if isinstance(bal, (int, float)) else 300)
    if has_prof:
        for p in old.execute("SELECT * FROM user_profiles"):
            age = pick(p, "age")
            gender = {"m": "m", "f": "f", "male": "m", "female": "f", "м": "m", "ж": "f"}.get(str(pick(p, "gender") or "").lower())
            photos = []
            try:
                photos = [x for x in json.loads(pick(p, "profile_photos") or "[]") if isinstance(x, str) and x.startswith("https://")]
            except ValueError:
                pass
            n_prof += await db.change(
                "INSERT OR IGNORE INTO profiles (tg_id, nickname, age, city, gender, about, photos, duet_visible) "
                "VALUES (?,?,?,?,?,?,?,?)",
                p["tg_id"], pick(p, "nickname"), int(age) if str(age or "").isdigit() and 14 <= int(age) <= 80 else None,
                pick(p, "city"), gender, pick(p, "duet_about") or "", json.dumps(photos[:4]),
                0 if pick(p, "duet_visible") in (0, "0") else 1)
    await db.close()
    print(f"Перенесено игроков: {n_users}, анкет: {n_prof}")
    print("Ранг и роли старая база не хранила — Лера попросит заполнить их при первом входе.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    asyncio.run(main(sys.argv[1]))
