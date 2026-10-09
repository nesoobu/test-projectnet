"""Начальное наполнение БД. Всё это потом редактируется из админ-панели."""

SETTING_GROUPS = {
    "price": "💱 Цены и уровни",
    "pay": "💳 Оплата",
    "delivery": "🚀 Выдача",
    "ref": "👥 Рефералы",
    "fraud": "🛡 Антифрод",
    "channels": "📢 Каналы и уведомления",
    "lang": "🌐 Языки",
    "system": "🔧 Система",
}

# key: (значение по умолчанию, описание, тип: str|int|float|bool, группа)
SETTINGS = {
    # цены
    "rate": ("1.45", "Цена 1 ⭐️ (если автокурс выключен)", "float", "price"),
    "currency": ("₽", "Символ валюты в текстах", "str", "price"),
    "fiat_code": ("RUB", "Код фиата (RUB, USD, EUR...)", "str", "price"),
    "min_stars": ("50", "Мин. звёзд в заказе (Fragment: от 50)", "int", "price"),
    "max_stars": ("100000", "Макс. звёзд в заказе", "int", "price"),
    "auto_rate": ("0", "Автокурс (себестоимость × курс USD × наценка)", "bool", "price"),
    "star_cost_usd": ("0.015", "Себестоимость 1 ⭐️ в USD (Fragment)", "float", "price"),
    "markup_percent": ("25", "Наценка для автокурса, %", "float", "price"),
    "levels": ("1000:2,5000:4,20000:6", "Уровни: куплено_звёзд:скидка% через запятую", "str", "price"),
    # оплата
    "pay_balance": ("1", "Оплата с баланса", "bool", "pay"),
    "pay_crypto": ("0", "CryptoBot", "bool", "pay"),
    "cryptobot_token": ("", "Токен Crypto Pay API", "str", "pay"),
    "cryptobot_testnet": ("0", "CryptoBot: тестовая сеть", "bool", "pay"),
    "crypto_assets": ("USDT,TON", "CryptoBot: принимаемые монеты", "str", "pay"),
    "pay_yookassa": ("0", "ЮKassa (карты, СБП)", "bool", "pay"),
    "yk_shop_id": ("", "ЮKassa: shopId", "str", "pay"),
    "yk_secret": ("", "ЮKassa: секретный ключ", "str", "pay"),
    "pay_ton": ("0", "Прямая оплата TON (Tonkeeper и др.)", "bool", "pay"),
    "ton_wallet": ("", "TON: адрес кошелька для приёма", "str", "pay"),
    "toncenter_key": ("", "TON: API-ключ toncenter (необязательно)", "str", "pay"),
    "pay_manual": ("1", "Ручная оплата (карта + чек)", "bool", "pay"),
    "card_details": ("0000 0000 0000 0000 — Банк, Имя", "Реквизиты для ручной оплаты", "str", "pay"),
    "topup_min": ("50", "Мин. сумма пополнения", "float", "pay"),
    "order_ttl_min": ("60", "Отмена неоплаченного заказа через, мин", "int", "pay"),
    # выдача
    "delivery_mode": ("manual", "Выдача: manual | fragment | api", "str", "delivery"),
    "delivery_api_url": ("", "URL API выдачи (Fragment-провайдер)", "str", "delivery"),
    "delivery_api_key": ("", "Ключ API выдачи", "str", "delivery"),
    "delivery_retries": ("4", "Попыток автовыдачи (пауза 1, 2, 4... мин)", "int", "delivery"),
    "auto_refund_min": ("0", "Автовозврат на баланс, если не выдано за N мин (0 — выкл)", "int", "delivery"),
    "delivery_balance_url": ("", "URL баланса провайдера (GET → {\"balance\": x})", "str", "delivery"),
    "low_balance_alert": ("0", "Алерт, если баланс для выдачи ниже (TON для fragment)", "float", "delivery"),
    "check_recipient": ("1", "Проверять @username до оплаты", "bool", "delivery"),
    # рефералы
    "ref_percent": ("5", "Реферальный % (1 уровень)", "float", "ref"),
    "ref_percent2": ("1", "Реферальный % (2 уровень)", "float", "ref"),
    "withdraw_min": ("500", "Мин. сумма вывода реферальных", "float", "ref"),
    # антифрод
    "new_user_hours": ("24", "Новый аккаунт — младше N часов", "int", "fraud"),
    "new_user_max_amount": ("5000", "Лимит суммы заказа для нового аккаунта", "float", "fraud"),
    "daily_max_orders": ("10", "Макс. заказов на пользователя в сутки", "int", "fraud"),
    "blacklist": ("", "Чёрный список получателей (через запятую)", "str", "fraud"),
    # каналы
    "required_channel": ("", "Обязательная подписка: @channel или -100id", "str", "channels"),
    "autopost_channel": ("", "Канал автопостинга продаж", "str", "channels"),
    "reviews_channel": ("", "Канал отзывов", "str", "channels"),
    "log_chat_id": ("", "Чат уведомлений (пусто — в личку админам)", "str", "channels"),
    "backup_chat_id": ("", "Чат для ежедневного бэкапа БД", "str", "channels"),
    "remind_after_min": ("15", "Напомнить о неоплаченном заказе через, мин (0 — выкл)", "int", "channels"),
    # языки
    "languages": ("ru,en", "Языки бота (первый — основной)", "str", "lang"),
    "lang_names": ("ru:🇷🇺 Русский,en:🇬🇧 English", "Названия языков", "str", "lang"),
    # система
    "support": ("@support", "Контакт поддержки", "str", "system"),
    "maintenance": ("0", "Режим техработ", "bool", "system"),
    "webapp_url": ("", "URL Mini App витрины (webapp/index.html)", "str", "system"),
}

