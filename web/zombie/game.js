// «Карантин» — выживание в городе, захваченном мертвецами.
(function () {
  'use strict';
  const Z = window.Z;
  const ITEMS = Z.ITEMS;
  const Sfx = Z.Sfx;

  const MIN_PER_SEC = 4;          // игровых минут в секунде: сутки ≈ 6 минут
  const START_MIN = 8 * 60;       // 08:00 первого дня
  const SLOTS = 12;               // ячеек в рюкзаке
  const WALK = 2.3, RUN = 3.9;    // клеток в секунду
  const P_R = 0.3, Z_R = 0.3;
  const REACH = 0.8;              // с какого расстояния можно обыскать мебель
  const BG = '#15181a';
  Z.JOY_R = 56;

  const pick = (a) => a[Math.floor(Math.random() * a.length)];
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const angDiff = (a, b) => Math.atan2(Math.sin(a - b), Math.cos(a - b));

  const $ = (id) => document.getElementById(id);
  const ui = {
    hud: $('hud'), day: $('day'), clock: $('clock'), kills: $('kills'), status: $('status'), toast: $('toast'),
    bars: { hp: $('b-hp'), hunger: $('b-hunger'), thirst: $('b-thirst'), stamina: $('b-stamina') },
    attack: $('btn-attack'), search: $('btn-search'), bag: $('btn-bag'), sound: $('btn-sound'),
    menu: $('menu'), menuBest: $('menu-best'), hint: $('controls-hint'),
    dead: $('dead'), deadTitle: $('dead-title'), deadTime: $('dead-time'), deadKills: $('dead-kills'),
    deadBest: $('dead-best'), deadRecord: $('dead-record'),
    panel: $('panel'), lootSec: $('loot-sec'), lootName: $('loot-name'), lootList: $('loot-list'),
    invList: $('inv-list'), invCount: $('inv-count'),
  };

  const S = Z.S = {
    state: 'menu', paused: false,
    p: null, zombies: [], corpses: [], decals: [], fx: [], parts: [], inv: [], shake: 0, flashlight: false, coneLen: 8,
    time: START_MIN, kills: 0, dark: 0, sight: 10, lightR: 12, hurtFlash: 0,
    near: null, open: null, cause: '', spawnT: 0, flowT: 0, dayShown: 1,
    best: { min: 0, kills: 0 },
    joy: { active: false, id: -1, ox: 0, oy: 0, dx: 0, dy: 0, run: false },
  };
  const keys = {};
  let attackHeld = false;

  // ---------- Вспомогательное ----------
  const weaponDef = () => (S.p.weapon ? ITEMS[S.p.weapon.id] : ITEMS.fists);
  S.gunEquipped = () => weaponDef().type === 'gun';
  const findItem = (id) => S.inv.find((e) => e.id === id);
  const dayNum = () => Math.floor(S.time / 1440) + 1;

  function fmtSurvived(min) {
    if (!min) return '—';
    const d = Math.floor(min / 1440), h = Math.floor((min % 1440) / 60);
    return d ? `${d} д. ${h} ч.` : `${h} ч. ${Math.floor(min % 60)} мин.`;
  }

  let toastTimer = 0;
  function toast(text) {
    ui.toast.textContent = text;
    ui.toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => ui.toast.classList.remove('show'), 2200);
  }

  function darkness(h) {
    const MAX = 0.9;
    if (h >= 7 && h < 19) return 0;
    if (h >= 21 || h < 5) return MAX;
    if (h >= 19) return ((h - 19) / 2) * MAX;
    return (1 - (h - 5) / 2) * MAX;
  }

  // ---------- Мир и зомби ----------
  function makeZombie(x, y) {
    return {
      x, y, zombie: true, hp: 8 + Math.random() * 5, speed: 0.85 + Math.random() * 0.55,
      face: Math.random() * Math.PI * 2, state: 'wander', tx: x, ty: y, moving: false,
      think: Math.random() * 0.3, atkCd: 0, stun: 0, wanderT: Math.random() * 3, lost: 0,
      sees: false, vis: false, alpha: 0, d: 99, walkT: Math.random() * 10, moving: false,
      variant: Math.floor(Math.random() * Z.ZOMBIE_VARIANTS), scale: 0.92 + Math.random() * 0.16,
      seed: Math.random(), flash: 0, atkAnim: 0,
    };
  }

  function spawnZombie(minDist, outdoorsOnly) {
    const T = Z.TILE;
    for (let k = 0; k < 40; k++) {
      const x = 2 + Math.floor(Math.random() * (Z.N - 4)), y = 2 + Math.floor(Math.random() * (Z.N - 4));
      const t = Z.tileAt(x, y);
      const ok = outdoorsOnly ? (t === T.GRASS || t === T.ROAD || t === T.WALK) : !Z.solid(x, y);
      if (!ok || Math.hypot(x + 0.5 - S.p.x, y + 0.5 - S.p.y) < minDist) continue;
      S.zombies.push(makeZombie(x + 0.5, y + 0.5));
      return;
    }
  }

  function noise(x, y, r) {
    for (const z of S.zombies) {
      if (z.state === 'chase') continue;
      if (Math.hypot(z.x - x, z.y - y) < r) {
        z.state = 'investigate';
        z.tx = x + (Math.random() - 0.5) * 2;
        z.ty = y + (Math.random() - 0.5) * 2;
        z.lost = 0;
      }
    }
  }

  function blood(x, y, n, size) {
    for (let k = 0; k < n; k++) {
      S.decals.push({
        x: x + (Math.random() - 0.5) * 0.5, y: y + (Math.random() - 0.5) * 0.5,
        r: (0.14 + Math.random() * 0.14) * (size || 1), a: 0.75 + Math.random() * 0.2,
        v: Math.floor(Math.random() * 6), rot: Math.random() * Math.PI * 2,
      });
    }
    if (S.decals.length > 220) S.decals.splice(0, S.decals.length - 220);
  }

  // брызги крови разлетаются от удара
  function spray(x, y, angle, n) {
    for (let k = 0; k < n; k++) {
      const a = angle + (Math.random() - 0.5) * 1.4, v = 2 + Math.random() * 4;
      S.parts.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, t: 0, life: 0.25 + Math.random() * 0.3, size: 0.03 + Math.random() * 0.04 });
    }
    if (S.parts.length > 200) S.parts.splice(0, S.parts.length - 200);
  }

  // ---------- Новая игра ----------
  function newGame() {
    Z.world = Z.genWorld((Math.random() * 1e9) | 0);
    Z.resetFlow();
    const sp = Z.world.spawn;
    S.p = {
      x: sp.x, y: sp.y, face: 0, hp: 100, hunger: 85, thirst: 80, stamina: 100, exhausted: false,
      bleeding: false, weapon: null, atkCd: 0, atkAnim: 0, walkT: 0, stepT: 0, moving: false, running: false,
    };
    S.zombies = []; S.corpses = []; S.decals = []; S.fx = []; S.parts = []; S.shake = 0;
    S.inv = [{ id: 'water', n: 1 }];
    S.time = START_MIN; S.kills = 0; S.hurtFlash = 0; S.cause = ''; S.dayShown = 1; S.lastBite = -1e9;
    S.spawnT = 20; S.open = null; S.near = null;
    for (let k = 0; k < 55; k++) spawnZombie(14, true);
    for (let k = 0; k < 20; k++) spawnZombie(14, false);
  }

  function start() {
    newGame();
    S.state = 'play';
    S.paused = false;
    ui.menu.classList.add('hidden');
    ui.dead.classList.add('hidden');
    ui.hud.classList.remove('hidden');
    Platform.confirmClose(true);
    updateHud();
    toast('Обыщи дом: подойди к мебели и нажми 🔍');
  }

  // ---------- Игрок ----------
  function updatePlayer(dt) {
    const p = S.p, j = S.joy;
    let mx = 0, my = 0, run = false;
    if (j.active) { mx = j.dx; my = j.dy; run = Math.hypot(mx, my) > 0.92; }
    if (keys.KeyW || keys.ArrowUp) my -= 1;
    if (keys.KeyS || keys.ArrowDown) my += 1;
    if (keys.KeyA || keys.ArrowLeft) mx -= 1;
    if (keys.KeyD || keys.ArrowRight) mx += 1;
    if (keys.ShiftLeft || keys.ShiftRight) run = true;
    let m = Math.hypot(mx, my);
    if (m > 1) { mx /= m; my /= m; m = 1; }

    run = run && m > 0.2 && !p.exhausted;
    j.run = run;
    p.moving = m > 0.1;
    p.running = run;
    if (m > 0.1) {
      const speed = (run ? RUN : WALK * Math.min(1, m * 1.4)) * (p.hp < 25 ? 0.8 : 1);
      p.x += (mx / m) * speed * dt;
      p.y += (my / m) * speed * dt;
      if (p.atkAnim <= 0) p.face = Math.atan2(my, mx);
      p.walkT += dt * speed * 2.4;
      p.stepT -= dt;
      if (p.stepT <= 0) { p.stepT = run ? 0.4 : 0.7; noise(p.x, p.y, run ? 7 : 2.5); }
    }
    Z.collide(p, P_R);

    // выносливость
    if (run && m > 0.1) p.stamina -= 16 * dt; else p.stamina += 9 * dt;
    p.stamina = clamp(p.stamina, 0, 100);
    if (p.stamina <= 0 && !p.exhausted) { p.exhausted = true; toast('Ты выдохся'); }
    if (p.stamina > 35) p.exhausted = false;

    // голод, жажда, кровь
    const wasHungry = p.hunger < 25, wasThirsty = p.thirst < 25;
    p.hunger = Math.max(0, p.hunger - (dt * 100) / 720);
    p.thirst = Math.max(0, p.thirst - (dt * 100) / 540);
    if (!wasHungry && p.hunger < 25) toast('🍗 Ты проголодался');
    if (!wasThirsty && p.thirst < 25) toast('💧 Хочется пить');
    if (p.hunger <= 0) { p.hp -= 0.5 * dt; S.cause = 'hunger'; }
    if (p.thirst <= 0) { p.hp -= 0.6 * dt; S.cause = 'thirst'; }
    if (p.bleeding) { p.hp -= 0.7 * dt; S.cause = 'blood'; }
    if (p.hunger > 40 && p.thirst > 40 && !p.bleeding) p.hp = Math.min(100, p.hp + 0.25 * dt);

    p.atkCd -= dt;
    p.atkAnim -= dt;
    if (attackHeld || keys.Space) attack();
    if (p.hp <= 0) die();
  }

  function attack() {
    const p = S.p;
    if (p.atkCd > 0 || S.state !== 'play') return;
    const w = weaponDef(), gun = w.type === 'gun';

    // автонаведение на ближайшего видимого зомби
    let target = null, best = Infinity;
    const reach = gun ? w.range : w.range + 0.9;
    for (const z of S.zombies) {
      if (z.alpha < 0.3 || z.d > reach + Z_R) continue;
      if (z.d < best) { best = z.d; target = z; }
    }
    if (target) p.face = Math.atan2(target.y - p.y, target.x - p.x);

    if (gun) {
      const ammo = findItem(w.ammo);
      if (!ammo) { Sfx.empty(); toast('Нет патронов'); p.atkCd = 0.5; return; }
      if (--ammo.n <= 0) S.inv.splice(S.inv.indexOf(ammo), 1);
      p.atkCd = w.cd;
      p.atkAnim = 0.12;
      Sfx.shot();
      Platform.haptic('heavy');
      S.shake = Math.max(S.shake, 5);
      noise(p.x, p.y, w.noise);
      const fx = p.x + Math.cos(p.face) * 0.5, fy = p.y + Math.sin(p.face) * 0.5;
      const ex = target ? target.x : p.x + Math.cos(p.face) * w.range;
      const ey = target ? target.y : p.y + Math.sin(p.face) * w.range;
      S.fx.push({ kind: 'tracer', x1: fx, y1: fy, x2: ex, y2: ey, t: 0, life: 0.08 });
      S.fx.push({ kind: 'flash', x1: fx, y1: fy, t: 0, life: 0.1 });
      if (target && Z.los(p.x, p.y, target.x, target.y)) hitZombie(target, w.dmg, w.knock);
      return;
    }

    const tired = p.stamina < 8;
    p.atkCd = w.cd * (tired ? 1.6 : 1);
    p.atkAnim = 0.3;
    p.stamina = Math.max(0, p.stamina - 7);
    Sfx.swing();
    noise(p.x, p.y, w.noise);
    let hits = 0;
    const victims = S.zombies.filter((z) => z.d <= w.range + Z_R).sort((a, b) => a.d - b.d);
    for (const z of victims) {
      if (hits >= w.hits) break;
      if (Math.abs(angDiff(Math.atan2(z.y - p.y, z.x - p.x), p.face)) > 1.0) continue;
      if (!Z.los(p.x, p.y, z.x, z.y)) continue;
      hitZombie(z, w.dmg * (tired ? 0.6 : 1), w.knock);
      hits++;
    }
    if (hits) {
      Sfx.hit();
      Platform.haptic('medium');
      S.shake = Math.max(S.shake, 4);
      if (p.weapon && --p.weapon.dur <= 0) {
        toast(`${ITEMS[p.weapon.id].name} — сломано`);
        S.inv.splice(S.inv.indexOf(p.weapon), 1);
        p.weapon = null;
      }
    }
  }

  function hitZombie(z, dmg, knock) {
    const crit = Math.random() < 0.12;
    z.hp -= dmg * (0.8 + Math.random() * 0.4) * (crit ? 2 : 1);
    const a = Math.atan2(z.y - S.p.y, z.x - S.p.x);
    z.x += Math.cos(a) * knock;
    z.y += Math.sin(a) * knock;
    Z.collide(z, Z_R);
    z.stun = 0.35 + knock * 0.4;
    z.state = 'chase';
    z.lost = 0;
    z.flash = 0.15;
    z.atkAnim = 0;
    blood(z.x, z.y, crit ? 2 : 1);
    spray(z.x, z.y, a, crit ? 14 : 8);
    if (z.hp <= 0) {
      z.dead = true;
      S.kills++;
      blood(z.x, z.y, 2, 2.2);
      S.corpses.push({ x: z.x, y: z.y, face: a + (Math.random() - 0.5) * 0.8, variant: z.variant, scale: z.scale });
      if (S.corpses.length > 80) S.corpses.shift();
      S.shake = Math.max(S.shake, 7);
    }
  }

  function zombieAttack(z) {
    const p = S.p;
    if (Math.random() < 0.25) return; // промахнулся
    p.hp -= 7 + Math.random() * 7;
    S.lastBite = S.time;
    S.hurtFlash = 1;
    S.shake = Math.max(S.shake, 9);
    spray(p.x, p.y, Math.atan2(p.y - z.y, p.x - z.x), 6);
    Sfx.hurt();
    Platform.haptic('heavy');
    blood(p.x, p.y, 2);
    if (!p.bleeding && Math.random() < 0.35) { p.bleeding = true; toast('🩸 Кровотечение! Нужен бинт'); }
    const a = Math.atan2(p.y - z.y, p.x - z.x);
    p.x += Math.cos(a) * 0.15;
    p.y += Math.sin(a) * 0.15;
    Z.collide(p, P_R);
  }

  // ---------- Зомби ----------
  let lastGroan = 0;
  function updateZombies(dt) {
    const p = S.p, night = S.dark > 0.5, alive = S.state === 'play';
    if ((S.flowT -= dt) <= 0) { S.flowT = 0.3; Z.buildFlow(p.x, p.y); }

    for (const z of S.zombies) {
      const dx = p.x - z.x, dy = p.y - z.y, d = Math.hypot(dx, dy);
      z.d = d;
      if (d > 40) continue; // далеко — стоит на месте

      if ((z.think -= dt) <= 0) {
        z.think = 0.2 + Math.random() * 0.15;
        const los = d < Math.max(S.sight, 1.6) && Z.los(z.x, z.y, p.x, p.y);
        z.vis = los || d < 1.2;
        z.sees = alive && los && d < S.sight;
        if (z.sees) {
          if (z.state !== 'chase' && performance.now() - lastGroan > 1500) { Sfx.groan(); lastGroan = performance.now(); }
          z.state = 'chase';
          z.tx = p.x; z.ty = p.y; z.lost = 0;
        }
      }
      z.alpha += ((z.vis ? 1 : 0) - z.alpha) * Math.min(1, dt * 6);
      z.atkCd -= dt;
      z.flash = Math.max(0, z.flash - dt);
      z.atkAnim = Math.max(0, z.atkAnim - dt);
      z.moving = false;
      if (z.stun > 0) { z.stun -= dt; continue; }

      let gx = null, gy = null, spd = 0;
      if (z.state === 'chase') {
        spd = z.speed * (night ? 1.15 : 1);
        if (!alive) { z.state = 'wander'; }
        else if (z.sees) { gx = p.x; gy = p.y; }
        else {
          z.lost += dt;
          const step = Z.flowStep(z.x, z.y);
          if (step && z.lost < 8) { gx = step.x; gy = step.y; }
          else { z.state = 'investigate'; z.lost = 0; }
        }
      } else if (z.state === 'investigate') {
        spd = z.speed * 0.75;
        const nearPlayer = Math.hypot(z.tx - p.x, z.ty - p.y) < 3;
        const step = nearPlayer ? Z.flowStep(z.x, z.y) : null;
        gx = step ? step.x : z.tx;
        gy = step ? step.y : z.ty;
        z.lost += dt;
        if (Math.hypot(z.tx - z.x, z.ty - z.y) < 0.6 || z.lost > 15) { z.state = 'wander'; z.wanderT = 2; }
      } else {
        if ((z.wanderT -= dt) <= 0) {
          z.wanderT = 2 + Math.random() * 4;
          z.moving = Math.random() < 0.5;
          z.tx = z.x + (Math.random() - 0.5) * 8;
          z.ty = z.y + (Math.random() - 0.5) * 8;
        }
        if (z.moving) {
          spd = 0.3; gx = z.tx; gy = z.ty;
          if (Math.hypot(z.tx - z.x, z.ty - z.y) < 0.4) z.moving = false;
        }
      }

      if (gx !== null) {
        const a = Math.atan2(gy - z.y, gx - z.x);
        z.face += angDiff(a, z.face) * Math.min(1, dt * 10);
        z.x += Math.cos(z.face) * spd * dt;
        z.y += Math.sin(z.face) * spd * dt;
        z.walkT += dt * spd * 3;
        z.moving = spd > 0;
      }
      if (alive && d < Z_R + P_R + 0.25 && z.atkCd <= 0) { z.atkCd = 1.4; z.atkAnim = 0.55; zombieAttack(z); }
    }

    // расталкиваем зомби между собой и от игрока
    const zs = S.zombies;
    for (let a = 0; a < zs.length; a++) {
      const za = zs[a];
      if (za.d > 40) continue;
      for (let b = a + 1; b < zs.length; b++) {
        const zb = zs[b];
        const dx = zb.x - za.x, dy = zb.y - za.y;
        if (Math.abs(dx) > 0.6 || Math.abs(dy) > 0.6) continue;
        const dd = Math.hypot(dx, dy);
        if (dd < 0.55 && dd > 1e-4) {
          const push = (0.55 - dd) / 2;
          za.x -= (dx / dd) * push; za.y -= (dy / dd) * push;
          zb.x += (dx / dd) * push; zb.y += (dy / dd) * push;
        }
      }
      const dx = za.x - p.x, dy = za.y - p.y, dd = Math.hypot(dx, dy);
      if (dd < P_R + Z_R && dd > 1e-4 && S.state === 'play') {
        za.x = p.x + (dx / dd) * (P_R + Z_R);
        za.y = p.y + (dy / dd) * (P_R + Z_R);
      }
      Z.collide(za, Z_R);
    }
    if (zs.some((z) => z.dead)) S.zombies = zs.filter((z) => !z.dead);

    // подкрепление: город понемногу заполняется
    if ((S.spawnT -= dt) <= 0) {
      S.spawnT = 15;
      const target = Math.min(170, 60 + (dayNum() - 1) * 18 + (night ? 20 : 0));
      for (let k = 0; k < 4 && S.zombies.length < target; k++) spawnZombie(18, true);
    }
  }

  // ---------- Смерть ----------
  function die() {
    S.state = 'dead';
    S.p.hp = 0;
    attackHeld = false;
    S.joy.active = false;
    closePanel();
    Sfx.die();
    Platform.haptic('error');
    Platform.confirmClose(false);
    const survived = Math.floor(S.time - START_MIN);
    const record = survived > S.best.min;
    if (record) {
      S.best = { min: survived, kills: S.kills };
      Platform.setItem('zb_best', JSON.stringify(S.best));
    }
    if (S.time - S.lastBite < 15) S.cause = 'zombie'; // укус в последние минуты — значит, сожрали
    const titles = { zombie: 'Тебя сожрали', hunger: 'Ты умер от голода', thirst: 'Ты умер от жажды', blood: 'Ты истёк кровью' };
    setTimeout(() => {
      ui.hud.classList.add('hidden');
      ui.deadTitle.textContent = titles[S.cause] || 'Ты погиб';
      ui.deadTime.textContent = fmtSurvived(survived);
      ui.deadKills.textContent = S.kills;
      ui.deadBest.textContent = fmtSurvived(S.best.min);
      ui.deadRecord.classList.toggle('hidden', !record);
      ui.menuBest.textContent = fmtSurvived(S.best.min);
      ui.dead.classList.remove('hidden');
    }, 1400);
  }

  // ---------- Инвентарь ----------
  function addItem(id, n, dur) {
    const d = ITEMS[id];
    if (d.stack) {
      for (const e of S.inv) {
        if (e.id !== id || e.n >= d.stack) continue;
        const k = Math.min(n, d.stack - e.n);
        e.n += k; n -= k;
        if (!n) return 0;
      }
      while (n > 0 && S.inv.length < SLOTS) {
        const k = Math.min(n, d.stack);
        S.inv.push({ id, n: k }); n -= k;
      }
      return n;
    }
    if (S.inv.length >= SLOTS) return n;
    S.inv.push({ id, n: 1, dur });
    return 0;
  }

  function useItem(e) {
    const d = ITEMS[e.id], p = S.p;
    if (d.type === 'weapon' || d.type === 'gun') {
      p.weapon = p.weapon === e ? null : e;
      return;
    }
    if (d.hunger) p.hunger = clamp(p.hunger + d.hunger, 0, 100);
    if (d.thirst) p.thirst = clamp(p.thirst + d.thirst, 0, 100);
    if (d.heal) p.hp = Math.min(100, p.hp + d.heal);
    if (d.stopsBleed && p.bleeding) { p.bleeding = false; toast('Кровотечение остановлено'); }
    if (d.type === 'med') Sfx.pick(); else Sfx.eat();
    Platform.haptic('light');
    if (--e.n <= 0) S.inv.splice(S.inv.indexOf(e), 1);
  }

  function removeEntry(e) {
    if (S.p.weapon === e) S.p.weapon = null;
    S.inv.splice(S.inv.indexOf(e), 1);
  }

  const USE_LABEL = { food: 'Съесть', drink: 'Выпить', med: 'Лечиться' };

  function itemRow(e, i, list, actions) {
    const d = ITEMS[e.id];
    const count = e.n > 1 ? ` <small>×${e.n}</small>` : '';
    const tag = e === S.p.weapon ? '<em class="tag">в руках</em>' : '';
    const dur = d.dur ? `<span class="dur"><i style="width:${Math.round((e.dur / d.dur) * 100)}%"></i></span>` : '';
    const btns = actions.map(([act, label, cls]) =>
      `<button class="${cls || ''}" data-list="${list}" data-act="${act}" data-i="${i}">${label}</button>`).join('');
    return `<li><span class="ic">${d.icon}</span><span class="nm">${d.name}${count}${tag}${dur}</span><span class="acts">${btns}</span></li>`;
  }

  function renderPanel() {
    const c = S.open;
    ui.lootSec.classList.toggle('hidden', !c);
    if (c) {
      ui.lootName.textContent = Z.CONTAINERS[c.type].name;
      ui.lootList.innerHTML = c.items.length
        ? c.items.map((e, i) => itemRow(e, i, 'loot', [['take', 'Взять', 'primary']])).join('')
        : '<li class="empty">Пусто</li>';
    }
    ui.invCount.textContent = `${S.inv.length}/${SLOTS}`;
    ui.invList.innerHTML = S.inv.length ? S.inv.map((e, i) => {
      const d = ITEMS[e.id], acts = [];
      if (USE_LABEL[d.type]) acts.push(['use', USE_LABEL[d.type], 'primary']);
      if (d.type === 'weapon' || d.type === 'gun') acts.push(['use', e === S.p.weapon ? 'Убрать' : 'В руки', 'primary']);
      acts.push(c ? ['put', 'Положить'] : ['drop', 'Выбросить']);
      return itemRow(e, i, 'inv', acts);
    }).join('') : '<li class="empty">Рюкзак пуст</li>';
  }

  function openPanel(container) {
    if (S.state !== 'play') return;
    if (container && !container.items) container.items = Z.rollLoot(container.type);
    S.open = container || null;
    S.paused = true;
    attackHeld = false;
    S.joy.active = false;
    renderPanel();
    ui.panel.classList.remove('hidden');
  }

  function closePanel() {
    S.paused = false;
    S.open = null;
    ui.panel.classList.add('hidden');
    updateHud();
  }

  ui.panel.addEventListener('click', (ev) => {
    if (ev.target === ui.panel) return closePanel(); // тап мимо листа
    const btn = ev.target.closest('button[data-act]');
    if (!btn) return;
    const i = +btn.dataset.i, act = btn.dataset.act, c = S.open;
    if (btn.dataset.list === 'loot') {
      const e = c.items[i];
      const left = addItem(e.id, e.n, e.dur);
      if (left === e.n) { toast('Рюкзак полон'); return; }
      Sfx.pick();
      if (left) e.n = left; else c.items.splice(i, 1);
    } else {
      const e = S.inv[i];
      if (act === 'use') useItem(e);
      if (act === 'drop') removeEntry(e);
      if (act === 'put') { removeEntry(e); c.items.push(e); }
    }
    renderPanel();
  });
  $('take-all').addEventListener('click', () => {
    const c = S.open;
    if (!c) return;
    let took = false;
    c.items = c.items.filter((e) => {
      const left = addItem(e.id, e.n, e.dur);
      if (left < e.n) took = true;
      e.n = left;
      return left > 0;
    });
    if (took) Sfx.pick();
    if (c.items.length) toast('Рюкзак полон');
    renderPanel();
  });
  $('panel-close').addEventListener('click', closePanel);

  // ---------- HUD ----------
  function updateHud() {
    const p = S.p;
    if (!p) return;
    const mins = Math.floor(S.time % 1440);
    ui.day.textContent = `День ${dayNum()}`;
    ui.clock.textContent = `${String(Math.floor(mins / 60)).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`;
    ui.kills.textContent = S.kills;
    for (const k of ['hp', 'hunger', 'thirst', 'stamina']) ui.bars[k].style.width = `${clamp(p[k], 0, 100)}%`;
    const st = [];
    if (p.bleeding) st.push('<span class="bad">🩸 Кровотечение</span>');
    if (p.hunger < 25) st.push('<span class="warn">🍗 Голод</span>');
    if (p.thirst < 25) st.push('<span class="warn">💧 Жажда</span>');
    if (p.exhausted) st.push('<span class="warn">⚡ Устал</span>');
    ui.status.innerHTML = st.join('');
    const w = weaponDef();
    const ammo = w.type === 'gun' ? (findItem('ammo') ? S.inv.filter((e) => e.id === 'ammo').reduce((s, e) => s + e.n, 0) : 0) : null;
    const icon = w.icon + (ammo !== null ? `<small>${ammo}</small>` : '');
    if (ui.attack.dataset.icon !== icon) { ui.attack.dataset.icon = icon; ui.attack.innerHTML = icon; }
    ui.search.classList.toggle('hidden', !S.near);
  }

  // ---------- Цикл ----------
  let last = performance.now(), hudT = 0;
  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (S.p && !S.paused && S.state !== 'menu') {
      if (S.state === 'play') {
        S.time += dt * MIN_PER_SEC;
        if (dayNum() !== S.dayShown) { S.dayShown = dayNum(); toast(`☀️ День ${S.dayShown}`); }
        updatePlayer(dt);
      }
      const h = (S.time % 1440) / 60;
      S.dark = darkness(h);
      const lamp = !!findItem('flashlight');
      S.flashlight = lamp && S.dark > 0.05;
      S.sight = 11 - (S.dark / 0.9) * (lamp ? 4 : 6.5);
      S.lightR = 13 - (S.dark / 0.9) * (lamp ? 10 : 9.5);
      updateZombies(dt);
      for (const f of S.fx) f.t += dt;
      S.fx = S.fx.filter((f) => f.t < f.life);
      for (const q of S.parts) { q.t += dt; q.x += q.vx * dt; q.y += q.vy * dt; q.vx *= 0.9; q.vy *= 0.9; }
      S.parts = S.parts.filter((q) => q.t < q.life);
      S.shake = Math.max(0, S.shake - dt * 45);
      S.hurtFlash = Math.max(0, S.hurtFlash - dt * 2);
      for (const b of Z.world.buildings) {
        const inside = S.p.x > b.x + 0.5 && S.p.x < b.x + b.w - 0.5 && S.p.y > b.y + 0.5 && S.p.y < b.y + b.h - 0.5;
        b.roofA += ((inside ? 0 : 1) - b.roofA) * Math.min(1, dt * 8);
      }
      findNear();
    }
    if (S.p) Z.render();
    if ((hudT -= dt) <= 0 && S.state === 'play') { hudT = 0.1; updateHud(); }
    requestAnimationFrame(frame);
  }

  function findNear() {
    const p = S.p;
    let best = null, bd = REACH;
    if (S.state === 'play') for (const c of Z.world.containers) {
      if (Math.abs(c.x - p.x) > 4 || Math.abs(c.y - p.y) > 4) continue;
      const dx = p.x - clamp(p.x, c.x, c.x + c.w), dy = p.y - clamp(p.y, c.y, c.y + c.h);
      const d = Math.hypot(dx, dy);
      if (d < bd && Z.los(p.x, p.y, c.x + c.w / 2, c.y + c.h / 2)) { bd = d; best = c; }
    }
    S.near = best;
  }

  // ---------- Управление ----------
  const canvas = document.getElementById('game');
  canvas.addEventListener('pointerdown', (e) => {
    if (S.state !== 'play' || S.paused) return;
    e.preventDefault();
    if (e.clientX > window.innerWidth * 0.6) { attack(); return; } // тап справа — удар
    if (S.joy.active) return;
    Object.assign(S.joy, { active: true, id: e.pointerId, ox: e.clientX, oy: e.clientY, dx: 0, dy: 0 });
    try { canvas.setPointerCapture(e.pointerId); } catch (err) { /* не критично */ }
  });
  canvas.addEventListener('pointermove', (e) => {
    const j = S.joy;
    if (!j.active || e.pointerId !== j.id) return;
    const R = Z.JOY_R;
    let dx = e.clientX - j.ox, dy = e.clientY - j.oy;
    const m = Math.hypot(dx, dy);
    if (m > R * 1.4) { // джойстик едет за пальцем
      j.ox += (dx / m) * (m - R * 1.4);
      j.oy += (dy / m) * (m - R * 1.4);
      dx = e.clientX - j.ox; dy = e.clientY - j.oy;
    }
    const k = Math.min(1, Math.hypot(dx, dy) / R) / (Math.hypot(dx, dy) || 1);
    j.dx = dx * k;
    j.dy = dy * k;
  });
  const endJoy = (e) => { if (e.pointerId === S.joy.id) S.joy.active = false; };
  canvas.addEventListener('pointerup', endJoy);
  canvas.addEventListener('pointercancel', endJoy);
  document.addEventListener('contextmenu', (e) => e.preventDefault());

  ui.attack.addEventListener('pointerdown', (e) => { e.preventDefault(); attackHeld = true; attack(); });
  for (const ev of ['pointerup', 'pointercancel', 'pointerleave']) ui.attack.addEventListener(ev, () => { attackHeld = false; });
  ui.search.addEventListener('click', () => { if (S.near) openPanel(S.near); });
  ui.bag.addEventListener('click', () => openPanel(null));
  ui.sound.addEventListener('click', () => {
    Sfx.muted = !Sfx.muted;
    ui.sound.textContent = Sfx.muted ? '🔇' : '🔊';
    Platform.setItem('zb_muted', Sfx.muted ? '1' : '0');
  });

  window.addEventListener('keydown', (e) => {
    keys[e.code] = true;
    if (S.state === 'menu' && e.code === 'Enter') return Z.A.ready && start();
    if (S.state !== 'play') return;
    if (e.code === 'Space' || e.code === 'Tab') e.preventDefault();
    if (e.code === 'Escape' && S.paused) closePanel();
    else if (e.code === 'KeyE') { if (S.paused) closePanel(); else if (S.near) openPanel(S.near); }
    else if (e.code === 'KeyI' || e.code === 'Tab') { if (S.paused) closePanel(); else openPanel(null); }
  });
  window.addEventListener('keyup', (e) => { keys[e.code] = false; });
  window.addEventListener('blur', () => { for (const k in keys) keys[k] = false; attackHeld = false; });

  $('play').addEventListener('click', () => { if (Z.A.ready) start(); });
  $('again').addEventListener('click', start);
  $('share').addEventListener('click', () => {
    Platform.share(`Я продержался ${fmtSurvived(S.best.min)} в «Карантине» и убил ${S.best.kills} зомби. А ты?`);
  });

  // ---------- Старт ----------
  const touch = window.matchMedia('(pointer: coarse)').matches;
  ui.hint.innerHTML = touch
    ? 'Левая часть экрана — джойстик, отклони до упора, чтобы бежать.<br>Справа — удар, 🔍 — обыскать, 🎒 — рюкзак.'
    : 'WASD — ходьба, Shift — бег, Пробел — удар,<br>E — обыскать, I — рюкзак.';
  Platform.init(BG);
  Z.resize();
  window.addEventListener('resize', Z.resize);
  Platform.getItem('zb_best').then((v) => {
    try { if (v) S.best = Object.assign(S.best, JSON.parse(v)); } catch (e) { /* битые данные */ }
    ui.menuBest.textContent = fmtSurvived(S.best.min);
  });
  Platform.getItem('zb_muted').then((v) => { Sfx.muted = v === '1'; ui.sound.textContent = Sfx.muted ? '🔇' : '🔊'; });

  // фон меню: живой город за полупрозрачной заставкой — после загрузки спрайтов
  const playBtn = $('play');
  playBtn.disabled = true;
  playBtn.textContent = 'Загрузка…';
  Z.loadAssets().then(() => {
    newGame();
    playBtn.disabled = false;
    playBtn.textContent = 'Начать';
  }, (err) => {
    playBtn.textContent = 'Ошибка загрузки';
    console.error(err);
  });
  requestAnimationFrame(frame);
})();
