import { S, api, html, mount, on, icon, sheet, toast, fail, haptic, avatar, nameEl, rankName, roleName, leraSays, emit, ago } from "../core.js";
import { openPerson, photoBg } from "./person.js";
import { openPremium } from "./more.js";

const FKEY = "lera_filters";
const DEF = { gender: "", age_min: 14, age_max: 80, rank_min: 0, rank_max: 7, role: "", online: 0 };
const loadF = () => { try { return { ...DEF, ...JSON.parse(localStorage.getItem(FKEY) || "{}") }; } catch { return { ...DEF }; } };
const saveF = (f) => { try { localStorage.setItem(FKEY, JSON.stringify(f)); } catch {} };
const activeFilters = (f) => Object.keys(DEF).filter((k) => f[k] !== DEF[k]).length;

const EMPTY = ["Анкеты кончились. Даже я столько не свайпаю.", "Тут пусто. Ослабь фильтры или зайди позже — люди подтянутся.", "Ты посмотрел всех. Может, пора собрать отряд?"];

export function render(root, arg) {
  root.classList.add("noscroll");
  let tab = arg === "likes" ? "likes" : "cards";
  let cards = [], loading = true, superLeft = 0, premium = false, busy = false;
  let f = loadF();

  root.innerHTML = `<div class="top"><div><div class="kicker" id="dk"></div><h1 class="h1" style="margin-top:6px">дуэт<i>.</i></h1></div>
    <button class="ibtn" data-act="filters" id="fbtn"></button></div>
    <div class="pad" style="margin-bottom:12px"><div class="seg" id="seg"></div></div>
    <div id="body" style="flex:1;display:flex;flex-direction:column;min-height:0"></div>`;
  const body = root.querySelector("#body");

  const drawHead = () => {
    const n = activeFilters(f);
    mount(root.querySelector("#fbtn"), html`${icon("sliders")}${n ? html`<i class="badge" style="background:var(--acc);color:var(--acc-ink)">${n}</i>` : ""}`);
    mount(root.querySelector("#seg"), html`
      <button class="${tab === "cards" ? "on" : ""}" data-act="tab" data-t="cards">Анкеты</button>
      <button class="${tab === "likes" ? "on" : ""}" data-act="tab" data-t="likes">Лайки ${S.unread.likes ? html`<i class="badge">${S.unread.likes}</i>` : ""}</button>`);
    const online = cards.filter((c) => c.online).length;
    mount(root.querySelector("#dk"), html`// поиск тиммейта${online ? html` · <b>${online} онлайн</b>` : ""}`);
  };

  async function load() {
    loading = true; draw();
    try {
      const q = new URLSearchParams(Object.entries(f).map(([k, v]) => [k, String(v)]));
      const [feed, st] = await Promise.all([api(`/api/duet/feed?${q}`), api("/api/duet/status")]);
      cards = feed.cards; superLeft = st.super_left; premium = st.premium;
    } catch (e) { fail(e); }
    loading = false; draw();
  }

  function draw() {
    drawHead();
    if (tab === "likes") return drawLikes();
    if (loading) return mount(body, html`<div class="deck"><div class="swipe skel"></div></div><div class="actions" style="height:96px"></div>`);
    if (!cards.length) {
      return mount(body, html`<div class="empty" style="flex:1;align-content:center">
        <h2 class="h2">пусто<span class="dot">.</span></h2>
        ${leraSays(EMPTY[Math.floor(Math.random() * EMPTY.length)])}
        <div class="row">${activeFilters(f) ? html`<button class="btn ghost" data-act="reset">сбросить фильтры</button>` : ""}
        <button class="btn" data-act="reload">обновить</button></div></div>`);
    }
    mount(body, html`
      <div class="deck">${cards.slice(0, 2).reverse().map((c, i, arr) => cardHtml(c, i === arr.length - 1))}</div>
      <div class="actions">
        <button class="act undo" data-act="undo" aria-label="отменить">${icon("undo")}</button>
        <button class="act no" data-act="pass" aria-label="мимо">${icon("x")}</button>
        <button class="act go" data-act="like" aria-label="лайк">${icon("heart")}</button>
        <button class="act sup" data-act="super" aria-label="суперлайк">${icon("star")}<i class="badge">${superLeft}</i></button>
      </div>`);
    bindDrag(body.querySelector(".swipe.top"));
  }

  function cardHtml(c, isTop) {
    return html`<div class="swipe ${isTop ? "top" : "behind"}" data-id="${c.tg_id}">
      <div class="ph">${photoBg(c, 0)}</div>
      ${c.photos.length > 1 ? html`<div class="bars">${c.photos.map((_, i) => html`<i class="${i === 0 ? "on" : ""}"></i>`)}</div>` : ""}
      <div class="vibe"><b>${c.vibe}</b><small>вайб</small></div>
      <div class="stamp go">го</div><div class="stamp no">мимо</div><div class="stamp sup">супер</div>
      <div class="shade"></div>
      <div class="info">
        <div class="row wrap" style="gap:6px;margin-bottom:10px">
          ${c.super_liked_me ? html`<span class="tag gold">${icon("star", 'width="11" height="11"')} суперлайкнул(а) тебя</span>` : ""}
          ${c.online ? html`<span class="tag on-dot">онлайн</span>` : ""}
          ${c.title ? html`<span class="tag">${c.title}</span>` : ""}
          ${c.premium ? html`<span class="tag gold">premium</span>` : ""}
        </div>
        <div class="nm">${nameEl(c)}${c.age ? html`<span class="age">${c.age}</span>` : ""}</div>
        <div class="chips" style="margin-top:12px">
          ${rankName(c.rank) ? html`<span class="chip on">${rankName(c.rank)}</span>` : ""}
          ${c.roles.map((r) => html`<span class="chip">${roleName(r)}</span>`)}
          ${c.voice ? html`<span class="chip">${icon("mic")}</span>` : ""}
        </div>
        ${c.about ? html`<div class="about">${c.about}</div>` : ""}
        <div class="more">${c.vibe_why.length ? html`<div class="chips">${c.vibe_why.map((w) => html`<span class="chip acc">${w}</span>`)}</div>` : ""}
          ${c.heroes.length ? html`<div class="kicker" style="margin:12px 0 8px">мейны</div><div class="chips">${c.heroes.map((h) => html`<span class="chip">${h}</span>`)}</div>` : ""}
        </div>
      </div>
    </div>`;
  }

  function bindDrag(el) {
    if (!el) return;
    const c = cards[0];
    let sx = 0, sy = 0, dx = 0, dy = 0, down = false, photo = 0;
    const st = { go: el.querySelector(".stamp.go"), no: el.querySelector(".stamp.no"), sup: el.querySelector(".stamp.sup") };
    const clamp = (v) => Math.max(0, Math.min(1, v));
    el.addEventListener("pointerdown", (e) => {
      down = true; sx = e.clientX; sy = e.clientY; dx = dy = 0;
      el.setPointerCapture(e.pointerId); el.style.transition = "none";
    });
    el.addEventListener("pointermove", (e) => {
      if (!down) return;
      dx = e.clientX - sx; dy = e.clientY - sy;
      el.style.transform = `translate(${dx}px, ${dy}px) rotate(${dx / 16}deg)`;
      const vertical = dy < 0 && Math.abs(dy) > Math.abs(dx);
      st.go.style.opacity = vertical ? 0 : clamp(dx / 90);
      st.no.style.opacity = vertical ? 0 : clamp(-dx / 90);
      st.sup.style.opacity = vertical ? clamp(-dy / 110) : 0;
    });
    const up = (e) => {
      if (!down) return;
      down = false;
      if (dx > 110) return fly("like");
      if (dx < -110) return fly("pass");
      if (dy < -140 && Math.abs(dy) > Math.abs(dx)) return fly("super");
      el.style.transition = "transform .35s cubic-bezier(.2,.8,.2,1)";
      el.style.transform = "";
      Object.values(st).forEach((s) => (s.style.opacity = 0));
      if (Math.abs(dx) < 6 && Math.abs(dy) < 6) {
        const r = el.getBoundingClientRect();
        const y = e.clientY - r.top;
        if (y > r.height * 0.55) { el.classList.toggle("open"); haptic.tap(); return; }
        if (c.photos.length > 1) {
          photo = (photo + (e.clientX - r.left > r.width / 2 ? 1 : -1) + c.photos.length) % c.photos.length;
          mount(el.querySelector(".ph"), photoBg(c, photo));
          el.querySelectorAll(".bars i").forEach((b, i) => b.classList.toggle("on", i === photo));
          haptic.sel();
        } else openPerson(c, { onLike: () => act("like"), onPass: () => act("pass") });
      }
    };
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
  }

  function fly(action) {
    const el = body.querySelector(".swipe.top");
    if (!el || busy) return;
    if (action === "super" && superLeft <= 0) {
      el.style.transition = "transform .35s"; el.style.transform = "";
      el.querySelectorAll(".stamp").forEach((s) => (s.style.opacity = 0));
      return premium ? toast("Суперлайки на сегодня всё. Завтра ещё", "err") : upsell("Суперлайков больше нет", "В Premium их 5 в день вместо одного.");
    }
    const c = cards[0];
    const x = action === "like" ? 1 : action === "pass" ? -1 : 0;
    el.querySelector(`.stamp.${action === "like" ? "go" : action === "pass" ? "no" : "sup"}`).style.opacity = 1;
    el.style.transition = "transform .4s cubic-bezier(.4,.2,.2,1), opacity .4s";
    el.style.transform = `translate(${x * innerWidth * 1.3}px, ${action === "super" ? -innerHeight : 40}px) rotate(${x * 24}deg)`;
    el.style.opacity = "0";
    action === "pass" ? haptic.tap() : haptic.hard();
    busy = true;
    setTimeout(() => { cards.shift(); busy = false; draw(); }, 260);
    send(c, action);
  }

  async function send(c, action) {
    try {
      const r = await api("/api/duet/swipe", { method: "POST", body: { to: c.tg_id, action } });
      if (action === "super") { superLeft = Math.max(0, superLeft - 1); }
      if (r.match) { matchOverlay(r.match); S.unread.likes = Math.max(0, S.unread.likes - 1); emit(); }
    } catch (e) {
      fail(e);
      if (e.status === 429) { cards.unshift(c); draw(); }
    }
  }

  function act(action) {
    if (tab !== "cards" || !cards.length) return;
    if (action === "undo") return undo();
    fly(action);
  }

  async function undo() {
    if (!premium) return upsell("Вернуть анкету?", "Отмена последнего свайпа — фича Premium. Промахнулся пальцем — не беда.");
    try {
      const p = await api("/api/duet/undo", { method: "POST" });
      if (p) { p.vibe = p.vibe || 50; p.vibe_why = p.vibe_why || []; cards.unshift(p); haptic.ok(); draw(); }
    } catch (e) { fail(e); }
  }

  async function drawLikes() {
    mount(body, html`<div class="spinner"></div>`);
    let likes = [];
    try { likes = (await api("/api/duet/likes")).likes; } catch (e) { return fail(e); }
    if (tab !== "likes") return;
    if (!likes.length) {
      return mount(body, html`<div class="empty" style="flex:1;align-content:center"><h2 class="h2">лайков пока нет<span class="dot">.</span></h2>
        ${leraSays("Заполни анкету поярче и добавь фото — так лайкают в 3 раза чаще. Это я сама посчитала.")}</div>`);
    }
    mount(body, html`<div style="overflow-y:auto;flex:1"><div class="likes-grid">${likes.map((p) => html`
      <button class="lk" data-act="open-like" data-id="${p.tg_id}">
        ${photoBg(p)}<div class="shade"></div>
        ${p.super ? html`<span class="tag gold">супер</span>` : p.online ? html`<span class="tag on-dot">онлайн</span>` : ""}
        <div class="t"><b>${nameEl(p)}${p.age ? `, ${p.age}` : ""}</b><span class="small muted">${rankName(p.rank) || ""} · ${ago(p.at)}</span></div>
      </button>`)}</div></div>`);
    body._likes = likes;
  }

  function upsell(title, text) {
    sheet((el, close) => {
      mount(el, html`<div class="kicker"><b>premium</b></div><h2 class="h2" style="margin:8px 0">${title}</h2><p class="muted">${text}</p>
        <button class="btn wide" data-act="go">${icon("crown")}посмотреть premium</button>`);
      on(el, { go: () => { close(); openPremium(); } });
    });
  }

  function filtersSheet() {
    const d = S.dict;
    sheet((el, close) => {
      const g = { ...f };
      const draw2 = () => mount(el, html`
        <h2 class="h2" style="margin-bottom:18px">фильтры<span class="dot">.</span></h2>
        <div class="field"><span class="lbl">кто в сети</span><div class="seg">
          <button class="${!g.online ? "on" : ""}" data-act="set" data-k="online" data-v="0">Все</button>
          <button class="${g.online ? "on" : ""}" data-act="set" data-k="online" data-v="1">Онлайн</button></div></div>
        <div class="field"><span class="lbl">пол</span><div class="seg">
          ${[["", "Все"], ["f", "Девушки"], ["m", "Парни"]].map(([v, t]) => html`<button class="${g.gender === v ? "on" : ""}" data-act="set" data-k="gender" data-v="${v}">${t}</button>`)}</div></div>
        <div class="field"><span class="lbl">возраст</span><div class="range2">
          <input class="input" type="number" inputmode="numeric" id="amin" value="${g.age_min}"><span class="muted">—</span>
          <input class="input" type="number" inputmode="numeric" id="amax" value="${g.age_max}"></div></div>
        <div class="field"><span class="lbl">ранг от и до</span>
          <div class="chips scroll">${d.ranks.map((r, i) => html`<button class="chip ${i >= g.rank_min && i <= g.rank_max ? "on" : ""}" data-act="rank" data-i="${i}">${r}</button>`)}</div></div>
        <div class="field"><span class="lbl">роль</span><div class="chips">
          <button class="chip ${!g.role ? "on" : ""}" data-act="set" data-k="role" data-v="">Любая</button>
          ${Object.entries(d.roles).map(([k, v]) => html`<button class="chip ${g.role === k ? "on" : ""}" data-act="set" data-k="role" data-v="${k}">${v}</button>`)}</div></div>
        <div class="row"><button class="btn ghost" data-act="reset">сброс</button><button class="btn grow" data-act="apply">показать</button></div>`);
      let rankTap = null;
      const readAges = () => {
        g.age_min = Math.max(14, +el.querySelector("#amin").value || 14);
        g.age_max = Math.min(80, +el.querySelector("#amax").value || 80);
      };
      draw2();
      on(el, {
        set: (b) => { readAges(); g[b.dataset.k] = b.dataset.k === "online" ? +b.dataset.v : b.dataset.v; haptic.sel(); draw2(); },
        rank: (b) => {
          readAges(); const i = +b.dataset.i;
          if (rankTap === null) { g.rank_min = g.rank_max = i; rankTap = i; }
          else { g.rank_min = Math.min(rankTap, i); g.rank_max = Math.max(rankTap, i); rankTap = null; }
          haptic.sel(); draw2();
        },
        reset: () => { Object.assign(g, DEF); draw2(); },
        apply: () => { readAges(); f = g; saveF(f); close(); load(); },
      });
    });
  }

  const off = on(root, {
    tab: (b) => { tab = b.dataset.t; haptic.sel(); tab === "cards" && !cards.length ? load() : draw(); },
    filters: filtersSheet,
    like: () => act("like"), pass: () => act("pass"), super: () => act("super"), undo: () => act("undo"),
    reload: load,
    reset: () => { f = { ...DEF }; saveF(f); load(); },
    "open-like": (b) => {
      const p = body._likes?.find((x) => x.tg_id === +b.dataset.id);
      if (!p) return;
      const done = (action) => async () => {
        body._likes = body._likes.filter((x) => x !== p);
        b.remove();
        S.unread.likes = Math.max(0, S.unread.likes - 1); emit(); drawHead();
        await send(p, action);
      };
      openPerson(p, { onLike: done("like"), onPass: done("pass") });
    },
  });

  load();
  return off;
}

export function matchOverlay(m) {
  haptic.ok();
  const el = document.createElement("div");
  el.className = "match";
  mount(el, html`
    <div class="word">мэтч!</div>
    <div class="pair">${avatar(S.me, 108)}${avatar(m.with, 108)}</div>
    ${leraSays(m.lera || "Взаимно! Напиши первым.")}
    <div class="row" style="width:100%;max-width:340px">
      <button class="btn ghost grow" data-act="close">дальше</button>
      <button class="btn grow" data-act="chat">${icon("chat")}написать</button>
    </div>`);
  document.body.append(el);
  on(el, {
    close: () => el.remove(),
    chat: async () => { el.remove(); const { openMatch } = await import("./chats.js"); openMatch(m.id); },
  });
}
