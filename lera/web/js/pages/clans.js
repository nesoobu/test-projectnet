// Кланы: список/топ, создание, страница клана, управление, чат
import { S, tg, api, html, mount, on, icon, avatar, nameEl, pushScreen, sheet, toast, fail, haptic, leraSays, GI, gameBadge, plural, refreshMe, confirmSheet } from "../core.js";
import { chatRoom } from "./chats.js";
import { openPerson } from "./person.js";

const COLORS = ["#d4ff3f", "#ff6fa5", "#7cc8ff", "#ffc64a", "#b48cff", "#ff7a59", "#5ef0c1", "#efeae0"];
const ROLES = { owner: "лидер", officer: "офицер", member: "боец" };

export const emblem = (c, size = 52) => html`<div class="emblem" style="--cc:${c.color};--s:${size}px"><span>${c.tag}</span></div>`;

export function render(root) {
  let q = "", data = null, mode = "game";
  mount(root, html`<div class="pad"><div class="row"><input class="input grow" id="cq" placeholder="Найти клан или тег…" autocomplete="off">
      </div><div class="chips scroll" id="cm" style="margin-top:10px"></div></div>
    <div id="cl" style="padding-bottom:90px"></div>
    <button class="fab" data-act="create">${icon("plus")}клан</button>`);
  const box = root.querySelector("#cl");

  const drawMode = () => mount(root.querySelector("#cm"), html`
    <button class="chip ${mode === "game" ? "on" : ""}" data-act="mode" data-v="game">${GI().short}</button>
    <button class="chip ${mode === "all" ? "on" : ""}" data-act="mode" data-v="all">Все кланы</button>`);

  async function load() {
    drawMode();
    try { data = await api(`/api/clans?q=${encodeURIComponent(q)}&game=${mode === "game" ? S.game : ""}`); } catch (e) { return fail(e); }
    const mine = data.clans.find((c) => c.id === data.my_clan);
    const rest = data.clans.filter((c) => c.id !== data.my_clan);
    mount(box, html`
      ${data.my_clan ? html`<div class="pad kicker" style="margin:16px 0 10px">мой клан</div>
        <div class="pad">${mine ? clanCard(mine, 0, true) : html`<button class="btn dark wide" data-act="open" data-id="${data.my_clan}">открыть мой клан</button>`}</div>`
        : html`<div class="pad" style="margin-top:16px">${leraSays(`В клане веселее: общий чат, общий опыт и место в топе. Вступай или собери свой за ${data.cost} несо.`)}</div>`}
      <div class="pad kicker" style="margin:22px 0 10px">топ недели · опыт за 7 дней</div>
      ${rest.length ? html`<div class="pad stack">${rest.map((c, i) => clanCard(c, i + 1))}</div>`
        : html`<p class="pad muted">${q ? "Ничего не нашла" : "Кланов пока нет — создай первый!"}</p>`}`);
  }

  function clanCard(c, pos, mine = false) {
    const pending = data.pending.includes(c.id);
    return html`<button class="clan-card ${mine ? "mine" : ""}" data-act="open" data-id="${c.id}" style="--cc:${c.color}">
      ${pos ? html`<span class="rank-n">${pos}</span>` : ""}${emblem(c, 48)}
      <div class="grow" style="min-width:0"><div class="row" style="gap:6px"><b class="ell">${c.name}</b>${c.game ? gameBadge(c.game) : ""}</div>
        <div class="small muted" style="margin-top:3px">ур. ${c.lvl.level} · ${c.members}/${c.lvl.max_members} · ${c.open ? "открытый" : "по заявке"}${pending ? " · заявка отправлена" : ""}</div></div>
      <div class="center"><b class="mono" style="color:var(--cc)">${c.week_xp}</b><div class="kicker" style="font-size:9px">xp/нед</div></div></button>`;
  }

  let t;
  root.querySelector("#cq").addEventListener("input", (e) => { q = e.target.value.trim(); clearTimeout(t); t = setTimeout(load, 300); });
  const off = on(root, {
    mode: (b) => { mode = b.dataset.v; haptic.sel(); load(); },
    open: (b) => openClan(+b.dataset.id, load),
    create: () => {
      if (data?.my_clan) return toast("Ты уже в клане — сначала выйди из него", "err");
      createClan((id) => { load(); openClan(id, load); });
    },
  });
  load();
  return off;
}

