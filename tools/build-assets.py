#!/usr/bin/env python3
"""Собирает атласы спрайтов для «Карантина» из исходных наборов.

Исходники (в репозиторий не кладём, качаются отдельно — см. README):
  --riley   папка asset_packs из github.com/D4M13N-D3V/zombie_game_prototype
            (Top_Down_Survivor_rileygombart, Top_Down_Zombie_rileygombart)
  --kenney  Kenney «Topdown Shooter» (папка с PNG/Tiles)
  --splats  Kenney «Splat Pack» (папка с PNG)
  --cars    DevilsWorkShop «2D Car Pack», City-Traffic-Vehicles

Результат: web/zombie/assets/{chars,world}.{png,json}
Требует Pillow и numpy.
"""
import argparse, glob, json, os
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

PAD = 2


# ---------- упаковка ----------
def pack(images, max_w=2048):
    """Полочная упаковка. images: {name: Image}. Возвращает (atlas, {name: [x, y, w, h]})."""
    order = sorted(images, key=lambda n: (-images[n].height, n))
    x = y = shelf = 0
    pos = {}
    for n in order:
        w, h = images[n].size
        if x + w + PAD * 2 > max_w:
            x, y, shelf = 0, y + shelf, 0
        pos[n] = (x + PAD, y + PAD)
        x += w + PAD * 2
        shelf = max(shelf, h + PAD * 2)
    W = max_w
    H = y + shelf
    atlas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    rects = {}
    for n, (px, py) in pos.items():
        im = images[n]
        atlas.paste(im, (px, py))
        rects[n] = [px, py, im.width, im.height]
    return atlas, rects


def extrude(im):
    """Тайл с продублированными краями — без щелей между клетками при масштабировании."""
    w, h = im.size
    out = Image.new('RGBA', (w + 2 * PAD, h + 2 * PAD))
    out.paste(im, (PAD, PAD))
    for i in range(PAD):
        out.paste(im.crop((0, 0, w, 1)), (PAD, i))
        out.paste(im.crop((0, h - 1, w, h)), (PAD, h + PAD + i))
    left = out.crop((PAD, 0, PAD + 1, h + 2 * PAD))
    right = out.crop((PAD + w - 1, 0, PAD + w, h + 2 * PAD))
    for i in range(PAD):
        out.paste(left, (i, 0))
        out.paste(right, (w + PAD + i, 0))
    return out


def mute(im, sat=0.55, bri=0.82, contrast=1.0):
    a = im.getchannel('A')
    rgb = im.convert('RGB')
    rgb = ImageEnhance.Color(rgb).enhance(sat)
    rgb = ImageEnhance.Brightness(rgb).enhance(bri)
    if contrast != 1.0:
        rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
    out = rgb.convert('RGBA')
    out.putalpha(a)
    return out


# ---------- персонажи ----------
def body_center(im):
    """Центр туловища: убираем тонкие руки/оружие эрозией альфы и берём центр масс."""
    a = im.getchannel('A').point(lambda v: 255 if v > 80 else 0)
    a = a.filter(ImageFilter.MinFilter(11))
    arr = np.asarray(a, dtype=np.float32)
    if arr.sum() == 0:
        arr = np.asarray(im.getchannel('A'), dtype=np.float32)
    ys, xs = np.indices(arr.shape)
    s = arr.sum()
    return float((xs * arr).sum() / s), float((ys * arr).sum() / s)


def align(ref, im, ref_pivot, search=24):
    """Ищем сдвиг кадра im относительно ref по максимальному перекрытию альфы."""
    ra = np.asarray(ref.getchannel('A'), dtype=np.float32) / 255
    ia = np.asarray(im.getchannel('A'), dtype=np.float32) / 255
    # стартовая догадка — совместить центры туловища
    cx, cy = body_center(im)
    gx, gy = int(round(ref_pivot[0] - cx)), int(round(ref_pivot[1] - cy))
    H = max(ra.shape[0], ia.shape[0]) + 2 * search + abs(gy) + 4
    Wd = max(ra.shape[1], ia.shape[1]) + 2 * search + abs(gx) + 4
    base = np.zeros((H, Wd), np.float32)
    ox, oy = search + 2 + max(0, -gx), search + 2 + max(0, -gy)
    base[oy:oy + ra.shape[0], ox:ox + ra.shape[1]] = ra
    best, bdx, bdy = -1, gx, gy
    for dy in range(gy - search, gy + search + 1, 2):
        for dx in range(gx - search, gx + search + 1, 2):
            y0, x0 = oy + dy, ox + dx
            if y0 < 0 or x0 < 0 or y0 + ia.shape[0] > H or x0 + ia.shape[1] > Wd:
                continue
            sc = np.minimum(base[y0:y0 + ia.shape[0], x0:x0 + ia.shape[1]], ia).sum()
            if sc > best:
                best, bdx, bdy = sc, dx, dy
    # пивот кадра im = пивот ref, сдвинутый обратно
    return ref_pivot[0] - bdx, ref_pivot[1] - bdy


