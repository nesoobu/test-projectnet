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
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, val TEXT);

CREATE TABLE IF NOT EXISTS user_games (
    tg_id INTEGER NOT NULL, game TEXT NOT NULL,
    rank INTEGER, roles TEXT NOT NULL DEFAULT '[]', heroes TEXT NOT NULL DEFAULT '[]',
    game_uid TEXT, pos INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tg_id, game)
);
CREATE INDEX IF NOT EXISTS ug_game ON user_games(game);

CREATE TABLE IF NOT EXISTS ready (
    tg_id INTEGER PRIMARY KEY, game TEXT NOT NULL, note TEXT, until TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS notify_log (tg_id INTEGER NOT NULL, kind TEXT NOT NULL, at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS nl_user ON notify_log(tg_id, kind, at);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER NOT NULL, to_id INTEGER NOT NULL, thumb INTEGER NOT NULL, tags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS rv_to ON reviews(to_id);

CREATE TABLE IF NOT EXISTS achievements (
    tg_id INTEGER NOT NULL, ach_id TEXT NOT NULL, at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (tg_id, ach_id)
);

CREATE TABLE IF NOT EXISTS guides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game TEXT NOT NULL, author INTEGER NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', views INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game TEXT NOT NULL, title TEXT NOT NULL, about TEXT, team_size INTEGER NOT NULL DEFAULT 1,
    max_teams INTEGER NOT NULL DEFAULT 8, prize INTEGER NOT NULL DEFAULT 0,
    starts_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'reg', winner INTEGER,
    created_by INTEGER, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS t_teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tid INTEGER NOT NULL, name TEXT NOT NULL, captain INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS t_members (
    team_id INTEGER NOT NULL, tid INTEGER NOT NULL, tg_id INTEGER NOT NULL, PRIMARY KEY (tid, tg_id)
);
CREATE TABLE IF NOT EXISTS t_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tid INTEGER NOT NULL, round INTEGER NOT NULL, pos INTEGER NOT NULL,
    team_a INTEGER, team_b INTEGER, winner INTEGER
);

CREATE TABLE IF NOT EXISTS polls (
    id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL, options TEXT NOT NULL,
    game TEXT, day TEXT NOT NULL, created_by INTEGER
);
CREATE TABLE IF NOT EXISTS poll_votes (poll_id INTEGER NOT NULL, tg_id INTEGER NOT NULL, option INTEGER NOT NULL,
    PRIMARY KEY (poll_id, tg_id));

CREATE TABLE IF NOT EXISTS leradle (
    tg_id INTEGER NOT NULL, day TEXT NOT NULL, guesses TEXT NOT NULL DEFAULT '[]', solved INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tg_id, day)
);