function createClan(done) {
  const st = { name: "", tag: "", about: "", color: COLORS[0], open: true, game: S.game };
  sheet((el, close) => {
    const read = () => { ["name", "tag", "about"].forEach((k) => { const i = el.querySelector(`#c_${k}`); if (i) st[k] = i.value; }); };
    const draw = () => {
      read();
      mount(el, html`<div class="row" style="margin-bottom:16px">${emblem({ tag: (st.tag || "TAG").toUpperCase(), color: st.color }, 56)}
          <div class="grow"><h2 class="h2">новый клан</h2><div class="small muted">стоит <span class="coin">${S.dict.clan_cost || 500}</span> несо</div></div></div>
        <div class="row" style="gap:10px"><div class="field grow"><label>название</label><input class="input" id="c_name" maxlength="24" value="${st.name}" placeholder="Ночные волки"></div>
          <div class="field" style="width:100px"><label>тег</label><input class="input" id="c_tag" maxlength="5" value="${st.tag}" placeholder="NW" style="text-transform:uppercase"></div></div>
        <div class="field"><label>о клане</label><textarea class="input" id="c_about" maxlength="300" placeholder="Кого ищем, во что играем, когда собираемся">${st.about}</textarea></div>
        <div class="field"><span class="lbl">цвет</span><div class="swatches">${COLORS.map((c) => html`<button class="swatch ${st.color === c ? "on" : ""}" style="background:${c}" data-act="col" data-v="${c}"></button>`)}</div></div>
        <div class="field"><span class="lbl">основная игра</span><div class="chips">
          <button class="chip ${!st.game ? "on" : ""}" data-act="game" data-v="">Любые</button>
          ${Object.entries(S.dict.games).map(([k, g]) => html`<button class="chip ${st.game === k ? "on" : ""}" data-act="game" data-v="${k}">${g.short}</button>`)}</div></div>
        <div class="field"><button class="toggle" data-act="open"><span>Вступать без заявки</span><i class="sw ${st.open ? "on" : ""}"></i></button></div>
        <button class="btn wide" data-act="go">${icon("squad")}создать клан</button>`);
    };
    draw();
    on(el, {
      col: (b) => { st.color = b.dataset.v; haptic.sel(); draw(); },
      game: (b) => { st.game = b.dataset.v || null; haptic.sel(); draw(); },
      open: () => { st.open = !st.open; haptic.sel(); draw(); },
      go: async () => {
        read();
        try {
          const r = await api("/api/clans", { method: "POST", body: { ...st, tag: st.tag.trim().toUpperCase() } });
          haptic.ok(); close(); await refreshMe(); toast("Клан создан!", "ok"); done(r.id);
        } catch (e) { fail(e); }
      },
    });
  });
}

