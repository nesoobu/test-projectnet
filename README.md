# Telegram Bot (aiogram 3)

Шаблон Telegram-бота на Python с использованием [aiogram 3](https://docs.aiogram.dev/).

## Структура проекта

```
.
├── main.py                  # Точка входа
├── requirements.txt         # Зависимости
├── .env.example             # Пример переменных окружения
├── bot/
│   ├── config.py            # Настройки (читает .env)
│   ├── handlers/
│   │   ├── __init__.py      # Регистрация роутеров
│   │   ├── start.py         # /start
│   │   ├── help.py          # /help
│   │   ├── menu.py          # /menu + inline-кнопки
│   │   ├── buttons.py       # Reply-кнопки
│   │   └── echo.py          # Эхо (повторяет сообщения)
│   ├── keyboards/
│   │   ├── reply.py         # Reply-клавиатуры
│   │   └── inline.py        # Inline-клавиатуры
│   └── middlewares/
│       └── logging.py       # Логирование сообщений
```

## Быстрый старт

### 1. Создайте бота

Откройте [@BotFather](https://t.me/BotFather) в Telegram и создайте нового бота командой `/newbot`. Скопируйте полученный токен.

### 2. Настройте окружение

```bash
cp .env.example .env
```

Откройте `.env` и вставьте ваш токен:

```
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
ADMIN_ID=ваш_telegram_id
```

### 3. Установите зависимости

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

### 4. Запустите бота

```bash
python main.py
```

## Возможности

- `/start` — приветственное сообщение + reply-клавиатура
- `/help` — список команд
- `/menu` — inline-меню с кнопками (Информация, Ping, Закрыть)
- Reply-кнопки "Меню" и "Помощь"
- Эхо — бот повторяет любое текстовое сообщение
- Middleware для логирования входящих сообщений

## Как добавить новый хэндлер

1. Создайте файл в `bot/handlers/`, например `bot/handlers/weather.py`
2. Определите `router = Router()` и добавьте обработчики
3. Импортируйте роутер в `bot/handlers/__init__.py` и добавьте в `get_all_routers()`

## Технологии

- [Python 3.10+](https://www.python.org/)
- [aiogram 3](https://docs.aiogram.dev/)
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
