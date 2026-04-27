# ЛЕРА — Игровой компаньон (Telegram Mini App)

## Общий контекст
Тим (@em_salatik, tg_id: 8171156371) — независимый разработчик, работает с телефона через Termius SSH.
Два проекта: **Лера** (HoK игровой компаньон + социальная сеть геймеров) и **Соня** (AI бот).

---

## Серверная инфраструктура

### Сервер Лера: `sportingtan` (62.60.235.252)
- Пользователь: `root`
- **Лера бот:** `/root/ler/`, venv: `~/ler/venv/`, БД: `~/ler/data/lera_bot.db`
- **Мини-апп:** `/opt/lera-miniapp/lera-miniapp/`
  - FastAPI: `miniapp_api.py` (порт 23054, 2 workers)
  - Фронтенд: `miniapp/` (React/Vite сборка)
  - Исходники Replit: `/root/replit-src.zip` → собирается в `/opt/lera-build/`
  - systemd: `lera-miniapp.service`
  - nginx: `app.lerarubot.ru` → `127.0.0.1:23054`
- **Bot token:** `8568968489:AAH-Isqdtl9bXsQEuqFQm9BLMLPVN-8OPMc`
- **Admin:** tg_id `8171156371`

### Сервер Соня: `roughbronze`, пользователь `botmaster`, `~/sonya_bot/`

---

## Архитектура мини-аппа

### Бэкенд (miniapp_api.py)
FastAPI + aiosqlite, использует `~/ler/data/lera_bot.db` (симлинк).

**Ключевые эндпоинты:**
- `/api/me` — профиль текущего пользователя
- `/api/duet/*` — система дуэта (поиск тиммейтов)
- `/api/squads/*` — лобби (отряды)
- `/api/profile/*` — профиль, фото
- `/api/inventory`, `/api/shop`, `/api/gacha/*` — инвентарь, магазин
- `/api/checkin`, `/api/leaderboard/*`, `/api/feed/*`, `/api/wiki/*`

**Важный баг:**
`lfg_lobbies.id` — `INTEGER AUTOINCREMENT`, код Replit пытается вставить hex-строку → `datatype mismatch`.
Фикс в `fix_build.py`: убирать `"id"` из списка fields при INSERT, использовать `cur.lastrowid`.

### Фронтенд (React/Vite/TypeScript)
Исходники от Replit в `/root/replit-src.zip`.
Сборка через `/root/build.sh` → `/root/fix_build.py`.

**Структура src/:**
- `pages/`: PartnerPage, SquadPage, ProfilePage, ChatsPage, FeedPage, WikiPage, GachaPage, ShopPage, PremiumPage, HelpPage
- `context/`: UserContext, SquadsContext, VoiceContext, ChatContext, MatchContext, WalletContext, PhotoContext, PostsContext
- `lib/`: leraApi.ts, api.ts, ui.tsx

**Известная проблема сборки (TDZ/circular deps):**
- Rollup при сборке в один чанк создаёт TDZ для переменных (`'oe' before initialization`, `'se' before initialization`)
- Решение: `manualChunks: () => "index"` в vite.config.ts + переместить `filters` useState перед `apiCards` useEffect в PartnerPage
- ProfilePage импортирует GachaPage, ShopPage, HelpPage, PremiumPage → делать их lazy
- ShopPage импортирует GachaPage → делать lazy
- PartnerPage импортирует DuoProfileEditor из ProfilePage → заменить на динамический компонент `LazyDuoEditor`

---