CREATE TABLE IF NOT EXISTS feeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL UNIQUE, game TEXT, title TEXT,
    seen TEXT NOT NULL DEFAULT '[]', active INTEGER NOT NULL DEFAULT 1, last_error TEXT
);
CREATE TABLE IF NOT EXISTS clans (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, tag TEXT NOT NULL UNIQUE, game TEXT, about TEXT,
    color TEXT NOT NULL DEFAULT '#d4ff3f', owner INTEGER NOT NULL, open INTEGER NOT NULL DEFAULT 1,
    xp INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS clan_members (
    clan_id INTEGER NOT NULL, tg_id INTEGER PRIMARY KEY, role TEXT NOT NULL DEFAULT 'member',
    xp INTEGER NOT NULL DEFAULT 0, joined_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS cm_clan ON clan_members(clan_id);
CREATE TABLE IF NOT EXISTS clan_requests (
    clan_id INTEGER NOT NULL, tg_id INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (clan_id, tg_id)
);
CREATE TABLE IF NOT EXISTS clan_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, clan_id INTEGER NOT NULL, sender INTEGER NOT NULL, text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS clm_clan ON clan_messages(clan_id, id);
CREATE TABLE IF NOT EXISTS clan_xp_log (clan_id INTEGER NOT NULL, amount INTEGER NOT NULL, at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS cxl ON clan_xp_log(at, clan_id);

CREATE TABLE IF NOT EXISTS bp_progress (tg_id INTEGER NOT NULL, season TEXT NOT NULL, xp INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tg_id, season));
CREATE TABLE IF NOT EXISTS bp_claims (tg_id INTEGER NOT NULL, season TEXT NOT NULL, level INTEGER NOT NULL, track TEXT NOT NULL,
    PRIMARY KEY (tg_id, season, level, track));
CREATE TABLE IF NOT EXISTS bp_pass (tg_id INTEGER NOT NULL, season TEXT NOT NULL, PRIMARY KEY (tg_id, season));

CREATE TABLE IF NOT EXISTS daily_active (day TEXT NOT NULL, tg_id INTEGER NOT NULL, PRIMARY KEY (day, tg_id));

CREATE TABLE IF NOT EXISTS promos (
    code TEXT PRIMARY KEY, kind TEXT NOT NULL, value TEXT NOT NULL, max_uses INTEGER NOT NULL DEFAULT 1,
    uses INTEGER NOT NULL DEFAULT 0, expires_at TEXT, created_by INTEGER, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS promo_uses (code TEXT NOT NULL, tg_id INTEGER NOT NULL, at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (code, tg_id));

CREATE TABLE IF NOT EXISTS broadcasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, filter TEXT, total INTEGER NOT NULL DEFAULT 0,
    sent INTEGER NOT NULL DEFAULT 0, failed INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'running',
    created_by INTEGER, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER NOT NULL, text TEXT NOT NULL, link TEXT,
    read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS notif_user ON notifications(tg_id, id);

CREATE TABLE IF NOT EXISTS friends (
    a INTEGER NOT NULL, b INTEGER NOT NULL, requester INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')), PRIMARY KEY (a, b)
);
CREATE INDEX IF NOT EXISTS friends_b ON friends(b);

CREATE TABLE IF NOT EXISTS mm_queue (
    tg_id INTEGER PRIMARY KEY, game TEXT NOT NULL, mode TEXT NOT NULL, size INTEGER NOT NULL, role TEXT,
    rank INTEGER, voice INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS leradle2 (
    tg_id INTEGER NOT NULL, day TEXT NOT NULL, game TEXT NOT NULL, guesses TEXT NOT NULL DEFAULT '[]',
    solved INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (tg_id, day, game)
);
CREATE TABLE IF NOT EXISTS wiki_tier (game TEXT NOT NULL, hero TEXT NOT NULL, tg_id INTEGER NOT NULL, tier INTEGER NOT NULL,
    PRIMARY KEY (game, hero, tg_id));
CREATE TABLE IF NOT EXISTS wiki_tips (
    id INTEGER PRIMARY KEY AUTOINCREMENT, game TEXT NOT NULL, hero TEXT NOT NULL, author INTEGER NOT NULL, text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS wiki_tips_h ON wiki_tips(game, hero);
CREATE TABLE IF NOT EXISTS wiki_tip_likes (tip_id INTEGER NOT NULL, tg_id INTEGER NOT NULL, PRIMARY KEY (tip_id, tg_id));
CREATE TABLE IF NOT EXISTS guide_likes (guide_id INTEGER NOT NULL, tg_id INTEGER NOT NULL, PRIMARY KEY (guide_id, tg_id));
CREATE TABLE IF NOT EXISTS t_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tid INTEGER NOT NULL, sender INTEGER NOT NULL, text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS admin_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, admin INTEGER NOT NULL, action TEXT NOT NULL, target INTEGER, details TEXT,
    at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Колонки, добавленные после первого релиза: (таблица, колонка, определение)
COLUMNS = [
    ("squads", "game", "TEXT NOT NULL DEFAULT 'hok'"),
    ("posts", "game", "TEXT"),
    ("posts", "kind", "TEXT NOT NULL DEFAULT 'user'"),
    ("posts", "link", "TEXT"),
    ("posts", "publish_at", "TEXT"),
    ("users", "leradle_streak", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "last_leradle", "TEXT"),
    ("users", "mute_ready", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "banned", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "ban_reason", "TEXT"),
    ("blocks", "resolved", "INTEGER NOT NULL DEFAULT 0"),
    ("tournaments", "best_of", "INTEGER NOT NULL DEFAULT 1"),
    ("tournaments", "entry_fee", "INTEGER NOT NULL DEFAULT 0"),
    ("tournaments", "checkin", "INTEGER NOT NULL DEFAULT 0"),
    ("tournaments", "auto_start", "INTEGER NOT NULL DEFAULT 0"),
    ("tournaments", "reminded", "INTEGER NOT NULL DEFAULT 0"),
    ("tournaments", "prize_split", "TEXT NOT NULL DEFAULT '[70,30]'"),
    ("tournaments", "rules", "TEXT"),
    ("t_teams", "checked_in", "INTEGER NOT NULL DEFAULT 0"),
    ("t_matches", "lobby", "TEXT"),
    ("t_matches", "score", "TEXT"),
    ("t_matches", "report_a", "INTEGER"),
    ("t_matches", "report_b", "INTEGER"),
    ("t_matches", "reported_at", "TEXT"),
    ("t_matches", "disputed", "INTEGER NOT NULL DEFAULT 0"),
    ("t_matches", "proof", "TEXT"),
    ("guides", "hero", "TEXT"),
    ("guides", "cat", "TEXT NOT NULL DEFAULT 'other'"),
]


async def migrate(conn):
    for table, col, ddl in COLUMNS:
        cur = await conn.execute(f"PRAGMA table_info({table})")
        if col not in {r[1] for r in await cur.fetchall()}:
            await conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    cur = await conn.execute("SELECT val FROM meta WHERE key='games_v1'")
    if not await cur.fetchone():
        # старые анкеты HoK → профиль игры
        await conn.execute(
            "INSERT OR IGNORE INTO user_games (tg_id, game, rank, roles, heroes) "
            "SELECT tg_id, 'hok', rank, roles, heroes FROM profiles WHERE rank IS NOT NULL OR roles != '[]'")
        await conn.execute("INSERT INTO meta (key, val) VALUES ('games_v1', '1')")
    cur = await conn.execute("SELECT val FROM meta WHERE key='leradle_v2'")
    if not await cur.fetchone():
        await conn.execute("INSERT OR IGNORE INTO leradle2 (tg_id, day, game, guesses, solved) "
                           "SELECT tg_id, day, 'hok', guesses, solved FROM leradle")
        await conn.execute("INSERT INTO meta (key, val) VALUES ('leradle_v2', '1')")
    # системный автор постов
    await conn.execute("INSERT OR IGNORE INTO users (tg_id, first_name, balance) VALUES (0, 'Лера', 0)")
    await conn.execute("INSERT OR IGNORE INTO profiles (tg_id, nickname, duet_visible) VALUES (0, 'Лера', 0)")
    await conn.commit()


_conn: aiosqlite.Connection | None = None


async def connect() -> aiosqlite.Connection:
    global _conn
    if _conn is None:
        Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _conn = await aiosqlite.connect(config.DB_PATH)
        _conn.row_factory = aiosqlite.Row
        await _conn.executescript(SCHEMA)
        await _conn.commit()
        await migrate(_conn)
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
