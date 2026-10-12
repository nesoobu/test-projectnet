// Друзья, подарки, входящие уведомления
import { S, api, html, mount, on, icon, avatar, nameEl, ago, pushScreen, sheet, toast, fail, haptic, leraSays, emit, refreshMe, confirmSheet, GI, plural } from "../core.js";
import { openPerson } from "./person.js";

export function openFriends() {
  pushScreen((el, pop) => {
    let tab = "friends", d = null;
    const load = async () => { try { d = await api("/api/friends"); } catch (e) { return fail(e); } draw(); };
    function draw() {
      const list = d[tab];
      mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><h2 class="h2 grow">друзья</h2>
          <button class="ibtn" data-act="invite">${icon("plus")}</button></div>
        <div class="pad" style="margin-bottom:10px"><div class="seg">
          <button class="${tab === "friends" ? "on" : ""}" data-act="tab" data-t="friends">Друзья · ${d.friends.length}</button>
          <button class="${tab === "incoming" ? "on" : ""}" data-act="tab" data-t="incoming">Заявки ${d.incoming.length ? html`<i class="badge">${d.incoming.length}</i>` : ""}</button>
          <button class="${tab === "outgoing" ? "on" : ""}" data-act="tab" data-t="outgoing">Отправлены</button></div></div>
        ${list.length ? html`<div class="pad"><div class="list">${list.map((p) => html`<div class="li">
          <button data-act="who" data-id="${p.tg_id}">${avatar(p, 46, { online: true })}</button>
          <div class="grow" style="min-width:0"><b class="ell" style="display:block">${nameEl(p)}</b>
            <span class="small ${p.ready ? "" : "muted"}" style="${p.ready ? "color:var(--acc)" : ""}">${p.ready ? `🔥 ищет пати в ${GI(p.ready.game).short}` : p.online ? "онлайн" : (p.games || []).map((g) => GI(g.game).short).join(" · ") || "в Лере"}</span></div>
          ${tab === "friends" ? html`<button class="ibtn" data-act="chat" data-id="${p.tg_id}">${icon("chat")}</button>
              <button class="ibtn" data-act="gift" data-id="${p.tg_id}">${icon("gift")}</button>`
            : tab === "incoming" ? html`<button class="btn sm" data-act="accept" data-id="${p.tg_id}">принять</button>
              <button class="ibtn" data-act="decline" data-id="${p.tg_id}">${icon("x")}</button>`
            : html`<button class="ibtn" data-act="decline" data-id="${p.tg_id}">${icon("x")}</button>`}</div>`)}</div></div>`
          : html`<div class="empty">${leraSays(tab === "friends" ? "Пока пусто. Добавляй тиммейтов из анкет, отрядов и кланов — кнопка «в друзья» в профиле игрока." : "Здесь пусто.")}</div>`}`);
    }
    load();
    return on(el, {
      back: pop,
      tab: (b) => { tab = b.dataset.t; haptic.sel(); draw(); },
      who: (b) => openPerson(+b.dataset.id),
      accept: async (b) => { try { await api(`/api/friends/${b.dataset.id}`, { method: "POST" }); haptic.ok(); toast("Теперь вы друзья!", "ok"); load(); } catch (e) { fail(e); } },
      decline: async (b) => { try { await api(`/api/friends/${b.dataset.id}`, { method: "DELETE" }); load(); } catch (e) { fail(e); } },
      chat: async (b) => openFriendChat(+b.dataset.id),
      gift: (b) => giftSheet(d.friends.find((p) => p.tg_id === +b.dataset.id)),
      invite: async () => { const { openInvite } = await import("./more.js"); openInvite(); },
    });
  });
}

export async function openFriendChat(uid) {
  try {
    const r = await api(`/api/friends/${uid}/chat`, { method: "POST" });
    const { openMatch } = await import("./chats.js");
    openMatch(r.match_id);
  } catch (e) { fail(e); }
}

// Кнопка дружбы в анкете игрока
export async function friendButton(uid) {
  try { return (await api(`/api/friends/status/${uid}`)).status; } catch { return "none"; }
}

export async function friendAction(p, status) {
  if (status === "friends") {
    if (!(await confirmSheet(`Удалить ${p.name} из друзей?`, "", "удалить", true))) return status;
    await api(`/api/friends/${p.tg_id}`, { method: "DELETE" }); return "none";
  }
  if (status === "outgoing") { await api(`/api/friends/${p.tg_id}`, { method: "DELETE" }); toast("Заявка отозвана"); return "none"; }
  const r = await api(`/api/friends/${p.tg_id}`, { method: "POST" });
  haptic.ok(); toast(r.status === "friends" ? "Теперь вы друзья!" : "Заявка отправлена", "ok");
  return r.status;
}

export function giftSheet(p) {
  let kind = "nesso", amount = 100, items = null, item = null;
  sheet(async (el, close) => {
    const draw = () => mount(el, html`<div class="row" style="margin-bottom:14px">${avatar(p, 44)}<div><div class="kicker">подарок</div><b>${p.name}</b></div></div>
      <div class="seg" style="margin-bottom:14px"><button class="${kind === "nesso" ? "on" : ""}" data-act="k" data-v="nesso">Несо</button>
        <button class="${kind === "item" ? "on" : ""}" data-act="k" data-v="item">Предмет</button></div>
      ${kind === "nesso" ? html`<div class="seg">${[50, 100, 250, 500, 1000].map((v) => html`<button class="${amount === v ? "on" : ""}" data-act="a" data-v="${v}">${v}</button>`)}</div>
          <p class="muted small">У тебя <span class="coin">${S.me.balance}</span></p>`
        : items === null ? html`<div class="spinner"></div>`
        : items.length ? html`<div class="chips" style="max-height:220px;overflow:auto">${items.map((i) => html`<button class="chip ${item === i.id ? "on" : ""}" data-act="it" data-v="${i.id}">${i.name}</button>`)}</div>
          <p class="muted small">Предмет перейдёт к другу и пропадёт у тебя.</p>`
        : html`<p class="muted">Нечего дарить — надетые предметы сначала сними.</p>`}
      <div class="field" style="margin-top:12px"><input class="input" id="gn" maxlength="120" placeholder="Подпись (необязательно)"></div>
      <button class="btn wide" data-act="send" ${kind === "item" && !item ? "disabled" : ""}>${icon("gift")}подарить</button>`);
    draw();
    on(el, {
      k: async (b) => {
        kind = b.dataset.v; draw();
        if (kind === "item" && items === null) {
          try { items = (await api("/api/inventory")).items.filter((i) => !i.equipped && !i.premium); } catch { items = []; }
          draw();
        }
      },
      a: (b) => { amount = +b.dataset.v; haptic.sel(); draw(); },
      it: (b) => { item = b.dataset.v; haptic.sel(); draw(); },
      send: async () => {
        try {
          const r = await api("/api/gift", { method: "POST", body: { to: p.tg_id, kind, value: kind === "nesso" ? String(amount) : item, note: el.querySelector("#gn").value } });
          haptic.ok(); toast(`Подарено: ${r.what}`, "ok"); close(); refreshMe();
        } catch (e) { fail(e); }
      },
    });
  });
}

export function openInbox() {
  pushScreen((el, pop) => {
    (async () => {
      let r; try { r = await api("/api/inbox"); } catch (e) { return fail(e); }
      api("/api/inbox/read", { method: "POST" }).then(() => { S.inbox = 0; emit(); }).catch(() => {});
      mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><h2 class="h2">уведомления</h2></div>
        ${r.items.length ? html`<div class="pad"><div class="list">${r.items.map((n) => html`<button class="li inbox-item ${n.read ? "" : "new"}" style="width:100%;text-align:left" data-act="go" data-l="${n.link || ""}">
          <span class="grow" style="white-space:pre-wrap">${n.text}</span><span class="small muted mono" style="flex:none">${ago(n.created_at)}</span></button>`)}</div></div>`
          : html`<div class="empty">${leraSays("Пока тихо. Здесь будут лайки, мэтчи, приглашения и подарки.")}</div>`}`);
    })();
    return on(el, {
      back: pop,
      go: async (b) => { if (!b.dataset.l) return; const { route } = await import("../app.js"); route(b.dataset.l); },
    });
  });
}