## /root/build.sh — Главный скрипт сборки
```bash
#!/bin/bash
set -e
ZIP="/root/replit-src.zip"
BUILD="/opt/lera-build"
MINIAPP="/opt/lera-miniapp/lera-miniapp/miniapp"
rm -rf $BUILD && mkdir -p $BUILD
unzip -o $ZIP -d /tmp/replit-src/ > /dev/null
cp -r /tmp/replit-src/home/runner/workspace/artifacts/lera-app/miniapp-src/. $BUILD/
cp /opt/lera-miniapp/lera-miniapp/miniapp-src/package.json $BUILD/
cp /opt/lera-miniapp/lera-miniapp/miniapp-src/vite.config.ts $BUILD/
cp /opt/lera-miniapp/lera-miniapp/miniapp-src/tsconfig*.json $BUILD/
cp -r /opt/lera-miniapp/lera-miniapp/miniapp-src/public $BUILD/
cp /opt/lera-miniapp/lera-miniapp/miniapp-src/index.html $BUILD/
cd $BUILD
pnpm install --silent 2>/dev/null
pnpm add --silent @radix-ui/react-alert-dialog @radix-ui/react-aspect-ratio @radix-ui/react-collapsible @radix-ui/react-context-menu @radix-ui/react-hover-card @radix-ui/react-menubar @radix-ui/react-navigation-menu @radix-ui/react-toggle @radix-ui/react-toggle-group react-day-picker embla-carousel-react cmdk react-hook-form input-otp react-resizable-panels next-themes 2>/dev/null
python3 /root/fix_build.py
pnpm build 2>&1 | tail -5
cp dist/assets/* $MINIAPP/assets/ 2>/dev/null || true
NEW_JS=$(ls dist/assets/index-*.js 2>/dev/null | head -1 | xargs basename)
NEW_CSS=$(ls dist/assets/index-*.css 2>/dev/null | head -1 | xargs basename)
sed -i "s|assets/index-[^\"]*\.js|assets/$NEW_JS|g" $MINIAPP/index.html
sed -i "s|assets/index-[^\"]*\.css|assets/$NEW_CSS|g" $MINIAPP/index.html
systemctl restart lera-miniapp
echo "Done: $NEW_JS"
```

## /root/fix_build.py — Фиксы перед сборкой
Применяет патчи к исходникам в `/opt/lera-build/src/`:
1. `leraApi.ts` — переписывает на простую функцию (убирает TDZ)
2. `ProfilePage.tsx` — lazy imports для sub-pages
3. `ShopPage.tsx` — lazy GachaPage
4. `PartnerPage.tsx` — убирает DuoProfileEditor import, добавляет LazyDuoEditor
5. `vite.config.ts` — `manualChunks: () => "index"`
6. Переносит `filters` useState перед `apiCards` useEffect

---

## БД (lera_bot.db) — Ключевые таблицы

### Основные (Лера бот)
- `users` — пользователи (tg_id, username, lang, balance, tg_photo_url)
- `user_profiles` — профили (nickname, age, city, gender, country, duet_visible, duet_about, duet_games, profile_photos, custom_avatar, accent_color, avatar_frame)
- `user_inventory` — инвентарь (item_id, category, is_equipped)

### Лобби (Отряд)
- `lfg_lobbies` — лобби (id INTEGER AUTOINCREMENT, creator_tg_id, game_id, title, max_players, status, has_voice, entry_mode, role, expires_at)
- `squad_members` — участники лобби (squad_id TEXT, tg_id INTEGER)
- `lobby_messages` — чат лобби (id, squad_id, sender_tg_id, sender_name, text, created_at)

### Дуэт
- `duet_likes` — лайки (from_tg_id, to_tg_id)
- `duet_matches` — матчи (user1_tg_id, user2_tg_id)
- `duet_messages` — сообщения в матче (match_id, sender_tg_id, text)

---

## Правила деплоя

1. **Никогда не редактировать бандл напрямую** если есть исходники — только через build.sh
2. **Откат на рабочий бандл:** `index-BkQLr0pe.js` + `index-C7zlb5we.css` (старая стабильная версия без лайков через API)
3. **Текущий рабочий бандл:** последний собранный через build.sh
4. **После каждого build.sh** — все патчи применяются автоматически через fix_build.py
5. **Проблема сборки** — если ошибка `Cannot access 'X' before initialization`, ищи useState хуки которые используются в useEffect до их объявления

---

## Статус (апрель 2026)

### Работает
- Лобби создаются и видны другим
- Чат лобби — через API (polling 3 сек)
- Дуэт — свайп карточки работает
- Лайки через реальный API (`POST /api/duet/like/{id}`)
- Уведомления при матче через бота
- Фото профиля загружаются
- Инвентарь (надеть предмет работает)
- Ежедневная награда, кошелёк, магазин, гача

### Не работает / в процессе
- Чат матчей (дуэт) — localStorage, виден только отправителю (нужно подключить `/api/duet/matches/{id}/messages`)
- Аватарки в чате лобби
- Рамки инвентаря не отображаются визуально
- Редактирование анкеты дуэта показывает заглушку (убрали из-за circular deps)

### Текущие задачи
- Убрать блоки "Лера советует", "Случайный тиммейт", "Показывать мне" из PartnerPage — оставить только шестерёнку фильтров
- Добавить в фильтры пункт "Онлайн/Все"
- Увеличить карточки в дуэте
