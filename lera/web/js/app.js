import { tg, S, api, refreshMe, onState, emit, html, mount, icon, on, fail, closeAllScreens, leraSays } from "./core.js";
import * as duet from "./pages/duet.js";
import * as squads from "./pages/squads.js";
import * as feed from "./pages/feed.js";
import * as chats from "./pages/chats.js";
import * as profile from "./pages/profile.js";

const TABS = [
  { id: "duet", label: "Дуэт", ic: "duet", mod: duet },
  { id: "squads", label: "Отряды", ic: "squad", mod: squads },
  { id: "feed", label: "Лента", ic: "feed", mod: feed },
  { id: "chats", label: "Чаты", ic: "chat", mod: chats },
  { id: "profile", label: "Я", ic: "user", mod: profile },
];

let current = null, cleanup = null, view, bar;

function renderBar() {
  mount(bar, TABS.map((t) => {
    const n = t.id === "chats" ? S.unread.chats : t.id === "duet" ? S.unread.likes : 0;
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
  onState(renderBar);

  // deep links: ?s=m12 (чат), s5 (отряд), p7 (пост), likes, duet  — из уведомлений бота
  const sp = new URLSearchParams(location.search).get("s") || tg?.initDataUnsafe?.start_param || "";
  let start = null;
  try { start = localStorage.getItem("lera_tab"); } catch {}
  if (/^m\d+$/.test(sp)) { go("chats"); chats.openMatch(+sp.slice(1)); }
  else if (/^s\d+$/.test(sp)) { go("squads"); squads.openSquad(+sp.slice(1)); }
  else if (/^p\d+$/.test(sp)) { go("feed"); feed.openComments(+sp.slice(1)); }
  else if (sp === "likes") go("duet", "likes");
  else if (sp === "duet") go("duet");
  else if (!S.me.profile_done) { go("profile"); profile.openEditor(true); }
  else go(TABS.some((t) => t.id === start) ? start : "duet");

  // присутствие + счётчики
  setInterval(async () => {
    if (document.hidden) return;
    try { S.unread = await api("/api/ping", { method: "POST" }); emit(); } catch {}
  }, 45000);
}

boot().catch(fail);
