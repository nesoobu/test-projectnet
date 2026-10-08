import os
import time

import aiosqlite

from . import defaults

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS screens (
    key TEXT PRIMARY KEY, title TEXT, text TEXT,
    media_type TEXT, media_id TEXT, builtin INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS buttons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screen TEXT, row INTEGER DEFAULT 0, pos INTEGER DEFAULT 0,
    emoji TEXT DEFAULT '', text TEXT, icon_id TEXT DEFAULT '', style TEXT DEFAULT '',
    action TEXT, value TEXT, enabled INTEGER DEFAULT 1
);
-- переводы: kind = screen (ref = key) | button (ref = id)
CREATE TABLE IF NOT EXISTS i18n (kind TEXT, ref TEXT, lang TEXT, text TEXT, PRIMARY KEY (kind, ref, lang));
CREATE TABLE IF NOT EXISTS packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT DEFAULT 'stars', stars INTEGER, price REAL,
    enabled INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
    balance REAL DEFAULT 0, ref_id INTEGER, ref_earned REAL DEFAULT 0, withdrawn REAL DEFAULT 0,
    promo TEXT, banned INTEGER DEFAULT 0, lang TEXT, source TEXT, created INTEGER, last_seen INTEGER
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT,
    stars INTEGER DEFAULT 0, recipient TEXT, recipient_name TEXT, amount REAL, discount REAL DEFAULT 0,
    promo TEXT, method TEXT, invoice_id TEXT, pay_url TEXT, pay_amount TEXT,
    status TEXT, attempts INTEGER DEFAULT 0, next_try INTEGER DEFAULT 0, reminded INTEGER DEFAULT 0,
    created INTEGER, updated INTEGER
);
CREATE TABLE IF NOT EXISTS promos (
    code TEXT PRIMARY KEY, discount REAL, uses_left INTEGER DEFAULT -1, used INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS promo_uses (code TEXT, user_id INTEGER, PRIMARY KEY (code, user_id));
CREATE TABLE IF NOT EXISTS withdrawals (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, details TEXT, status TEXT, created INTEGER
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER UNIQUE, user_id INTEGER, rating INTEGER,
    text TEXT, created INTEGER
);
CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY, role TEXT, name TEXT);
CREATE TABLE IF NOT EXISTS admin_log (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, action TEXT, ts INTEGER);
CREATE TABLE IF NOT EXISTS broadcasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, msg_id INTEGER, segment TEXT,
    send_at INTEGER, status TEXT, ok INTEGER DEFAULT 0, fail INTEGER DEFAULT 0, admin_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_users_ref ON users(ref_id);
