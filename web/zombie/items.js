// Предметы и содержимое контейнеров.
// icon — эмодзи, чтобы обойтись без спрайтов. Оружие: dmg — урон, range — дальность (в клетках),
// cd — пауза между ударами (сек), knock — отбрасывание, noise — радиус шума, dur — прочность.
(function () {
  const Z = window.Z = window.Z || {};

  Z.ITEMS = {
    fists:      { name: 'Кулаки', icon: '✊', type: 'weapon', dmg: 2, range: 0.85, cd: 0.45, knock: 0.25, noise: 3, hits: 1 },
    knife:      { name: 'Кухонный нож', icon: '🔪', type: 'weapon', dmg: 4, range: 0.95, cd: 0.38, knock: 0.15, noise: 3, hits: 1, dur: 30,
                  look: { len: 0.55, w: 0.12, color: '#c9cdd1' } },
    bat:        { name: 'Бейсбольная бита', icon: '🏏', type: 'weapon', dmg: 5, range: 1.3, cd: 0.7, knock: 0.7, noise: 4, hits: 2, dur: 40,
                  look: { len: 1.35, w: 0.24, color: '#a0703f' } },
    crowbar:    { name: 'Монтировка', icon: '🔧', type: 'weapon', dmg: 6, range: 1.15, cd: 0.7, knock: 0.5, noise: 4, hits: 2, dur: 70,
                  look: { len: 1.2, w: 0.16, color: '#b8433a' } },
    axe:        { name: 'Топор', icon: '🪓', type: 'weapon', dmg: 10, range: 1.25, cd: 0.95, knock: 0.6, noise: 4, hits: 2, dur: 45,
                  look: { len: 1.25, w: 0.16, color: '#8a6a45', head: '#9aa3a8' } },
    pistol:     { name: 'Пистолет', icon: '🔫', type: 'gun', dmg: 12, range: 8, cd: 0.45, knock: 0.4, noise: 22, ammo: 'ammo',
                  look: { len: 0.6, w: 0.2, color: '#26282b' } },
    ammo:       { name: 'Патроны', icon: '🔸', type: 'ammo', stack: 60 },

    canned:     { name: 'Консервы', icon: '🥫', type: 'food', hunger: 35, thirst: -5, stack: 10 },
    bread:      { name: 'Хлеб', icon: '🍞', type: 'food', hunger: 25, thirst: -5, stack: 10 },
    chips:      { name: 'Чипсы', icon: '🍟', type: 'food', hunger: 15, thirst: -8, stack: 10 },
    choco:      { name: 'Шоколадка', icon: '🍫', type: 'food', hunger: 15, stack: 10 },
    apple:      { name: 'Яблоко', icon: '🍎', type: 'food', hunger: 12, thirst: 6, stack: 10 },
    water:      { name: 'Бутылка воды', icon: '💧', type: 'drink', thirst: 45, stack: 10 },
    soda:       { name: 'Газировка', icon: '🥤', type: 'drink', thirst: 25, hunger: 5, stack: 10 },

    bandage:    { name: 'Бинт', icon: '🩹', type: 'med', heal: 8, stopsBleed: true, stack: 10 },
    pills:      { name: 'Обезболивающее', icon: '💊', type: 'med', heal: 25, stack: 10 },
    flashlight: { name: 'Фонарик', icon: '🔦', type: 'tool' },
  };

  // n — сколько предметов может лежать (мин, макс); loot — [предмет, вес].
  Z.CONTAINERS = {
    fridge:   { name: 'Холодильник', n: [0, 4], loot: [['water', 4], ['soda', 3], ['apple', 3], ['bread', 2], ['canned', 1]] },
    cupboard: { name: 'Кухонный шкаф', n: [0, 3], loot: [['canned', 4], ['chips', 3], ['choco', 2], ['bread', 1], ['knife', 1.5], ['water', 1]] },
    wardrobe: { name: 'Шкаф', n: [0, 2], loot: [['bandage', 3], ['pills', 2], ['flashlight', 1.2], ['bat', 1]] },
    toolbox:  { name: 'Ящик с инструментами', n: [0, 2], loot: [['crowbar', 2], ['axe', 1], ['knife', 1], ['flashlight', 1]] },
    shelf:    { name: 'Стеллаж', n: [0, 3], loot: [['canned', 3], ['chips', 3], ['choco', 3], ['water', 3], ['soda', 2], ['bread', 2]] },
    drinks:   { name: 'Холодильник с напитками', n: [1, 4], loot: [['water', 3], ['soda', 3]] },
    locker:   { name: 'Шкафчик', n: [0, 3], loot: [['pistol', 1], ['ammo', 3], ['bandage', 2], ['crowbar', 1], ['flashlight', 1]] },
    desk:     { name: 'Стол', n: [0, 2], loot: [['ammo', 2], ['choco', 1], ['pills', 1], ['soda', 1]] },
    car:      { name: 'Машина', n: [0, 2], loot: [['water', 2], ['choco', 2], ['bandage', 1], ['flashlight', 1], ['crowbar', 1], ['pistol', 0.2], ['ammo', 0.5]] },
  };

  Z.rollLoot = function (type) {
    const def = Z.CONTAINERS[type];
    const total = def.loot.reduce((s, l) => s + l[1], 0);
    const count = def.n[0] + Math.floor(Math.random() * (def.n[1] - def.n[0] + 1));
    const items = [];
    for (let k = 0; k < count; k++) {
      let r = Math.random() * total, id = def.loot[0][0];
      for (const [lid, w] of def.loot) { r -= w; if (r <= 0) { id = lid; break; } }
      const item = Z.ITEMS[id];
      if (item.dur) { items.push({ id, n: 1, dur: Math.round(item.dur * (0.4 + Math.random() * 0.6)) }); continue; }
      const amount = id === 'ammo' ? 3 + Math.floor(Math.random() * 10) : 1;
      const same = items.find((e) => e.id === id && item.stack);
      if (same) same.n += amount; else items.push({ id, n: amount });
    }
    return items;
  };
})();
