# Соня — передача проекта в новый чат

Прочти это целиком. В архиве: `sonya/` — актуальный код (= волна 52), `tests/` — тесты, `sonya_promo_kit.md` — продвижение.

## Кто я и как работаем
- Тим, ИП, делаю Telegram-ботов. Работаю **только с телефона через Termius**, команды выполняю по шагам.
- Отвечать: по-русски, коротко, с юмором, без пересказов и чек-листов.
- Код для `nano` и команды терминала — **в разных блоках**. Команды установки — в чат, не в zip.
- Каждое обновление — **отдельный zip с новым именем** `sonya_waveNN_*.zip` (следующая — **wave53**). Старые не перезаписывать.
- В zip **не класть** `.env`, `data/`, `__pycache__`.
- Всё новое — в `/help` (`ui.HELP` / `HELP_SECTIONS`, лимит 4096 символов на раздел).
- Прежде чем описывать возможность бота — проверить в коде.
- Токены в чат не просить — Тим вставляет их в `.env` сам. Не советовать покупать «рефералов».

## Сервер
- Код: `/home/sonya/sonya`, юзер `sonya`, служба `sonya` (systemd).
- `ExecStart=/home/sonya/sonya/venv312/bin/python main.py`, `WorkingDirectory=/home/sonya/sonya`.
- venv от uv, pip поставлен через `python -m ensurepip`. `uv` в PATH нет.
- Zip-ы Тим кладёт в `/root/`. Шаблон установки:
```
systemctl stop sonya
unzip -o /root/sonya_waveNN_xxx.zip -d /home/sonya/sonya
chown -R sonya:sonya /home/sonya/sonya
systemctl start sonya
sleep 5; journalctl -u sonya -n 10 --no-pager
```
- Новые pip-зависимости: `/home/sonya/sonya/venv312/bin/python -m pip install ...`
- Серверу нужен reboot (давно висит).

## Стек
Python 3.12, aiogram 3.31, SQLite (aiosqlite).
- Новые таблицы — в `db.SCHEMA_V14`/`V15`, новые колонки — ALTER в `db.init()`.
- ИИ: Groq через OpenAI-совместимый API. Цепочка: основная → `LLM_MODEL_FALLBACK` → второй провайдер (`LLM_URL_2`/`LLM_KEY_2`/`LLM_MODEL_2`).
- Зрение: `qwen/qwen3.8-27b` с `reasoning_effort: "none"` (preview — может пропасть). Картинку Соня сама качает и шлёт data-URL.
- Рисование: pollinations, с `POLLINATIONS_TOKEN` → `gen.pollinations.ai/image/` (ключ берут на enter.pollinations.ai/keys).
- Стриминг: `send_message_draft` в личке, при ошибке — правки.
- Эфемерные ответы в группах: `ui.personal()` (`EphemeralMessageParameters`), фолбэк — обычный reply.
- edge-tts 6.1 без `pitch` — обёрнуто в try/except.

Переменные окружения: BOT_TOKEN OWNER_ID LLM_KEY LLM_URL LLM_MODEL LLM_MODEL_FALLBACK LLM_URL_2 LLM_KEY_2 LLM_MODEL_2 LLM_VISION_MODEL SEARCH_MODEL STREAM STT_URL STT_KEY STT_MODEL POLLINATIONS_TOKEN VK_TOKEN YTDLP_COOKIES AI_DAY_LIMIT AI_DAY_LIMIT_PLUS FREE_CHANNELS REQUIRED_CHANNEL BOT_PROFILE DB_FILE MAIN_BOT.
Config использует `setdefault` — переменные systemd перекрывают `.env`.

## Дизайн и UI
- `ui.py`: `head`, `quote` (blockquote), `stats`, `hint`, `tog` ✅/⬜, `LINE`, `share_url`, `personal`.
- Кнопки «›» открывают список выбора. В помощи — «‹ Разделы» и «‹ Меню», окна не путать.
- `uikit`: экран узнаётся по первой строке текста, кнопка — по callback + тексту.
- `ap_common.kb_rows`: data с http(s):// или tg:// → URL-кнопка.

