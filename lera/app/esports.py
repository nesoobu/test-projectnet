"""Про-сцена: загрузка матчей из PandaScore (API, токен) и Liquipedia (страницы Liquipedia:Matches, без ключа).

Каждый парсер возвращает список словарей одного формата (см. norm()). Ошибки не роняют цикл — пишутся в source_state.
Liquipedia: соблюдаем правила API — свой User-Agent, gzip, не чаще одного parse-запроса в 30 секунд, атрибуция в UI.
"""
import hashlib
import logging
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger("lera.esports")
UA = "LeraBot/7.1 (Telegram mini app lera.lerarubot.ru; esports schedule widget)"

# slug PandaScore → наша игра (остальные дисциплины показываем в «Все» под своим именем)
PS_GAME = {"cs-go": "cs2", "cs-2": "cs2", "csgo": "cs2", "dota-2": "dota2", "dota2": "dota2", "valorant": "valorant",
           "kog": "hok", "king-of-glory": "hok", "honor-of-kings": "hok", "mlbb": "mlbb", "mobile-legends": "mlbb",
           "pubg-mobile": "pubgm", "brawl-stars": "brawl"}
# вики Liquipedia → наша игра
LQ_WIKI = {"dota2": "dota2", "counterstrike": "cs2", "valorant": "valorant", "mobilelegends": "mlbb",
           "honorofkings": "hok", "pubgmobile": "pubgm", "brawlstars": "brawl", "wildrift": None, "leagueoflegends": None}
LQ_NAME = {"dota2": "Dota 2", "counterstrike": "CS2", "valorant": "Valorant", "mobilelegends": "MLBB", "honorofkings": "HoK",
           "pubgmobile": "PUBG Mobile", "brawlstars": "Brawl Stars", "wildrift": "Wild Rift", "leagueoflegends": "LoL"}


def iso(ts: float | int | str | None) -> str | None:
    if ts in (None, ""):
        return None
    if isinstance(ts, str):
        try:
            d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        d = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def acronym(name: str) -> str:
    words = re.findall(r"[A-Za-zА-Яа-я0-9]+", name or "")
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:3].upper()
    return "".join(w[0] for w in words[:4]).upper()


# ── PandaScore ───────────────────────────────────────────────────────────

def ps_match(m: dict) -> dict | None:
    opp = [o.get("opponent") or {} for o in (m.get("opponents") or [])]
    if len(opp) < 2:
        return None
    a, b = opp[0], opp[1]
    res = {r.get("team_id") or r.get("player_id"): r.get("score") for r in (m.get("results") or [])}
    vg = m.get("videogame") or {}
    st = {"running": "live", "finished": "done", "canceled": "cancelled", "postponed": "upcoming"}.get(m.get("status"), "upcoming")
    win = m.get("winner_id")
    streams = [{"url": s.get("raw_url"), "lang": s.get("language"), "main": bool(s.get("main"))}
               for s in (m.get("streams_list") or []) if s.get("raw_url")]
    league = (m.get("league") or {})
    serie = (m.get("serie") or {})
    return {
        "id": f"ps:{m['id']}", "source": "pandascore", "game": PS_GAME.get(vg.get("slug", "")), "game_name": vg.get("name") or "",
        "league": league.get("name") or "", "league_img": league.get("image_url"),
        "tournament": " · ".join(x for x in (serie.get("full_name"), (m.get("tournament") or {}).get("name")) if x),
        "best_of": m.get("number_of_games") or 1, "status": st,
        "begin_at": iso(m.get("begin_at") or m.get("scheduled_at")),
        "team_a": a.get("name") or "?", "team_b": b.get("name") or "?",
        "acr_a": a.get("acronym") or acronym(a.get("name")), "acr_b": b.get("acronym") or acronym(b.get("name")),
        "logo_a": a.get("image_url"), "logo_b": b.get("image_url"),
        "flag_a": a.get("location"), "flag_b": b.get("location"),
        "score_a": res.get(a.get("id")), "score_b": res.get(b.get("id")),
        "winner": "a" if win and win == a.get("id") else "b" if win and win == b.get("id") else None,
        "streams": streams,
    }


async def fetch_pandascore(client: httpx.AsyncClient, token: str) -> list[dict]:
    out = []
    h = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    plan = [("running", 1, None), ("upcoming", 3, "begin_at"), ("past", 2, "-begin_at")]
    for kind, pages, sort in plan:
        for page in range(1, pages + 1):
            params = {"per_page": 100, "page": page}
            if sort:
                params["sort"] = sort
            r = await client.get(f"https://api.pandascore.co/matches/{kind}", params=params, headers=h)
            r.raise_for_status()
            rows = r.json()
            out += [x for x in (ps_match(m) for m in rows) if x]
            if len(rows) < 100:
                break
    return out


# ── Liquipedia ───────────────────────────────────────────────────────────

