"""Статический контент: ранги, роли, герои, предметы, квесты, фразы Леры."""

RANKS = ["Бронза", "Серебро", "Золото", "Платина", "Алмаз", "Мастер", "Грандмастер", "Мифик"]
ROLES = {
    "clash": "Линия дуэли",
    "jungle": "Лес",
    "mid": "Мид",
    "farm": "Линия фарма",
    "roam": "Роум",
}
PLAY_TIMES = {"morning": "Утро", "day": "День", "evening": "Вечер", "night": "Ночь"}
SQUAD_MODES = {"ranked": "Рейтинг", "normal": "Обычный", "fun": "Фан-режим", "tourney": "Турнир"}

# (имя, класс, линия)
HEROES = [
    ("Arli", "Стрелок", "farm"), ("Marco Polo", "Стрелок", "farm"), ("Hou Yi", "Стрелок", "farm"),
    ("Luban No.7", "Стрелок", "farm"), ("Di Renjie", "Стрелок", "farm"), ("Lady Sun", "Стрелок", "farm"),
    ("Huang Zhong", "Стрелок", "farm"), ("Garo", "Стрелок", "farm"), ("Consort Yu", "Стрелок", "farm"),
    ("Loong", "Стрелок", "farm"), ("Shouyue", "Стрелок", "farm"), ("Gongsun Li", "Стрелок", "farm"),
    ("Angela", "Маг", "mid"), ("Daji", "Маг", "mid"), ("Diaochan", "Маг", "mid"),
    ("Wang Zhaojun", "Маг", "mid"), ("Xiao Qiao", "Маг", "mid"), ("Zhou Yu", "Маг", "mid"),
    ("Gan & Mo", "Маг", "mid"), ("Shangguan", "Маг", "mid"), ("Kongming", "Маг", "mid"),
    ("Nuwa", "Маг", "mid"), ("Mai Shiranui", "Маг", "mid"), ("Heino", "Маг", "mid"),
    ("Milady", "Маг", "mid"), ("Yixing", "Маг", "mid"), ("Dr Bian", "Маг", "mid"),
    ("Li Bai", "Убийца", "jungle"), ("Han Xin", "Убийца", "jungle"), ("Lam", "Убийца", "jungle"),
    ("Lanling Wang", "Убийца", "jungle"), ("Nakoruru", "Убийца", "jungle"), ("Jing", "Убийца", "jungle"),
    ("Wukong", "Убийца", "jungle"), ("Cirrus", "Убийца", "jungle"), ("Augran", "Боец", "jungle"),
    ("Mulan", "Боец", "clash"), ("Arthur", "Боец", "clash"), ("Lu Bu", "Боец", "clash"),
    ("Charlotte", "Боец", "clash"), ("Fuzi", "Боец", "clash"), ("Kaizer", "Боец", "clash"),
    ("Mayene", "Боец", "clash"), ("Dharma", "Боец", "clash"), ("Ukyo Tachibana", "Боец", "jungle"),
    ("Yao", "Поддержка", "roam"), ("Dolia", "Поддержка", "roam"), ("Da Qiao", "Поддержка", "roam"),
    ("Cai Yan", "Поддержка", "roam"), ("Ming", "Поддержка", "roam"), ("Sun Bin", "Поддержка", "roam"),
    ("Kui", "Поддержка", "roam"), ("Guiguzi", "Поддержка", "roam"), ("Zhang Fei", "Танк", "roam"),
    ("Liu Shan", "Танк", "roam"), ("Lian Po", "Танк", "roam"), ("Xiang Yu", "Танк", "roam"),
    ("Bai Qi", "Танк", "roam"), ("Zhuangzi", "Танк", "roam"), ("Liu Bang", "Танк", "roam"),
    ("Donghuang", "Танк", "roam"),
]

RARITY_WEIGHTS = {"common": 64, "rare": 26, "epic": 8.5, "legendary": 1.5}
GACHA_PITY = 50          # гарант легендарки
GACHA_COST = 100
GACHA_COST_X10 = 900
DUPLICATE_REFUND = {"common": 15, "rare": 40, "epic": 120, "legendary": 400}

