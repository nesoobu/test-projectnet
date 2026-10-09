"""Реалтайм: хаб WebSocket-подключений. Один процесс uvicorn → состояние в памяти."""
import asyncio
import json
import logging

log = logging.getLogger("lera.rt")


class Hub:
    def __init__(self):
        self.conns: dict[int, set] = {}

    def online(self, uid: int) -> bool:
        return bool(self.conns.get(uid))

    def add(self, uid: int, ws):
        self.conns.setdefault(uid, set()).add(ws)

    def remove(self, uid: int, ws):
        s = self.conns.get(uid)
        if s:
            s.discard(ws)
            if not s:
                self.conns.pop(uid, None)

    async def _send(self, ws, data: str):
        try:
            await asyncio.wait_for(ws.send_text(data), timeout=5)
        except Exception:  # noqa: BLE001 — мёртвое соединение уберёт обработчик
            pass

    def push(self, uids, event: dict):
        """Неблокирующая рассылка события пользователям."""
        data = json.dumps(event, ensure_ascii=False, default=str)
        for uid in set(uids):
            for ws in list(self.conns.get(uid, ())):
                asyncio.create_task(self._send(ws, data))


hub = Hub()
