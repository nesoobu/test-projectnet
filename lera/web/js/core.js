// ─── Ядро: шаблоны, API, Telegram, UI-примитивы ──────────────────────────
export const tg = window.Telegram?.WebApp;

// безопасные шаблоны: всё интерполированное экранируется, кроме html`` и raw()
class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
export const raw = (s) => new Raw(s);
const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (v) => String(v).replace(/[&<>"']/g, (c) => ESC[c]);
const fmt = (v) => v == null || v === false ? "" : v instanceof Raw ? v.s : Array.isArray(v) ? v.map(fmt).join("") : esc(v);
export function html(str, ...vals) {
  let out = str[0];
  for (let i = 0; i < vals.length; i++) out += fmt(vals[i]) + str[i + 1];
  return new Raw(out);
}
export const safeUrl = (u) => (typeof u === "string" && (u.startsWith("/uploads/") || u.startsWith("/static/") || u.startsWith("https://"))) ? u : "";

// ─── state ───
export const S = { me: null, dict: null, unread: { chats: 0, likes: 0 }, game: null };
const listeners = new Set();
export const onState = (fn) => (listeners.add(fn), () => listeners.delete(fn));
export const emit = () => listeners.forEach((fn) => fn(S));

// ─── api ───
const params = new URLSearchParams(location.search);
let devUser = params.get("dev");
try { if (devUser) localStorage.setItem("lera_dev", devUser); else devUser = localStorage.getItem("lera_dev"); } catch {}

export async function api(path, { method = "GET", body, form } = {}) {
  const headers = { "X-Init-Data": tg?.initData || "" };
  if (devUser && !tg?.initData) headers["X-Dev-User"] = devUser;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  let r;
  try { r = await fetch(path, { method, headers, body: payload }); }
  catch { throw new Error("Нет связи. Проверь интернет"); }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = data.detail;
    const e = new Error(typeof d === "string" ? d : Array.isArray(d) ? "Проверь поля формы" : "Что-то пошло не так");
    e.status = r.status; throw e;
  }
  return data;
}

export async function refreshMe() {
  const b = await api("/api/bootstrap");
  S.me = b.me; S.dict = b.dict; S.unread = b.unread;
  if (!S.game || !S.dict.games[S.game]) {
    let saved = null;
    try { saved = localStorage.getItem("lera_game"); } catch {}
    S.game = S.me.games.find((g) => g.game === saved)?.game || S.me.games[0]?.game || (S.dict.games[saved] ? saved : "hok");
  }
  applyAccent(S.me.accent);
  applyGameColor();
  emit();
  return b;
}

export function applyAccent(hex) {
  const c = hex || "#d4ff3f";
  document.documentElement.style.setProperty("--acc", c);
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  document.documentElement.style.setProperty("--acc-ink", lum > 0.55 ? "#0b0b0c" : "#ffffff");
}

// ─── telegram helpers ───
export const haptic = {
  tap: () => tg?.HapticFeedback?.impactOccurred?.("light"),
  hard: () => tg?.HapticFeedback?.impactOccurred?.("heavy"),
  ok: () => tg?.HapticFeedback?.notificationOccurred?.("success"),
  err: () => tg?.HapticFeedback?.notificationOccurred?.("error"),
  sel: () => tg?.HapticFeedback?.selectionChanged?.(),
};

// ─── toast ───
export function toast(text, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = text;
  document.getElementById("toasts").append(el);
  if (kind === "err") haptic.err();
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 260); }, 2600);
}
export const fail = (e) => toast(e?.message || String(e), "err");

// ─── el helpers ───
export function mount(el, content) { el.innerHTML = fmt(content); return el; }
export function on(root, handlers) {
  const fn = (ev) => {
    const t = ev.target.closest("[data-act]");
    if (!t || !root.contains(t)) return;
    const h = handlers[t.dataset.act];
    if (h) { ev.preventDefault?.(); h(t, ev); }
  };
  root.addEventListener("click", fn);
  return () => root.removeEventListener("click", fn);
}
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// ─── screens (стек поверх вкладок) + BackButton ───
const stack = [];
function syncBack() {
  if (!tg?.BackButton) return;
  stack.length ? tg.BackButton.show() : tg.BackButton.hide();
}
tg?.BackButton?.onClick(() => popScreen());

