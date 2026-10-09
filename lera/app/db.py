import aiosqlite
from pathlib import Path

from . import config

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    username TEXT, first_name TEXT, photo_url TEXT, lang TEXT,
    balance INTEGER NOT NULL DEFAULT 300,
    tickets INTEGER NOT NULL DEFAULT 1,
    xp INTEGER NOT NULL DEFAULT 0,
    streak INTEGER NOT NULL DEFAULT 0,
    last_checkin TEXT,
    pity INTEGER NOT NULL DEFAULT 0,
    premium_until TEXT,
    referrer INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS profiles (
    tg_id INTEGER PRIMARY KEY REFERENCES users(tg_id),
    nickname TEXT, age INTEGER, city TEXT, gender TEXT, about TEXT,
    rank INTEGER, roles TEXT NOT NULL DEFAULT '[]', heroes TEXT NOT NULL DEFAULT '[]',
    play_times TEXT NOT NULL DEFAULT '[]', voice INTEGER NOT NULL DEFAULT 0,
    photos TEXT NOT NULL DEFAULT '[]', accent TEXT,
    duet_visible INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS swipes (
    from_id INTEGER NOT NULL, to_id INTEGER NOT NULL,
    action TEXT NOT NULL,            -- like | super | pass
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (from_id, to_id)
);
CREATE INDEX IF NOT EXISTS swipes_to ON swipes(to_id, action);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    u1 INTEGER NOT NULL, u2 INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (u1, u2)
);

CREATE TABLE IF NOT EXISTS match_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL REFERENCES matches(id),
    sender INTEGER NOT NULL, text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS mm_match ON match_messages(match_id, id);

CREATE TABLE IF NOT EXISTS match_reads (
    match_id INTEGER NOT NULL, tg_id INTEGER NOT NULL, last_id INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (match_id, tg_id)
);

CREATE TABLE IF NOT EXISTS blocks (
    from_id INTEGER NOT NULL, to_id INTEGER NOT NULL, reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (from_id, to_id)
);

CREATE TABLE IF NOT EXISTS squads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator INTEGER NOT NULL, title TEXT NOT NULL, mode TEXT NOT NULL,
    rank INTEGER, roles_needed TEXT NOT NULL DEFAULT '[]',
    max_players INTEGER NOT NULL DEFAULT 5, voice INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS squad_members (
    squad_id INTEGER NOT NULL REFERENCES squads(id), tg_id INTEGER NOT NULL,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (squad_id, tg_id)
);

CREATE TABLE IF NOT EXISTS squad_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    squad_id INTEGER NOT NULL REFERENCES squads(id),
    sender INTEGER NOT NULL, text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS sm_squad ON squad_messages(squad_id, id);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author INTEGER NOT NULL, text TEXT NOT NULL, image TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS post_likes (
    post_id INTEGER NOT NULL, tg_id INTEGER NOT NULL, PRIMARY KEY (post_id, tg_id)
);
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL REFERENCES posts(id),
    author INTEGER NOT NULL, text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS inventory (
    tg_id INTEGER NOT NULL, item_id TEXT NOT NULL,
    equipped INTEGER NOT NULL DEFAULT 0,
    obtained_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (tg_id, item_id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL, amount INTEGER NOT NULL, reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quest_progress (
    tg_id INTEGER NOT NULL, day TEXT NOT NULL, quest_id TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0, claimed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tg_id, day, quest_id)
);

CREATE TABLE IF NOT EXISTS payments (
    charge_id TEXT PRIMARY KEY, tg_id INTEGER NOT NULL, payload TEXT NOT NULL, stars INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_conn: aiosqlite.Connection | None = None


async def connect() -> aiosqlite.Connection:
    global _conn
    if _conn is None:
        Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _conn = await aiosqlite.connect(config.DB_PATH)
        _conn.row_factory = aiosqlite.Row
        await _conn.executescript(SCHEMA)
        await _conn.commit()
    return _conn


async def close():
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


async def one(sql: str, *args) -> dict | None:
    cur = await _conn.execute(sql, args)
    row = await cur.fetchone()
    return dict(row) if row else None


async def all_(sql: str, *args) -> list[dict]:
    cur = await _conn.execute(sql, args)
    return [dict(r) for r in await cur.fetchall()]


async def run(sql: str, *args) -> int:
    """Выполнить и закоммитить; вернуть lastrowid."""
    cur = await _conn.execute(sql, args)
    await _conn.commit()
    return cur.lastrowid


async def val(sql: str, *args):
    cur = await _conn.execute(sql, args)
    row = await cur.fetchone()
    return row[0] if row else None


async def change(sql: str, *args) -> int:
    """Выполнить и закоммитить; вернуть rowcount (для атомарных списаний)."""
    cur = await _conn.execute(sql, args)
    await _conn.commit()
    return cur.rowcount
