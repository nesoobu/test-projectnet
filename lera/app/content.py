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