## Карта модулей
- `main.py` — `routers_for(profile)`, `SOLO_CMDS`, `setup_commands` (чистит чужие команды во всех scope/языках).
- `limits.py`, `achievements.py`, `handlers/life.py` — ДР, /stats, /ach, nudge.
- `handlers/fun.py` — задания (asyncio.Lock на юзера), браки, питомец, дуэль, лотерея, сезоны.
- `handlers/aigames.py` — акинатор, крокодил, правда/действие, эмодзи-песня.
- `handlers/character.py` — /mode, /search. `handlers/chat.py` — болтовня, стриминг.
- `handlers/community.py` — правила, заметки, тишина, итоги дня, AntiSpam, /welcome, clean_service, /report.
- `handlers/studio.py` — мем, кружок, gif, cut, qr, конвертер, крипта, документы.
- `handlers/luck.py` — колесо, блэкджек, гороскоп. `handlers/rp.py` — РП, /pair, /hero (флаг `rp` в chats).
- `handlers/gate.py` — обязательная подписка. `handlers/admin.py` — /admin, «Сервер» (кнопка «⬆️ Обновить yt-dlp»), «📝 Профиль бота» (BOT_SHORT/BOT_DESC/BIO).
- `handlers/solo.py` — узкие боты. `handlers/media.py` — скачивание, альбомы, TikTok/Pinterest-карусели.
- `downloader/core.py` — yt-dlp, `tiktok_photos` (tikwm API → страница TikTok), `resolve_redirect`, `fetch_bytes`.
- Автопостинг: `autopost/*`, `handlers/ap_*.py`. Pinterest: внутренний API (как gallery-dl), `BaseSearch` без входа работает, `RelatedPinFeed` без входа отдаёт 0 → «похожие» сделаны поиском по ключевым словам пина. Карусели: `carousel_data.carousel_slots[].images`. Фильтр фото/видео под тип канала. dHash-дедуп и водяной знак — `autopost/imgtools.py`.

## Боты (один код, разные профили BOT_PROFILE)
| профиль | служба | env | что это |
|---|---|---|---|
| full | sonya | .env | Соня — всё |
| dl | sonya-dl | dl.env | скачивалка видео |
| music | sonya-music | music.env | музыка (@SonyaMusicruBot) |
| gw | sonya-gw | gw.env | розыгрыши |
| games | sonya-games | games.env | игры для чатов |
| anon | sonya-anon | anon.env | анонимные вопросы |
| grp | sonya-grp | grp.env | помощник для групп: модерация + голосовые в текст (волна 44) |
| stk | sonya-stk | stk.env | стикеры и эмодзи-паки из картинок (волна 44) |
Каждый env: BOT_TOKEN, BOT_PROFILE, DB_FILE (свою базу в data/). Юнит = копия sonya.service + `EnvironmentFile=/home/sonya/sonya/<x>.env` перед ExecStart.
`main.routers_for(profile)` — какие роутеры у профиля; `SOLO_CMDS` — меню команд; `admin.BIO` — описания; `solo.py` — стартовые экраны узких ботов.
**После любого обновления:** `systemctl restart sonya sonya-dl sonya-music sonya-gw sonya-games sonya-anon sonya-grp sonya-stk`
Память: 1.9 ГБ + swap 1 ГБ. Каждый бот ~175 МБ — почти всё это сам aiogram (код Сони ~12 МБ), поэтому ленивые импорты не помогут; экономия только объединением процессов (большая переделка, решили не делать). После 8 ботов available ~300 МБ.

