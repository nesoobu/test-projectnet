"""Уведомления через Bot API (fire-and-forget)."""
import asyncio
import logging
import re

import httpx

from . import config, db
from .realtime import hub

log = logging.getLogger("lera.notify")
_tasks: set[asyncio.Task] = set()


async def _send(chat_id: int, text: str, start: str | None):
    if not config.BOT_TOKEN:
        return
    body = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if config.WEBAPP_URL:
        url = config.WEBAPP_URL + (f"?s={start}" if start else "")
        body["reply_markup"] = {"inline_keyboard": [[{"text": "Открыть Леру", "web_app": {"url": url}}]]}
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            await c.post(f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage", json=body)
    except Exception as e:  # уведомление не должно ронять запрос
        log.warning("notify %s failed: %s", chat_id, e)


async def _deliver(chat_id: int, text: str, start: str | None, bot: bool):
    """Входящие в приложении + мгновенный пуш по WebSocket. В бота — только если человек сейчас не в Лере."""
    plain = re.sub(r"<[^>]+>", "", text).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    try:
        if db._conn is not None and chat_id:
            nid = await db.run("INSERT INTO notifications (tg_id, text, link) VALUES (?,?,?)", chat_id, plain[:500], start)
            hub.push([chat_id], {"type": "notif", "notif": {"id": nid, "text": plain[:500], "link": start}})
    except Exception as e:  # noqa: BLE001
        log.warning("inbox %s failed: %s", chat_id, e)
    if bot and not hub.online(chat_id):
        await _send(chat_id, text, start)


def send(chat_id: int, text: str, start: str | None = None, bot: bool = True):
    t = asyncio.create_task(_deliver(chat_id, text, start, bot))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


async def create_stars_invoice(title: str, description: str, payload: str, stars: int) -> str | None:
    if not config.BOT_TOKEN:
        return None
    body = {"title": title, "description": description, "payload": payload,
            "currency": "XTR", "prices": [{"label": title, "amount": stars}]}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"https://api.telegram.org/bot{config.BOT_TOKEN}/createInvoiceLink", json=body)
    data = r.json()
    return data.get("result") if data.get("ok") else None
