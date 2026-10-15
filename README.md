# Башня

Аркада для Telegram Mini App: ставь блоки друг на друга, всё лишнее отрезается.
Чистый HTML5 + Canvas, без сборки и зависимостей — легко перенести в мобильное приложение.

## Запуск локально

```bash
python3 -m http.server -d web 8080   # открыть http://localhost:8080
```

## Публикация в Telegram

1. **Хостинг (нужен HTTPS).** В репо есть workflow для GitHub Pages:
   Settings → Pages → Source: **GitHub Actions**, затем пуш в `main`.
   Игра будет на `https://<user>.github.io/<repo>/`.
2. **Бот.** В [@BotFather](https://t.me/BotFather): `/newbot` → создать бота.
3. **Mini App.** `/newapp` → выбрать бота, указать название, описание, картинку 640×360,
   URL из п.1 и короткое имя. Получишь ссылку вида `https://t.me/<bot>/<name>`.
4. (Опц.) `/setmenubutton` — кнопка запуска игры в чате с ботом.
5. Вписать ссылку из п.3 в `web/config.js` (`shareUrl`) — для кнопки «Поделиться».

## Перенос в приложение (Android / iOS)

Весь код, завязанный на Telegram, — в `web/platform.js`. В приложении он автоматически
работает в «браузерном» режиме (localStorage, `navigator.vibrate`).

```bash
npm init -y
npm i @capacitor/core @capacitor/cli @capacitor/android @capacitor/ios
npx cap init "Башня" com.example.tower --web-dir=web
npx cap add android        # и/или: npx cap add ios
npx cap open android       # сборка в Android Studio
```

Для нативной вибрации можно заменить `haptic()` в `platform.js` на `@capacitor/haptics`.

## Структура

| Файл | Что внутри |
|---|---|
| `web/index.html` | разметка, экраны меню и проигрыша |
| `web/game.js` | логика и отрисовка игры |
| `web/platform.js` | Telegram SDK: хаптика, CloudStorage, «поделиться» |
| `web/config.js` | настройки (ссылка для шаринга) |
| `web/style.css` | стили |
