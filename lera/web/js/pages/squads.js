import { S, tg, api, html, mount, on, icon, avatar, nameEl, left, pushScreen, sheet, leraSays, fail, toast, haptic, rankName, roleName, modeName, confirmSheet, GI, gameBadge } from "../core.js";
import { chatRoom } from "./chats.js";
import { openPerson } from "./person.js";

export function render(root) {
  let mode = "", mine = 0;
  mount(root, html`    <div class="pad"><div class="chips scroll" id="modes"></div></div>
    <div class="pad" id="list" style="padding-top:14px;padding-bottom:90px"></div>
    <button class="fab" data-act="create">${icon("plus")}собрать</button>`);
  const list = root.querySelector("#list");

  const drawModes = () => mount(root.querySelector("#modes"), html`
    <button class="chip ${!mode && !mine ? "on" : ""}" data-act="mode" data-m="">Все</button>
    <button class="chip ${mine ? "on" : ""}" data-act="mine">Мои</button>
    ${Object.entries(GI().modes).map(([k, v]) => html`<button class="chip ${mode === k ? "on" : ""}" data-act="mode" data-m="${k}">${v}</button>`)}`);

  async function load() {
    drawModes();
    mount(list, html`<div class="skel" style="height:150px"></div><div class="sp"></div><div class="skel" style="height:150px"></div>`);
    let squads;
    try { squads = (await api(`/api/squads?game=${S.game}&mode=${mode}&mine=${mine}`)).squads; } catch (e) { return fail(e); }
    if (!squads.length) {
      return mount(list, html`<div class="empty"><h2 class="h2">никто не собирает<span class="dot">.</span></h2>
        ${leraSays("Будь первым — создай отряд, а я позову людей. Обычно набирается минут за десять.")}</div>`);
    }
    mount(list, html`<div class="stack">${squads.map(squadCard)}</div>`);
  }

  const off = on(root, {
    mode: (b) => { mode = b.dataset.m; mine = 0; haptic.sel(); load(); },
    mine: () => { mine = 1; mode = ""; haptic.sel(); load(); },
    create: () => createSheet((s) => { load(); openSquad(s.id, load); }),
    open: (b) => openSquad(+b.dataset.id, load),
  });
  load();
  return off;
}

function squadCard(s) {
  const free = s.max_players - s.count;
  return html`<button class="sq" style="width:100%;text-align:left" data-act="open" data-id="${s.id}">
    <div class="side" style="background:${GI(s.game).color}">${modeName(s.mode, s.game)}</div>
    <div class="body">
      <div class="row"><b class="h3 grow">${s.title}</b>${s.game !== S.game ? gameBadge(s.game) : ""}${s.voice ? html`<span class="tag">${icon("mic", 'width="11" height="11"')}</span>` : ""}</div>
      <div class="row wrap small muted" style="margin-top:6px;gap:8px">
        ${rankName(s.rank, s.game) ? html`<span>${rankName(s.rank, s.game)}+</span>` : html`<span>любой ранг</span>`}
        <span>·</span><span class="mono">${icon("clock", 'width="12" height="12" style="vertical-align:-2px"')} ${left(s.expires_at)}</span>
      </div>
      ${s.roles_needed.length ? html`<div class="chips" style="margin-top:10px">${s.roles_needed.map((r) => html`<span class="chip" style="height:26px;font-size:12px">ищем: ${roleName(r, s.game)}</span>`)}</div>` : ""}
      <div class="slots">${s.members.map((m) => avatar(m, 34))}${Array.from({ length: free }, () => html`<span class="slot-empty">${icon("plus")}</span>`)}
        <span class="grow"></span>${s.joined ? html`<span class="tag acc">ты тут</span>` : html`<span class="kicker">${free} ${free === 1 ? "место" : free < 5 ? "места" : "мест"}</span>`}</div>
    </div></button>`;
}