# id: (название, тип, редкость, цена в магазине или None — только гача)
ITEMS = {
    "frame_dash":    ("Пунктир", "frame", "common", 150),
    "frame_ice":     ("Лёд", "frame", "common", 200),
    "frame_neon":    ("Неон", "frame", "rare", 450),
    "frame_sakura":  ("Сакура", "frame", "rare", None),
    "frame_ember":   ("Угли", "frame", "epic", None),
    "frame_gold":    ("Золото Мифика", "frame", "epic", 1500),
    "frame_glitch":  ("Глитч", "frame", "legendary", None),
    "frame_crown":   ("Корона Premium", "frame", "legendary", None),

    "color_lime":    ("Кислотный ник", "color", "common", 120),
    "color_coral":   ("Коралловый ник", "color", "common", 120),
    "color_sky":     ("Небесный ник", "color", "rare", None),
    "color_rainbow": ("Переливающийся ник", "color", "legendary", None),

    "title_carry":   ("Тащер", "title", "common", 100),
    "title_support": ("Святой саппорт", "title", "common", 100),
    "title_jungle":  ("Хозяин леса", "title", "rare", None),
    "title_feeder":  ("Кормилец врагов", "title", "rare", None),
    "title_night":   ("Ночной дозор", "title", "rare", 350),
    "title_mvp":     ("MVP", "title", "epic", None),
    "title_lera":    ("Любимчик Леры", "title", "legendary", None),

    "banner_grid":   ("Сетка", "banner", "common", 200),
    "banner_dusk":   ("Сумерки", "banner", "rare", None),
    "banner_toxic":  ("Токсик", "banner", "epic", None),
    "banner_aurora": ("Аврора", "banner", "legendary", None),
}
PREMIUM_ONLY = {"frame_crown"}

# id: (описание, цель, награда)
QUESTS = {
    "checkin":  ("Забери ежедневку", 1, 15),
    "swipe":    ("Оцени 10 анкет в дуэте", 10, 30),
    "squad_msg": ("Напиши в любой отряд", 1, 20),
    "post_like": ("Лайкни 3 поста в ленте", 3, 15),
    "gacha":    ("Крутани гачу", 1, 25),
}

ICEBREAKERS = [
    "Го катку? 🎮",
    "Какой у тебя мейн?",
    "Ты больше тащишь или страдаешь?",
    "Во сколько обычно играешь?",
    "Микро есть?",
    "Самый токсичный герой по-твоему?",
]

LERA_LINES = {
    "checkin": [
        "Пришёл! Держи монетки, только не спусти всё на гачу. Хотя кого я обманываю.",
        "Стрик растёт — уважение тоже.",
        "Ежедневка забрана. Теперь иди и сделай кого-нибудь MVP.",
    ],
    "match": [
        "Мэтч! Я же говорила, что вы сыграетесь.",
        "Оу, взаимно. Не стесняйся — напиши первым.",
    ],
    "empty_duet": [
        "Анкеты кончились. Даже я столько не свайпаю.",
        "Тут пусто. Ослабь фильтры или зайди позже.",
    ],
    "legendary": [
        "ЛЕГЕНДАРКА. Скринь, пока не проснулся.",
    ],
}


