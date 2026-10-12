// Карточка игрока 1080×1920 для Telegram-сторис (рисуем на canvas — шрифты те же, что в Лере)
import { S, tg, api, html, mount, on, icon, sheet, toast, fail, haptic, GI, rankName, roleName } from "../core.js";

const W = 1080, H = 1920;

function rr(c, x, y, w, h, r) { c.beginPath(); c.roundRect ? c.roundRect(x, y, w, h, r) : c.rect(x, y, w, h); }
function loadImg(src) {
  return new Promise((res) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => res(null); i.src = src; });
}

export async function drawCard() {
  await Promise.all(["900 110px Unbounded", "700 40px Unbounded", "500 40px Onest", "600 40px Onest", "700 30px 'JetBrains Mono'"].map((f) => document.fonts.load(f).catch(() => {})));
  const me = S.me, acc = me.accent || "#d4ff3f";
  const cv = Object.assign(document.createElement("canvas"), { width: W, height: H });
  const c = cv.getContext("2d");
  // фон
  c.fillStyle = "#0b0b0c"; c.fillRect(0, 0, W, H);
  let g = c.createRadialGradient(W * 0.85, 120, 40, W * 0.85, 120, 1100);
  g.addColorStop(0, acc + "55"); g.addColorStop(1, "#0b0b0c00"); c.fillStyle = g; c.fillRect(0, 0, W, H);
  const gc = GI(me.games?.[0]?.game || S.game).color;
  g = c.createRadialGradient(80, H - 200, 40, 80, H - 200, 900);
  g.addColorStop(0, gc + "44"); g.addColorStop(1, "#0b0b0c00"); c.fillStyle = g; c.fillRect(0, 0, W, H);
  // шапка
  c.fillStyle = "#efeae0"; c.font = "900 64px Unbounded"; c.fillText("лера", 80, 150);
  c.fillStyle = acc; c.beginPath(); c.arc(80 + c.measureText("лера").width + 18, 138, 12, 0, 7); c.fill();
  c.fillStyle = "#8f897e"; c.font = "700 30px 'JetBrains Mono'"; c.textAlign = "right"; c.fillText("// КАРТОЧКА ИГРОКА", W - 80, 140); c.textAlign = "left";
  // аватар
  const cx = W / 2, cy = 470, R = 210;
  c.save(); c.beginPath(); c.arc(cx, cy, R + 14, 0, 7); c.fillStyle = acc; c.fill(); c.restore();
  const av = me.avatar && me.avatar.startsWith("/uploads/") ? await loadImg(me.avatar) : null;
  c.save(); c.beginPath(); c.arc(cx, cy, R, 0, 7); c.clip();
  if (av) {
    const s = Math.max((2 * R) / av.width, (2 * R) / av.height);
    c.drawImage(av, cx - (av.width * s) / 2, cy - (av.height * s) / 2, av.width * s, av.height * s);
  } else {
    c.fillStyle = "#1f1f23"; c.fillRect(cx - R, cy - R, 2 * R, 2 * R);
    c.fillStyle = acc; c.font = "900 190px Unbounded"; c.textAlign = "center"; c.textBaseline = "middle";
    c.fillText((me.name || "?").slice(0, 1).toUpperCase(), cx, cy + 10); c.textAlign = "left"; c.textBaseline = "alphabetic";
  }
  c.restore();
  // имя
  let fs = 120; const name = (me.name || "игрок").toLowerCase();
  c.font = `900 ${fs}px Unbounded`;
  while (c.measureText(name).width > W - 200 && fs > 56) { fs -= 6; c.font = `900 ${fs}px Unbounded`; }
  c.fillStyle = "#efeae0"; c.textAlign = "center"; c.fillText(name, cx, 830);
  c.font = "600 40px Onest"; c.fillStyle = "#8f897e";
  const sub = [`ур. ${me.level?.level ?? me.level ?? 1}`, me.rep ? `репутация ${me.rep > 0 ? "+" : ""}${me.rep}` : null, me.reliability != null ? `надёжность ${me.reliability}%` : null].filter(Boolean).join("  ·  ");
  c.fillText(sub, cx, 900); c.textAlign = "left";
  // игры
  let y = 990;
  let ruMap = {};
  try {
    const { wikiData } = await import("./wiki.js");
    const d = await wikiData(me.games?.[0]?.game || S.game);
    ruMap = Object.fromEntries((d.heroes || []).map((h) => [h.name, h.ru || h.name]));
  } catch {}
  for (const gm of (me.games || []).slice(0, 3)) {
    const gi = GI(gm.game);
    rr(c, 80, y, W - 160, 200, 40); c.fillStyle = "#18181b"; c.fill();
    rr(c, 80, y, 16, 200, 8); c.fillStyle = gi.color; c.fill();
    c.fillStyle = gi.color; c.font = "700 34px 'JetBrains Mono'"; c.fillText(gi.short.toUpperCase(), 130, y + 64);
    c.fillStyle = "#efeae0"; c.font = "700 50px Unbounded";
    c.fillText((rankName(gm.rank, gm.game) || "без ранга") + (gm.verified ? " ✓" : ""), 130, y + 128);
    c.fillStyle = "#8f897e"; c.font = "500 34px Onest";
    const line = [gm.roles.map((r) => roleName(r, gm.game)).join(", "), gm.heroes.slice(0, 3).map((h) => (gm.game === (me.games?.[0]?.game) ? ruMap[h] || h : h)).join(", ")].filter(Boolean).join("  ·  ");
    let t = line; while (c.measureText(t).width > W - 260 && t.length > 4) t = t.slice(0, -2);
    c.fillText(t + (t !== line ? "…" : ""), 130, y + 176);
    y += 230;
  }
  // о себе
  if (me.about && y < 1600) {
    c.fillStyle = "#efeae0"; c.font = "500 38px Onest";
    const words = me.about.split(/\s+/); let line = "", lines = [];
    for (const w of words) { const t = line ? line + " " + w : w; if (c.measureText(t).width > W - 160) { lines.push(line); line = w; } else line = t; }
    if (line) lines.push(line);
    lines.slice(0, 3).forEach((l, i) => c.fillText(l, 80, y + 50 + i * 54));
  }
  // низ
  rr(c, 80, H - 260, W - 160, 150, 75); c.fillStyle = acc; c.fill();
  c.fillStyle = "#0b0b0c"; c.font = "900 40px Unbounded"; c.textAlign = "center";
  c.fillText("го катку? найди меня в лере", cx, H - 172);
  c.font = "700 30px 'JetBrains Mono'"; c.fillText(`t.me/${S.dict.bot}`.toUpperCase(), cx, H - 128);
  c.textAlign = "left";
  return cv;
}