# key: (название, текст). Плейсхолдеры: {name} {id} {balance} {currency} {rate} ...
SCREENS = {
    "main": ("Главное меню",
             "⭐️ <b>Привет, {name}!</b>\n\n"
             "Покупай Telegram Stars и Premium дешевле, чем в приложении — себе или в подарок.\n\n"
             "💱 Курс: 1 ⭐️ = <b>{rate} {currency}</b>\n"
             "💰 Баланс: <b>{balance} {currency}</b>\n\n"
             "✅ Уже продано <b>{sold_stars} ⭐️</b> · <b>{done_orders}</b> заказов"),
    "buy": ("Выбор пакета", "⭐️ <b>Выберите пакет звёзд</b> или укажите своё количество:"),
    "premium": ("Выбор Premium", "👑 <b>Telegram Premium</b>\n\nВыберите срок подписки:"),
    "ask_amount": ("Ввод количества", "✍️ Введите количество звёзд (от <b>{min_stars}</b> до <b>{max_stars}</b>):"),
    "ask_recipient": ("Ввод получателя",
                      "👤 Кому отправить <b>{product}</b>?\n\nНажмите «Себе» или пришлите @username получателя."),
    "recipient_not_found": ("Получатель не найден",
                            "❌ Пользователь @{recipient} не найден или недоступен. Проверьте username."),
    "checkout": ("Оформление заказа",
                 "🧾 <b>Заказ #{order_id}</b>\n\n"
                 "🛒 Товар: <b>{product}</b>\n"
                 "👤 Получатель: <b>{recipient_display}</b>\n"
                 "💵 К оплате: <b>{amount} {currency}</b>{discount_line}\n\n"
                 "Выберите способ оплаты:"),
    "pay_crypto": ("Оплата CryptoBot",
                   "💎 Счёт на <b>{amount} {currency}</b> создан.\n\n"
                   "Оплатите по кнопке ниже, затем нажмите «Проверить оплату»."),
    "pay_yookassa": ("Оплата ЮKassa",
                     "💳 Счёт на <b>{amount} {currency}</b> создан.\n\n"
                     "Оплатите картой или через СБП по кнопке ниже, затем нажмите «Проверить оплату»."),
    "pay_ton": ("Оплата TON",
                "💎 Переведите <b>{ton_amount} TON</b> на адрес:\n<code>{ton_wallet}</code>\n\n"
                "⚠️ Обязательно укажите комментарий: <code>{ton_comment}</code>\n\n"
                "Оплата проверяется автоматически в течение минуты."),
    "pay_manual": ("Ручная оплата",
                   "💳 Переведите <b>{amount} {currency}</b> по реквизитам:\n\n"
                   "<code>{card}</code>\n\n"
                   "После оплаты пришлите сюда <b>скриншот чека</b>."),
    "receipt_sent": ("Чек отправлен", "⏳ Чек отправлен на проверку. Обычно это занимает до 15 минут."),
    "not_paid": ("Оплата не найдена", "⏳ Оплата пока не поступила. Попробуйте через минуту."),
    "no_balance": ("Мало баланса", "❌ Недостаточно средств. Баланс: <b>{balance} {currency}</b>"),
    "order_paid": ("Заказ оплачен", "✅ Оплата по заказу #{order_id} получена! {product} уже в пути."),
    "order_done": ("Заказ выполнен", "🎉 <b>{product}</b> отправлено на @{recipient}!\n\nСпасибо за покупку 💛"),
    "order_canceled": ("Заказ отменён", "❌ Заказ #{order_id} отменён.{refund_line}"),
    "reminder": ("Напоминание о заказе",
                 "⏰ Вы не завершили заказ #{order_id} — <b>{product}</b> за {amount} {currency}.\n\nПродолжим?"),
    "review_ask": ("Отзыв: оценка", "⭐️ Оцените, пожалуйста, заказ #{order_id}:"),
    "review_text": ("Отзыв: текст", "✍️ Напишите пару слов об опыте покупки или нажмите «Пропустить»."),
    "review_thanks": ("Отзыв: спасибо", "💛 Спасибо за отзыв!"),
    "review_post": ("Пост отзыва в канал", "{rating_stars}\n\n{review_text}\n\n— {name_masked}, {product}"),
    "autopost": ("Пост продажи в канал", "✅ <b>{product}</b> → {recipient_masked}\n⚡️ Выдано автоматически"),
    "topup_ask": ("Пополнение: сумма", "💰 Введите сумму пополнения (от {topup_min} {currency}):"),
    "topup_checkout": ("Пополнение: оплата", "💰 Пополнение на <b>{amount} {currency}</b>\n\nВыберите способ оплаты:"),
    "topup_done": ("Баланс пополнен", "✅ Баланс пополнен на <b>{amount} {currency}</b>."),
    "profile": ("Профиль",
                "👤 <b>Профиль</b>\n\n"
                "🆔 ID: <code>{id}</code>\n"
                "💰 Баланс: <b>{balance} {currency}</b>\n"
                "⭐️ Куплено звёзд: <b>{total_stars}</b>\n"
                "🧾 Заказов: <b>{orders_count}</b>\n\n"
                "🏆 Ваша скидка: <b>{level_discount}%</b>\n{next_level}"),
    "history": ("История заказов", "🧾 <b>Последние заказы</b>\n\n{history}"),
    "referral": ("Рефералы",
                 "👥 <b>Реферальная программа</b>\n\n"
                 "Получайте <b>{ref_percent}%</b> с покупок друзей и <b>{ref_percent2}%</b> с покупок их друзей.\n\n"
                 "🔗 Ваша ссылка:\n<code>{ref_link}</code>\n\n"
                 "Приглашено: <b>{ref_count}</b> (2 уровень: {ref_count2})\n"
                 "Заработано: <b>{ref_earned} {currency}</b>\nДоступно к выводу: <b>{withdraw_available} {currency}</b>"),
    "withdraw_ask": ("Вывод: сумма",
                     "💸 Доступно к выводу: <b>{withdraw_available} {currency}</b>\n"
                     "Минимум: {withdraw_min} {currency}\n\nВведите сумму:"),
    "withdraw_details": ("Вывод: реквизиты", "💳 Пришлите реквизиты для вывода (карта/телефон СБП/кошелёк):"),
    "withdraw_sent": ("Вывод: заявка создана", "⏳ Заявка #{wid} на {amount} {currency} отправлена. Ожидайте."),
    "withdraw_done": ("Вывод: выполнен", "✅ Вывод #{wid} на {amount} {currency} выполнен."),
    "withdraw_rejected": ("Вывод: отклонён", "❌ Вывод #{wid} отклонён, средства возвращены на баланс."),
    "withdraw_unavailable": ("Вывод: недоступен",
                             "Пока нечего выводить: минимум {withdraw_min} {currency}, доступно {withdraw_available}."),
    "promo_ask": ("Ввод промокода", "🎟 Отправьте промокод:"),
    "promo_ok": ("Промокод принят", "✅ Промокод <b>{code}</b> активирован: скидка <b>{discount}%</b> на следующий заказ."),
    "promo_bad": ("Промокод неверный", "❌ Промокод не найден, истёк или уже использован."),
    "bad_input": ("Неверный ввод", "⚠️ Неверное значение, попробуйте ещё раз."),
    "limit_reached": ("Антифрод-лимит", "⛔️ Превышен лимит заказов. Напишите в поддержку: {support}"),
    "lang": ("Выбор языка", "🌐 Выберите язык / Choose language:"),
    "faq": ("FAQ",
            "❓ <b>Частые вопросы</b>\n\n"
            "<b>Как быстро приходят звёзды?</b>\nОбычно 1–5 минут после оплаты.\n\n"
            "<b>Нужен ли доступ к аккаунту?</b>\nНет, только @username получателя.\n\n"
            "<b>Можно ли подарить?</b>\nДа, укажите username друга при оформлении.\n\n"
            "<b>Что если звёзды не пришли?</b>\nДеньги вернутся на баланс автоматически, либо напишите в поддержку."),
    "support": ("Поддержка", "💬 По любым вопросам пишите: {support}"),
    "subscribe": ("Обязательная подписка", "📢 Чтобы пользоваться ботом, подпишитесь на наш канал."),
    "maintenance": ("Техработы", "🛠 Бот на технических работах. Загляните чуть позже."),
    "banned": ("Бан", "⛔️ Доступ ограничен."),
    "alert_stale": ("Алерт: заказ неактуален", "Заказ уже неактуален"),
    "alert_no_username": ("Алерт: нет username", "У вас нет username — укажите получателя вручную"),
    "alert_pay_unavailable": ("Алерт: оплата недоступна", "Способ оплаты временно недоступен, выберите другой"),
}