# ── Мультиигры ────────────────────────────────────────────────────────────
# Добавить игру = добавить запись сюда. heroes — список (имя, класс, линия) или None.
GAMES = {
    "hok": {
        "name": "Honor of Kings", "short": "HoK", "color": "#ffc64a",
        "ranks": RANKS, "roles": ROLES, "modes": SQUAD_MODES, "heroes": HEROES,
    },
    "mlbb": {
        "name": "Mobile Legends", "short": "MLBB", "color": "#7cc8ff",
        "ranks": ["Воин", "Элита", "Мастер", "Грандмастер", "Эпик", "Легенда", "Мифический", "Мифическая слава"],
        "roles": {"exp": "Линия опыта", "jungle": "Лес", "mid": "Мид", "gold": "Линия золота", "roam": "Роум"},
        "modes": {"ranked": "Рейтинг", "classic": "Классика", "brawl": "Бойня", "fun": "Фан"},
    },
    "pubgm": {
        "name": "PUBG Mobile", "short": "PUBG M", "color": "#ffb36b",
        "ranks": ["Бронза", "Серебро", "Золото", "Платина", "Алмаз", "Корона", "Ас", "Завоеватель"],
        "roles": {"igl": "Капитан", "fragger": "Фраггер", "support": "Саппорт", "sniper": "Снайпер", "scout": "Разведка"},
        "modes": {"ranked": "Рейтинг", "tdm": "TDM", "arena": "Арена", "fun": "Фан"},
    },
    "so2": {
        "name": "Standoff 2", "short": "SO2", "color": "#ff7a59",
        "ranks": ["Бронза", "Серебро", "Золото", "Феникс", "Рейнджер", "Чемпион", "Мастер", "Элита", "Легенда"],
        "roles": {"entry": "Энтри", "awp": "Снайпер", "support": "Саппорт", "lurk": "Люркер", "igl": "Капитан"},
        "modes": {"comp": "Соревновательный", "allies": "Союзники", "dm": "Дезматч", "fun": "Фан"},
    },
    "cs2": {
        "name": "Counter-Strike 2", "short": "CS2", "color": "#d4ff3f",
        "ranks": ["до 5000", "5000+", "10000+", "15000+", "20000+", "25000+", "30000+"],
        "roles": {"entry": "Энтри", "awp": "Снайпер", "support": "Саппорт", "lurk": "Люркер", "igl": "Капитан"},
        "modes": {"premier": "Premier", "comp": "Соревновательный", "wingman": "Напарники", "faceit": "FACEIT"},
    },
    "dota2": {
        "name": "Dota 2", "short": "Dota 2", "color": "#ff5a36",
        "ranks": ["Рекрут", "Страж", "Рыцарь", "Герой", "Легенда", "Властелин", "Божество", "Титан"],
        "roles": {"carry": "Керри", "mid": "Мид", "off": "Оффлейн", "sup4": "Саппорт 4", "sup5": "Саппорт 5"},
        "modes": {"ranked": "Рейтинг", "normal": "Обычный", "turbo": "Турбо", "fun": "Фан"},
    },
    "valorant": {
        "name": "Valorant", "short": "Valo", "color": "#ff6fa5",
        "ranks": ["Железо", "Бронза", "Серебро", "Золото", "Платина", "Алмаз", "Восхождение", "Бессмертный", "Радиант"],
        "roles": {"duelist": "Дуэлянт", "initiator": "Инициатор", "controller": "Контроллер", "sentinel": "Страж"},
        "modes": {"comp": "Рейтинг", "unrated": "Без рейтинга", "spike": "Быстрая закладка", "fun": "Фан"},
    },
    "brawl": {
        "name": "Brawl Stars", "short": "Brawl", "color": "#b48cff",
        "ranks": ["до 5к кубков", "5–15к", "15–30к", "30–50к", "50к+"],
        "roles": {"tank": "Танк", "dd": "Урон", "support": "Поддержка", "control": "Контроль"},
        "modes": {"ranked": "Рейтинг", "trophies": "Кубки", "club": "Клубная лига", "fun": "Фан"},
    },
    "genshin": {
        "name": "Genshin Impact", "short": "Genshin", "color": "#5ef0c1",
        "ranks": ["AR 1–30", "AR 31–45", "AR 46–55", "AR 56–60"],
        "roles": {"dps": "Мейн-ДД", "sub": "Саб-ДД", "support": "Поддержка", "healer": "Хил"},
        "modes": {"coop": "Кооп", "abyss": "Бездна", "boss": "Боссы", "chill": "Просто чилл"},
    },
}
DEFAULT_GAME = "hok"

# Опрос дня, если админ не задал свой
POLL_POOL = [
    ("Как ты обычно играешь?", ["Соло", "С другом", "Фулл пати", "Как повезёт"]),
    ("Что бесит больше всего?", ["Афкшники", "Токсики", "Читеры", "Свой пинг"]),
    ("Сколько часов в день играешь?", ["Меньше часа", "1–3", "3–6", "Не спрашивай"]),
    ("Микрофон в рейтинге — это…", ["Обязательно", "Только с друзьями", "Нет, спасибо", "Только слушаю"]),
    ("Лучшее время для катки?", ["Утро", "День", "Вечер", "Глубокая ночь"]),
    ("Проиграл 3 подряд. Твои действия?", ["Ещё одну", "Перерыв", "Меняю роль", "Удаляю игру (на час)"]),
    ("Какая роль самая недооценённая?", ["Саппорт", "Танк", "Лес", "Капитан"]),
    ("Донатишь в игры?", ["Никогда", "Только пропуск", "Иногда", "Без комментариев"]),
    ("Кто виноват в поражении?", ["Тиммейты", "Матчмейкинг", "Я", "Лаги"]),
    ("Во что поиграть на выходных?", ["Свою мейн-игру", "Что-то новое", "Кооп с друзьями", "Отдохнуть от игр"]),
]