function createSheet(done) {
  const d = GI();
  const mg = S.me.games.find((x) => x.game === S.game);
  const g = { title: "", game: S.game, mode: Object.keys(d.modes)[0], rank: mg?.rank ?? null, roles_needed: [], max_players: 5, voice: false, hours: 2 };
  sheet((el, close) => {
    const draw = () => {
      const t = el.querySelector("#t")?.value; if (t !== undefined) g.title = t;
      mount(el, html`<div class="row" style="margin-bottom:18px"><h2 class="h2 grow">новый отряд<span class="dot">.</span></h2>${gameBadge(S.game)}</div>
      <div class="field"><label>название</label><input class="input" id="t" maxlength="48" placeholder="Апаем мифик без токсиков" value="${g.title}"></div>
      <div class="field"><span class="lbl">режим</span><div class="chips">${Object.entries(d.modes).map(([k, v]) => html`<button class="chip ${g.mode === k ? "on" : ""}" data-act="m" data-v="${k}">${v}</button>`)}</div></div>
      <div class="field"><span class="lbl">минимальный ранг</span><div class="chips scroll">
        <button class="chip ${g.rank == null ? "on" : ""}" data-act="r" data-v="">Любой</button>
        ${d.ranks.map((r, i) => html`<button class="chip ${g.rank === i ? "on" : ""}" data-act="r" data-v="${i}">${r}</button>`)}</div></div>
      <div class="field"><span class="lbl">кого ищем</span><div class="chips">${Object.entries(d.roles).map(([k, v]) => html`<button class="chip ${g.roles_needed.includes(k) ? "on" : ""}" data-act="role" data-v="${k}">${v}</button>`)}</div></div>
      <div class="field"><span class="lbl">размер пати</span><div class="seg">${[2, 3, 4, 5].map((n) => html`<button class="${g.max_players === n ? "on" : ""}" data-act="n" data-v="${n}">${n}</button>`)}</div></div>
      <div class="field"><span class="lbl">живёт</span><div class="seg">${[1, 2, 4, 8].map((n) => html`<button class="${g.hours === n ? "on" : ""}" data-act="h" data-v="${n}">${n} ч</button>`)}</div></div>
      <div class="field"><button class="toggle" data-act="voice"><span>${icon("mic", 'width="18" height="18" style="vertical-align:-3px"')} Играем с голосом</span><i class="sw ${g.voice ? "on" : ""}"></i></button></div>
      <button class="btn wide" data-act="go">${icon("squad")}создать</button>`);
    };
    draw();
    on(el, {
      m: (b) => { g.mode = b.dataset.v; haptic.sel(); draw(); },
      r: (b) => { g.rank = b.dataset.v === "" ? null : +b.dataset.v; haptic.sel(); draw(); },
      role: (b) => { const v = b.dataset.v; g.roles_needed = g.roles_needed.includes(v) ? g.roles_needed.filter((x) => x !== v) : [...g.roles_needed, v]; haptic.sel(); draw(); },
      n: (b) => { g.max_players = +b.dataset.v; haptic.sel(); draw(); },
      h: (b) => { g.hours = +b.dataset.v; haptic.sel(); draw(); },
      voice: () => { g.voice = !g.voice; haptic.sel(); draw(); },
      go: async () => {
        g.title = el.querySelector("#t").value.trim();
        if (g.title.length < 2) return toast("Придумай название", "err");
        try { const s = await api("/api/squads", { method: "POST", body: g }); haptic.ok(); close(); done(s); } catch (e) { fail(e); }
      },
    });
  });
}