export function openClan(id, onChange) {
  pushScreen((el, pop) => {
    let c = null, tab = "info", stop = null;
    const load = async () => {
      try { c = await api(`/api/clans/${id}`); } catch (e) { fail(e); return pop(); }
      draw();
    };
    function draw() {
      if (stop) { stop(); stop = null; }
      el.classList.toggle("flex", tab === "chat");
      if (tab === "chat") return room();
      const lv = c.lvl, pct = Math.round(((lv.xp - lv.from) / Math.max(1, lv.to - lv.from)) * 100);
      const staff = c.my_role === "owner" || c.my_role === "officer";
      mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><span class="kicker grow">клан</span>
          <button class="ibtn" data-act="share">${icon("share")}</button>${staff ? html`<button class="ibtn" data-act="edit">${icon("edit")}</button>` : ""}</div>
        <div class="pad">
          <div class="clan-hero" style="--cc:${c.color}">${emblem(c, 76)}
            <div class="grow" style="min-width:0"><h1 class="h1" style="text-transform:none;font-size:26px">${c.name}</h1>
              <div class="row wrap" style="gap:6px;margin-top:8px"><span class="tag">#${c.rank_pos} в топе</span>${c.game ? gameBadge(c.game) : ""}
                <span class="tag">${c.open ? "открытый" : "по заявке"}</span></div></div></div>
          <div class="lvl"><div class="row"><span class="kicker grow">уровень клана <b>${lv.level}</b></span><span class="kicker mono">${lv.xp} / ${lv.to}</span></div>
            <div class="track"><i style="width:${pct}%;background:${c.color}"></i></div></div>
          <div class="stats"><div class="stat"><b>${c.members}/${lv.max_members}</b><span class="kicker">бойцов</span></div>
            <div class="stat"><b>${c.week_xp}</b><span class="kicker">xp за неделю</span></div>
            <div class="stat"><b>${c.xp}</b><span class="kicker">всего xp</span></div></div>
          ${c.about ? html`<p style="white-space:pre-wrap;margin:16px 0 0">${c.about}</p>` : ""}
          <div class="sp"></div>
          ${c.my_role ? html`<div class="row"><button class="btn grow" data-act="chat">${icon("chat")}чат клана</button>
              <button class="btn ghost" data-act="leave">выйти</button></div>`
            : c.requested ? html`<button class="btn wide" disabled>заявка отправлена</button>`
            : html`<button class="btn wide" data-act="join">${icon("squad")}${c.open ? "вступить" : "подать заявку"}</button>`}
          <p class="muted small" style="margin:10px 0 0">Весь опыт, что бойцы получают в Лере, идёт и в копилку клана.</p>
        </div>
        ${c.requests.length ? html`<div class="pad kicker" style="margin:22px 0 4px">заявки · <b>${c.requests.length}</b></div>
          <div class="pad"><div class="list">${c.requests.map((p) => html`<div class="li">${avatar(p, 40)}<button class="grow" style="text-align:left" data-act="who" data-id="${p.tg_id}"><b>${nameEl(p)}</b>
            <div class="small muted">ур. ${p.level}${p.rep ? ` · реп ${p.rep}` : ""}</div></button>
            <button class="ibtn" data-act="req" data-id="${p.tg_id}" data-ok="1" style="color:var(--acc)">${icon("check")}</button>
            <button class="ibtn" data-act="req" data-id="${p.tg_id}" data-ok="0" style="color:var(--hot)">${icon("x")}</button></div>`)}</div></div>` : ""}
        <div class="pad kicker" style="margin:22px 0 4px">состав</div>
        <div class="pad"><div class="list">${c.members_list.map((m, i) => html`<div class="li">
          <span class="rank-n">${i + 1}</span>${avatar(m, 40, { online: true })}
          <button class="grow" style="text-align:left;min-width:0" data-act="who" data-id="${m.tg_id}"><b class="ell" style="display:block">${nameEl(m)}</b>
            <span class="small muted">${ROLES[m.role]} · ${m.clan_xp} xp</span></button>
          ${staff && m.tg_id !== S.me.tg_id && m.role !== "owner" && (c.my_role === "owner" || m.role === "member")
            ? html`<button class="ibtn" data-act="manage" data-id="${m.tg_id}">${icon("dots")}</button>` : ""}</div>`)}</div></div>
        ${S.me.is_admin ? html`<div class="pad" style="margin-top:20px"><button class="btn hot wide sm" data-act="admin-del">удалить клан (админ)</button></div>` : ""}
        <div class="sp"></div>`);
    }
    function room() {
      stop = chatRoom(el, {
        group: true, back: null,
        head: () => html`<div class="row grow">${emblem(c, 36)}<div style="min-width:0"><b class="ell" style="display:block">${c.name}</b>
          <span class="small muted">${c.members} ${plural(c.members, "боец", "бойца", "бойцов")}</span></div></div>`,
        load: (after) => api(`/api/clans/${id}/messages?after=${after}`),
        send: (text) => api(`/api/clans/${id}/messages`, { method: "POST", body: { text } }),
        empty: () => leraSays("Чат клана. Договаривайтесь о катках, турнирах и кто сегодня тащит."),
      });
    }
    const off = on(el, {
      back: () => { if (tab === "chat") { tab = "info"; draw(); } else pop(); },
      chat: () => { tab = "chat"; draw(); },
      who: (b) => openPerson(+b.dataset.id),
      share: () => {
        const link = `https://t.me/${S.dict.bot}?start=c${id}`;
        const url = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(`Го в клан [${c.tag}] ${c.name} в Лере`)}`;
        tg?.openTelegramLink ? tg.openTelegramLink(url) : window.open(url);
      },
      join: async () => {
        try { const r = await api(`/api/clans/${id}/join`, { method: "POST" }); haptic.ok(); toast(r.joined ? "Ты в клане!" : "Заявка отправлена", "ok"); await refreshMe(); load(); onChange?.(); }
        catch (e) { fail(e); }
      },
      leave: async () => {
        const alone = c.members === 1;
        if (!(await confirmSheet("Выйти из клана?", alone ? "Ты последний — клан будет удалён." : c.my_role === "owner" ? "Лидерство перейдёт офицеру или самому активному бойцу." : "Вернуться можно будет снова.", "выйти", true))) return;
        try { await api(`/api/clans/${id}/leave`, { method: "POST" }); await refreshMe(); onChange?.(); alone ? pop() : load(); } catch (e) { fail(e); }
      },
      req: async (b) => { try { await api(`/api/clans/${id}/requests/${b.dataset.id}`, { method: "POST", body: { accept: b.dataset.ok === "1" } }); haptic.sel(); load(); } catch (e) { fail(e); } },
      manage: (b) => {
        const m = c.members_list.find((x) => x.tg_id === +b.dataset.id);
        sheet((sh, close) => {
          mount(sh, html`<div class="row" style="margin-bottom:14px">${avatar(m, 44)}<div><b>${m.name}</b><div class="small muted">${ROLES[m.role]}</div></div></div>
            <div class="stack">${c.my_role === "owner" ? html`
              ${m.role === "member" ? html`<button class="btn dark wide" data-act="role" data-r="officer">сделать офицером</button>` : html`<button class="btn dark wide" data-act="role" data-r="member">понизить до бойца</button>`}
              <button class="btn dark wide" data-act="role" data-r="owner">передать лидерство</button>` : ""}
              <button class="btn hot wide" data-act="kick">исключить</button></div>`);
          on(sh, {
            role: async (x) => { close(); try { await api(`/api/clans/${id}/role/${m.tg_id}`, { method: "POST", body: { role: x.dataset.r } }); load(); } catch (e) { fail(e); } },
            kick: async () => { close(); if (!(await confirmSheet(`Исключить ${m.name}?`, "", "исключить", true))) return; try { await api(`/api/clans/${id}/kick/${m.tg_id}`, { method: "POST" }); load(); } catch (e) { fail(e); } },
          });
        });
      },
      edit: () => sheet((sh, close) => {
        const st = { about: c.about || "", color: c.color, open: !!c.open, game: c.game };
        const draw2 = () => {
          st.about = sh.querySelector("#ca")?.value ?? st.about;
          mount(sh, html`<h2 class="h2" style="margin-bottom:14px">настройки клана</h2>
            <div class="field"><label>о клане</label><textarea class="input" id="ca" maxlength="300">${st.about}</textarea></div>
            <div class="field"><span class="lbl">цвет</span><div class="swatches">${COLORS.map((x) => html`<button class="swatch ${st.color === x ? "on" : ""}" style="background:${x}" data-act="col" data-v="${x}"></button>`)}</div></div>
            <div class="field"><button class="toggle" data-act="op"><span>Вступать без заявки</span><i class="sw ${st.open ? "on" : ""}"></i></button></div>
            <button class="btn wide" data-act="save">сохранить</button>`);
        };
        draw2();
        on(sh, {
          col: (x) => { st.color = x.dataset.v; draw2(); },
          op: () => { st.open = !st.open; draw2(); },
          save: async () => { st.about = sh.querySelector("#ca").value; try { await api(`/api/clans/${id}`, { method: "PUT", body: st }); close(); load(); } catch (e) { fail(e); } },
        });
      }),
      "admin-del": async () => {
        if (!(await confirmSheet("Удалить клан?", "Насовсем, вместе с чатом.", "удалить", true))) return;
        try { await api(`/api/admin/clans/${id}`, { method: "DELETE" }); toast("Клан удалён"); onChange?.(); pop(); } catch (e) { fail(e); }
      },
    });
    load();
    return () => { off(); stop?.(); };
  });
}