def load_frames(folder, step, scale):
    files = sorted(glob.glob(os.path.join(folder, '*.png')), key=lambda f: int(f.rsplit('_', 1)[1].split('.')[0]))
    files = files[::step]
    out = []
    for f in files:
        im = Image.open(f).convert('RGBA')
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        out.append(im)
    return out


def build_chars(riley, out_dir, scale):
    S = os.path.join(riley, 'Top_Down_Survivor_rileygombart')
    Zd = os.path.join(riley, 'Top_Down_Zombie_rileygombart')
    spec = [
        # имя, папка, шаг прореживания, fps
        ('p_melee_idle', f'{S}/knife/idle', 2, 10),
        ('p_melee_move', f'{S}/knife/move', 2, 12),
        ('p_melee_attack', f'{S}/knife/meleeattack', 2, 24),
        ('p_gun_idle', f'{S}/handgun/idle', 2, 10),
        ('p_gun_move', f'{S}/handgun/move', 2, 12),
        ('p_gun_shoot', f'{S}/handgun/shoot', 1, 20),
        ('p_gun_reload', f'{S}/handgun/reload', 2, 12),
        ('feet_idle', f'{S}/feet/idle', 1, 1),
        ('feet_walk', f'{S}/feet/walk', 2, 12),
        ('feet_run', f'{S}/feet/run', 2, 16),
        ('z_idle', f'{Zd}/idle', 2, 8),
        ('z_move', f'{Zd}/move', 2, 10),
        ('z_attack', f'{Zd}/attack', 1, 16),
    ]
    frames = {}
    anims = {}
    loaded = {name: (load_frames(path, step, scale), fps) for name, path, step, fps in spec}

    p_ref = loaded['p_melee_idle'][0][0]
    p_pivot = body_center(p_ref)
    z_ref = loaded['z_idle'][0][0]
    z_pivot = body_center(z_ref)

    for name, (imgs, fps) in loaded.items():
        if name.startswith('feet'):
            pivot = (imgs[0].width / 2, imgs[0].height / 2)
        elif name.startswith('z_'):
            pivot = z_pivot if name == 'z_idle' else align(z_ref, imgs[0], z_pivot)
        else:
            pivot = p_pivot if name == 'p_melee_idle' else align(p_ref, imgs[0], p_pivot)
        for i, im in enumerate(imgs):
            frames[f'{name}_{i}'] = im
        anims[name] = {'fps': fps, 'n': len(imgs), 'w': imgs[0].width, 'h': imgs[0].height,
                       'pivot': [round(pivot[0], 1), round(pivot[1], 1)]}

    # зомби — в отдельном атласе: игра перекрашивает его в несколько вариантов одежды
    for sheet, prefix in (('chars', ('p_', 'feet')), ('zombies', ('z_',))):
        part = {k: v for k, v in frames.items() if k.startswith(prefix)}
        atlas, rects = pack(part)
        for name, a in anims.items():
            if name.startswith(prefix):
                a['sheet'] = sheet
                a['frames'] = [rects[f'{name}_{i}'][:2] for i in range(a['n'])]
        atlas.save(os.path.join(out_dir, f'{sheet}.png'), optimize=True)
    return {'ppt': round(190 * scale, 2), 'anims': anims}


