import { GI, modeName, S, api, html, mount, on, icon, avatar, nameEl, ago, hhmm, pushScreen, leraSays, fail, haptic, emit, sheet, confirmSheet, toast } from "../core.js";
import { openPerson, reportSheet } from "./person.js";

export function render(root) {
  mount(root, html`<div class="top"><div><div class="kicker">// мэтчи и отряды</div><h1 class="h1" style="margin-top:6px">чаты<i>.</i></h1></div></div>
    <div id="list"><div class="spinner"></div></div>`);
  const list = root.querySelector("#list");
  let data = null;

  async function load() {
    try { data = await api("/api/chats"); } catch (e) { return fail(e); }
    const fresh = data.matches.filter((m) => !m.last_text);
    const convo = data.matches.filter((m) => m.last_text);
    if (!data.matches.length && !data.squads.length && !S.me.clan) {
      return mount(list, html`<div class="empty"><h2 class="h2">тишина<span class="dot">.</span></h2>
        ${leraSays("Здесь появятся чаты, когда случится мэтч в дуэте или ты вступишь в отряд.")}
        <button class="btn" data-act="duet">${icon("duet")}к анкетам</button></div>`);
    }
    mount(list, html`
      ${fresh.length ? html`<div class="pad kicker" style="margin-bottom:12px">новые мэтчи · <b>${fresh.length}</b></div>
        <div class="new-matches">${fresh.map((m) => html`<button data-act="match" data-id="${m.id}">${avatar(m.with, 64, { online: true })}<span class="ell" style="max-width:68px">${m.with?.name}</span></button>`)}</div>` : ""}
      ${convo.length ? html`<div class="pad"><div class="kicker" style="margin:4px 0 4px">сообщения</div><div class="list">${convo.map((m) => html`
        <button class="li" style="width:100%;text-align:left" data-act="match" data-id="${m.id}">
          ${avatar(m.with, 52, { online: true })}
          <div class="grow"><div class="row"><b class="grow ell">${nameEl(m.with)}</b><span class="small muted mono">${ago(m.at)}</span></div>
            <div class="row" style="margin-top:4px"><span class="grow ell ${m.unread ? "" : "muted"}" style="${m.unread ? "font-weight:600" : ""}">${m.mine ? "ты: " : ""}${m.last_text}</span>
            ${m.unread ? html`<i class="badge">${m.unread}</i>` : ""}</div></div>
        </button>`)}</div></div>` : ""}
      ${S.me.clan ? html`<div class="pad"><div class="kicker" style="margin:20px 0 4px">клан</div>
        <button class="li" style="width:100%;text-align:left" data-act="clan">
          <div class="emblem" style="--cc:${S.me.clan.color};--s:52px"><span>${S.me.clan.tag}</span></div>
          <div class="grow"><b>Чат клана [${S.me.clan.tag}]</b><div class="muted small" style="margin-top:4px">общий чат бойцов</div></div>${icon("send", 'width="18" height="18"')}</button></div>` : ""}
      ${data.squads.length ? html`<div class="pad"><div class="kicker" style="margin:20px 0 4px">мои отряды</div><div class="list">${data.squads.map((s) => html`
        <button class="li" style="width:100%;text-align:left" data-act="squad" data-id="${s.id}">
          <div class="av" style="--s:52px"><div class="in" style="background:var(--acc);color:var(--acc-ink)">${icon("squad", 'width="24" height="24"')}</div></div>
          <div class="grow"><div class="row"><b class="grow ell">${s.title}</b><span class="tag">${s.members}/${s.max_players}</span></div>
            <div class="muted ell small" style="margin-top:4px">${s.last_text || `${GI(s.game).short} · ${modeName(s.mode, s.game)}`}</div></div>
        </button>`)}</div></div>` : ""}
      <div class="sp"></div>`);
  }

  const off = on(root, {
    match: (b) => openMatch(+b.dataset.id, load),
    clan: async () => { const { openClan } = await import("./clans.js"); openClan(S.me.clan.id, load); },
    squad: async (b) => { const { openSquad } = await import("./squads.js"); openSquad(+b.dataset.id, load); },
    duet: async () => { const { go } = await import("../app.js"); go("duet"); },
  });
  load();
  return off;
}