SCREENS_EN = {
    "main": "⭐️ <b>Hi, {name}!</b>\n\nBuy Telegram Stars and Premium cheaper than in the app — for yourself or as a gift.\n\n"
            "💱 Rate: 1 ⭐️ = <b>{rate} {currency}</b>\n💰 Balance: <b>{balance} {currency}</b>\n\n"
            "✅ Already sold <b>{sold_stars} ⭐️</b> · <b>{done_orders}</b> orders",
    "buy": "⭐️ <b>Choose a stars package</b> or enter your own amount:",
    "premium": "👑 <b>Telegram Premium</b>\n\nChoose subscription period:",
    "ask_amount": "✍️ Enter the number of stars (from <b>{min_stars}</b> to <b>{max_stars}</b>):",
    "ask_recipient": "👤 Who should receive <b>{product}</b>?\n\nTap «Myself» or send the recipient's @username.",
    "recipient_not_found": "❌ User @{recipient} not found. Please check the username.",
    "checkout": "🧾 <b>Order #{order_id}</b>\n\n🛒 Item: <b>{product}</b>\n👤 Recipient: <b>{recipient_display}</b>\n"
                "💵 To pay: <b>{amount} {currency}</b>{discount_line}\n\nChoose a payment method:",
    "pay_crypto": "💎 Invoice for <b>{amount} {currency}</b> created.\n\nPay with the button below, then tap «Check payment».",
    "pay_yookassa": "💳 Invoice for <b>{amount} {currency}</b> created.\n\nPay with the button below, then tap «Check payment».",
    "pay_ton": "💎 Send <b>{ton_amount} TON</b> to:\n<code>{ton_wallet}</code>\n\n"
               "⚠️ Comment is required: <code>{ton_comment}</code>\n\nPayment is detected automatically within a minute.",
    "pay_manual": "💳 Transfer <b>{amount} {currency}</b> to:\n\n<code>{card}</code>\n\nThen send a <b>screenshot of the receipt</b> here.",
    "receipt_sent": "⏳ Receipt sent for review. Usually takes up to 15 minutes.",
    "not_paid": "⏳ Payment not received yet. Try again in a minute.",
    "no_balance": "❌ Insufficient funds. Balance: <b>{balance} {currency}</b>",
    "order_paid": "✅ Payment for order #{order_id} received! {product} is on its way.",
    "order_done": "🎉 <b>{product}</b> sent to @{recipient}!\n\nThank you for your purchase 💛",
    "order_canceled": "❌ Order #{order_id} canceled.{refund_line}",
    "reminder": "⏰ You didn't finish order #{order_id} — <b>{product}</b> for {amount} {currency}.\n\nContinue?",
    "review_ask": "⭐️ Please rate order #{order_id}:",
    "review_text": "✍️ Write a few words about your experience or tap «Skip».",
    "review_thanks": "💛 Thanks for your feedback!",
    "topup_ask": "💰 Enter top-up amount (from {topup_min} {currency}):",
    "topup_checkout": "💰 Top-up of <b>{amount} {currency}</b>\n\nChoose a payment method:",
    "topup_done": "✅ Balance topped up by <b>{amount} {currency}</b>.",
    "profile": "👤 <b>Profile</b>\n\n🆔 ID: <code>{id}</code>\n💰 Balance: <b>{balance} {currency}</b>\n"
               "⭐️ Stars bought: <b>{total_stars}</b>\n🧾 Orders: <b>{orders_count}</b>\n\n"
               "🏆 Your discount: <b>{level_discount}%</b>\n{next_level}",
    "history": "🧾 <b>Recent orders</b>\n\n{history}",
    "referral": "👥 <b>Referral program</b>\n\nEarn <b>{ref_percent}%</b> from friends' purchases and "
                "<b>{ref_percent2}%</b> from their friends.\n\n🔗 Your link:\n<code>{ref_link}</code>\n\n"
                "Invited: <b>{ref_count}</b> (level 2: {ref_count2})\nEarned: <b>{ref_earned} {currency}</b>\n"
                "Available to withdraw: <b>{withdraw_available} {currency}</b>",
    "withdraw_ask": "💸 Available: <b>{withdraw_available} {currency}</b>\nMinimum: {withdraw_min} {currency}\n\nEnter amount:",
    "withdraw_details": "💳 Send payout details (card / phone / wallet):",
    "withdraw_sent": "⏳ Withdrawal #{wid} for {amount} {currency} submitted.",
    "withdraw_done": "✅ Withdrawal #{wid} for {amount} {currency} completed.",
    "withdraw_rejected": "❌ Withdrawal #{wid} rejected, funds returned to balance.",
    "withdraw_unavailable": "Nothing to withdraw yet: minimum {withdraw_min} {currency}, available {withdraw_available}.",
    "promo_ask": "🎟 Send a promo code:",
    "promo_ok": "✅ Promo code <b>{code}</b> activated: <b>{discount}%</b> off your next order.",
    "promo_bad": "❌ Promo code not found, expired or already used.",
    "bad_input": "⚠️ Invalid value, please try again.",
    "limit_reached": "⛔️ Order limit exceeded. Contact support: {support}",
    "lang": "🌐 Выберите язык / Choose language:",
    "faq": "❓ <b>FAQ</b>\n\n<b>How fast are stars delivered?</b>\nUsually 1–5 minutes after payment.\n\n"
           "<b>Do you need access to my account?</b>\nNo, only the recipient's @username.\n\n"
           "<b>Can I send as a gift?</b>\nYes, enter your friend's username at checkout.",
    "support": "💬 Any questions — contact {support}",
    "subscribe": "📢 Please subscribe to our channel to use the bot.",
    "maintenance": "🛠 The bot is under maintenance. Please come back later.",
    "banned": "⛔️ Access restricted.",
    "alert_stale": "This order is no longer active",
    "alert_no_username": "You don't have a username — enter the recipient manually",
    "alert_pay_unavailable": "This payment method is temporarily unavailable",
}

