// Город: генерация карты, столкновения, прямая видимость и поиск пути к игроку.
// Координаты мира — в клетках (1 = одна клетка).
(function () {
  const Z = window.Z = window.Z || {};

  const T = Z.TILE = { GRASS: 0, ROAD: 1, WALK: 2, FLOOR: 3, WALL: 4, TREE: 5, FURN: 6, DOOR: 7 };
  const N = Z.N = 80;
  const ROADS = [3, 27, 51, 75];          // верхний ряд каждой дороги (ширина 3)
  const D4 = [[1, 0], [-1, 0], [0, 1], [0, -1]];
  const ROOFS = ['#6b3b32', '#5a4a3f', '#4f5a63', '#6e5a3a', '#5d3f4a', '#4a5546'];
  const CARS = ['car01', 'car02', 'car03', 'pickupTruck01', 'pickupTruck02'];

  function rng(seed) { // mulberry32
    return function () {
      seed = (seed + 0x6D2B79F5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  Z.genWorld = function (seed) {
    const R = rng(seed);
    const ri = (a, b) => a + Math.floor(R() * (b - a + 1));
    const pick = (arr) => arr[Math.floor(R() * arr.length)];
    const shuffle = (arr) => { for (let i = arr.length - 1; i > 0; i--) { const j = Math.floor(R() * (i + 1)); [arr[i], arr[j]] = [arr[j], arr[i]]; } return arr; };

    const tiles = new Uint8Array(N * N);
    const deco = new Uint8Array(N * N);      // случайная вариация для отрисовки
    const mark = new Uint8Array(N * N);      // разметка: 1 — горизонтальная, 2 — вертикальная
    const floor = new Uint8Array(N * N);     // пол: 0–3 доски (разные), 4 плитка, 5 линолеум
    const contAt = new Int16Array(N * N).fill(-1);
    const containers = [];
    const buildings = [];
    const decor = [];      // мебель для красоты: диваны, столы, ковры (не обыскивается)

    const idx = (x, y) => y * N + x;
    const inside = (x, y) => x >= 0 && y >= 0 && x < N && y < N;
    const get = (x, y) => (inside(x, y) ? tiles[idx(x, y)] : T.TREE);
    const set = (x, y, t) => { if (inside(x, y)) tiles[idx(x, y)] = t; };

    for (let i = 0; i < N * N; i++) deco[i] = Math.floor(R() * 256);

    // лес по краю карты
    for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
      if (x < 2 || y < 2 || x >= N - 1 || y >= N - 1) set(x, y, T.TREE);
    }

    // дороги, разметка, тротуары
    const onRoad = (v) => ROADS.some((p) => v >= p && v <= p + 2);
    for (const p of ROADS) for (let i = 0; i < N; i++) for (let k = 0; k < 3; k++) {
      set(i, p + k, T.ROAD);
      set(p + k, i, T.ROAD);
    }
    for (const p of ROADS) for (let i = 0; i < N; i++) {
      if (!onRoad(i)) { mark[idx(i, p + 1)] = 1; mark[idx(p + 1, i)] = 2; }
      for (const q of [p - 1, p + 3]) {
        if (get(i, q) === T.GRASS) set(i, q, T.WALK);
        if (get(q, i) === T.GRASS) set(q, i, T.WALK);
      }
    }

    function addContainer(type, x, y, w, h) {
      const c = { type, x, y, w, h, items: null, rot: 0 };
      if (type === 'car') c.model = R() < 0.12 ? 'policeCar' : pick(CARS);
      if (type === 'cupboard') c.sprite = pick(['counter', 'counter', 'sink']);
      for (let j = y; j < y + h; j++) for (let i = x; i < x + w; i++) {
        set(i, j, T.FURN);
        contAt[idx(i, j)] = containers.length;
      }
      containers.push(c);
      return c;
    }

    function building(x, y, w, h, kind, style) {
      const b = { x, y, w, h, kind, doors: [], roof: pick(ROOFS), roofA: 1 };
      for (let j = y; j < y + h; j++) for (let i = x; i < x + w; i++) {
        const edge = i === x || j === y || i === x + w - 1 || j === y + h - 1;
        set(i, j, edge ? T.WALL : T.FLOOR);
        floor[idx(i, j)] = style;
      }
      buildings.push(b);
      return b;
    }

    // дверь в стене: side 0 — верх, 1 — право, 2 — низ, 3 — лево
    function door(b, side, width) {
      const len = side % 2 === 0 ? b.w : b.h;
      for (let attempt = 0; attempt < 30; attempt++) {
        const off = ri(1, len - 1 - width);
        const cells = [];
        for (let k = 0; k < width; k++) {
          const o = off + k;
          if (side === 0) cells.push([b.x + o, b.y, 0, 1]);
          if (side === 2) cells.push([b.x + o, b.y + b.h - 1, 0, -1]);
          if (side === 3) cells.push([b.x, b.y + o, 1, 0]);
          if (side === 1) cells.push([b.x + b.w - 1, b.y + o, -1, 0]);
        }
        // за дверью внутри должен быть пол, а не перегородка
        if (!cells.every(([x, y, dx, dy]) => get(x + dx, y + dy) === T.FLOOR)) continue;
        for (const [x, y] of cells) { set(x, y, T.DOOR); b.doors.push([x, y]); }
        return;
      }
    }

    // все клетки пола внутри здания достижимы от входа
    function connected(b) {
      let total = 0;
      for (let j = b.y; j < b.y + b.h; j++) for (let i = b.x; i < b.x + b.w; i++) {
        const t = get(i, j);
        if (t === T.FLOOR || t === T.DOOR) total++;
      }
      const [sx, sy] = b.doors[0];
      const seen = new Set([idx(sx, sy)]);
      const queue = [[sx, sy]];
      while (queue.length) {
        const [x, y] = queue.pop();
        for (const [dx, dy] of D4) {
          const nx = x + dx, ny = y + dy;
          if (nx < b.x || ny < b.y || nx >= b.x + b.w || ny >= b.y + b.h) continue;
          const t = get(nx, ny);
          if ((t === T.FLOOR || t === T.DOOR) && !seen.has(idx(nx, ny))) { seen.add(idx(nx, ny)); queue.push([nx, ny]); }
        }
      }
      return seen.size === total;
    }

    // мебель вдоль стен, не загораживая проходы
    function furnish(b, types) {
      if (!b.doors.length) return;
      const cand = [];
      for (let j = b.y + 1; j < b.y + b.h - 1; j++) for (let i = b.x + 1; i < b.x + b.w - 1; i++) {
        if (get(i, j) !== T.FLOOR) continue;
        let walls = 0, nearDoor = false;
        for (const [dx, dy] of D4) {
          const t = get(i + dx, j + dy);
          if (t === T.WALL) walls++;
          if (t === T.DOOR) nearDoor = true;
        }
        if (walls > 0 && !nearDoor) cand.push([i, j]);
      }
      shuffle(cand);
      for (const type of types) {
        while (cand.length) {
          const [i, j] = cand.pop();
          if (get(i, j) !== T.FLOOR) continue;
          set(i, j, T.FURN);
          if (connected(b)) { set(i, j, T.FLOOR); addContainer(type, i, j, 1, 1); break; }
          set(i, j, T.FLOOR);
        }
      }
    }

    function house(x, y, w, h, sides) {
      const b = building(x, y, w, h, 'house', ri(0, 3));
      if (w >= 8 && R() < 0.8) {
        const wx = x + ri(3, w - 4);
        for (let j = y + 1; j < y + h - 1; j++) set(wx, j, T.WALL);
        set(wx, ri(y + 1, y + h - 2), T.DOOR);
      } else if (h >= 8 && R() < 0.8) {
        const wy = y + ri(3, h - 4);
        for (let i = x + 1; i < x + w - 1; i++) set(i, wy, T.WALL);
        set(ri(x + 1, x + w - 2), wy, T.DOOR);
      }
      door(b, pick(sides), 1);
      if (!b.doors.length) door(b, sides[0], 1);
      const extra = shuffle(['wardrobe', 'cupboard', R() < 0.5 ? 'toolbox' : 'wardrobe']);
      furnish(b, ['fridge', 'cupboard'].concat(extra.slice(0, ri(0, 2))));
      if (R() < 0.7) placeDecor(b, R() < 0.5 ? ['sofa_l', 'sofa_m', 'sofa_r'] : ['sofa2_l', 'sofa2_m', 'sofa2_r'], 'wall', true);
      if (R() < 0.5) placeDecor(b, ['stove'], 'wall', true);
      if (R() < 0.4) placeDecor(b, ['tv'], 'wall', true);
      if (R() < 0.4) placeDecor(b, [pick(['armchair', 'armchair2'])], 'wall', true);
      if (R() < 0.6) placeDecor(b, ['plant'], 'wall', true);
      if (R() < 0.5) placeDecor(b, ['table_round'], 'open', true);
      if (R() < 0.5) placeDecor(b, ['rug_l', 'rug_m', 'rug_r'], 'open', false);
      return b;
    }

    // куда «спиной» стоит предмет у стены (спинка спрайта смотрит вверх)
    function wallRot(i, j) {
      if (get(i, j - 1) === T.WALL) return 0;
      if (get(i + 1, j) === T.WALL) return Math.PI / 2;
      if (get(i, j + 1) === T.WALL) return Math.PI;
      if (get(i - 1, j) === T.WALL) return -Math.PI / 2;
      return 0;
    }

    // декор длиной parts.length клеток (по горизонтали). where: 'wall' — у верхней/нижней стены, 'open' — посреди комнаты
    function placeDecor(b, parts, where, solid) {
      const w = parts.length;
      const cand = [];
      for (let j = b.y + 1; j < b.y + b.h - 1; j++) for (let i = b.x + 1; i + w <= b.x + b.w - 1; i++) {
        let ok = true, top = true, bottom = true, open = true;
        for (let k = 0; k < w && ok; k++) {
          const x = i + k;
          if (get(x, j) !== T.FLOOR || decor.some((d) => d.solid !== false && x >= d.x && x < d.x + d.w && j === d.y)) ok = false;
          for (const [dx, dy] of D4) if (get(x + dx, j + dy) === T.DOOR) ok = false;
          if (get(x, j - 1) !== T.WALL) top = false;
          if (get(x, j + 1) !== T.WALL) bottom = false;
          for (const [dx, dy] of D4) if (get(x + dx, j + dy) === T.WALL || get(x + dx, j + dy) === T.FURN) open = false;
        }
        if (!ok) continue;
        if (where === 'wall' && w === 1) { const r = wallRot(i, j); if (get(i, j - 1) === T.WALL || get(i + 1, j) === T.WALL || get(i, j + 1) === T.WALL || get(i - 1, j) === T.WALL) cand.push([i, j, r]); }
        else if (where === 'wall') { if (top) cand.push([i, j, 0]); else if (bottom) cand.push([i, j, Math.PI]); }
        else if (open || !solid) cand.push([i, j, 0]);
      }
      shuffle(cand);
      for (const [i, j, rot] of cand) {
        if (solid) {
          for (let k = 0; k < w; k++) set(i + k, j, T.FURN);
          if (!connected(b)) { for (let k = 0; k < w; k++) set(i + k, j, T.FLOOR); continue; }
        }
        decor.push({ parts, x: i, y: j, w, h: 1, rot, solid });
        return true;
      }
      return false;
    }

    // ---- кварталы ----
    const blocks = [];
    for (let a = 0; a < ROADS.length - 1; a++) for (let c = 0; c < ROADS.length - 1; c++) {
      blocks.push({ x0: ROADS[a] + 4, y0: ROADS[c] + 4, size: ROADS[a + 1] - ROADS[a] - 5 });
    }
    const kinds = shuffle(['store', 'police', 'park', 'houses', 'houses', 'houses', 'houses', 'houses', 'houses']);

    blocks.forEach((bl, k) => {
      const S = bl.size; // 19
      if (kinds[k] === 'houses') {
        const half = Math.floor(S / 2); // 9
        const lots = [
          [bl.x0, bl.y0, [0, 3]], [bl.x0 + half + 1, bl.y0, [0, 1]],
          [bl.x0, bl.y0 + half + 1, [2, 3]], [bl.x0 + half + 1, bl.y0 + half + 1, [2, 1]],
        ];
        for (const [lx, ly, sides] of lots) {
          if (R() > 0.88) continue;
          const w = ri(6, half), h = ri(6, half);
          house(lx + ri(0, half - w), ly + ri(0, half - h), w, h, sides);
        }
      } else if (kinds[k] === 'store') {
        const w = S - 2, h = ri(12, 15);
        const b = building(bl.x0 + 1, bl.y0 + ri(1, S - h - 1), w, h, 'store', 4);
        b.name = 'МАГАЗИН';
        b.roof = '#55595c';
        for (let j = b.y + 3; j <= b.y + h - 4; j += 3) {
          for (let i = b.x + 3; i + 2 <= b.x + w - 4; i += 4) addContainer('shelf', i, j, 3, 1);
        }
        for (let i = b.x + 2; i < b.x + w - 2; i += 3) addContainer('drinks', i, b.y + h - 2, 1, 1);
        door(b, R() < 0.5 ? 0 : 2, 2);
      } else if (kinds[k] === 'police') {
        const w = ri(13, 15), h = ri(10, 12);
        const b = building(bl.x0 + ri(1, S - w - 1), bl.y0 + ri(1, S - h - 1), w, h, 'police', 5);
        b.name = 'ПОЛИЦИЯ';
        b.roof = '#3f4650';
        const wx = b.x + Math.floor(w / 2);
        for (let j = b.y + 1; j < b.y + h - 1; j++) set(wx, j, T.WALL);
        set(wx, b.y + ri(2, h - 3), T.DOOR);
        door(b, R() < 0.5 ? 0 : 2, 2);
        furnish(b, ['locker', 'locker', 'locker', 'desk', 'desk', 'desk', 'locker']);
        placeDecor(b, ['plant'], 'wall', true);
      } else { // парк
        for (let j = bl.y0; j < bl.y0 + S; j++) for (let i = bl.x0; i < bl.x0 + S; i++) {
          if (R() < 0.18) set(i, j, T.TREE);
        }
      }
    });

    // деревья во дворах — не у стен и не у дверей
    for (let y = 2; y < N - 2; y++) for (let x = 2; x < N - 2; x++) {
      if (get(x, y) !== T.GRASS || R() > 0.05) continue;
      let ok = true;
      for (let dy = -2; dy <= 2 && ok; dy++) for (let dx = -2; dx <= 2; dx++) {
        const t = get(x + dx, y + dy);
        if (t === T.DOOR || (Math.abs(dx) <= 1 && Math.abs(dy) <= 1 && (t === T.WALL || t === T.WALK))) { ok = false; break; }
      }
      if (ok) set(x, y, T.TREE);
    }

    // брошенные машины
    for (const p of ROADS) for (let s = 0; s < ROADS.length - 1; s++) {
      const a = ROADS[s] + 3, b = ROADS[s + 1] - 1;
      if (R() < 0.6) {
        const lane = R() < 0.5 ? p : p + 2, cx = ri(a + 1, b - 2);
        if (get(cx, lane) === T.ROAD && get(cx + 1, lane) === T.ROAD) addContainer('car', cx, lane, 2, 1);
      }
      if (R() < 0.6) {
        const lane = R() < 0.5 ? p : p + 2, cy = ri(a + 1, b - 2);
        if (get(lane, cy) === T.ROAD && get(lane, cy + 1) === T.ROAD) addContainer('car', lane, cy, 1, 2);
      }
    }

    for (const c of containers) if (c.w === 1 && c.h === 1) c.rot = wallRot(c.x, c.y);

    // старт — в случайном доме, на свободной клетке ближе к центру
    const homes = buildings.filter((b) => b.kind === 'house');
    const home = pick(homes);
    let spawn = null, bestD = Infinity;
    for (let j = home.y + 1; j < home.y + home.h - 1; j++) for (let i = home.x + 1; i < home.x + home.w - 1; i++) {
      if (get(i, j) !== T.FLOOR) continue;
      const d = Math.hypot(i - (home.x + home.w / 2), j - (home.y + home.h / 2));
      if (d < bestD) { bestD = d; spawn = { x: i + 0.5, y: j + 0.5 }; }
    }

    return { tiles, deco, mark, floor, contAt, containers, buildings, decor, spawn, home };
  };

  // ---------- Запросы к карте ----------
  Z.tileAt = (x, y) => (x < 0 || y < 0 || x >= N || y >= N ? T.TREE : Z.world.tiles[y * N + x]);
  Z.solid = (x, y) => { const t = Z.tileAt(x, y); return t === T.WALL || t === T.TREE || t === T.FURN; };
  Z.walkable = (x, y) => !Z.solid(x, y);

  // прямая видимость: стены загораживают, деревья и мебель — нет
  Z.los = function (ax, ay, bx, by) {
    const dx = bx - ax, dy = by - ay;
    const steps = Math.ceil(Math.hypot(dx, dy) * 3);
    for (let i = 1; i < steps; i++) {
      const t = i / steps;
      if (Z.tileAt(Math.floor(ax + dx * t), Math.floor(ay + dy * t)) === T.WALL) return false;
    }
    return true;
  };

  // выталкиваем круг радиуса r из непроходимых клеток
  Z.collide = function (e, r) {
    const x0 = Math.floor(e.x - r), x1 = Math.floor(e.x + r);
    const y0 = Math.floor(e.y - r), y1 = Math.floor(e.y + r);
    for (let ty = y0; ty <= y1; ty++) for (let tx = x0; tx <= x1; tx++) {
      if (!Z.solid(tx, ty)) continue;
      const cx = Math.max(tx, Math.min(e.x, tx + 1));
      const cy = Math.max(ty, Math.min(e.y, ty + 1));
      const dx = e.x - cx, dy = e.y - cy, d2 = dx * dx + dy * dy;
      if (d2 >= r * r) continue;
      if (d2 > 1e-9) {
        const d = Math.sqrt(d2);
        e.x += (dx / d) * (r - d);
        e.y += (dy / d) * (r - d);
      } else { // центр внутри клетки — к ближайшему краю
        const l = e.x - tx, rr = tx + 1 - e.x, u = e.y - ty, b = ty + 1 - e.y;
        const m = Math.min(l, rr, u, b);
        if (m === l) e.x = tx - r; else if (m === rr) e.x = tx + 1 + r;
        else if (m === u) e.y = ty - r; else e.y = ty + 1 + r;
      }
    }
  };

  // ---------- Поле расстояний до игрока (BFS) — по нему зомби обходят стены ----------
  const dist = new Int16Array(N * N);
  const queue = new Int32Array(N * N);
  let fx = -1, fy = -1;
  const MAX_FLOW = 40;

  Z.resetFlow = () => { fx = fy = -1; };

  Z.buildFlow = function (px, py) {
    const sx = Math.floor(px), sy = Math.floor(py);
    if (sx === fx && sy === fy) return;
    fx = sx; fy = sy;
    dist.fill(-1);
    let head = 0, tail = 0;
    dist[sy * N + sx] = 0;
    queue[tail++] = sy * N + sx;
    while (head < tail) {
      const cur = queue[head++], d = dist[cur];
      if (d >= MAX_FLOW) continue;
      const x = cur % N, y = (cur / N) | 0;
      for (const [dx, dy] of D4) {
        const nx = x + dx, ny = y + dy;
        if (nx < 0 || ny < 0 || nx >= N || ny >= N) continue;
        const ni = ny * N + nx;
        if (dist[ni] !== -1 || Z.solid(nx, ny)) continue;
        dist[ni] = d + 1;
        queue[tail++] = ni;
      }
    }
  };

  // следующая клетка по пути к игроку (или null, если пути нет)
  Z.flowStep = function (x, y) {
    const tx = Math.floor(x), ty = Math.floor(y);
    if (tx < 0 || ty < 0 || tx >= N || ty >= N) return null;
    const d0 = dist[ty * N + tx];
    if (d0 <= 0) return null;
    let best = d0, bx = -1, by = -1;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      if (!dx && !dy) continue;
      const nx = tx + dx, ny = ty + dy;
      if (nx < 0 || ny < 0 || nx >= N || ny >= N) continue;
      if (dx && dy && (Z.solid(tx + dx, ty) || Z.solid(tx, ty + dy))) continue; // не срезаем углы
      const d = dist[ny * N + nx];
      if (d >= 0 && d < best) { best = d; bx = nx; by = ny; }
    }
    return bx < 0 ? null : { x: bx + 0.5, y: by + 0.5 };
  };
})();