# ---------- окружение ----------
def build_world(kenney, splats, cars, out_dir):
    T = os.path.join(kenney, 'PNG', 'Tiles')

    def tile(n):
        return Image.open(os.path.join(T, f'tile_{n:02d}.png')).convert('RGBA')

    images = {}
    def add_tile(name, n, **m):
        images[name] = extrude(mute(tile(n), **m))

    # пол и земля (бесшовные клетки)
    for i, n in enumerate((1, 2, 3, 4)):
        add_tile(f'grass{i}', n, sat=0.42, bri=0.72)
    add_tile('dirt', 5, sat=0.5, bri=0.75)
    add_tile('asphalt0', 86, sat=1, bri=0.95)
    add_tile('asphalt1', 93, sat=1, bri=0.92)
    add_tile('walk0', 7, sat=0.15, bri=0.78)
    add_tile('walk1', 8, sat=0.15, bri=0.78)
    for i, n in enumerate((42, 43, 44, 45)):
        add_tile(f'wood{i}', n, sat=0.55, bri=0.78)
    add_tile('tileA', 11, sat=0.25, bri=0.86)
    add_tile('tileB', 12, sat=0.25, bri=0.80)
    add_tile('lino0', 9, sat=0.1, bri=0.72)
    add_tile('lino1', 10, sat=0.1, bri=0.72)

    # мебель (без выдавливания краёв — у неё прозрачный фон)
    furn = {
        'fridge': 322, 'counter': 294, 'stove': 297, 'sink': 323, 'dresser': 453, 'crate': 130, 'crate_big': 129,
        'shelf_l': 480, 'shelf_m': 481, 'shelf_r': 482, 'drinks': 321, 'locker': 243, 'laptop': 269,
        'desk_l': 507, 'desk_m': 508, 'desk_r': 509, 'table_round': 506, 'plant': 134,
        'sofa_l': 447, 'sofa_m': 448, 'sofa_r': 449, 'sofa2_l': 474, 'sofa2_m': 475, 'sofa2_r': 476,
        'armchair': 450, 'armchair2': 477, 'rug_l': 343, 'rug_m': 344, 'rug_r': 345,
        'rug2_l': 373, 'rug2_m': 374, 'rug2_r': 375, 'tv': 537,
        'tree0': 183, 'tree1': 186, 'tree2': 183, 'bush': 235,
    }
    for name, n in furn.items():
        sat, bri = (0.5, 0.75) if name.startswith(('tree', 'bush')) else (0.6, 0.84)
        if name == 'tree2':
            sat, bri = 0.35, 0.6
        images[name] = mute(tile(n), sat=sat, bri=bri)

    # машины: вид сверху, длина = 2 клетки (128 px)
    for name in ('car01', 'car02', 'car03', 'pickupTruck01', 'pickupTruck02', 'policeCar'):
        im = Image.open(os.path.join(cars, name, 'top_0000.png')).convert('RGBA')
        k = 124 / im.height
        im = im.resize((round(im.width * k), 124), Image.LANCZOS)
        images[f'car_{name}'] = mute(im, sat=0.5, bri=0.82)

    # кровь: белые кляксы → тёмно-красные
    for i, n in enumerate((0, 3, 7, 12, 18, 25)):
        path = glob.glob(os.path.join(splats, '**', f'splat{n:02d}.png'), recursive=True)
        path = [p for p in path if '256' in p] or path
        a = Image.open(path[0]).convert('RGBA').resize((72, 72), Image.LANCZOS).getchannel('A')
        red = Image.new('RGBA', a.size, (92, 8, 10, 255))
        red.putalpha(a.point(lambda v: int(v * 0.88)))
        images[f'blood{i}'] = red

    atlas, rects = pack(images)
    for n in rects:
        if images[n].width == 64 + 2 * PAD and n.rstrip('0123456789') in (
                'grass', 'dirt', 'asphalt', 'walk', 'wood', 'tileA', 'tileB', 'lino'):
            x, y, w, h = rects[n]
            rects[n] = [x + PAD, y + PAD, w - 2 * PAD, h - 2 * PAD]
    atlas.save(os.path.join(out_dir, 'world.png'), optimize=True)
    return {'ppt': 64, 'rects': rects}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--riley', required=True)
    ap.add_argument('--kenney', required=True)
    ap.add_argument('--splats', required=True)
    ap.add_argument('--cars', required=True)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', 'web', 'zombie', 'assets'))
    ap.add_argument('--scale', type=float, default=0.42)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    chars = build_chars(a.riley, a.out, a.scale)
    world = build_world(a.kenney, a.splats, a.cars, a.out)
    # разметка атласов — обычным скриптом, чтобы игра открывалась и без сервера
    with open(os.path.join(a.out, 'atlas.js'), 'w') as f:
        f.write('window.Z_ATLAS = ' + json.dumps({'chars': chars, 'world': world}, separators=(',', ':')) + ';\n')
    print('ok', {k: os.path.getsize(os.path.join(a.out, k)) for k in ('chars.png', 'zombies.png', 'world.png', 'atlas.js')})


if __name__ == '__main__':
    main()