# Кастомные кнопки экранов. (screen, row, pos, emoji, text, action, value[, enabled])
BUTTONS = [
    ("main", 0, 0, "⭐️", "Купить звёзды", "func", "buy"),
    ("main", 1, 0, "🎁", "Подарить другу", "func", "gift"),
    ("main", 1, 1, "👑", "Premium", "func", "premium"),
    ("main", 2, 0, "🛍", "Витрина", "webapp", "{webapp_link}", 0),
    ("main", 3, 0, "👤", "Профиль", "func", "profile"),
    ("main", 3, 1, "👥", "Рефералы", "func", "referral"),
    ("main", 4, 0, "🎟", "Промокод", "func", "promo"),
    ("main", 4, 1, "❓", "FAQ", "screen", "faq"),
    ("main", 5, 0, "💬", "Поддержка", "screen", "support"),
    ("buy", 9, 0, "◀️", "Назад", "screen", "main"),
    ("premium", 9, 0, "◀️", "Назад", "screen", "main"),
    ("profile", 9, 0, "◀️", "Назад", "screen", "main"),
    ("referral", 9, 0, "◀️", "Назад", "screen", "main"),
    ("faq", 9, 0, "◀️", "Назад", "screen", "main"),
    ("support", 9, 0, "◀️", "Назад", "screen", "main"),
    ("history", 9, 0, "◀️", "Назад", "func", "profile"),
    ("order_done", 0, 0, "⭐️", "Купить ещё", "func", "buy"),
    ("autopost", 0, 0, "⭐️", "Купить звёзды", "url", "https://t.me/{bot_username}"),
    ("review_post", 0, 0, "⭐️", "Купить звёзды", "url", "https://t.me/{bot_username}"),
]
BUTTONS_EN = {"Купить звёзды": "Buy stars", "Подарить другу": "Gift to a friend", "Витрина": "Shop",
              "Профиль": "Profile", "Рефералы": "Referrals", "Промокод": "Promo code", "Поддержка": "Support",
              "Назад": "Back", "Купить ещё": "Buy more"}

