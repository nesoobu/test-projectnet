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
CREATE TABLE IF NOT EXISTS packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, stars INTEGER, price REAL,
    enabled INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
    balance REAL DEFAULT 0, ref_id INTEGER, ref_earned REAL DEFAULT 0,
    promo TEXT, banned INTEGER DEFAULT 0, created INTEGER
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT,
    stars INTEGER DEFAULT 0, recipient TEXT, amount REAL, discount REAL DEFAULT 0,
    promo TEXT, method TEXT, invoice_id TEXT, pay_url TEXT,
    status TEXT, created INTEGER, updated INTEGER
);
CREATE TABLE IF NOT EXISTS promos (
    code TEXT PRIMARY KEY, discount REAL, uses_left INTEGER DEFAULT -1, used INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS promo_uses (code TEXT, user_id INTEGER, PRIMARY KEY (code, user_id));
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
"""


class DB:
    def __init__(self):
        self.conn: aiosqlite.Connection | None = None

    async def connect(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.conn = await aiosqlite.connect(path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
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

    async def _seed(self):
        for k, (v, _, _) in defaults.SETTINGS.items():
            await self.conn.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (k, v))
        for k, (title, text) in defaults.SCREENS.items():
            await self.conn.execute(
                "INSERT OR IGNORE INTO screens (key, title, text, builtin) VALUES (?, ?, ?, 1)",
                (k, title, text))
        for k, (emoji, text) in defaults.SYS_BUTTONS.items():
            exists = await self.one("SELECT 1 FROM buttons WHERE screen='__sys__' AND value=?", k)
            if not exists:
                await self.conn.execute(
                    "INSERT INTO buttons (screen, emoji, text, action, value) VALUES ('__sys__', ?, ?, 'sys', ?)",
                    (emoji, text, k))
        if not await self.one("SELECT 1 FROM buttons WHERE screen != '__sys__'"):
            for s, row, pos, emoji, text, action, value in defaults.BUTTONS:
                await self.conn.execute(
                    "INSERT INTO buttons (screen, row, pos, emoji, text, action, value) VALUES (?,?,?,?,?,?,?)",
                    (s, row, pos, emoji, text, action, value))
        if not await self.one("SELECT 1 FROM packages"):
            for stars, price in defaults.PACKAGES:
                await self.conn.execute("INSERT INTO packages (stars, price) VALUES (?, ?)", (stars, price))
        await self.conn.commit()

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

    # --- users ---
    async def user(self, uid: int):
        return await self.one("SELECT * FROM users WHERE id=?", uid)

    async def upsert_user(self, uid: int, username: str | None, first_name: str | None):
        u = await self.user(uid)
        if u:
            if u["username"] != username or u["first_name"] != first_name:
                await self.run("UPDATE users SET username=?, first_name=? WHERE id=?", username, first_name, uid)
                u["username"], u["first_name"] = username, first_name
            return u, False
        await self.run("INSERT INTO users (id, username, first_name, created) VALUES (?,?,?,?)",
                       uid, username, first_name, int(time.time()))
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


db = DB()
