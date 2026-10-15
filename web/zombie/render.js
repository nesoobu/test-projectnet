// Отрисовка: город, люди, зомби, крыши, ночь.
(function () {
  const Z = window.Z;
  const T = Z.TILE, N = Z.N;
  const canvas = document.getElementById('game');
  const ctx = canvas.getContext('2d');
  const shade = document.createElement('canvas');   // слой темноты (в половинном разрешении)
  const sctx = shade.getContext('2d');

  let W = 0, H = 0, U = 32, camX = 0, camY = 0;

  const GRASS = ['#3e4a30', '#3b472e', '#415034', '#394429'];
  const WOOD = ['#7a6248', '#735c43'];
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
    U = Math.max(24, Math.min(90, Math.min(W, H) / 13));
    shade.width = Math.ceil(W / 2);
    shade.height = Math.ceil(H / 2);
  };

  function circ(x, y, r) { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); }
  function line(x1, y1, x2, y2) { ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); }

  // ---------- Клетки ----------
  function drawFloor(style, dv, X, Y, w, h, tx, ty) {
    if (style === 1) { // плитка
      ctx.fillStyle = (tx + ty) % 2 ? '#9a978e' : '#8e8b83';
      ctx.fillRect(X, Y, w, h);
    } else if (style === 2) { // линолеум
      ctx.fillStyle = '#6c7176';
      ctx.fillRect(X, Y, w, h);
      ctx.fillStyle = 'rgba(0,0,0,0.08)';
      ctx.fillRect(X, Y, w, 1);
    } else { // доски
      ctx.fillStyle = WOOD[dv & 1];
      ctx.fillRect(X, Y, w, h);
      ctx.fillStyle = 'rgba(0,0,0,0.13)';
      for (let k = 1; k < 3; k++) ctx.fillRect(X, Y + Math.round((h * k) / 3), w, 1);
      ctx.fillRect(X + ((dv * 7) % w), Y, 1, Math.round(h / 3));
    }
  }

  function drawRoad(i, dv, X, Y, w, h) {
    ctx.fillStyle = dv > 128 ? '#3c3d40' : '#393a3d';
    ctx.fillRect(X, Y, w, h);
    const m = Z.world.mark[i];
    if (m && ((i % N) + ((i / N) | 0)) % 2 === 0) {
      ctx.fillStyle = 'rgba(190,170,100,0.55)';
      if (m === 1) ctx.fillRect(X + w * 0.2, Y + h * 0.45, w * 0.6, Math.max(2, h * 0.09));
      else ctx.fillRect(X + w * 0.45, Y + h * 0.2, Math.max(2, w * 0.09), h * 0.6);
    }
  }

  function drawTiles(x0, y0, x1, y1) {
    const wd = Z.world;
    for (let ty = y0; ty <= y1; ty++) {
      const Y = Math.round(sy(ty)), h = Math.round(sy(ty + 1)) - Y;
      for (let tx = x0; tx <= x1; tx++) {
        const X = Math.round(sx(tx)), w = Math.round(sx(tx + 1)) - X;
        if (tx < 0 || ty < 0 || tx >= N || ty >= N) { ctx.fillStyle = '#26301f'; ctx.fillRect(X, Y, w, h); continue; }
        const i = ty * N + tx, t = wd.tiles[i], dv = wd.deco[i];
        switch (t) {
          case T.GRASS: case T.TREE:
            ctx.fillStyle = GRASS[dv & 3];
            ctx.fillRect(X, Y, w, h);
            if (dv > 190) {
              ctx.fillStyle = 'rgba(120,140,80,0.35)';
              ctx.fillRect(X + (dv % 7) * w / 8, Y + (dv % 5) * h / 6, 2, 3);
              ctx.fillRect(X + (dv % 3) * w / 4 + w / 3, Y + (dv % 4) * h / 5 + h / 4, 2, 3);
            }
            break;
          case T.ROAD: drawRoad(i, dv, X, Y, w, h); break;
          case T.WALK:
            ctx.fillStyle = dv > 200 ? '#726f67' : '#77746c';
            ctx.fillRect(X, Y, w, h);
            ctx.fillStyle = 'rgba(0,0,0,0.12)';
            ctx.fillRect(X, Y, w, 1);
            ctx.fillRect(X, Y, 1, h);
            break;
          case T.FLOOR: drawFloor(wd.floor[i], dv, X, Y, w, h, tx, ty); break;
          case T.FURN: {
            const c = wd.containers[wd.contAt[i]];
            if (c.type === 'car') drawRoad(i, dv, X, Y, w, h);
            else drawFloor(wd.floor[i], dv, X, Y, w, h, tx, ty);
            break;
          }
          case T.DOOR: {
            drawFloor(wd.floor[i], dv, X, Y, w, h, tx, ty);
            const horiz = Z.tileAt(tx - 1, ty) === T.WALL || Z.tileAt(tx + 1, ty) === T.WALL;
            ctx.fillStyle = '#4a3220';
            if (horiz) ctx.fillRect(X, Y, Math.max(2, w * 0.12), h);
            else ctx.fillRect(X, Y, w, Math.max(2, h * 0.12));
            break;
          }
          case T.WALL: {
            ctx.fillStyle = '#d6cdbb';
            ctx.fillRect(X, Y, w, h);
            const below = Z.tileAt(tx, ty + 1);
            if (below !== T.WALL) { ctx.fillStyle = '#a0967f'; ctx.fillRect(X, Y + h * 0.62, w, h * 0.38 + 1); }
            ctx.fillStyle = '#7f7563';
            if (Z.tileAt(tx - 1, ty) !== T.WALL) ctx.fillRect(X, Y, 1, h);
            if (Z.tileAt(tx + 1, ty) !== T.WALL) ctx.fillRect(X + w - 1, Y, 1, h);
            if (Z.tileAt(tx, ty - 1) !== T.WALL) ctx.fillRect(X, Y, w, 1);
            break;
          }
        }
      }
    }
  }

  // ---------- Мебель и машины ----------
  function drawContainer(c, active) {
    const X = sx(c.x), Y = sy(c.y), w = c.w * U, h = c.h * U, m = U * 0.08;
    const rect = (x, y, ww, hh, col) => { ctx.fillStyle = col; ctx.fillRect(x, y, ww, hh); };
    switch (c.type) {
      case 'fridge': case 'drinks':
        rect(X + m, Y + m, w - 2 * m, h - 2 * m, '#dedfd9');
        rect(X + m, Y + h * 0.4, w - 2 * m, 1.5, '#a9aaa4');
        if (c.type === 'drinks') rect(X + m * 2, Y + h * 0.45, w - 4 * m, h * 0.4, '#8fb6c2');
        rect(X + w * 0.75, Y + h * 0.15, 2, h * 0.18, '#8a8b86');
        break;
      case 'cupboard':
        rect(X + m, Y + m, w - 2 * m, h - 2 * m, '#7a5534');
        rect(X + w / 2 - 0.5, Y + m, 1, h - 2 * m, '#4f3520');
        rect(X + w * 0.38, Y + h * 0.45, 2, 2, '#d2b07a');
        rect(X + w * 0.58, Y + h * 0.45, 2, 2, '#d2b07a');
        break;
      case 'wardrobe':
        rect(X + m, Y + m, w - 2 * m, h - 2 * m, '#5e4027');
        rect(X + m * 2, Y + m * 2, w - 4 * m, h - 4 * m, '#6b4a2e');
        rect(X + w / 2 - 0.5, Y + m * 2, 1, h - 4 * m, '#3e2a19');
        break;
      case 'toolbox':
        rect(X + w * 0.2, Y + h * 0.3, w * 0.6, h * 0.45, '#a23a2c');
        rect(X + w * 0.35, Y + h * 0.22, w * 0.3, h * 0.1, '#5a1f18');
        break;
      case 'shelf': {
        rect(X + m, Y + m, w - 2 * m, h - 2 * m, '#85857f');
        const cols = ['#c94c3c', '#e0b84a', '#4c8ac9', '#6bb05a', '#e8e4da'];
        const empty = c.items && c.items.length === 0;
        if (!empty) for (let k = 0; k < c.w * 3; k++) {
          ctx.fillStyle = cols[(c.x * 7 + c.y * 3 + k * 5) % cols.length];
          ctx.fillRect(X + m * 1.5 + k * (w - 3 * m) / (c.w * 3), Y + h * 0.3, (w - 3 * m) / (c.w * 3) - 2, h * 0.4);
        }
        break;
      }
      case 'locker':
        rect(X + m, Y + m, w - 2 * m, h - 2 * m, '#5b6a78');
        ctx.fillStyle = '#3f4a55';
        for (let k = 1; k < 4; k++) ctx.fillRect(X + m + k * (w - 2 * m) / 4, Y + m * 2, 1, h - 4 * m);
        break;
      case 'desk':
        rect(X + m, Y + m * 2, w - 2 * m, h - 4 * m, '#8a6a46');
        rect(X + w * 0.25, Y + h * 0.3, w * 0.3, h * 0.3, '#e8e4da');
        break;
      case 'car': {
        const horiz = c.w > c.h;
        const p = U * 0.08;
        ctx.fillStyle = 'rgba(0,0,0,0.3)';
        ctx.fillRect(X + p + 3, Y + p + 4, w - 2 * p, h - 2 * p);
        rect(X + p, Y + p, w - 2 * p, h - 2 * p, c.color);
        ctx.fillStyle = '#2a3640';
        if (horiz) { ctx.fillRect(X + w * 0.28, Y + p * 2, w * 0.14, h - 4 * p); ctx.fillRect(X + w * 0.68, Y + p * 2, w * 0.1, h - 4 * p); }
        else { ctx.fillRect(X + p * 2, Y + h * 0.28, w - 4 * p, h * 0.14); ctx.fillRect(X + p * 2, Y + h * 0.68, w - 4 * p, h * 0.1); }
        ctx.fillStyle = 'rgba(255,255,255,0.12)';
        if (horiz) ctx.fillRect(X + w * 0.42, Y + p * 2, w * 0.26, h - 4 * p);
        else ctx.fillRect(X + p * 2, Y + h * 0.42, w - 4 * p, h * 0.26);
        break;
      }
    }
    if (c.items && c.items.length === 0) { ctx.fillStyle = 'rgba(0,0,0,0.22)'; ctx.fillRect(X, Y, w, h); }
    if (active) {
      ctx.strokeStyle = '#f2d16b';
      ctx.lineWidth = 2;
      ctx.strokeRect(X + 1, Y + 1, w - 2, h - 2);
    }
  }

  // ---------- Люди ----------
  function drawWeapon(look, r) {
    ctx.strokeStyle = look.color;
    ctx.lineWidth = look.w * U;
    ctx.lineCap = 'round';
    const hx = r * 0.85, hy = r * 0.55, ex = hx + look.len * U * 0.75, ey = hy - r * 0.15;
    line(hx, hy, ex, ey);
    if (look.head) { ctx.fillStyle = look.head; ctx.fillRect(ex - U * 0.12, ey - U * 0.2, U * 0.2, U * 0.3); }
  }

  function drawHuman(x, y, face, h) {
    const r = 0.34 * U;
    ctx.save();
    ctx.translate(sx(x), sy(y));
    ctx.globalAlpha = h.alpha == null ? 1 : h.alpha;
    if (h.dead) {
      ctx.fillStyle = 'rgba(90,12,12,0.75)';
      ctx.beginPath(); ctx.ellipse(r * 0.3, r * 0.2, r * 1.6, r * 1.2, h.blood || 0, 0, Math.PI * 2); ctx.fill();
    } else {
      ctx.fillStyle = 'rgba(0,0,0,0.25)';
      ctx.beginPath(); ctx.ellipse(r * 0.15, r * 0.25, r * 1.1, r * 1.0, 0, 0, Math.PI * 2); ctx.fill();
    }
    ctx.rotate(face);
    const st = h.dead ? 0 : Math.sin(h.walkT || 0) * r * 0.55;
    ctx.fillStyle = '#2b2a28';
    circ(st, -r * 0.42, r * 0.26);
    circ(-st, r * 0.42, r * 0.26);
    ctx.lineCap = 'round';
    if (h.zombie || h.dead) {
      ctx.strokeStyle = h.cloth;
      ctx.lineWidth = r * 0.42;
      const spread = h.dead ? r * 0.5 : 0;
      line(0, -r * 0.7, r * 1.05, -r * 0.5 - spread);
      line(0, r * 0.7, r * 1.05 + st * 0.3, r * 0.5 + spread);
      ctx.fillStyle = h.skin;
      circ(r * 1.1, -r * 0.5 - spread, r * 0.2);
      circ(r * 1.1 + st * 0.3, r * 0.5 + spread, r * 0.2);
    } else {
      ctx.save();
      ctx.rotate(h.swing || 0);
      if (h.weapon) drawWeapon(h.weapon, r);
      ctx.fillStyle = h.skin;
      circ(r * 0.85, r * 0.55, r * 0.2);
      ctx.restore();
      ctx.fillStyle = h.skin;
      circ(r * 0.45 - st * 0.4, -r * 0.78, r * 0.2);
    }
    ctx.fillStyle = h.cloth;
    ctx.beginPath(); ctx.ellipse(0, 0, r * 0.6, r * 0.95, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = h.skin;
    circ(r * 0.12, 0, r * 0.52);
    if (h.hair) {
      ctx.fillStyle = h.hair;
      ctx.beginPath(); ctx.arc(r * 0.12, 0, r * 0.52, Math.PI * 0.5, Math.PI * 1.5); ctx.fill();
    }
    ctx.restore();
  }

  // ---------- Деревья и крыши ----------
  function drawTrees(x0, y0, x1, y1) {
    const wd = Z.world;
    for (let ty = y0; ty <= y1; ty++) for (let tx = x0; tx <= x1; tx++) {
      if (Z.tileAt(tx, ty) !== T.TREE) continue;
      const dv = tx >= 0 && ty >= 0 && tx < N && ty < N ? wd.deco[ty * N + tx] : 77;
      const cx = sx(tx + 0.5 + ((dv % 5) - 2) * 0.04), cy = sy(ty + 0.5 + ((dv % 7) - 3) * 0.03);
      const r = U * (0.58 + (dv % 4) * 0.05);
      ctx.fillStyle = 'rgba(0,0,0,0.28)';
      circ(cx + U * 0.12, cy + U * 0.16, r);
      ctx.fillStyle = dv % 3 === 0 ? '#2a3a22' : '#2f4226';
      circ(cx, cy, r);
      ctx.fillStyle = dv % 3 === 0 ? '#34492a' : '#3b5530';
      circ(cx - r * 0.25, cy - r * 0.25, r * 0.55);
    }
  }

  function drawRoof(b) {
    if (b.roofA < 0.01) return;
    const o = 0.12;
    const X = sx(b.x - o), Y = sy(b.y - o), w = (b.w + 2 * o) * U, h = (b.h + 2 * o) * U;
    if (X > W || Y > H || X + w < 0 || Y + h < 0) return;
    ctx.globalAlpha = b.roofA;
    ctx.fillStyle = 'rgba(0,0,0,0.3)';
    ctx.fillRect(X + U * 0.15, Y + U * 0.2, w, h);
    ctx.fillStyle = b.roof;
    ctx.fillRect(X, Y, w, h);
    if (b.kind === 'house') {
      // двускатная крыша: тёмный скат, светлый скат, конёк
      ctx.fillStyle = 'rgba(0,0,0,0.16)';
      if (b.w >= b.h) ctx.fillRect(X, Y + h / 2, w, h / 2); else ctx.fillRect(X + w / 2, Y, w / 2, h);
      ctx.fillStyle = 'rgba(0,0,0,0.12)';
      const step = U * 0.5;
      if (b.w >= b.h) for (let yy = Y + step; yy < Y + h; yy += step) ctx.fillRect(X, yy, w, 1);
      else for (let xx = X + step; xx < X + w; xx += step) ctx.fillRect(xx, Y, 1, h);
      ctx.fillStyle = 'rgba(255,255,255,0.18)';
      if (b.w >= b.h) ctx.fillRect(X, Y + h / 2 - 1, w, 2); else ctx.fillRect(X + w / 2 - 1, Y, 2, h);
    } else {
      ctx.strokeStyle = 'rgba(0,0,0,0.25)';
      ctx.lineWidth = 2;
      ctx.strokeRect(X + U * 0.3, Y + U * 0.3, w - U * 0.6, h - U * 0.6);
      ctx.fillStyle = 'rgba(0,0,0,0.25)';
      ctx.fillRect(X + w * 0.15, Y + h * 0.2, U * 0.8, U * 0.8);
      ctx.fillRect(X + w * 0.75, Y + h * 0.7, U * 0.8, U * 0.6);
      ctx.fillStyle = b.kind === 'police' ? '#a9c2e6' : '#e8e0c8';
      ctx.font = `800 ${Math.round(U * 0.85)}px system-ui, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(b.name, X + w / 2, Y + h / 2);
    }
    ctx.globalAlpha = 1;
  }

  // ---------- Кадр ----------
  Z.render = function () {
    const S = Z.S, p = S.p, wd = Z.world;
    camX = p.x;
    camY = p.y;
    ctx.fillStyle = '#1d2418';
    ctx.fillRect(0, 0, W, H);

    const x0 = Math.floor(camX - W / 2 / U) - 1, x1 = Math.ceil(camX + W / 2 / U) + 1;
    const y0 = Math.floor(camY - H / 2 / U) - 1, y1 = Math.ceil(camY + H / 2 / U) + 1;
    const inView = (x, y, m) => x > x0 - m && x < x1 + m && y > y0 - m && y < y1 + m;

    drawTiles(x0, y0, x1, y1);

    for (const d of S.decals) {
      if (!inView(d.x, d.y, 1)) continue;
      ctx.fillStyle = `rgba(105,12,12,${d.a})`;
      circ(sx(d.x), sy(d.y), d.r * U);
    }

    for (const c of wd.containers) {
      if (inView(c.x, c.y, 3)) drawContainer(c, c === S.near);
    }

    for (const c of S.corpses) {
      if (inView(c.x, c.y, 2)) drawHuman(c.x, c.y, c.face, c);
    }

    for (const z of S.zombies) {
      if (z.alpha < 0.02 || !inView(z.x, z.y, 2)) continue;
      drawHuman(z.x, z.y, z.face, z);
    }

    // игрок
    const w = S.weaponLook();
    let swing = 0;
    if (p.atkAnim > 0 && !S.gunEquipped()) {
      const t = 1 - p.atkAnim / 0.25;
      swing = 0.9 - 1.9 * (1 - (1 - t) * (1 - t));
    }
    drawHuman(p.x, p.y, p.face, {
      skin: '#e3b48c', cloth: '#4b6584', hair: '#3b2a20', walkT: p.walkT,
      weapon: w, swing, dead: S.state === 'dead', blood: 0.4,
    });

    // выстрелы
    for (const f of S.fx) {
      const a = 1 - f.t / f.life;
      if (f.kind === 'tracer') {
        ctx.strokeStyle = `rgba(255,230,150,${a})`;
        ctx.lineWidth = 2;
        line(sx(f.x1), sy(f.y1), sx(f.x2), sy(f.y2));
      } else if (f.kind === 'flash') {
        ctx.fillStyle = `rgba(255,220,120,${a})`;
        circ(sx(f.x1), sy(f.y1), U * 0.25);
      }
    }

    drawTrees(x0, y0, x1, y1);
    for (const b of wd.buildings) drawRoof(b);

    // ночь: темнота с пятном света вокруг игрока
    if (S.dark > 0.01) {
      const sw = shade.width, sh = shade.height;
      sctx.globalCompositeOperation = 'source-over';
      sctx.clearRect(0, 0, sw, sh);
      sctx.fillStyle = `rgba(4,6,16,${S.dark})`;
      sctx.fillRect(0, 0, sw, sh);
      sctx.globalCompositeOperation = 'destination-out';
      const lights = [[p.x, p.y, S.lightR]];
      for (const f of S.fx) if (f.kind === 'flash') lights.push([f.x1, f.y1, 5 * (1 - f.t / f.life)]);
      for (const [lx, ly, lr] of lights) {
        const px = sx(lx) / 2, py = sy(ly) / 2, R = (lr * U) / 2;
        const g = sctx.createRadialGradient(px, py, R * 0.1, px, py, R);
        g.addColorStop(0, 'rgba(0,0,0,1)');
        g.addColorStop(0.55, 'rgba(0,0,0,0.8)');
        g.addColorStop(1, 'rgba(0,0,0,0)');
        sctx.fillStyle = g;
        sctx.beginPath(); sctx.arc(px, py, R, 0, Math.PI * 2); sctx.fill();
      }
      ctx.drawImage(shade, 0, 0, W, H);
    }

    // вспышка урона и низкое здоровье
    const hurt = Math.max(S.hurtFlash, p.hp < 30 && S.state === 'play' ? 0.25 + 0.15 * Math.sin(performance.now() / 250) : 0);
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