## Что сделано в волнах 28–42
- 28: тексты песен (lrclib), инлайн у помощников, экран «🤝 Помощники».
- 29–30: музыка: каталог (Яндекс→Deezer→YouTube; Яндекс с сервера 451 — отключается на 6ч), список с номерами, обложки, ❤️ мои, похожие, чарт, эффекты slowed/8D/bass (ffmpeg), рингтон, «угадай мелодию», /taste карточка, релизы артистов, «что за песня в видео».
- 31–32: видео: качество, без сжатия, кружок, GIF, обрезка, инфо, обложка, текст из видео, /history, прогресс %, очередь, tikwm-запасной для TikTok, журнал скачиваний, автообновление yt-dlp. 32b: YouTube 403 → перебор player_client.
- 33: трек/текст в комментариях канала, живые команды «Сонь, …» (quick.py, intents.py).
- 34: «📤 В канал» под скачанным, трек в подписи видео-поста.
- 35: монетизация: premium.py — лимиты (эффекты/текст из видео 3/день, HD и подписки), пробная Соня+ 3 дня, подписка 99⭐/мес (create_invoice_link subscription_period), приоритет очереди, «💰 Доходы». FREE_CHANNELS/FREE_SOURCES в .env (0 = без лимита).
- 36: фонд звёзд на подарки (gifts.py, /fund), розыгрыш подарков Telegram (sendGift), победитель выбирает.
- 37–39: розыгрыши (giveaway.py): спонсоры, билеты за друзей, Premium, итоги по числу, картинка/видео, перевыбор, отмена с возвратом, капча, отсев ботов, бусты, подтверждение победы 24ч, CSV, хэш итогов заранее (commit-reveal) + /check, призы по местам, отложенный старт, повтор, прирост подписчиков, «через @бот», итоги проигравшим.
- 40: fleet.py — здоровье всех ботов, сердцебиение и тревога, бэкап всех баз zip в 4:00, рассылка через всех помощников.
- 41: боты games и anon. 42: анонимки — темы ссылок, картинки для сторис (anoncards.py, QR), карточка «вопрос-ответ», /inbox.
- 43: свой Bot API (`tgapi.py`): BOT_API_URL → файлы до 2 ГБ (TG_SEND_MB / TG_GET_MB). 43b: сначала проверяем свой сервер, потом logOut из облака; сервер лежит → работаем через облако и тревога владельцу. **Не включён**: my.telegram.org не выдаёт api_id (ERROR) — нужен другой номер. Скрипт `tgkey.py` (вход один раз). Долбилку с рандомными именами НЕ делать.
- 44: Соня+ одна на все боты: помощники читают `plus_until` из базы Сони (`extra.main_until`, MAIN_DB_PATH, кэш 60 с), покупка только в Соне (`?start=plus`). Лимиты теперь и в помощниках. Новое платное: видео > 30 мин (звук — всем), розыгрыш без «через @бот». Боты grp (`handlers/grp.py`: голосовые 20/день на чат, до 5 мин; 💎 ИИ-антиспам и итоги дня — если плюс у любого админа) и stk (`handlers/stickers.py`: 1 пак, 30 штук, без видео, подпись бота в названии; с плюсом — без лимитов). `/bots` в Соне — все помощники со ссылками.
- 45: улучшения новых ботов (games/anon/grp/stk; старые 4 — Соня, скачалка, музыка, розыгрыши — не трогали). Мафия: мёртвые молчат и ночью тишина (удаление сообщений), ⏱ спокойный темп в лобби, /gstats (таблица game_stats). Группы: 🤬 антимат (`profanity.py`, колонка chats.antimat), «✅ Не спам» под ИИ-антиспамом (kv trust:chat:uid), /top за неделю. Стикеры: ✂️ вырезание однотонного фона + белая обводка (floodfill от углов, kv stk:cut), текст → стикер-цитата (tools.quote_image), чужой стикер → «в мой пак» / «скачать PNG», «поделиться» паком. Анонимки: 🔒 «авторов не раскрываю ни за что», 🤬 не принимать мат (anon_links.nomat). Для NEW_BOTS — middlewares.Throttle (личка/кнопки) и RetryAfter (повтор в сессии).
- 46: анонимки — маски (anon_masks: owner+sender → «🦊 Хитрый Лис», постоянная у этого получателя, у другого — своя; 320 комбинаций, дальше номер; ✏️ подпись видна только получателю), ответ приходит реплаем на вопрос и с именем, «↩️ Ответить» — переписка веткой (anon_msgs.src_mid/dlv_mid/ans_mid/parent), /inbox по маскам. 🎲 Случайный анонимный чат `handlers/anonchat.py` (/chat /next /stop): 16+ и правила, темы, ссылки/@ники не передаём, медиа после 5 сообщений от каждого и под спойлером, 👍/👎, жалоба → пару не сводим, 3 жалобы за сутки → бан 7 дней + сигнал владельцу; поиск по полу — Соня+ (пол самоназванный). Очередь и пары — в памяти (рестарт обрывает чаты).
- 46b: маски сгорают после ANON_MASK_HOURS (по умолчанию 2 ч) тишины в паре — таблица anon_masks2 (активна одна маска на пару, старые 💤 остаются отдельными ветками; anon_msgs.mask_id). Ответ в старой ветке (parent) возвращает старую маску. Сгоревшие маски 7 дней не выдаются другим. Подпись сгорает с маской.
- 47: «Интерфейс 2.0» в новых ботах. kb_rows понимает 3-й элемент — стиль кнопки (success/danger/primary, Bot API 9.4). Анонимки: одно событие = одно сообщение (anon.deliver: текст в цитате, у медиа шапка в подписи), подсказка «напиши…» удаляется после отправки, подтверждение коротко реплаем, длинные подсказки — один раз (anon.first_time, kv seen:*), главная компактная, настройки отдельным экраном (an:set), входящие/ветка/меню чата — правкой того же сообщения (ap_common.show). Стикеры: короткий старт, подробности по «❔».
- 48: анонимки — 👁 «прочитано» без ответа (anon_msgs.seen; ответ = прочитано; открыл ветку = прочитал) и «✅ Прочитать всё» во входящих; 👀 счётчик переходов по ссылке (kv an:visits:uid, свои не считаем); 🙋 «Раскрыться» — только сам автор, с подтверждением, маска подписывается его именем. 🎨 Редактор сторис (an:sc:*): 8 градиентов, своё фото фоном (kv an:sphoto), 8 шрифтов с кириллицей в assets/fonts (Google Fonts, OFL), плашка светлая/стекло/тёмная, свой текст, тема; правка той же картинкой (edit_media); стиль в kv an:style:uid, карточка ответа рисуется тем же стилем.
- 49: анонимки — реакции ❤️😂🔥😮 под сообщением (anon_msgs.react, автору приходит «❤️ Тим отреагировал(а)», повтор не шлём); «оцени меня» — кнопки 1–10 (an:rt), оценка и словами (anon_msgs.score), карточка рейтинга anoncards.rating_card (an:rating, кнопка на главной); 💡 вопрос дня в 12:00 МСК (anon.loop, тем, кто был активен 14 дней и daily=1), 🌙 ночью 23–8 без звука + ☀️ сводка в 8:00 (anon_links.quiet); срок маски выбирает получатель (anon_links.mask_hours: 2/24/168), аноним может взять «🎭 Новую маску» (блок всё равно по человеку). Анонимный чат: 🙋 взаимное раскрытие — только если оба нажали.
- 50: маска живёт ровно 12 ч с последнего сообщения (ANON_MASK_HOURS, по умолчанию 12); выбор срока 2/24/168 и кнопка an:mh убраны, колонка mask_hours больше не читается. Исследование: маски = «ID на тред» как на 4chan — работает; главная ненависть к конкурентам (NGL и т.п.) — фейковые сообщения и платные «подсказки, кто написал» → у нас этого нет и не будет. Идеи на потом: «🦊 Лис · 3 сообщения», строка «все сообщения от живых людей».
- 51: стикер-бот «богатый» (handlers/stickers.py переписан, bgcut.py новый). После добавления бот присылает сам стикер с карточкой (kv stk:card:<tok>, кнопки stk:c:<act>:<tok>): 😀 эмодзи (setStickerEmojiList, ✍️ свои до 20), ✂️ без фона/↩️ с фоном (replaceStickerInSet на том же месте), ⬅️ первым (setStickerPositionInSet), 🖼 обложка (setStickerSetThumbnail / setCustomEmojiStickerSetThumbnail), 🗑. Умный фон — нейросеть u2netp (bgcut.py, ОТДЕЛЬНЫЙ процесс, пик ~240 МБ, запускается только при MemAvailable ≥ STK_SMART_MIN_MB=320, по одной картинке); нет модели/onnxruntime/памяти — однотонный фон как раньше; всегда белая обводка + тень. Подпись к картинке → надпись на стикере (RussoOne) + keywords; альбомы — пачкой с одним прогрессом (ALBUM_WAIT 1.5 с); кружок → круглый видео-стикер (geq alpha), видео 3–10 с ускоряется до 3 с; экран пака stk:p (прогресс, 👀 витрина-картинка stk:v, удалить пак stk:pd → stk:pdy); «📦 Весь пак себе» stk:cp — только Соня+ (копия по file_id, 50 сразу + остальные). Лимиты: stk_video 3/день бесплатно (было 0), stk_cut 10/день, stk_copy — плюс. Модель: data/models/u2netp.onnx (в zip не кладём — data/). По отзывам: людей бесят реклама, водяные знаки, платное после факта — у нас этого нет.
- 52: редакторы пака (handlers/stkedit.py, роутер перед stickers). Мастер нового пака: stk:new:<kind> → kv stk:wiz:<uid> {k,t,s,st}: шаг 1 название (текст или 🎲 stk:wt — шаблоны TITLES с именем), шаг 2 ссылка (текст → clean_slug: транслит, латиница/цифры/_, с буквы, без «__», ≤64 с хвостом _by_<бот>; проверка занятости в базе и getStickerSet; 🎲 stk:ws), ✅ stk:wok; «⚡ Всё случайно» stk:wr. Картинки во время мастера придерживаются (_pending) и идут в пак после ✅. Уход на главную сбрасывает мастер. 🛠 Инструменты stk:t (только хозяин): 🔗 новая ссылка stk:mv/stk:mvy (перенос: копия по file_id + deleteStickerSet старого), 📥 архив stk:zip (PNG/WEBM/TGS, доступен и соавтору), 🧩 эмодзи-версия stk:ev (Соня+, stk_emojiver), 👥 соавторы stk:co (таблица sticker_coauthors, приглашение /start stkj_<pid>_<код из kv stk:inv:<pid>>, 🔄 новый код, 🚫 убрать всех; соавтор добавляет стикеры с user_id хозяина, лимит — по Соне+ хозяина, может выйти stk:leave). Переименовать/удалить/инструменты — только хозяин.
- Правило UI: навигацию — edit, а не новое сообщение; кнопки короткие, по 2–3 в ряд; главное действие зелёным, опасное красным; простыни — только в первый раз.
- «Кто задал вопрос» в анонимках за деньги — НЕ делать (деанон). Конкуренты на этом теряют доверие.
- ВПН — решили НЕ делать (закон о рекламе VPN, риск для Сони). Казино на звёздах — не делать.

