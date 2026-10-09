import { tg, S, api, refreshMe, onState, emit, html, mount, icon, on, fail, closeAllScreens, leraSays } from "./core.js";
import "./games.js";
import * as home from "./pages/home.js";
import * as mates from "./pages/mates.js";
import * as feed from "./pages/feed.js";
import * as chats from "./pages/chats.js";
import * as profile from "./pages/profile.js";

const TABS = [
  { id: "home", label: "Главная", ic: "home", mod: home },
  { id: "mates", label: "Тиммейты", ic: "pad", mod: mates },
  { id: "feed", label: "Лента", ic: "feed", mod: feed },
  { id: "chats", label: "Чаты", ic: "chat", mod: chats },
  { id: "profile", label: "Я", ic: "user", mod: profile },
];

let current = null, cleanup = null, view, bar, lastGame = null;

function renderBar() {
  mount(bar, TABS.map((t) => {
    const n = t.id === "chats" ? S.unread.chats : t.id === "mates" ? S.unread.likes : 0;
    return html`<button class="tab ${t.id === current ? "on" : ""}" data-act="tab" data-id="${t.id}">
      ${icon(t.ic)}<span>${t.label}</span>${n ? html`<i class="badge">${n > 99 ? "99+" : n}</i>` : ""}
    </button>`;
  }));
}

export function go(id, arg) {
  const t = TABS.find((x) => x.id === id) || TABS[0];
  closeAllScreens();
  if (typeof cleanup === "function") cleanup();
  current = t.id;
  lastGame = S.game;
  try { localStorage.setItem("lera_tab", current); } catch {}
  view.className = "view";
  view.scrollTop = 0;
  view.innerHTML = "";
  cleanup = t.mod.render(view, arg) || null;
  renderBar();
}

async function boot() {
  tg?.ready();
  tg?.expand();
  try { tg?.disableVerticalSwipes?.(); } catch {}
  try { tg?.setHeaderColor?.("#0b0b0c"); tg?.setBackgroundColor?.("#0b0b0c"); tg?.setBottomBarColor?.("#0b0b0c"); } catch {}

  const app = document.getElementById("app");
  try {
    await refreshMe();
  } catch (e) {
    mount(app, html`<div class="empty" style="height:100vh;align-content:center">
      <div class="boot-mark">лера<i>.</i></div>
      ${leraSays(e.status === 401 ? "Я работаю только внутри Telegram. Открой меня через бота 👀" : e.message)}
      <button class="btn" onclick="location.reload()">ещё раз</button></div>`);
    return;
  }

  app.innerHTML = "";
  view = document.createElement("div");
  bar = document.createElement("nav");
  bar.className = "tabbar";
  app.append(view, bar);
  on(bar, { tab: (b) => { tg?.HapticFeedback?.selectionChanged?.(); go(b.dataset.id); } });
  onState(() => {
    renderBar();
    if (lastGame && S.game !== lastGame && current) go(current);   // сменили игру — перерисовать вкладку
  });

  // deep links из уведомлений: m12 чат, s5 отряд, p7 пост, t3 турнир, likes, duet, home
  const sp = new URLSearchParams(location.search).get("s") || tg?.initDataUnsafe?.start_param || "";
  let start = null;
  try { start = localStorage.getItem("lera_tab"); } catch {}
  if (!S.me.profile_done) { go("profile"); profile.openEditor(true); }
  else if (/^m\d+$/.test(sp)) { go("chats"); chats.openMatch(+sp.slice(1)); }
  else if (/^s\d+$/.test(sp)) { go("mates", "squads"); const { openSquad } = await import("./pages/squads.js"); openSquad(+sp.slice(1)); }
  else if (/^p\d+$/.test(sp)) { go("feed"); feed.openComments(+sp.slice(1)); }
  else if (/^t\d+$/.test(sp)) { go("home"); const { openTournament } = await import("./pages/more.js"); openTournament(+sp.slice(1)); }
  else if (sp === "likes") go("mates", "likes");
  else if (sp === "duet") go("mates");
  else if (sp === "home") go("home");
  else go(TABS.some((t) => t.id === start) ? start : "home");

  setInterval(async () => {
    if (document.hidden) return;
    try { S.unread = await api("/api/ping", { method: "POST" }); emit(); } catch {}
  }, 45000);
}

boot().catch(fail);