def _team(node) -> str:
    if node is None:
        return ""
    for sel in (".name a[title]", ".team-template-text a[title]", "a[title]"):
        a = node.select_one(sel)
        if a and a.get("title") and "page does not exist" not in a["title"]:
            return re.sub(r"\s*\(page does not exist\)", "", a["title"]).strip()
    for sel in (".name", ".team-template-text", ".team-template-team-standard", "span"):
        s = node.select_one(sel)
        if s and s.get_text(strip=True):
            return s.get_text(" ", strip=True)
    return node.get_text(" ", strip=True)


def _short(node) -> str:
    if node is None:
        return ""
    for sel in (".team-template-text", ".name", "a"):
        s = node.select_one(sel)
        t = s.get_text(strip=True) if s else ""
        if t and len(t) <= 5:
            return t.upper()
    return ""


def _scores(text: str):
    m = re.search(r"(\d+)\s*[:\-–]\s*(\d+)", text or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def lq_parse(html_text: str, wiki: str, now: datetime | None = None) -> list[dict]:
    """Разбор Liquipedia:Matches. Понимает старую таблицу (infobox_matches_content) и новый блок match-info."""
    now = now or datetime.now(timezone.utc)
    soup = BeautifulSoup(html_text, "html.parser")
    blocks = soup.select("table.infobox_matches_content") or soup.select("div.match-info")
    out, seen = [], set()
    for bl in blocks:
        timer = bl.select_one("[data-timestamp]")
        if not timer:
            continue
        try:
            ts = int(timer["data-timestamp"])
        except (ValueError, KeyError):
            continue
        left = bl.select_one(".team-left, .match-info-header-opponent-left, .match-info-opponent-left")
        right = bl.select_one(".team-right, .match-info-header-opponent-right, .match-info-opponent-right")
        a, b = _team(left), _team(right)
        if not a or not b or a.upper() == "TBD" and b.upper() == "TBD":
            continue
        # счёт и формат
        vs = bl.select_one(".versus, .match-info-header-scoreholder, .match-info-scoreholder")
        vs_text = vs.get_text(" ", strip=True) if vs else ""
        sa, sb = _scores(vs_text)
        sc = bl.select(".match-info-header-scoreholder-score, .match-info-scoreholder-score")
        if len(sc) >= 2 and sc[0].get_text(strip=True).isdigit() and sc[1].get_text(strip=True).isdigit():
            sa, sb = int(sc[0].get_text(strip=True)), int(sc[1].get_text(strip=True))
        bo = re.search(r"Bo\s*(\d+)", vs_text) or re.search(r"Best of (\d+)", str(vs or ""))
        best_of = int(bo.group(1)) if bo else 1
        tour_a = bl.select_one(".tournament-text a, .match-info-tournament-name a, .league-icon-small-image a, .match-tournament a")
        tournament = (tour_a.get_text(" ", strip=True) or tour_a.get("title", "")) if tour_a else ""
        live = bool(bl.select_one(".timer-object-countdown-live, .match-countdown-live, .timer-object[data-finished], .timer-object-live"))
        started = ts <= now.timestamp()
        need = best_of // 2 + 1
        if sa is not None and sb is not None and max(sa, sb) >= need:
            status = "done"
        elif started or live:
            status = "live"
        else:
            status = "upcoming"
        streams = []
        for el in bl.select("[data-stream-twitch], [data-stream-youtube]"):
            if el.get("data-stream-twitch"):
                streams.append({"url": f"https://twitch.tv/{el['data-stream-twitch']}", "lang": None, "main": not streams})
            if el.get("data-stream-youtube"):
                streams.append({"url": f"https://youtube.com/{el['data-stream-youtube']}", "lang": None, "main": not streams})
        key = f"{wiki}|{ts}|{a}|{b}"
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "id": "lq:" + hashlib.sha1(key.encode()).hexdigest()[:16], "source": "liquipedia", "game": LQ_WIKI.get(wiki),
            "game_name": LQ_NAME.get(wiki, wiki), "league": tournament, "league_img": None, "tournament": tournament, "best_of": best_of,
            "status": status, "begin_at": iso(ts), "team_a": a, "team_b": b,
            "acr_a": _short(left) or acronym(a), "acr_b": _short(right) or acronym(b), "logo_a": None, "logo_b": None,
            "flag_a": None, "flag_b": None,
            "score_a": sa if status != "upcoming" else None, "score_b": sb if status != "upcoming" else None,
            "winner": ("a" if sa > sb else "b") if status == "done" and sa != sb else None, "streams": streams[:4],
        })
    return out


async def fetch_liquipedia(client: httpx.AsyncClient, wiki: str) -> list[dict]:
    r = await client.get(f"https://liquipedia.net/{wiki}/api.php",
                         params={"action": "parse", "page": "Liquipedia:Matches", "format": "json", "prop": "text"},
                         headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("info", "liquipedia error"))
    return lq_parse(data["parse"]["text"]["*"], wiki)