# id: (название, описание, награда, метрика, порог)
ACHIEVEMENTS = [
    ("first_match", "Первый мэтч", "Получи взаимный лайк в дуэте", 50, "matches", 1),
    ("matchmaker", "Сердцеед", "10 мэтчей", 150, "matches", 10),
    ("squad_leader", "Лидер", "Создай 5 отрядов", 100, "squads", 5),
    ("talker", "Душа компании", "100 сообщений в чатах", 100, "messages", 100),
    ("blogger", "Блогер", "5 постов в ленте", 80, "posts", 5),
    ("popular", "Звезда ленты", "50 лайков на постах", 200, "post_likes", 50),
    ("streak7", "Неделя без пропусков", "Стрик ежедневки 7 дней", 150, "streak", 7),
    ("streak30", "Железная воля", "Стрик ежедневки 30 дней", 600, "streak", 30),
    ("respected", "Уважаемый", "10 хороших отзывов от тиммейтов", 200, "rep", 10),
    ("legend", "Везунчик", "Выбей легендарку в гаче", 150, "legendaries", 1),
    ("collector", "Коллекционер", "15 предметов в инвентаре", 200, "items", 15),
    ("multigamer", "Мультигеймер", "Добавь 3 игры в профиль", 80, "games", 3),
    ("leradle5", "Знаток", "Разгадай Лерадл 5 раз", 120, "leradle", 5),
    ("champion", "Чемпион", "Выиграй турнир", 500, "t_wins", 1),
    ("ready10", "Всегда готов", "10 раз нажми «Готов играть»", 80, "ready", 10),
]

REVIEW_TAGS = {"chill": "Не токсик", "carry": "Тащер", "mic": "С микро", "brain": "Тактик", "fun": "Весело",
               "toxic": "Токсичный", "afk": "Ливает", "noob": "Слабо играет"}
NEGATIVE_TAGS = {"toxic", "afk", "noob"}

QUESTS["leradle"] = ("Разгадай Лерадл", 1, 30)
QUESTS["ready"] = ("Нажми «Готов играть»", 1, 15)


# ── Боевой пропуск ────────────────────────────────────────────────────────
# Сезон = календарный месяц. Опыт пропуска копится вместе с обычным xp.
BP_LEVELS = 30
BP_XP_PER_LEVEL = 40
BP_STARS = 149            # цена премиум-линейки на сезон (Lera Premium открывает её бесплатно)

ITEMS.update({
    "frame_season":  ("Сезонный огонь", "frame", "epic", None),
    "color_season":  ("Сезонный градиент", "color", "epic", None),
    "title_season":  ("Ветеран сезона", "title", "epic", None),
    "banner_season": ("Сезонный неон", "banner", "legendary", None),
})
BP_ONLY = {"frame_season", "color_season", "title_season", "banner_season"}


def bp_reward(level: int, track: str) -> tuple:
    """(тип, значение): nesso/ticket/item."""
    if track == "free":
        if level == 30:
            return ("item", "title_season")
        if level % 5 == 0:
            return ("ticket", 1)
        return ("nesso", 20 + level * 2)
    special = {10: "frame_season", 20: "color_season", 30: "banner_season"}
    if level in special:
        return ("item", special[level])
    if level % 3 == 0:
        return ("ticket", 1)
    return ("nesso", 50 + level * 4)


# ── Кланы ─────────────────────────────────────────────────────────────────
CLAN_COST = 500
CLAN_COLORS = ["#d4ff3f", "#ff6fa5", "#7cc8ff", "#ffc64a", "#b48cff", "#ff7a59", "#5ef0c1", "#efeae0"]
CLAN_ROLES = {"owner": "Лидер", "officer": "Офицер", "member": "Боец"}


def clan_level(xp: int) -> dict:
    import math
    lvl = int(math.sqrt(max(xp, 0) / 200)) + 1
    return {"level": lvl, "xp": xp, "from": 200 * (lvl - 1) ** 2, "to": 200 * lvl ** 2, "max_members": min(50, 18 + 2 * lvl)}


# ── Персонажи/карты по играм (для вики, мейнов и Лерадла) ─────────────────
# (имя, класс, ключ роли из GAMES[g]["roles"] или None)
def _h(names: str, cls: str, role: str | None):
    return [(n.strip(), cls, role) for n in names.split(",") if n.strip()]


