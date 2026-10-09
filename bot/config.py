import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}
DB_PATH = os.getenv("DB_PATH", "data/bot.db")

# Необязательно: Redis для FSM (переживает перезапуск, нужен при нескольких инстансах)
REDIS_URL = os.getenv("REDIS_URL", "")

# Необязательно: webhook вместо polling
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # https://example.com
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/tg")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "8080"))

# Автовыдача через Fragment (delivery_mode = fragment). Секреты храним только здесь, не в БД.
FRAGMENT_SEED = os.getenv("FRAGMENT_SEED", "")            # 24 слова кошелька, через пробел
FRAGMENT_COOKIES = os.getenv("FRAGMENT_COOKIES", "")      # stel_ssid=...; stel_dt=...; stel_token=...; stel_ton_token=...
FRAGMENT_API_KEY = os.getenv("FRAGMENT_API_KEY", "")      # ключ tonapi.io (tonconsole.com) или toncenter
FRAGMENT_API_PROVIDER = os.getenv("FRAGMENT_API_PROVIDER", "tonapi")  # tonapi | toncenter
FRAGMENT_WALLET_VERSION = os.getenv("FRAGMENT_WALLET_VERSION", "V5R1")  # Tonkeeper W5 = V5R1, старые = V4R2
