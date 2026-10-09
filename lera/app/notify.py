"""Уведомления через Bot API (fire-and-forget)."""
import asyncio
import logging

import httpx

from . import config

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


def send(chat_id: int, text: str, start: str | None = None):
    t = asyncio.create_task(_send(chat_id, text, start))
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