GAMES["mlbb"]["heroes"] = (
    _h("Layla, Miya, Bruno, Clint, Granger, Beatrix, Brody, Claude, Moskov, Wanwan, Karrie, Melissa, Irithel, Lesley, Natan, Popol and Kupa", "Стрелок", "gold")
    + _h("Eudora, Aurora, Kagura, Lunox, Harith, Valentina, Xavier, Pharsa, Yve, Lylia, Cecilion, Vale, Chang'e, Nana, Zhask", "Маг", "mid")
    + _h("Saber, Fanny, Gusion, Lancelot, Hayabusa, Ling, Benedetta, Karina, Natalia, Helcurt, Hanzo", "Убийца", "jungle")
    + _h("Alucard, Zilong, Chou, Paquito, Yu Zhong, X.Borg, Esmeralda, Dyrroth, Martis, Terizla, Thamuz, Fredrinn", "Боец", "exp")
    + _h("Tigreal, Franco, Khufra, Atlas, Akai, Johnson, Grock, Hylos, Lolita, Minotaur, Uranus, Gloo", "Танк", "roam")
    + _h("Angela, Estes, Rafaela, Diggie, Mathilda, Floryn, Faramis", "Поддержка", "roam")
)
GAMES["dota2"]["heroes"] = (
    _h("Anti-Mage, Juggernaut, Phantom Assassin, Faceless Void, Spectre, Medusa, Terrorblade, Slark, Luna, Morphling", "Керри", "carry")
    + _h("Shadow Fiend, Invoker, Storm Spirit, Queen of Pain, Puck, Templar Assassin, Ember Spirit, Lina, Zeus, Sniper", "Мидер", "mid")
    + _h("Axe, Mars, Tidehunter, Centaur Warrunner, Underlord, Legion Commander, Bristleback, Dark Seer, Timbersaw, Beastmaster", "Оффлейнер", "off")
    + _h("Earthshaker, Rubick, Pudge, Tusk, Snapfire, Mirana", "Саппорт 4", "sup4")
    + _h("Crystal Maiden, Lion, Shadow Shaman, Witch Doctor, Io, Dazzle, Lich", "Саппорт 5", "sup5")
)
GAMES["valorant"]["heroes"] = (
    _h("Jett, Reyna, Phoenix, Raze, Yoru, Neon, Iso, Waylay", "Дуэлянт", "duelist")
    + _h("Sova, Breach, Skye, KAY/O, Fade, Gekko, Tejo", "Инициатор", "initiator")
    + _h("Brimstone, Viper, Omen, Astra, Harbor, Clove", "Контроллер", "controller")
    + _h("Sage, Cypher, Killjoy, Chamber, Deadlock, Vyse", "Страж", "sentinel")
)
GAMES["brawl"]["heroes"] = (
    _h("El Primo, Bull, Frank, Rosa, Jacky, Darryl, Ash, Buster", "Танк", "tank")
    + _h("Shelly, Colt, Rico, 8-Bit, Chester, Lola, Clancy", "Урон", "dd")
    + _h("Brock, Piper, Bea, Belle, Mandy, Nani", "Снайпер", "dd")
    + _h("Mortis, Leon, Crow, Edgar, Fang, Stu, Cordelius", "Ассасин", "dd")
    + _h("Poco, Pam, Gene, Max, Byron, Gus, Berry", "Поддержка", "support")
    + _h("Gale, Emz, Lou, Squeak, Otis, Dynamike, Barley, Tick, Grom, Sprout", "Контроль", "control")
)
GAMES["genshin"]["heroes"] = (
    _h("Diluc, Hu Tao, Yoimiya, Arlecchino", "Пиро", "dps") + _h("Xiangling", "Пиро", "sub") + _h("Bennett", "Пиро", "healer")
    + _h("Raiden Shogun, Keqing", "Электро", "dps") + _h("Fischl, Beidou", "Электро", "sub")
    + _h("Kamisato Ayaka, Ganyu, Wriothesley, Eula", "Крио", "dps") + _h("Qiqi", "Крио", "healer")
    + _h("Neuvillette, Tartaglia", "Гидро", "dps") + _h("Xingqiu, Yelan, Furina", "Гидро", "sub") + _h("Sangonomiya Kokomi, Barbara", "Гидро", "healer")
    + _h("Alhaitham", "Дендро", "dps") + _h("Nahida", "Дендро", "sub") + _h("Baizhu", "Дендро", "healer")
    + _h("Kaedehara Kazuha, Venti, Sucrose", "Анемо", "support") + _h("Jean", "Анемо", "healer")
    + _h("Navia", "Гео", "dps") + _h("Zhongli", "Гео", "support")
)
GAMES["cs2"]["heroes"] = _h("Mirage, Inferno, Nuke, Ancient, Anubis, Dust II, Train, Vertigo, Overpass", "Карта", None)
GAMES["pubgm"]["heroes"] = _h("Erangel, Miramar, Sanhok, Vikendi, Livik", "Карта", None)

# как называть сущности в вики и Лерадле
ENTITY = {"hok": "Герои", "mlbb": "Герои", "dota2": "Герои", "valorant": "Агенты", "brawl": "Бойцы",
          "genshin": "Персонажи", "cs2": "Карты", "pubgm": "Карты"}
LERADLE_GAMES = [g for g in ("hok", "mlbb", "dota2", "valorant", "brawl", "genshin")]