"""

# Миграции для БД первой версии: (таблица, колонка, DDL)
MIGRATIONS = [
    ("users", "withdrawn", "REAL DEFAULT 0"), ("users", "lang", "TEXT"), ("users", "source", "TEXT"),
    ("users", "last_seen", "INTEGER"), ("packages", "kind", "TEXT DEFAULT 'stars'"),
    ("orders", "recipient_name", "TEXT"), ("orders", "pay_amount", "TEXT"),
    ("orders", "attempts", "INTEGER DEFAULT 0"), ("orders", "next_try", "INTEGER DEFAULT 0"),
    ("orders", "reminded", "INTEGER DEFAULT 0"),
]


class DB:
    def __init__(self):
        self.conn: aiosqlite.Connection | None = None
        self.path = ""

    async def connect(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self.conn = await aiosqlite.connect(path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.executescript(SCHEMA)
        await self._migrate()
        await self.conn.commit()
        await self._seed()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def one(self, q, *a):
        cur = await self.conn.execute(q, a)
        r = await cur.fetchone()
        return dict(r) if r else None

    async def all(self, q, *a):
        cur = await self.conn.execute(q, a)
        return [dict(r) for r in await cur.fetchall()]

    async def run(self, q, *a) -> aiosqlite.Cursor:
        cur = await self.conn.execute(q, a)
        await self.conn.commit()
        return cur

    async def _migrate(self):
        for table, col, ddl in MIGRATIONS:
            cols = {r["name"] for r in await self.all(f"PRAGMA table_info({table})")}
            if col not in cols:
                await self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")

    async def _seed(self):
        c = self.conn
        for k, (v, *_) in defaults.SETTINGS.items():
            await c.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (k, v))
        for k, (title, text) in defaults.SCREENS.items():
            await c.execute("INSERT OR IGNORE INTO screens (key, title, text, builtin) VALUES (?, ?, ?, 1)",
                            (k, title, text))
        for k, text in defaults.SCREENS_EN.items():
            await c.execute("INSERT OR IGNORE INTO i18n VALUES ('screen', ?, 'en', ?)", (k, text))
        for k, (emoji, text, en) in defaults.SYS_BUTTONS.items():
            b = await self.one("SELECT id FROM buttons WHERE screen='__sys__' AND value=?", k)
            if not b:
                cur = await c.execute("INSERT INTO buttons (screen, emoji, text, action, value) "
                                      "VALUES ('__sys__', ?, ?, 'sys', ?)", (emoji, text, k))
                await c.execute("INSERT OR IGNORE INTO i18n VALUES ('button', ?, 'en', ?)", (str(cur.lastrowid), en))
        if not await self.one("SELECT 1 FROM buttons WHERE screen != '__sys__'"):
            for s, row, pos, emoji, text, action, value, *rest in defaults.BUTTONS:
                cur = await c.execute(
                    "INSERT INTO buttons (screen, row, pos, emoji, text, action, value, enabled) VALUES (?,?,?,?,?,?,?,?)",
                    (s, row, pos, emoji, text, action, value, rest[0] if rest else 1))
                if text in defaults.BUTTONS_EN:
                    await c.execute("INSERT OR IGNORE INTO i18n VALUES ('button', ?, 'en', ?)",
                                    (str(cur.lastrowid), defaults.BUTTONS_EN[text]))
        for kind in ("stars", "premium"):
            if not await self.one("SELECT 1 FROM packages WHERE kind=?", kind):
                for k, qty, price in defaults.PACKAGES:
                    if k == kind:
                        await c.execute("INSERT INTO packages (kind, stars, price) VALUES (?, ?, ?)", (k, qty, price))
        await c.commit()

    # --- settings ---
    async def get(self, key: str) -> str:
        r = await self.one("SELECT value FROM settings WHERE key=?", key)
        if r is None:
            return defaults.SETTINGS.get(key, ("",))[0]
        return r["value"]

    async def get_float(self, key: str) -> float:
        try:
            return float((await self.get(key)).replace(",", "."))
        except ValueError:
            return 0.0

    async def get_int(self, key: str) -> int:
        return int(await self.get_float(key))

    async def get_bool(self, key: str) -> bool:
        return (await self.get(key)) == "1"

    async def set(self, key: str, value: str):
        await self.run("INSERT OR REPLACE INTO settings VALUES (?, ?)", key, value)

    async def languages(self) -> list[str]:
        langs = [x.strip() for x in (await self.get("languages")).split(",") if x.strip()]
        return langs or ["ru"]

    async def lang_names(self) -> dict[str, str]:
        names = {}
        for part in (await self.get("lang_names")).split(","):
            if ":" in part:
                k, v = part.split(":", 1)
                names[k.strip()] = v.strip()
        return names

    # --- переводы ---
    async def tr(self, kind: str, ref, lang: str) -> str | None:
        r = await self.one("SELECT text FROM i18n WHERE kind=? AND ref=? AND lang=?", kind, str(ref), lang)
        return r["text"] if r else None

    async def set_tr(self, kind: str, ref, lang: str, text: str):
        await self.run("INSERT OR REPLACE INTO i18n VALUES (?, ?, ?, ?)", kind, str(ref), lang, text)

    # --- users ---
    async def user(self, uid: int):
        return await self.one("SELECT * FROM users WHERE id=?", uid)

    async def upsert_user(self, uid: int, username: str | None, first_name: str | None):
        now = int(time.time())
        u = await self.user(uid)
        if u:
            await self.run("UPDATE users SET username=?, first_name=?, last_seen=? WHERE id=?",
                           username, first_name, now, uid)
            u.update(username=username, first_name=first_name, last_seen=now)
            return u, False
        await self.run("INSERT INTO users (id, username, first_name, created, last_seen) VALUES (?,?,?,?,?)",
                       uid, username, first_name, now, now)
        return await self.user(uid), True

    async def add_balance(self, uid: int, amount: float):
        await self.run("UPDATE users SET balance=ROUND(balance+?, 2) WHERE id=?", amount, uid)

    async def take_balance(self, uid: int, amount: float) -> bool:
        cur = await self.run("UPDATE users SET balance=ROUND(balance-?, 2) WHERE id=? AND balance>=?",
                             amount, uid, amount)
        return cur.rowcount > 0

    # --- orders ---
    async def order(self, oid: int):
        return await self.one("SELECT * FROM orders WHERE id=?", oid)

    async def set_status(self, oid: int, status: str, only_from: tuple[str, ...] | None = None) -> bool:
        """Атомарная смена статуса (защита от двойной выдачи)."""
        q = "UPDATE orders SET status=?, updated=? WHERE id=?"
        args = [status, int(time.time()), oid]
        if only_from:
            q += f" AND status IN ({','.join('?' * len(only_from))})"
            args += list(only_from)
        cur = await self.run(q, *args)
        return cur.rowcount > 0

    # --- admins ---
    async def admin_role(self, uid: int, env_admins: "set[int]") -> str | None:
        if uid in env_admins:
            return "owner"
        r = await self.one("SELECT role FROM admins WHERE id=?", uid)
        return r["role"] if r else None

    async def log_admin(self, uid: int, action: str):
        await self.run("INSERT INTO admin_log (admin_id, action, ts) VALUES (?, ?, ?)", uid, action[:300], int(time.time()))


db = DB()