export function openSquad(id, onChange) {
  pushScreen((el, pop) => {
    let s = null, stop = null;

    async function load() {
      try { s = await api(`/api/squads/${id}`); } catch (e) { fail(e); return pop(); }
      if (stop) { stop(); stop = null; }
      if (s.joined) room(); else details();
    }

    function details() {
      el.classList.remove("flex");
      const free = s.max_players - s.count;
      const closed = s.status === "closed" || s.expired;
      mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><span class="kicker">${modeName(s.mode, s.game)}</span></div>
        <div class="pad">
          <h1 class="h1" style="text-transform:none;font-size:28px;margin:10px 0 12px">${s.title}</h1>
          <div class="chips">${rankName(s.rank, s.game) ? html`<span class="chip on">${rankName(s.rank, s.game)}+</span>` : ""}
            ${s.voice ? html`<span class="chip">${icon("mic")}с голосом</span>` : ""}
            <span class="chip">${icon("clock")}${left(s.expires_at)}</span></div>
          ${s.roles_needed.length ? html`<div class="kicker" style="margin:20px 0 8px">ищут</div><div class="chips">${s.roles_needed.map((r) => html`<span class="chip acc">${roleName(r, s.game)}</span>`)}</div>` : ""}
          <div class="kicker" style="margin:22px 0 4px">состав · ${s.count}/${s.max_players}</div>
          <div class="list">${s.members.map((m) => html`<button class="li" style="width:100%;text-align:left" data-act="who" data-id="${m.tg_id}">${avatar(m, 44, { online: true })}
            <div class="grow"><b>${nameEl(m)}</b><div class="small muted">${[rankName(m.rank, m.game), ...m.roles.map((r) => roleName(r, m.game))].filter(Boolean).join(" · ")}</div></div>
            ${m.tg_id === s.creator ? html`<span class="tag acc">лидер</span>` : ""}</button>`)}
            ${Array.from({ length: free }, () => html`<div class="li"><span class="slot-empty" style="width:44px;height:44px">${icon("plus")}</span><span class="muted">свободно</span></div>`)}</div>
          <div class="sp"></div>
          ${closed ? leraSays("Этот отряд уже распущен. Загляни в список — там есть живые.")
            : free > 0 ? html`<button class="btn wide" data-act="join">${icon("squad")}вступить</button>` : html`<button class="btn wide" disabled>мест нет</button>`}
        </div>`);
    }

    function room() {
      el.classList.add("flex");
      stop = chatRoom(el, {
        group: true,
        back: pop,
        key: `s${id}`,
        head: () => html`<button class="row grow" data-act="info" style="text-align:left">
            <div class="grow" style="min-width:0"><b class="ell" style="display:block">${s.title}</b>
            <span class="small muted">${s.count}/${s.max_players} · ${modeName(s.mode, s.game)} · ${left(s.expires_at)}</span></div></button>
          <button class="ibtn" data-act="share">${icon("share")}</button><button class="ibtn" data-act="info">${icon("dots")}</button>`,
        load: (after) => api(`/api/squads/${id}/messages?after=${after}`),
        send: (text) => api(`/api/squads/${id}/messages`, { method: "POST", body: { text } }),
        empty: () => leraSays("Чат отряда. Договоритесь, кто на какой линии, и кидайте друг другу ID в игре."),
        actions: { info: infoSheet, share },
      });
    }

    function share() {
      const link = `https://t.me/${S.dict.bot}?start=s${id}`;
      const text = `Го в отряд «${s.title}» — ${s.count}/${s.max_players}`;
      const url = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`;
      tg?.openTelegramLink ? tg.openTelegramLink(url) : window.open(url);
    }

    function infoSheet() {
      sheet((sh, close) => {
        mount(sh, html`<h2 class="h2">${s.title}</h2><div class="kicker" style="margin:6px 0 10px">${s.count}/${s.max_players} · ${modeName(s.mode, s.game)}</div>
          <div class="list">${s.members.map((m) => html`<button class="li" style="width:100%;text-align:left" data-act="who" data-id="${m.tg_id}">${avatar(m, 40, { online: true })}
            <b class="grow">${nameEl(m)}</b>${m.tg_id === s.creator ? html`<span class="tag acc">лидер</span>` : ""}</button>`)}</div>
          <div class="sp"></div>
          <div class="stack">
            <button class="btn dark wide" data-act="share">${icon("share")}позвать друзей</button>
            ${s.is_owner ? html`<button class="btn hot wide" data-act="close">распустить отряд</button>` : html`<button class="btn ghost wide" data-act="leave">выйти</button>`}
          </div>`);
        on(sh, {
          who: (b) => { close(); openPerson(+b.dataset.id); },
          share: () => { close(); share(); },
          leave: async () => { close(); try { await api(`/api/squads/${id}/leave`, { method: "POST" }); toast("Ты вышел из отряда"); onChange?.(); pop(); } catch (e) { fail(e); } },
          close: async () => {
            close();
            if (!(await confirmSheet("Распустить отряд?", "Чат закроется для всех.", "распустить", true))) return;
            try { await api(`/api/squads/${id}/close`, { method: "POST" }); onChange?.(); pop(); } catch (e) { fail(e); }
          },
        });
      });
    }

    const off = on(el, {
      back: pop,
      who: (b) => openPerson(+b.dataset.id),
      join: async () => {
        try { s = await api(`/api/squads/${id}/join`, { method: "POST" }); haptic.ok(); toast("Ты в отряде!", "ok"); onChange?.(); room(); } catch (e) { fail(e); }
      },
    });
    load();
    return () => { off(); stop?.(); };
  });
}