export function pushScreen(render, { flex = false } = {}) {
  const el = document.createElement("div");
  el.className = "screen" + (flex ? " flex" : "");
  document.getElementById("app").append(el);
  const entry = { el, cleanup: null };
  stack.push(entry);
  syncBack();
  try { entry.cleanup = render(el, () => popScreen(entry)) || null; } catch (e) { console.error(e); }
  return entry;
}
export function popScreen(entry) {
  const e = entry || stack[stack.length - 1];
  if (!e) return;
  const i = stack.indexOf(e);
  if (i < 0) return;
  stack.splice(i, 1);
  syncBack();
  if (typeof e.cleanup === "function") e.cleanup();
  e.el.classList.add("out");
  setTimeout(() => e.el.remove(), 220);
}
export const closeAllScreens = () => [...stack].reverse().forEach((e) => popScreen(e));
export const screenDepth = () => stack.length;

// ─── bottom sheet ───
export function sheet(render) {
  const wrap = document.createElement("div");
  wrap.className = "sheet-wrap";
  const sh = document.createElement("div");
  sh.className = "sheet";
  wrap.append(sh);
  document.body.append(wrap);
  let closed = false;
  const close = () => {
    if (closed) return; closed = true;
    wrap.classList.add("out");
    setTimeout(() => wrap.remove(), 200);
  };
  wrap.addEventListener("click", (e) => { if (e.target === wrap) close(); });
  render(sh, close);
  return close;
}

export function confirmSheet(title, text, okText = "да", danger = false) {
  return new Promise((res) => {
    sheet((el, close) => {
      mount(el, html`
        <h2 class="h2">${title}</h2>
        <p class="muted">${text}</p>
        <div class="row" style="margin-top:18px">
          <button class="btn ghost grow" data-act="no">отмена</button>
          <button class="btn grow ${danger ? "hot" : ""}" data-act="yes">${okText}</button>
        </div>`);
      on(el, { yes: () => { close(); res(true); }, no: () => { close(); res(false); } });
    });
  });
}

// ─── formatting ───
export function ago(ts) {
  if (!ts) return "";
  const d = new Date(ts.replace(" ", "T") + "Z");
  const s = (Date.now() - d) / 1000;
  if (s < 60) return "сейчас";
  if (s < 3600) return `${Math.floor(s / 60)} мин`;
  if (s < 86400) return `${Math.floor(s / 3600)} ч`;
  if (s < 7 * 86400) return `${Math.floor(s / 86400)} д`;
  return d.toLocaleDateString("ru", { day: "numeric", month: "short" });
}
export const hhmm = (ts) => new Date(ts.replace(" ", "T") + "Z").toLocaleTimeString("ru", { hour: "2-digit", minute: "2-digit" });
export function left(ts) {
  const s = (new Date(ts.replace(" ", "T") + "Z") - Date.now()) / 1000;
  if (s <= 0) return "истёк";
  if (s < 3600) return `${Math.ceil(s / 60)} мин`;
  return `${Math.floor(s / 3600)} ч ${Math.floor((s % 3600) / 60)} мин`;
}
export const plural = (n, a, b, c) => {
  const m10 = n % 10, m100 = n % 100;
  return m10 === 1 && m100 !== 11 ? a : m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? b : c;
};

// цвет-заглушка по id
const HUES = ["#d4ff3f", "#ff6fa5", "#7cc8ff", "#ffc64a", "#b48cff", "#ff7a59", "#5ef0c1"];
export const tint = (id) => HUES[Math.abs(Number(id) || 0) % HUES.length];
export const initial = (name) => (name || "?").trim().charAt(0).toUpperCase() || "?";

