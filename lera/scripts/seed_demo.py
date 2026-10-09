"""Демо-данные для локальной разработки: python -m scripts.seed_demo  (потом открыть /?dev=1001)"""
import asyncio
import json
import random

from app import content as C, db

NAMES = [("Ника", "f"), ("Шторм", "m"), ("Мия", "f"), ("Kайto", "m"), ("Лиса", "f"), ("Гром", "m"), ("Ева", "f"),
         ("Сайлент", "m"), ("Кира", "f"), ("Дэн", "m"), ("Юки", "f"), ("Арчи", "m")]
CITIES = ["Москва", "Питер", "Казань", "Минск", "Алматы", None]
ABOUT = ["Саппорт с синдромом спасателя. Ищу стрелка, который не уходит в лес на 3-й минуте.",
         "Мейню лес, тащу ночами. Без токсика, с юмором.", "Апаю мифик, нужен стабильный дуо. Микро есть.",
         "Играю на фан, но проигрывать не люблю 😤", "Ищу пати на вечер, могу в любую роль."]


async def main():
    await db.connect()
    heroes = [h[0] for h in C.HEROES]
    for i, (name, g) in enumerate(NAMES):
        uid = 2000 + i
        await db.run("INSERT OR IGNORE INTO users (tg_id, first_name, xp, streak, last_checkin, last_seen) VALUES "
                      "(?,?,?,?,date('now'),datetime('now', ?))",
                      uid, name, random.randint(0, 900), random.randint(0, 12), f"-{random.choice([0, 1, 2, 90, 600])} minutes")
        await db.run("INSERT OR REPLACE INTO profiles (tg_id, nickname, age, city, gender, about, rank, roles, heroes, "
                      "play_times, voice) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      uid, name, random.randint(16, 29), random.choice(CITIES), g, random.choice(ABOUT),
                      random.randint(1, 7), json.dumps(random.sample(list(C.ROLES), random.randint(1, 2))),
                      json.dumps(random.sample(heroes, 3)), json.dumps(random.sample(list(C.PLAY_TIMES), 2)),
                      random.random() > .4)
        if random.random() > .5:
            item = random.choice([k for k, v in C.ITEMS.items() if v[1] == "frame" and k not in C.PREMIUM_ONLY])
            await db.run("INSERT OR IGNORE INTO inventory (tg_id, item_id, equipped) VALUES (?,?,1)", uid, item)
        if i % 3 == 0:
            await db.run("INSERT OR IGNORE INTO swipes (from_id, to_id, action) VALUES (?,1001,?)", uid, random.choice(["like", "super"]))
    for i, t in enumerate(["Кто на ночь в рейтинг? Нужен мид", "Лучший саппорт патча — спорим?", "Вчера взял MVP на Арли 😎"]):
        await db.run("INSERT INTO posts (author, text) VALUES (?,?)", 2000 + i, t)
    await db.run("INSERT INTO squads (creator, title, mode, rank, roles_needed, max_players, voice, expires_at) "
                 "VALUES (2001, 'Апаем мифик без токсиков', 'ranked', 4, '[\"mid\",\"roam\"]', 5, 1, datetime('now','+2 hours'))")
    sid = await db.val("SELECT MAX(id) FROM squads")
    for u in (2001, 2002):
        await db.run("INSERT OR IGNORE INTO squad_members (squad_id, tg_id) VALUES (?,?)", sid, u)
    await db.close()
    print("ok")


asyncio.run(main())
