// «Башня» — ставь блоки друг на друга. Всё, что не попало на башню, отрезается.
(function () {
  'use strict';

  // Мир в условных единицах: ширина поля = 400, экран масштабируется под устройство.
  const WORLD_W = 400;
  const BLOCK_H = 34;
  const DEPTH_X = 16, DEPTH_Y = 11;  // «объём» блока
  const START_W = 220;
  const PERFECT_TOL = 5;             // допуск идеального попадания
  const GROW_AFTER = 3;              // после N идеальных подряд блок расширяется
  const GROW_BY = 12;
  const GRAVITY = 1600;
  const BG = '#16182f';

  const canvas = document.getElementById('game');
  const ctx = canvas.getContext('2d');
  const $ = (id) => document.getElementById(id);
  const ui = {
    hud: $('hud'), score: $('score'), combo: $('combo'), sound: $('sound'),
    menu: $('menu'), menuBest: $('menu-best'),
    over: $('over'), final: $('final-score'), overBest: $('over-best'), record: $('new-record'),
  };

  let W = 0, H = 0, baseScale = 1, groundY = 0;
  let state = 'menu';      // menu | play | over
  let stack, current, debris, effects;
  let cam = 0, camTarget = 0, zoom = 1, zoomTarget = 1;
  let score = 0, best = 0, combo = 0, hueBase = 0;
  let muted = false, overTimer = 0;

  // ---------- Экран ----------
  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    baseScale = Math.min(Math.min(W, 480) / WORLD_W, H / 640);
    groundY = H * 0.78;
    if (stack) camTarget = state === 'over' ? 0 : cameraFor(stack.length);
  }

  function cameraFor(height) {
    // держим движущийся блок примерно на 42% высоты экрана
    const top = (height + 1) * BLOCK_H;
    return Math.max(0, top - (groundY - H * 0.42) / baseScale);
  }

  const hueOf = (i) => (hueBase + i * 7) % 360;

  // ---------- Звук (WebAudio, без файлов) ----------
  let actx = null;
  function tone(freq, dur, type, vol) {
    if (muted) return;
    try {
      actx = actx || new (window.AudioContext || window.webkitAudioContext)();
      if (actx.state === 'suspended') actx.resume();
      const t = actx.currentTime;
      const o = actx.createOscillator(), g = actx.createGain();
      o.type = type || 'sine';
      o.frequency.value = freq;
      g.gain.setValueAtTime(vol || 0.15, t);
      g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      o.connect(g).connect(actx.destination);
      o.start(t);
      o.stop(t + dur);
    } catch (e) { /* звук недоступен */ }
  }
  const SCALE = [523, 587, 659, 784, 880, 1047, 1175, 1319, 1568];

  function updateSoundIcon() { ui.sound.textContent = muted ? '🔇' : '🔊'; }

  // ---------- Игра ----------
  function reset() {
    hueBase = Math.floor(Math.random() * 360);
    stack = [{ x: (WORLD_W - START_W) / 2, w: START_W, hue: hueOf(0) }];
    debris = [];
    effects = [];
    score = 0;
    combo = 0;
    zoomTarget = 1;
    camTarget = cameraFor(1);
    spawn();
  }

  function spawn() {
    const top = stack[stack.length - 1];
    const fromLeft = stack.length % 2 === 0;
    current = {
      x: fromLeft ? -top.w * 0.5 : WORLD_W - top.w * 0.5,
      w: top.w,
      dir: fromLeft ? 1 : -1,
      speed: 150 + Math.min(score, 60) * 5.5,
      hue: hueOf(stack.length),
    };
  }

  function start() {
    clearTimeout(overTimer);
    reset();
    state = 'play';
    ui.score.textContent = '0';
    ui.menu.classList.add('hidden');
    ui.over.classList.add('hidden');
    ui.hud.classList.remove('hidden');
  }

  function place() {
    const top = stack[stack.length - 1];
    const c = current;
    const wy = stack.length * BLOCK_H;
    const delta = c.x - top.x;

    if (Math.abs(delta) <= PERFECT_TOL) {
      combo++;
      let x = top.x, w = top.w;
      if (combo >= GROW_AFTER && w < START_W) {
        const g = Math.min(GROW_BY, START_W - w);
        w += g;
        x -= g / 2;
      }
      stack.push({ x, w, hue: c.hue });
      effects.push({ x, wy, w, t: 0 });
      showCombo();
      tone(SCALE[Math.min(combo - 1, SCALE.length - 1)], 0.3, 'sine', 0.18);
      Platform.haptic(combo >= GROW_AFTER ? 'success' : 'medium');
    } else {
      const left = Math.max(c.x, top.x);
      const right = Math.min(c.x + c.w, top.x + top.w);
      const overlap = right - left;
      if (overlap <= 0) {
        debris.push({ x: c.x, y: wy, w: c.w, vx: c.dir * 30, vy: 0, hue: c.hue, a: 1 });
        current = null;
        return gameOver();
      }
      combo = 0;
      // отрезанный кусок падает вниз
      debris.push({
        x: delta > 0 ? right : c.x, y: wy, w: c.w - overlap,
        vx: (delta > 0 ? 1 : -1) * 50, vy: 0, hue: c.hue, a: 1,
      });
      stack.push({ x: left, w: overlap, hue: c.hue });
      tone(200 + Math.min(score, 40) * 8, 0.12, 'triangle', 0.2);
      Platform.haptic('light');
    }

    score++;
    ui.score.textContent = score;
    camTarget = cameraFor(stack.length);
    spawn();
  }

  function showCombo() {
    ui.combo.textContent = combo > 1 ? 'Идеально ×' + combo : 'Идеально!';
    ui.combo.classList.remove('show');
    void ui.combo.offsetWidth; // перезапуск анимации
    ui.combo.classList.add('show');
  }

  function gameOver() {
    state = 'over';
    tone(140, 0.45, 'sawtooth', 0.12);
    Platform.haptic('error');

    const isRecord = score > best;
    if (isRecord) {
      best = score;
      Platform.setItem('best', best);
    }

    // отдаляем камеру, чтобы показать всю башню
    const towerPx = (stack.length + 1) * BLOCK_H * baseScale;
    zoomTarget = Math.min(1, (groundY - H * 0.22) / towerPx);
    camTarget = 0;

    overTimer = setTimeout(() => {
      ui.hud.classList.add('hidden');
      ui.final.textContent = score;
      ui.overBest.textContent = best;
      ui.menuBest.textContent = best;
      ui.record.classList.toggle('hidden', !isRecord || score === 0);
      ui.over.classList.remove('hidden');
    }, 800);
  }

  // ---------- Цикл ----------
  function update(dt) {
    if (current) {
      current.x += current.dir * current.speed * dt;
      const lo = -current.w * 0.5, hi = WORLD_W - current.w * 0.5;
      if (current.x < lo) { current.x = lo; current.dir = 1; }
      if (current.x > hi) { current.x = hi; current.dir = -1; }
    }
    for (const d of debris) {
      d.vy -= GRAVITY * dt;
      d.y += d.vy * dt;
      d.x += d.vx * dt;
      d.a -= dt * 0.7;
    }
    debris = debris.filter((d) => d.a > 0);
    for (const f of effects) f.t += dt;
    effects = effects.filter((f) => f.t < 0.5);

    const k = Math.min(1, dt * 5);
    cam += (camTarget - cam) * k;
    zoom += (zoomTarget - zoom) * Math.min(1, dt * 3);
  }

  function render() {
    const s = baseScale * zoom;
    const ox = (W - WORLD_W * s) / 2;
    const dx = DEPTH_X * s, dy = DEPTH_Y * s;
    const toY = (wy) => groundY - (wy - cam) * s;

    // фон плавно меняет оттенок по мере роста
    const bh = (hueBase + 200 + score * 3) % 360;
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, `hsl(${bh}, 35%, 14%)`);
    g.addColorStop(1, `hsl(${(bh + 40) % 360}, 40%, 28%)`);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);

    function box(x, wy, w, h, hue, alpha) {
      const X = ox + x * s, Y = toY(wy + h), bw = w * s, bhgt = h * s;
      if (Y > H + dy || Y + bhgt < -dy) return;
      ctx.globalAlpha = alpha;
      ctx.fillStyle = `hsl(${hue}, 65%, 56%)`;           // перед
      ctx.fillRect(X, Y, bw, bhgt);
      ctx.fillStyle = `hsl(${hue}, 75%, 70%)`;           // верх
      ctx.beginPath();
      ctx.moveTo(X, Y); ctx.lineTo(X + dx, Y - dy); ctx.lineTo(X + bw + dx, Y - dy); ctx.lineTo(X + bw, Y);
      ctx.closePath(); ctx.fill();
      ctx.fillStyle = `hsl(${hue}, 60%, 40%)`;           // бок
      ctx.beginPath();
      ctx.moveTo(X + bw, Y); ctx.lineTo(X + bw + dx, Y - dy); ctx.lineTo(X + bw + dx, Y + bhgt - dy); ctx.lineTo(X + bw, Y + bhgt);
      ctx.closePath(); ctx.fill();
      ctx.globalAlpha = 1;
    }

    // постамент + башня
    const base = stack[0];
    const pedestal = H / s + 50;
    box(base.x, -pedestal, base.w, pedestal + BLOCK_H, base.hue, 1);
    for (let i = 1; i < stack.length; i++) {
      const b = stack[i];
      box(b.x, i * BLOCK_H, b.w, BLOCK_H, b.hue, 1);
    }
    for (const d of debris) box(d.x, d.y, d.w, BLOCK_H, d.hue, Math.max(0, d.a));
    if (current) box(current.x, stack.length * BLOCK_H, current.w, BLOCK_H, current.hue, 1);

    // вспышка при идеальном попадании
    for (const f of effects) {
      const p = f.t / 0.5, pad = p * 16 * s;
      ctx.strokeStyle = `rgba(255, 255, 255, ${1 - p})`;
      ctx.lineWidth = 3;
      ctx.strokeRect(ox + f.x * s - pad, toY(f.wy + BLOCK_H) - dy - pad, f.w * s + dx + pad * 2, BLOCK_H * s + dy + pad * 2);
    }
  }

  let last = performance.now();
  function frame(now) {
    const dt = Math.min(0.033, (now - last) / 1000);
    last = now;
    update(dt);
    render();
    requestAnimationFrame(frame);
  }

  // ---------- Управление ----------
  canvas.addEventListener('pointerdown', (e) => {
    if (state !== 'play') return;
    e.preventDefault();
    place();
  });
  window.addEventListener('keydown', (e) => {
    if (e.code !== 'Space' && e.code !== 'Enter') return;
    e.preventDefault();
    if (state === 'play') place();
    else if (state === 'menu' || !ui.over.classList.contains('hidden')) start();
  });
  $('play').addEventListener('click', start);
  $('again').addEventListener('click', start);
  $('share').addEventListener('click', () => {
    Platform.share('Я построил башню из ' + score + ' блоков в «Башне»! Сможешь выше?');
  });
  ui.sound.addEventListener('click', () => {
    muted = !muted;
    updateSoundIcon();
    Platform.setItem('muted', muted ? '1' : '0');
  });

  // ---------- Старт ----------
  Platform.init(BG);
  resize();
  window.addEventListener('resize', resize);
  reset();
  requestAnimationFrame(frame);

  Platform.getItem('best').then((v) => {
    best = Math.max(best, parseInt(v, 10) || 0);
    ui.menuBest.textContent = best;
  });
  Platform.getItem('muted').then((v) => { muted = v === '1'; updateSoundIcon(); });
})();