## Открыто / идеи
- Волна 44 — Тим ставит. Нужны 2 токена от BotFather (grp, stk), у grp выключить privacy (/setprivacy → Disable).
- Свой Bot API — ждёт api_id с другого номера.
- Fragment-юзернейм без «bot» — на будущее; пока канал-витрина.
- Свой Bot API (BOT_API_URL) для файлов до 2 ГБ — по желанию.

## Тесты
`tests/harness.py` — мок-сессия aiogram (SENT, ADMINS, LEFT, DICE), `setup()` собирает диспетчер как main.
Запуск (из папки tests, venv с requirements.txt):
```
python test_w27.py ../sonya full
BOT_PROFILE=dl python test_w27.py ../sonya dl
BOT_PROFILE=gw python test_w39.py ../sonya gw
BOT_PROFILE=anon python test_w42.py ../sonya anon
python test_w43.py ../sonya
BOT_PROFILE=grp python test_w44.py ../sonya grp   # и full / dl / stk
BOT_PROFILE=games python test_w45.py ../sonya games   # и grp / stk / anon
BOT_PROFILE=anon python test_w46.py ../sonya
python smoke.py ../sonya          # и с BOT_PROFILE=dl/music/gw/games/anon/grp/stk
```
Первый аргумент — путь к коду. Регрессия — все `test_*.py` подряд.

## Грабли, на которые уже наступали
- Путь установки — `/home/sonya/sonya`, не `/home/sonya`.
- aiogram «проглатывает» апдейт, если хендлер сматчился и сделал return — условия выносить в фильтры.
- `m.answer(*tuple)` с клавиатурой — клавиатура улетает в parse_mode.
- Не выдумывать адреса сервисов — проверять.
- Тесты с python stdout в пайп: запускать `python -u … > log`, иначе при таймауте вывод теряется.
- ffmpeg-тесты (эффекты, кружок) используют настоящий ffmpeg.
- В .env токены не просить в чат.
- В тестах владелец (OWNER_ID=1) всегда с Соней+ — не клади его в админы группы, если проверяешь лимиты.
- BOT_API_URL без поднятого сервера раньше валил бота (43b исправил).
