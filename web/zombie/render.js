// Отрисовка: город, мебель, персонажи (спрайты с анимацией), свет и эффекты.
(function () {
  const Z = window.Z;
  const T = Z.TILE, N = Z.N;
  const canvas = document.getElementById('game');
  const ctx = canvas.getContext('2d');
  const shade = document.createElement('canvas');   // слой темноты (в половинном разрешении)
  const sctx = shade.getContext('2d');

  let W = 0, H = 0, U = 32, camX = 0, camY = 0;
  const sx = (x) => (x - camX) * U + W / 2;
  const sy = (y) => (y - camY) * U + H / 2;
  Z.toWorld = (px, py) => ({ x: (px - W / 2) / U + camX, y: (py - H / 2) / U + camY });

  Z.resize = function () {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingQuality = 'high';
    U = Math.max(28, Math.min(96, Math.min(W, H) / 11));
    shade.width = Math.ceil(W / 2);
    shade.height = Math.ceil(H / 2);
  };

  // ---------- Ассеты ----------
  const A = Z.A = { ready: false };
  const ZOMBIE_LOOKS = [null, [215, 0.55, 0.9], [355, 0.6, 0.85], [0, 0.08, 0.95]]; // [оттенок, насыщенность×, яркость×]
  Z.ZOMBIE_VARIANTS = ZOMBIE_LOOKS.length;

  function loadImage(src) {
    return new Promise((ok, fail) => {
      const im = new Image();
      im.onload = () => ok(im);
      im.onerror = () => fail(new Error('Не загрузилось: ' + src));
      im.src = src;
    });
  }

  function toCanvas(img) {
    const c = document.createElement('canvas');
    c.width = img.width;
    c.height = img.height;
    c.getContext('2d').drawImage(img, 0, 0);
    return c;
  }

  // перекрашиваем зелёную одежду зомби, кожу не трогаем
  function recolor(img, look) {
    const c = toCanvas(img);
    if (!look) return c;
    const g = c.getContext('2d');
    try {
      const data = g.getImageData(0, 0, c.width, c.height), p = data.data;
      const [hue, ks, kl] = look;
      for (let i = 0; i < p.length; i += 4) {
        if (!p[i + 3]) continue;
        const r = p[i] / 255, gg = p[i + 1] / 255, b = p[i + 2] / 255;
        const max = Math.max(r, gg, b), min = Math.min(r, gg, b), d = max - min;
        if (d < 0.08) continue;
        let h;
        if (max === r) h = ((gg - b) / d) % 6; else if (max === gg) h = (b - r) / d + 2; else h = (r - gg) / d + 4;
        h *= 60; if (h < 0) h += 360;
        if (h < 65 || h > 175) continue;
        let l = (max + min) / 2, s = d / (1 - Math.abs(2 * l - 1));
        s = Math.min(1, s * ks); l = Math.min(1, l * kl);
        const C = (1 - Math.abs(2 * l - 1)) * s, X = C * (1 - Math.abs(((hue / 60) % 2) - 1)), m = l - C / 2;
        let rr, g2, bb;
        const seg = Math.floor(hue / 60) % 6;
        if (seg === 0) [rr, g2, bb] = [C, X, 0]; else if (seg === 1) [rr, g2, bb] = [X, C, 0];
        else if (seg === 2) [rr, g2, bb] = [0, C, X]; else if (seg === 3) [rr, g2, bb] = [0, X, C];
        else if (seg === 4) [rr, g2, bb] = [X, 0, C]; else [rr, g2, bb] = [C, 0, X];
        p[i] = (rr + m) * 255; p[i + 1] = (g2 + m) * 255; p[i + 2] = (bb + m) * 255;
      }
      g.putImageData(data, 0, 0);
    } catch (e) { /* холст недоступен для чтения (file://) — оставляем как есть */ }
    return c;
  }

  // тело для трупа: первый кадр стоящего зомби, притемнённый
  function makeCorpse(sheet) {
    const a = A.chars.anims.z_idle, [fx, fy] = a.frames[0];
    const c = document.createElement('canvas');
    c.width = a.w; c.height = a.h;
    const g = c.getContext('2d');
    g.drawImage(sheet, fx, fy, a.w, a.h, 0, 0, a.w, a.h);
    g.globalCompositeOperation = 'source-atop';
    g.fillStyle = 'rgba(25,8,8,0.45)';
    g.fillRect(0, 0, a.w, a.h);
    return c;
  }

  Z.loadAssets = function () {
    const atlas = window.Z_ATLAS, data = window.Z_ASSET_DATA || {};
    const url = (n) => data[n] || `assets/${n}.png`;
    return Promise.all([loadImage(url('chars')), loadImage(url('zombies')), loadImage(url('world'))])
      .then(([chars, zombies, world]) => {
        A.chars = atlas.chars;
        A.world = atlas.world;
        A.charSheet = chars;
        A.worldSheet = world;
        A.zombieSheets = ZOMBIE_LOOKS.map((look) => recolor(zombies, look));
        A.corpses = A.zombieSheets.map(makeCorpse);
        A.ready = true;
      });
  };

  function spr(name, x, y, w, h) {
    const r = A.world.rects[name];
    ctx.drawImage(A.worldSheet, r[0], r[1], r[2], r[3], x, y, w, h);
  }

  // спрайт мира по центру (cx, cy) с поворотом, размер в клетках
  function sprRot(name, cx, cy, w, h, rot) {
    ctx.save();
    ctx.translate(sx(cx), sy(cy));
    if (rot) ctx.rotate(rot);
    spr(name, -w * U / 2, -h * U / 2, w * U, h * U);
    ctx.restore();
  }

  function drawAnim(sheet, name, frame, x, y, rot, scale, alpha) {
    const a = A.chars.anims[name];
    const [fx, fy] = a.frames[((frame % a.n) + a.n) % a.n];
    const k = (U / A.chars.ppt) * (scale || 1);
    ctx.save();
    ctx.translate(sx(x), sy(y));
    ctx.rotate(rot);
    if (alpha != null) ctx.globalAlpha = alpha;
    ctx.drawImage(sheet, fx, fy, a.w, a.h, -a.pivot[0] * k, -a.pivot[1] * k, a.w * k, a.h * k);
    ctx.restore();
  }

  function circ(x, y, r) { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); }
  function line(x1, y1, x2, y2) { ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); }

  // ---------- Клетки ----------
  const FLOORS = ['wood0', 'wood1', 'wood2', 'wood3'];
  function floorSprite(style, tx, ty) {
    if (style === 4) return 'tileA';
    if (style === 5) return (tx * 3 + ty) % 5 ? 'lino0' : 'lino1';
    return FLOORS[style] || 'wood0';
  }

  function drawTiles(x0, y0, x1, y1) {
    const wd = Z.world;
    for (let ty = y0; ty <= y1; ty++) {
      const Y = Math.round(sy(ty)), h = Math.round(sy(ty + 1)) - Y;
      for (let tx = x0; tx <= x1; tx++) {
        const X = Math.round(sx(tx)), w = Math.round(sx(tx + 1)) - X;
        if (tx < 0 || ty < 0 || tx >= N || ty >= N) { spr('grass' + ((tx * 7 + ty * 3) & 3), X, Y, w, h); continue; }
        const i = ty * N + tx, t = wd.tiles[i], dv = wd.deco[i];
        switch (t) {
          case T.GRASS: case T.TREE:
            spr('grass' + (dv & 3), X, Y, w, h);
            break;
          case T.ROAD: drawRoad(i, dv, X, Y, w, h); break;
          case T.WALK:
            spr(dv & 1 ? 'walk1' : 'walk0', X, Y, w, h);
            ctx.fillStyle = 'rgba(0,0,0,0.25)';  // бордюр у проезжей части
            if (Z.tileAt(tx - 1, ty) === T.ROAD) ctx.fillRect(X, Y, 2, h);
            if (Z.tileAt(tx + 1, ty) === T.ROAD) ctx.fillRect(X + w - 2, Y, 2, h);
            if (Z.tileAt(tx, ty - 1) === T.ROAD) ctx.fillRect(X, Y, w, 2);
            if (Z.tileAt(tx, ty + 1) === T.ROAD) ctx.fillRect(X, Y + h - 2, w, 2);
            break;
          case T.FLOOR: spr(floorSprite(wd.floor[i], tx, ty), X, Y, w, h); break;
          case T.FURN: {
            const ci = wd.contAt[i];
            if (ci >= 0 && wd.containers[ci].type === 'car') drawRoad(i, dv, X, Y, w, h);
            else spr(floorSprite(wd.floor[i], tx, ty), X, Y, w, h);
            break;
          }
          case T.DOOR: {
            spr(floorSprite(wd.floor[i], tx, ty), X, Y, w, h);
            const vert = Z.tileAt(tx, ty - 1) === T.WALL || Z.tileAt(tx, ty + 1) === T.WALL;
            ctx.fillStyle = '#4a3322';  // открытая дверь
            if (vert) ctx.fillRect(X, Y, w * 0.85, Math.max(2, h * 0.13));
            else ctx.fillRect(X, Y, Math.max(2, w * 0.13), h * 0.85);
            break;
          }
          case T.WALL: drawWall(tx, ty, X, Y, w, h); break;
        }
      }
    }
  }

  function drawRoad(i, dv, X, Y, w, h) {
    spr(dv & 1 ? 'asphalt1' : 'asphalt0', X, Y, w, h);
    const m = Z.world.mark[i];
    if (m && ((i % N) + ((i / N) | 0)) % 2 === 0) {
      ctx.fillStyle = 'rgba(200,180,110,0.5)';
      if (m === 1) ctx.fillRect(X + w * 0.15, Y + h * 0.46, w * 0.7, Math.max(2, h * 0.08));
      else ctx.fillRect(X + w * 0.46, Y + h * 0.15, Math.max(2, w * 0.08), h * 0.7);
    }
  }

  function drawWall(tx, ty, X, Y, w, h) {
    const isW = (x, y) => Z.tileAt(x, y) === T.WALL;
    ctx.fillStyle = '#cbc2b0';
    ctx.fillRect(X, Y, w, h);
    ctx.fillStyle = 'rgba(0,0,0,0.06)';
    ctx.fillRect(X, Y + h * 0.5, w, h * 0.5);
    if (!isW(tx, ty + 1)) { ctx.fillStyle = '#8b816e'; ctx.fillRect(X, Y + h * 0.66, w, h * 0.34 + 1); }
    ctx.fillStyle = '#5f5647';
    if (!isW(tx - 1, ty)) ctx.fillRect(X, Y, 2, h);
    if (!isW(tx + 1, ty)) ctx.fillRect(X + w - 2, Y, 2, h);
    if (!isW(tx, ty - 1)) ctx.fillRect(X, Y, w, 2);
    if (!isW(tx, ty + 1)) ctx.fillRect(X, Y + h - 2, w, 2);
  }

  // ---------- Мебель, машины ----------
  const GOODS = ['#a8453a', '#c99a3e', '#4f7aa3', '#5f8f4e', '#d8d2c2', '#8a5a8f'];
  const CONT_SPRITE = { fridge: 'fridge', wardrobe: 'dresser', toolbox: 'crate', drinks: 'drinks', locker: 'locker' };

  function drawContainer(c, active) {
    const cx = c.x + c.w / 2, cy = c.y + c.h / 2;
    if (c.type === 'car') {
      ctx.fillStyle = 'rgba(0,0,0,0.3)';
      const horiz = c.w > c.h;
      ctx.save();
      ctx.translate(sx(cx) + U * 0.08, sy(cy) + U * 0.12);
      if (horiz) ctx.rotate(Math.PI / 2);
      ctx.fillRect(-U * 0.42, -U * 0.95, U * 0.84, U * 1.9);
      ctx.restore();
      sprRot('car_' + c.model, cx, cy, 1.25, 2, horiz ? (c.x % 2 ? Math.PI / 2 : -Math.PI / 2) : (c.y % 2 ? 0 : Math.PI));
    } else if (c.type === 'shelf') {
      for (let k = 0; k < c.w; k++) sprRot(k === 0 ? 'shelf_l' : k === c.w - 1 ? 'shelf_r' : 'shelf_m', c.x + k + 0.5, cy, 1, 1, 0);
      // товар на полке, пока её не вынесли
      const left = c.items ? Math.min(1, c.items.length / 3) : 1;
      const n = Math.round(c.w * 6 * left);
      for (let k = 0; k < n; k++) {
        ctx.fillStyle = GOODS[(c.x * 7 + c.y * 3 + k * 5) % GOODS.length];
        const gx = sx(c.x + 0.2 + (k % (c.w * 3)) * ((c.w - 0.4) / (c.w * 3)));
        const gy = sy(c.y + (k < c.w * 3 ? 0.27 : 0.53));
        ctx.fillRect(gx, gy, U * 0.17, U * 0.2);
      }
    } else if (c.type === 'desk') {
      sprRot('desk_m', cx, cy, 1, 1, c.rot);
      sprRot('laptop', cx, cy, 0.5, 0.5, c.rot);
    } else {
      sprRot(c.type === 'cupboard' ? c.sprite : CONT_SPRITE[c.type], cx, cy, 1, 1, c.rot);
    }
    if (c.items && c.items.length === 0) {
      ctx.fillStyle = 'rgba(0,0,0,0.2)';
      ctx.fillRect(sx(c.x), sy(c.y), c.w * U, c.h * U);
    }
    if (active) {
      const t = (Math.sin(performance.now() / 180) + 1) / 2;
      ctx.strokeStyle = `rgba(242,209,107,${0.55 + 0.45 * t})`;
      ctx.lineWidth = 2;
      ctx.strokeRect(sx(c.x) + 1, sy(c.y) + 1, c.w * U - 2, c.h * U - 2);
    }
  }

  function drawDecor(d) {
    ctx.save();
    ctx.translate(sx(d.x + d.w / 2), sy(d.y + 0.5));
    if (d.rot) ctx.rotate(d.rot);
    for (let k = 0; k < d.parts.length; k++) spr(d.parts[k], (k - d.w / 2) * U, -U / 2, U, U);
    ctx.restore();
  }

  // ---------- Деревья и крыши ----------
  function drawTrees(x0, y0, x1, y1) {
    const wd = Z.world;
    for (let ty = y0 - 1; ty <= y1 + 1; ty++) for (let tx = x0 - 1; tx <= x1 + 1; tx++) {
      if (Z.tileAt(tx, ty) !== T.TREE) continue;
      const dv = tx >= 0 && ty >= 0 && tx < N && ty < N ? wd.deco[ty * N + tx] : (tx * 31 + ty * 17) & 255;
      const size = 1.55 + (dv % 5) * 0.08;
      const cx = tx + 0.5 + ((dv % 5) - 2) * 0.05, cy = ty + 0.5 + ((dv % 7) - 3) * 0.04;
      ctx.fillStyle = 'rgba(0,0,0,0.28)';
      circ(sx(cx + 0.18), sy(cy + 0.24), size * U * 0.42);
      sprRot('tree' + (dv % 3), cx, cy, size, size, (dv / 255) * Math.PI * 2);
    }
  }

  function drawRoof(b) {
    if (b.roofA < 0.01) return;
    const o = 0.12;
    const X = sx(b.x - o), Y = sy(b.y - o), w = (b.w + 2 * o) * U, h = (b.h + 2 * o) * U;
    if (X > W || Y > H || X + w < 0 || Y + h < 0) return;
    ctx.globalAlpha = b.roofA;
    ctx.fillStyle = 'rgba(0,0,0,0.3)';
    ctx.fillRect(X + U * 0.18, Y + U * 0.24, w, h);
    ctx.fillStyle = b.roof;
    ctx.fillRect(X, Y, w, h);
    if (b.kind === 'house') {
      const along = b.w >= b.h;
      ctx.fillStyle = 'rgba(0,0,0,0.18)';
      if (along) ctx.fillRect(X, Y + h / 2, w, h / 2); else ctx.fillRect(X + w / 2, Y, w / 2, h);
      ctx.fillStyle = 'rgba(0,0,0,0.13)';
      const step = U * 0.36;
      if (along) for (let yy = Y + step; yy < Y + h; yy += step) ctx.fillRect(X, yy, w, 1);
      else for (let xx = X + step; xx < X + w; xx += step) ctx.fillRect(xx, Y, 1, h);
      ctx.fillStyle = 'rgba(255,255,255,0.16)';
      if (along) ctx.fillRect(X, Y + h / 2 - 1.5, w, 3); else ctx.fillRect(X + w / 2 - 1.5, Y, 3, h);
      ctx.fillStyle = 'rgba(0,0,0,0.35)';
      ctx.fillRect(X, Y + h - 2, w, 2);
    } else {
      ctx.strokeStyle = 'rgba(0,0,0,0.25)';
      ctx.lineWidth = 2;
      ctx.strokeRect(X + U * 0.3, Y + U * 0.3, w - U * 0.6, h - U * 0.6);
      ctx.fillStyle = 'rgba(0,0,0,0.25)';
      ctx.fillRect(X + w * 0.15, Y + h * 0.2, U * 0.8, U * 0.8);
      ctx.fillRect(X + w * 0.75, Y + h * 0.7, U * 0.8, U * 0.6);
      ctx.fillStyle = b.kind === 'police' ? '#a9c2e6' : '#e8e0c8';
      ctx.font = `800 ${Math.round(U * 0.8)}px system-ui, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(b.name, X + w / 2, Y + h / 2);
    }
    ctx.globalAlpha = 1;
  }

  // ---------- Персонажи ----------
  function shadow(x, y, r) {
    ctx.fillStyle = 'rgba(0,0,0,0.28)';
    ctx.beginPath();
    ctx.ellipse(sx(x) + U * 0.06, sy(y) + U * 0.1, r * U, r * U * 0.85, 0, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawZombie(z, now) {
    const sheet = A.zombieSheets[z.variant];
    let name, frame;
    if (z.atkAnim > 0) { name = 'z_attack'; frame = Math.floor((1 - z.atkAnim / 0.55) * A.chars.anims.z_attack.n); }
    else if (z.moving) { name = 'z_move'; frame = Math.floor(z.walkT * 2.4); }
    else { name = 'z_idle'; frame = Math.floor(now / 110 + z.seed * 9); }
    ctx.globalAlpha = z.alpha;
    shadow(z.x, z.y, 0.36 * z.scale);
    drawAnim(sheet, name, frame, z.x, z.y, z.face, z.scale, z.alpha);
    if (z.flash > 0) {
      ctx.globalCompositeOperation = 'lighter';
      drawAnim(sheet, name, frame, z.x, z.y, z.face, z.scale, Math.min(1, z.flash * 6) * z.alpha);
      ctx.globalCompositeOperation = 'source-over';
    }
    ctx.globalAlpha = 1;
  }

  function drawCorpse(c) {
    const img = A.corpses[c.variant || 0], a = A.chars.anims.z_idle;
    const k = (U / A.chars.ppt) * (c.scale || 1);
    ctx.save();
    ctx.translate(sx(c.x), sy(c.y));
    ctx.rotate(c.face);
    ctx.drawImage(img, -a.pivot[0] * k, -a.pivot[1] * k, a.w * k, a.h * k);
    ctx.restore();
  }

  function drawPlayer(p, S, now) {
    const gun = S.gunEquipped(), set = gun ? 'p_gun' : 'p_melee';
    const sheet = A.charSheet;
    if (S.state === 'dead') {
      ctx.globalAlpha = 0.9;
      drawAnim(sheet, set + '_idle', 0, p.x, p.y, p.face + 1.2, 1);
      ctx.globalAlpha = 1;
      return;
    }
    shadow(p.x, p.y, 0.36);
    // ноги
    if (p.moving) drawAnim(sheet, p.running ? 'feet_run' : 'feet_walk', Math.floor(p.walkT * 2.2), p.x, p.y, p.face, 1);
    else drawAnim(sheet, 'feet_idle', 0, p.x, p.y, p.face, 1);
    // туловище
    let name, frame;
    if (p.atkAnim > 0) {
      const dur = gun ? 0.12 : 0.3;
      name = gun ? 'p_gun_shoot' : 'p_melee_attack';
      frame = Math.floor((1 - p.atkAnim / dur) * A.chars.anims[name].n);
    } else if (p.moving) { name = set + '_move'; frame = Math.floor(p.walkT * 2.2); }
    else { name = set + '_idle'; frame = Math.floor(now / 100); }
    drawAnim(sheet, name, frame, p.x, p.y, p.face, 1);
  }

  // ---------- Кадр ----------
  let vignette = null, vW = 0, vH = 0;
  Z.render = function () {
    const S = Z.S, p = S.p, wd = Z.world, now = performance.now();
    if (!A.ready) return;
    const shake = S.shake || 0;
    camX = p.x + (Math.random() - 0.5) * shake / U;
    camY = p.y + (Math.random() - 0.5) * shake / U;

    const x0 = Math.floor(camX - W / 2 / U) - 1, x1 = Math.ceil(camX + W / 2 / U) + 1;
    const y0 = Math.floor(camY - H / 2 / U) - 1, y1 = Math.ceil(camY + H / 2 / U) + 1;
    const inView = (x, y, m) => x > x0 - m && x < x1 + m && y > y0 - m && y < y1 + m;

    drawTiles(x0, y0, x1, y1);

    for (const d of wd.decor) if (!d.solid && inView(d.x, d.y, 3)) drawDecor(d);
    for (const d of S.decals) {
      if (!inView(d.x, d.y, 1)) continue;
      ctx.globalAlpha = d.a;
      sprRot('blood' + d.v, d.x, d.y, d.r * 2, d.r * 2, d.rot);
    }
    ctx.globalAlpha = 1;
    for (const d of wd.decor) if (d.solid && inView(d.x, d.y, 3)) drawDecor(d);
    for (const c of wd.containers) if (inView(c.x, c.y, 3)) drawContainer(c, c === S.near);
    for (const c of S.corpses) if (inView(c.x, c.y, 2)) drawCorpse(c);

    for (const z of S.zombies) {
      if (z.alpha < 0.02 || !inView(z.x, z.y, 2)) continue;
      drawZombie(z, now);
    }
    drawPlayer(p, S, now);

    // брызги крови
    for (const q of S.parts) {
      ctx.fillStyle = `rgba(120,10,12,${Math.max(0, 1 - q.t / q.life)})`;
      circ(sx(q.x), sy(q.y), q.size * U);
    }
    // выстрелы
    for (const f of S.fx) {
      const a = 1 - f.t / f.life;
      if (f.kind === 'tracer') {
        ctx.strokeStyle = `rgba(255,230,150,${a})`;
        ctx.lineWidth = 2;
        line(sx(f.x1), sy(f.y1), sx(f.x2), sy(f.y2));
      } else if (f.kind === 'flash') {
        const g = ctx.createRadialGradient(sx(f.x1), sy(f.y1), 0, sx(f.x1), sy(f.y1), U * 0.6);
        g.addColorStop(0, `rgba(255,240,180,${a})`);
        g.addColorStop(1, 'rgba(255,160,60,0)');
        ctx.fillStyle = g;
        circ(sx(f.x1), sy(f.y1), U * 0.6);
      }
    }

    drawTrees(x0, y0, x1, y1);
    for (const b of wd.buildings) drawRoof(b);

    // ночь: темнота, пятно света и луч фонарика
    if (S.dark > 0.01) {
      const sw = shade.width, sh = shade.height;
      sctx.globalCompositeOperation = 'source-over';
      sctx.clearRect(0, 0, sw, sh);
      sctx.fillStyle = `rgba(3,6,18,${S.dark})`;
      sctx.fillRect(0, 0, sw, sh);
      sctx.globalCompositeOperation = 'destination-out';
      const px = sx(p.x) / 2, py = sy(p.y) / 2;
      const holes = [[px, py, (S.lightR * U) / 2]];
      for (const f of S.fx) if (f.kind === 'flash') holes.push([sx(f.x1) / 2, sy(f.y1) / 2, (5 * (1 - f.t / f.life) * U) / 2]);
      for (const [hx, hy, R] of holes) {
        const g = sctx.createRadialGradient(hx, hy, R * 0.1, hx, hy, R);
        g.addColorStop(0, 'rgba(0,0,0,1)');
        g.addColorStop(0.55, 'rgba(0,0,0,0.8)');
        g.addColorStop(1, 'rgba(0,0,0,0)');
        sctx.fillStyle = g;
        sctx.beginPath(); sctx.arc(hx, hy, R, 0, Math.PI * 2); sctx.fill();
      }
      if (S.flashlight && S.state === 'play') {
        const L = (S.coneLen * U) / 2;
        const g = sctx.createRadialGradient(px, py, 0, px, py, L);
        g.addColorStop(0, 'rgba(0,0,0,1)');
        g.addColorStop(0.7, 'rgba(0,0,0,0.85)');
        g.addColorStop(1, 'rgba(0,0,0,0)');
        sctx.fillStyle = g;
        sctx.beginPath();
        sctx.moveTo(px, py);
        sctx.arc(px, py, L, p.face - 0.42, p.face + 0.42);
        sctx.closePath();
        sctx.fill();
      }
      ctx.drawImage(shade, 0, 0, W, H);
      if (S.flashlight && S.state === 'play') { // тёплый оттенок луча
        ctx.save();
        ctx.globalCompositeOperation = 'soft-light';
        const L = S.coneLen * U, cxp = sx(p.x), cyp = sy(p.y);
        const g = ctx.createRadialGradient(cxp, cyp, 0, cxp, cyp, L);
        g.addColorStop(0, `rgba(255,220,150,${0.5 * S.dark})`);
        g.addColorStop(1, 'rgba(255,220,150,0)');
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.moveTo(cxp, cyp); ctx.arc(cxp, cyp, L, p.face - 0.42, p.face + 0.42); ctx.closePath(); ctx.fill();
        ctx.restore();
      }
    }

    // виньетка (заготовка пересоздаётся только при смене размера)
    if (!vignette || vW !== W || vH !== H) {
      vW = W; vH = H;
      vignette = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.35, W / 2, H / 2, Math.hypot(W, H) * 0.6);
      vignette.addColorStop(0, 'rgba(0,0,0,0)');
      vignette.addColorStop(1, 'rgba(0,0,0,0.45)');
    }
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, W, H);

    // вспышка урона и низкое здоровье
    const hurt = Math.max(S.hurtFlash, p.hp < 30 && S.state === 'play' ? 0.25 + 0.15 * Math.sin(now / 250) : 0);
    if (hurt > 0.01) {
      const g = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.3, W / 2, H / 2, Math.max(W, H) * 0.75);
      g.addColorStop(0, 'rgba(150,0,0,0)');
      g.addColorStop(1, `rgba(150,0,0,${0.55 * hurt})`);
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
    }

    // джойстик
    const j = S.joy;
    if (j.active) {
      const R = Z.JOY_R;
      ctx.fillStyle = 'rgba(255,255,255,0.08)';
      ctx.strokeStyle = 'rgba(255,255,255,0.3)';
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(j.ox, j.oy, R, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.fillStyle = j.run ? 'rgba(255,200,120,0.55)' : 'rgba(255,255,255,0.4)';
      circ(j.ox + j.dx * R, j.oy + j.dy * R, R * 0.42);
    }
  };
})();