export function openMatch(id, onClose) {
  pushScreen((el, pop) => {
    let other = null;
    const stop = chatRoom(el, {
      head: () => other ? html`<button data-act="who" class="row grow" style="text-align:left">${avatar(other, 40, { online: true })}
          <div class="grow"><b class="ell" style="display:block">${nameEl(other)}</b><span class="small muted">${other.online ? "онлайн" : "был(а) недавно"}</span></div></button>
        <button class="ibtn" data-act="menu">${icon("dots")}</button>` : "",
      load: async (after) => {
        const r = await api(`/api/chats/${id}?after=${after}`);
        if (r.with) other = r.with;
        return { messages: r.messages, otherRead: r.other_read };
      },
      send: (text) => api(`/api/chats/${id}`, { method: "POST", body: { text } }),
      empty: () => leraSays(`Вы с ${other?.name || "игроком"} лайкнули друг друга. Ледокол ниже — если не знаешь, с чего начать.`),
      ice: true,
      back: pop,
      actions: {
        who: () => other && openPerson(other),
        menu: () => sheet((s, close) => {
          mount(s, html`<div class="stack">
            <button class="btn dark wide" data-act="report">${icon("flag")}пожаловаться</button>
            <button class="btn hot wide" data-act="unmatch">${icon("x")}удалить мэтч</button></div>`);
          on(s, {
            report: () => { close(); reportSheet(other); },
            unmatch: async () => {
              close();
              if (!(await confirmSheet("Удалить мэтч?", "Чат пропадёт у обоих.", "удалить", true))) return;
              try { await api(`/api/chats/${id}/unmatch`, { method: "POST" }); toast("Мэтч удалён"); pop(); } catch (e) { fail(e); }
            },
          });
        }),
      },
    });
    return () => { stop(); onClose?.(); refreshUnread(); };
  }, { flex: true });
}

async function refreshUnread() {
  try { S.unread = await api("/api/ping", { method: "POST" }); emit(); } catch {}
}

// Универсальная комната чата: личка и отряд
export function chatRoom(el, { head, load, send, empty, back, ice = false, group = false, actions = {}, poll = 3000 }) {
  let last = 0, msgs = [], otherRead = 0, alive = true, timer;
  mount(el, html`<div class="chat-head"><button class="ibtn" data-act="back" style="background:none;margin-left:-10px">${icon("back")}</button><div class="row grow" id="hd"></div></div>
    <div class="msgs" id="msgs"><div class="spinner"></div></div>
    ${ice ? html`<div class="ice" id="ice"></div>` : ""}
    <div class="composer"><textarea id="ta" rows="1" placeholder="Сообщение…" maxlength="1000"></textarea>
      <button class="ibtn send" data-act="send">${icon("send")}</button></div>`);
  const box = el.querySelector("#msgs"), ta = el.querySelector("#ta");

  const bubble = (m, prev) => {
    const mine = m.sender === S.me.tg_id;
    const t = html`<time>${hhmm(m.created_at)}</time>`;
    if (!group || mine) return html`<div class="msg ${mine ? "me" : ""}">${m.text}${t}</div>`;
    const cont = prev && prev.sender === m.sender;
    return html`<div class="msg-group">${cont ? html`<div style="width:30px"></div>` : avatar({ tg_id: m.sender, name: m.name, avatar: m.avatar, frame: m.frame }, 30)}
      <div class="msg">${cont ? "" : html`<div class="who ${m.color || ""}">${m.name}</div>`}${m.text}${t}</div></div>`;
  };

  function draw() {
    mount(el.querySelector("#hd"), head());
    if (!msgs.length) {
      mount(box, html`<div class="empty" style="margin:auto">${empty()}</div>`);
    } else {
      const lastMine = [...msgs].reverse().find((m) => m.sender === S.me.tg_id);
      mount(box, html`${msgs.map((m, i) => bubble(m, msgs[i - 1]))}
        ${!group && lastMine && msgs[msgs.length - 1] === lastMine ? html`<div class="read-mark">${otherRead >= lastMine.id ? "прочитано" : "доставлено"}</div>` : ""}`);
    }
    box.scrollTop = box.scrollHeight;
    const iceEl = el.querySelector("#ice");
    if (iceEl) mount(iceEl, msgs.some((m) => m.sender === S.me.tg_id) ? "" :
      S.dict.icebreakers.map((t) => html`<button class="chip" data-act="ice">${t}</button>`));
  }

  async function tick(first = false) {
    try {
      const r = await load(last);
      if (!alive) return;
      const changed = r.messages.length || (r.otherRead ?? 0) !== otherRead || first;
      if (r.messages.length) { msgs = msgs.concat(r.messages).slice(-300); last = msgs[msgs.length - 1].id; }
      otherRead = r.otherRead ?? otherRead;
      if (changed) draw();
    } catch (e) { if (first) { fail(e); mount(box, html`<div class="empty">${leraSays(e.message)}</div>`); } }
    if (alive) timer = setTimeout(tick, document.hidden ? poll * 3 : poll);
  }

  async function doSend(text) {
    text = text.trim();
    if (!text) return;
    ta.value = ""; ta.style.height = "";
    haptic.tap();
    try {
      await send(text);
      clearTimeout(timer); await tick();
    } catch (e) { fail(e); ta.value = text; }
  }

  ta.addEventListener("input", () => { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 120) + "px"; });
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && matchMedia("(pointer:fine)").matches) { e.preventDefault(); doSend(ta.value); } });
  const off = on(el, { send: () => doSend(ta.value), ice: (b) => doSend(b.textContent), back: () => back?.(), ...actions });
  tick(true);
  return () => { alive = false; clearTimeout(timer); off(); };
}