export function avatar(p, size = 44, { online = false } = {}) {
  if (!p) return "";
  const src = safeUrl(p.avatar);
  return html`<div class="av ${p.frame || ""}" style="--s:${size}px">
    <div class="in" style="background:${src ? "var(--card2)" : tint(p.tg_id)}">
      ${src ? html`<img src="${src}" alt="" loading="lazy">` : initial(p.name)}
    </div>${online && p.online ? html`<i class="on"></i>` : ""}
  </div>`;
}
export const nameEl = (p, cls = "") => html`<span class="${cls} ${p?.color || ""}">${p?.name || "Игрок"}</span>`;

export function leraSays(text) {
  return html`<div class="lera"><div class="face">Л</div><div class="bub">${text}</div></div>`;
}

// ─── игры ───
export const GI = (g = S.game) => S.dict?.games?.[g] || S.dict?.games?.hok;
export const rankName = (i, g = S.game) => (i == null ? null : GI(g)?.ranks?.[i]);
export const roleName = (r, g = S.game) => GI(g)?.roles?.[r] || r;
export const modeName = (m, g = S.game) => GI(g)?.modes?.[m] || m;
export function setGame(g) {
  if (!S.dict.games[g] || S.game === g) return;
  S.game = g;
  try { localStorage.setItem("lera_game", g); } catch {}
  applyGameColor();
  emit();
}
export function applyGameColor() {
  document.documentElement.style.setProperty("--game", GI()?.color || "#d4ff3f");
}
export const gameBadge = (g, extra = "") => html`<span class="gbadge" style="--gc:${GI(g)?.color}" ${raw(extra)}>${GI(g)?.short || g}</span>`;
export const myGame = (g = S.game) => S.me?.games?.find((x) => x.game === g);