# Системные кнопки, которые бот генерирует сам. key: (emoji, text, en_text)
SYS_BUTTONS = {
    "package": ("⭐️", "{stars} — {price} {currency}", "{stars} — {price} {currency}"),
    "premium_package": ("👑", "{months} мес. — {price} {currency}", "{months} mo. — {price} {currency}"),
    "custom_amount": ("✍️", "Своё количество", "Custom amount"),
    "to_self": ("🙋", "Себе", "Myself"),
    "pay_balance": ("💰", "С баланса ({balance} {currency})", "From balance ({balance} {currency})"),
    "pay_crypto": ("💎", "CryptoBot", "CryptoBot"),
    "pay_yookassa": ("💳", "Карта / СБП", "Card"),
    "pay_ton": ("💠", "TON", "TON"),
    "pay_manual": ("🏦", "Перевод на карту", "Bank transfer"),
    "pay_link": ("🔗", "Оплатить", "Pay"),
    "ton_link": ("💠", "Открыть Tonkeeper", "Open Tonkeeper"),
    "copy_address": ("📋", "Скопировать адрес", "Copy address"),
    "copy_comment": ("📋", "Скопировать комментарий", "Copy comment"),
    "check_payment": ("🔄", "Проверить оплату", "Check payment"),
    "cancel": ("❌", "Отменить", "Cancel"),
    "continue": ("▶️", "Продолжить", "Continue"),
    "history": ("🧾", "История заказов", "Order history"),
    "topup": ("💰", "Пополнить баланс", "Top up balance"),
    "change_lang": ("🌐", "Язык / Language", "Язык / Language"),
    "share_ref": ("📤", "Поделиться ссылкой", "Share link"),
    "withdraw": ("💸", "Вывести", "Withdraw"),
    "review_skip": ("➡️", "Пропустить", "Skip"),
    "subscribe_channel": ("📢", "Подписаться", "Subscribe"),
    "subscribe_check": ("✅", "Я подписался", "I've subscribed"),
    "menu": ("🏠", "В меню", "Menu"),
}

PACKAGES = [("stars", 50, None), ("stars", 100, None), ("stars", 250, None), ("stars", 500, None),
            ("stars", 1000, None), ("stars", 2500, None),
            ("premium", 3, 1290), ("premium", 6, 1690), ("premium", 12, 2990)]

# Встроенные функции, которые можно повесить на любую кнопку
FUNCS = {
    "buy": "Покупка звёзд (пакеты)",
    "buy_custom": "Своё количество звёзд",
    "gift": "Подарок звёзд другу",
    "premium": "Telegram Premium",
    "profile": "Профиль",
    "history": "История заказов",
    "referral": "Рефералы",
    "withdraw": "Вывод реферальных",
    "promo": "Ввод промокода",
    "topup": "Пополнение баланса",
    "lang": "Смена языка",
    "menu": "Главное меню",
}

# Права оператора (роль operator): только эти разделы админки
OPERATOR_PREFIXES = ("ad:menu", "ad:ord", "ad:o:", "ad:op:", "ad:od:", "ad:or:", "ad:oc:", "ad:wd", "ad:wl")
