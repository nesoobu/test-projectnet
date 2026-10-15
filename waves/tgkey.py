"""Получить api_id / api_hash на my.telegram.org с сервера и записать в tgapi.env."""
import http.cookiejar
import json
import re
import sys
import urllib.parse
import urllib.request

ENV = "/home/sonya/sonya/tgapi.env"
BASE = "https://my.telegram.org"
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
op.addheaders = [("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) Chrome/126.0 Safari/537.36"),
                 ("X-Requested-With", "XMLHttpRequest"), ("Origin", BASE), ("Referer", BASE + "/auth")]


def req(path, data=None):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    with op.open(BASE + path, body, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def keys(html):
    i = re.search(r"api_id.{0,300}?(\d{5,})", html, re.S)
    h = re.search(r"api_hash.{0,300}?([0-9a-f]{32})", html, re.S)
    return (i.group(1), h.group(1)) if i and h else None


phone = input("номер телефона (+7...): ").strip().replace(" ", "")
r = req("/auth/send_password", {"phone": phone})
try:
    rh = json.loads(r)["random_hash"]
except Exception:
    sys.exit("не отправился код: " + r[:200])
code = input("код из Телеграма (от аккаунта Telegram): ").strip()
r = req("/auth/login", {"phone": phone, "random_hash": rh, "password": code})
if r.strip() != "true":
    sys.exit("вход не прошёл: " + r[:200])
print("вошёл ✓")

page = req("/apps")
k = keys(page)
if not k:
    m = re.search(r'name="hash" value="([^"]+)"', page)
    if not m:
        sys.exit("не нашёл форму создания на странице /apps")
    r = req("/apps/create", {"hash": m.group(1), "app_title": "Sonya Bot API",
                             "app_shortname": "sonya7api2026", "app_url": "", "app_platform": "other",
                             "app_desc": "Local Bot API server for my Telegram bots"})
    if r.strip():
        print("ответ сайта:", r[:200])
    k = keys(req("/apps"))
if not k:
    sys.exit("приложение не создалось — попробуй ещё раз через 15-30 минут")
with open(ENV, "w") as f:
    f.write(f"TELEGRAM_API_ID={k[0]}\nTELEGRAM_API_HASH={k[1]}\n")
print("готово ✓ ключи записаны в", ENV, "(в чат их не кидай)")