// ─── icons ───
const P = {
  heart: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  star: '<path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.8z"/>',
  undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
  sliders: '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
  squad: '<path d="M12 3l7 3v5c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V6z"/><path d="M9 12l2 2 4-4"/>',
  feed: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 13h8M8 17h5"/>',
  chat: '<path d="M20 12a8 8 0 0 1-11.6 7.1L4 20l1-4.2A8 8 0 1 1 20 12z"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-7 8-7s8 3 8 7"/>',
  duet: '<path d="M7 4h7a3 3 0 0 1 3 3v12a1 1 0 0 1-1 1H7a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3z"/><path d="M17 7h1a2 2 0 0 1 2 2v9"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  send: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/>',
  back: '<path d="M15 5l-7 7 7 7"/>',
  dots: '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>',
  flag: '<path d="M5 21V4h12l-2 4 2 4H5"/>',
  check: '<path d="M5 12l5 5 9-10"/>',
  bolt: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  gift: '<rect x="3" y="8" width="18" height="5" rx="1"/><path d="M5 13v8h14v-8M12 8v13M12 8S10 3 7.5 4.5 9 8 12 8zM12 8s2-5 4.5-3.5S15 8 12 8z"/>',
  crown: '<path d="M3 8l4 4 5-7 5 7 4-4-2 11H5z"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4-4"/>',
  trophy: '<path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4M8 21h8M9 17h6v4"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM4 21V5M8 7h7"/>',
  bag: '<path d="M5 8h14l-1 13H6zM9 8V6a3 3 0 0 1 6 0v2"/>',
  sparkle: '<path d="M12 3c.5 4.5 2 6 6.5 6.5-4.5.5-6 2-6.5 6.5-.5-4.5-2-6-6.5-6.5C10 9 11.5 7.5 12 3zM18.5 15c.3 2 1 2.7 3 3-2 .3-2.7 1-3 3-.3-2-1-2.7-3-3 2-.3 2.7-1 3-3z"/>',
  box: '<path d="M3 8l9-5 9 5v8l-9 5-9-5z"/><path d="M3 8l9 5 9-5M12 13v8"/>',
  target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r=".8"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .8-1 1.5V14M12 17.5v.01"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M14 6l4 4"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  share: '<path d="M12 15V3M7 8l5-5 5 5"/><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20a2 2 0 0 0 4 0"/>',
  home: '<path d="M4 11l8-7 8 7v9a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z"/>',
  pad: '<path d="M7 8h10a5 5 0 0 1 4.6 7l-.7 1.7a2.5 2.5 0 0 1-4.2.6L15 15H9l-1.7 2.3a2.5 2.5 0 0 1-4.2-.6L2.4 15A5 5 0 0 1 7 8z"/><path d="M7 11v3M5.5 12.5h3M16 12h.01M18 13.5h.01"/>',
  swords: '<path d="M14.5 17.5L3 6V3h3l11.5 11.5M13 19l6-6M16 16l4 4M19 21l2-2M9.5 6.5L14 2h3v3l-4.5 4.5M5 14l-2 2 3 3 2-2"/>',
  puzzle: '<path d="M10 3h4v3a2 2 0 1 0 4 0V5h3v5h-1a2 2 0 1 0 0 4h1v6h-6v-1a2 2 0 1 0-4 0v1H4v-6h1a2 2 0 1 0 0-4H4V5h6z"/>',
  poll: '<path d="M4 20h16M7 16V9M12 16V4M17 16v-5"/>',
  rss: '<path d="M5 19a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16"/>',
  medal: '<circle cx="12" cy="15" r="5"/><path d="M8.5 11L6 3h4l2 5 2-5h4l-2.5 8"/>',
  thumb: '<path d="M7 11v9H4v-9zM7 11l4-8a2 2 0 0 1 2 2v4h5.5a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 17.3 20H7"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  down: '<path d="M6 9l6 6 6-6"/>',
  fire: '<path d="M12 21c-4 0-7-2.7-7-6.5 0-3 2-5 3.5-6.5.3 2 1.5 3 2.5 3-1-3 .5-6.5 3.5-8 0 3 5.5 5.5 5.5 11.5 0 3.8-3 6.5-8 6.5z"/>',
  coin: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v10M9.5 9.5h4a1.5 1.5 0 0 1 0 3h-3a1.5 1.5 0 0 0 0 3h4"/>',
};
export const icon = (name, extra = "") =>
  raw(`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" ${extra}>${P[name] || ""}</svg>`);

// ─── реалтайм (WebSocket) ───
const rtHandlers = {};
let rtSock = null, rtRetry = 0, rtPing = null;
export const rt = {
  connected: false,
  on(type, fn) { (rtHandlers[type] ||= new Set()).add(fn); return () => rtHandlers[type].delete(fn); },
  send(obj) { if (rtSock?.readyState === 1) rtSock.send(JSON.stringify(obj)); },
  connect() {
    if (rtSock && rtSock.readyState <= 1) return;
    const qs = tg?.initData ? `init=${encodeURIComponent(tg.initData)}` : devUser ? `dev=${encodeURIComponent(devUser)}` : "";
    try { rtSock = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws?${qs}`); } catch { return; }
    rtSock.onopen = () => {
      rt.connected = true; rtRetry = 0;
      clearInterval(rtPing); rtPing = setInterval(() => rt.send({ type: "ping" }), 25000);
      (rtHandlers.open || []).forEach((fn) => fn());
    };
    rtSock.onmessage = (e) => {
      let ev; try { ev = JSON.parse(e.data); } catch { return; }
      (rtHandlers[ev.type] || []).forEach((fn) => { try { fn(ev); } catch (err) { console.error(err); } });
    };
    rtSock.onclose = (e) => {
      rt.connected = false; clearInterval(rtPing);
      if (e.code === 4401 || e.code === 4403) return;
      setTimeout(() => rt.connect(), Math.min(30000, 1000 * 2 ** rtRetry++));
    };
  },
};
document.addEventListener("visibilitychange", () => { if (!document.hidden) rt.connect(); });
