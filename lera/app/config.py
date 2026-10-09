import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
DB_PATH = str(ROOT / os.getenv("DB_PATH", "data/lera.db"))
UPLOAD_DIR = ROOT / os.getenv("UPLOAD_DIR", "data/uploads")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}
PREMIUM_STARS = int(os.getenv("PREMIUM_STARS", "99"))
DEV_USER_ID = int(os.getenv("DEV_USER_ID") or 0)
BOT_USERNAME = os.getenv("BOT_USERNAME", "lerarubot").lstrip("@")
WEB_DIR = ROOT / "web"
# Про-сцена: PandaScore (структурные данные, лого, live-счёт) — бесплатный токен на pandascore.co; Liquipedia — без ключа
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN", "")
LIQUIPEDIA = os.getenv("LIQUIPEDIA", "1") not in ("0", "", "false", "no")