export async function openStoryCard() {
  const cv = await drawCard();
  const blob = await new Promise((r) => cv.toBlob(r, "image/png"));
  const preview = URL.createObjectURL(blob);
  sheet((el, close) => {
    mount(el, html`<h2 class="h2" style="margin-bottom:12px">твоя карточка<span class="dot">.</span></h2>
      <img src="${preview}" alt="" style="width:62%;display:block;margin:0 auto 16px;border-radius:18px;box-shadow:0 10px 40px #0008">
      <button class="btn wide" data-act="story">${icon("share")}выложить в сторис</button>
      <button class="btn dark wide" style="margin-top:8px" data-act="save">сохранить картинку</button>
      <p class="small muted center" style="margin:10px 0 0">По ссылке в сторис друзья попадут прямо в Леру — тебе +150 несо за каждого.</p>`);
    let url = null;
    const upload = async () => {
      if (url) return url;
      const fd = new FormData(); fd.append("file", blob, "card.png");
      url = location.origin + (await api("/api/upload", { method: "POST", form: fd })).url;
      return url;
    };
    on(el, {
      story: async () => {
        try {
          const u = await upload();
          const ref = `https://t.me/${S.dict.bot}?start=ref_${S.me.tg_id}`;
          if (tg?.shareToStory && tg.isVersionAtLeast?.("7.8")) {
            tg.shareToStory(u, { text: "Ищу тиммейтов в Лере 🎮", widget_link: { url: ref, name: "Лера" } });
            haptic.ok(); close();
          } else {
            toast("Сторис доступны в свежем Telegram — сохрани картинку и выложи сам", "err");
          }
        } catch (e) { fail(e); }
      },
      save: async () => {
        try {
          const u = await upload();
          if (tg?.downloadFile && tg.isVersionAtLeast?.("8.0")) tg.downloadFile({ url: u, file_name: "lera-card.png" });
          else if (tg?.openLink) tg.openLink(u);
          else { const a = Object.assign(document.createElement("a"), { href: preview, download: "lera-card.png" }); a.click(); }
        } catch (e) { fail(e); }
      },
    });
  });
}
