#!/usr/bin/env python3
"""Одноразовый патч: добавляет уведомление при лайке в miniapp_api.py"""
import re

PATH = "/opt/lera-miniapp/lera-miniapp/miniapp_api.py"
with open(PATH) as f:
    code = f.read()

if "like_notify" in code:
    print("Уже пропатчен"); exit(0)

# 1. Добавить httpx если нет
if "import httpx" not in code:
    code = code.replace("import aiosqlite", "import httpx\nimport aiosqlite")
    print("httpx import добавлен")

# 2. Добавить функцию like_notify перед первым @app роутом
NOTIFY_FN = '''
_BOT_TOKEN = "8568968489:AAH-Isqdtl9bXsQEuqFQm9BLMLPVN-8OPMc"

async def like_notify(chat_id: int, from_name: str):
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(
                f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": f"\\u2764\\ufe0f <b>{from_name}</b> \\u043b\\u0430\\u0439\\u043a\\u043d\\u0443\\u043b(\\u0430) \\u0442\\u0432\\u043e\\u044e \\u0430\\u043d\\u043a\\u0435\\u0442\\u0443 \\u0432 \\u0434\\u0443\\u044d\\u0442\\u0435!\\n\\n\\u041e\\u0442\\u043a\\u0440\\u043e\\u0439 \\u041b\\u0435\\u0440\\u0443 \\u0447\\u0442\\u043e\\u0431\\u044b \\u043f\\u043e\\u0441\\u043c\\u043e\\u0442\\u0440\\u0435\\u0442\\u044c \\ud83d\\udc40",
                    "parse_mode": "HTML"
                }
            )
    except Exception:
        pass

'''
code = re.sub(r'(@app\.(?:get|post|put|delete)\()', NOTIFY_FN + r'\1', code, count=1)

# 3. Вызов like_notify после INSERT лайка
OLD = 'except Exception: pass\n        # Взаимность?'
NEW = '''except Exception: pass
        # Уведомить о лайке
        try:
            _fn = user.get("first_name") or user.get("username") or "Игрок"
            await like_notify(target_tg_id, _fn)
        except Exception: pass
        # Взаимность?'''

if OLD in code:
    code = code.replace(OLD, NEW)
    print("Уведомление при лайке добавлено")
else:
    print("ВНИМАНИЕ: якорь не найден — проверь вручную")

with open(PATH, "w") as f:
    f.write(code)
print("miniapp_api.py OK")
print("Запусти: systemctl restart lera-miniapp")
