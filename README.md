# Игры для Telegram Mini App

Чистый HTML5 + Canvas, без сборки и зависимостей — легко перенести в мобильное приложение.

| Игра | Папка | Что это |
|---|---|---|
| **Карантин** | `web/zombie/` | выживание в городе зомби: вид сверху, обыск домов, еда/вода, оружие, день и ночь |
| **Башня** | `web/tower/` | аркада: ставь блоки точно друг на друга |

`web/index.html` — простая страница выбора игры.

## Запуск локально

```bash
python3 -m http.server -d web 8080   # открыть http://localhost:8080
```

## Карантин — как устроено

- Город генерируется заново каждую игру: дома с комнатами и мебелью, магазин, полиция, парк, брошенные машины.
- Мебель и машины можно обыскать (🔍). Добыча — еда, вода, бинты, оружие с прочностью, пистолет и патроны.
- Голод, жажда, выносливость, кровотечение. Сутки длятся около 6 минут; ночью темно и зомби быстрее.
- Зомби идут на шум (бег, удары, выстрелы) и обходят стены, чтобы найти вход в дом.
- Управление: джойстик слева, удар справа (с автонаведением). На ПК: WASD, Shift, Пробел, E, I.

| Файл | Что внутри |
|---|---|
| `items.js` | предметы и таблицы добычи — баланс правится здесь |
| `world.js` | генерация города, столкновения, видимость, поиск пути |
| `game.js` | игрок, зомби, инвентарь, интерфейс, управление |
| `render.js` | отрисовка |
| `sound.js` | звуки (синтез WebAudio) |
| `platform.js` | Telegram SDK: хаптика, CloudStorage, «поделиться» |
| `assets/` | атласы спрайтов (собираются скриптом, см. ниже) |

### Графика

Персонажи и окружение — готовые наборы художников, игра их только собирает и анимирует:

| Что | Набор | Лицензия |
|---|---|---|
| Выживший (ноги + тело, анимации) | Riley Gombart, «Animated Top Down Survivor Player» | CC BY 3.0 — нужно указывать автора (есть в меню) |
| Зомби (ходьба, атака) | Riley Gombart, «Animated Top Down Zombie» | CC0 |
| Тайлы, мебель, деревья | Kenney, «Topdown Shooter» | CC0 |
| Кровь | Kenney, «Splat Pack» | CC0 |
| Машины | DevilsWorkShop, «2D Car Pack» | CC0 |

Атласы `web/zombie/assets/*` собирает `tools/build-assets.py` (Python 3 + Pillow + numpy): режет кадры,
выравнивает их по туловищу, приглушает цвета под общий мрачный стиль и упаковывает в PNG-атласы.

```bash
python3 tools/build-assets.py \
  --riley  <zombie_game_prototype>/asset_packs \
  --kenney <kenney-topdown-shooter> --splats <kenney-splat-pack> \
  --cars   <2d-car-pack>/City-Traffic-Vehicles
```

Исходники: Kenney и машины — зеркало [series-ai/jam-ready-assets](https://github.com/series-ai/jam-ready-assets)
(или kenney.nl / opengameart.org), персонажи — [D4M13N-D3V/zombie_game_prototype](https://github.com/D4M13N-D3V/zombie_game_prototype)
(или opengameart.org, автор rileygombart). Одежду зомби игра перекрашивает на лету — получается несколько видов зомби из одного набора.

## Публикация в Telegram

1. **Хостинг (нужен HTTPS).** В репо есть workflow для GitHub Pages:
   Settings → Pages → Source: **GitHub Actions**, затем пуш в `main`.
   Игры будут на `https://<user>.github.io/<repo>/zombie/` и `.../tower/`.
2. **Бот.** В [@BotFather](https://t.me/BotFather): `/newbot` → создать бота.
3. **Mini App.** `/newapp` → выбрать бота, указать название, описание, картинку 640×360,
   URL игры из п.1 и короткое имя. Получишь ссылку вида `https://t.me/<bot>/<name>`.
4. (Опц.) `/setmenubutton` — кнопка запуска игры в чате с ботом.
5. Вписать ссылку из п.3 в `config.js` игры (`shareUrl`) — для кнопки «Поделиться».

## Перенос в приложение (Android / iOS)

Весь код, завязанный на Telegram, — в `platform.js` каждой игры. В приложении он автоматически
работает в «браузерном» режиме (localStorage, `navigator.vibrate`).

```bash
npm init -y
npm i @capacitor/core @capacitor/cli @capacitor/android @capacitor/ios
npx cap init "Карантин" com.example.quarantine --web-dir=web/zombie
npx cap add android        # и/или: npx cap add ios
npx cap open android       # сборка в Android Studio
```

Для нативной вибрации можно заменить `haptic()` в `platform.js` на `@capacitor/haptics`.
