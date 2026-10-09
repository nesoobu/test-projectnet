// Квесты, гача, магазин, инвентарь, топ, вики, premium, рефералка, помощь, админка
import { S, tg, api, html, raw, mount, on, icon, avatar, nameEl, refreshMe, pushScreen, sheet, toast, fail, haptic, leraSays, rankName, emit, GI, myGame, gameBadge, confirmSheet } from "../core.js";
import { openPerson } from "./person.js";

const RAR = { common: "обычный", rare: "редкий", epic: "эпик", legendary: "легенда" };
const KIND = { frame: "Рамки", color: "Цвет ника", title: "Титулы", banner: "Баннеры" };

function screen(title, kicker, body) {
  return pushScreen((el, pop) => {
    mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><span class="kicker grow" style="text-align:right">${kicker}</span></div>
      <div class="pad" style="margin:4px 0 16px"><h1 class="h1">${title}<i>.</i></h1></div><div id="b"></div>`);
    const offBack = on(el, { back: pop });
    const cleanup = body(el.querySelector("#b"), pop, el);
    return () => { offBack(); typeof cleanup === "function" && cleanup(); };
  });
}

function preview(it) {
  const me = S.me;
  if (it.kind === "frame") return avatar({ ...me, frame: it.id }, 56);
  if (it.kind === "color") return html`<span class="nm ${it.id}">${me.name}</span>`;
  if (it.kind === "title") return html`<span class="tag" style="height:26px;font-size:11px">${it.name}</span>`;
  return html`<div class="pv-banner ${it.id}"></div>`;
}

function itemCard(it, action) {
  return html`<div class="item r-${it.rarity} ${it.equipped ? "eq" : ""}">
    <div class="pv" style="position:relative">${preview(it)}</div><div class="rbar"></div>
    <div><div class="rar">${RAR[it.rarity]}</div><div class="name" style="margin-top:4px">${it.name}</div></div>
    ${action}</div>`;
}

// ─── квесты ───
export function openQuests() {
  screen("квесты", "// обновляются в 00:00 мск", (b) => {
    const load = async () => {
      let q; try { q = (await api("/api/quests")).quests; } catch (e) { return fail(e); }
      mount(b, html`<div class="pad stack">${q.map((x) => {
        const pct = Math.min(100, Math.round((x.progress / x.goal) * 100));
        const ready = x.progress >= x.goal && !x.claimed;
        return html`<div class="quest ${x.claimed ? "done" : ""}">
          <div class="ring" style="--p:${pct}"><span>${x.claimed ? "✓" : `${x.progress}/${x.goal}`}</span></div>
          <div class="grow"><b>${x.title}</b><div class="coin small" style="margin-top:6px">+${x.reward}</div></div>
          ${ready ? html`<button class="btn sm" data-act="claim" data-id="${x.id}">забрать</button>` : ""}</div>`;
      })}<div class="sp"></div>${leraSays("Квесты обновляются каждый день. Выполнишь все — я буду гордиться. Молча.")}</div>`);
    };
    load();
    return on(b, {
      claim: async (btn) => {
        btn.disabled = true;
        try { const r = await api(`/api/quests/${btn.dataset.id}/claim`, { method: "POST" }); haptic.ok(); toast(`+${r.reward} несо`, "ok"); await refreshMe(); load(); }
        catch (e) { fail(e); btn.disabled = false; }
      },
    });
  });
}

// ─── гача ───
export function openGacha() {
  screen("гача", "// капсулы с косметикой", (b) => {
    let info = null, rolling = false;
    const draw = () => {
      const p = Math.round((info.pity / info.pity_max) * 100);
      mount(b, html`<div class="machine ${rolling ? "rolling" : ""}">
          <div class="row"><span class="coin grow">${info.balance}</span><span class="tag">🎟 ${info.tickets}</span></div>
          <div class="orb"></div>
          <div class="pity"><div class="row"><span class="kicker grow">гарант легендарки</span><span class="kicker mono"><b>${info.pity}</b> / ${info.pity_max}</span></div>
            <div class="track"><i style="width:${p}%"></i></div></div>
          <div class="stack">
            ${info.tickets ? html`<button class="btn wide" data-act="roll" data-n="1" data-t="1" ${rolling ? "disabled" : ""}>крутить за тикет</button>` : ""}
            <div class="row">
              <button class="btn ${info.tickets ? "dark" : ""} grow" data-act="roll" data-n="1" ${rolling ? "disabled" : ""}>×1 · <span class="coin">${info.cost}</span></button>
              <button class="btn dark grow" data-act="roll" data-n="10" ${rolling ? "disabled" : ""}>×10 · <span class="coin">${info.cost10}</span></button>
            </div>
          </div>
          <div class="rates">${Object.entries(info.rates).map(([k, v]) => html`<div class="r-${k}"><b class="rar" style="font-size:13px">${v}%</b><span class="kicker">${RAR[k]}</span></div>`)}</div>
        </div>
        <div class="pad" style="margin-top:16px">${leraSays("В десятке всегда минимум редкий предмет. Дубли превращаются обратно в несо — ничего не сгорает.")}</div><div class="sp"></div>`);
    };
    (async () => { try { info = await api("/api/gacha/info"); draw(); } catch (e) { fail(e); } })();
    return on(b, {
      roll: async (btn) => {
        if (rolling) return;
        rolling = true; draw(); haptic.hard();
        try {
          const [r] = await Promise.all([
            api("/api/gacha/roll", { method: "POST", body: { count: +btn.dataset.n, ticket: !!btn.dataset.t } }),
            new Promise((res) => setTimeout(res, 900)),
          ]);
          Object.assign(info, { balance: r.balance, tickets: r.tickets, pity: r.pity });
          reveal(r);
          refreshMe().catch(() => {});
        } catch (e) { fail(e); }
        rolling = false; draw();
      },
    });
  });
}

function reveal(r) {
  const el = document.createElement("div");
  const leg = r.results.some((x) => x.rarity === "legendary");
  el.className = "reveal" + (leg ? " flash" : "");
  mount(el, html`<div class="center"><div class="kicker">${r.results.length > 1 ? "десятка" : "капсула"}</div>
      <h2 class="h1" style="margin-top:8px">${leg ? "легенда!" : "твой дроп"}<i>.</i></h2></div>
    <div class="reveal-grid ${r.results.length === 1 ? "one" : ""}">${r.results.map((x) => html`
      <div class="rv r-${x.rarity}"><div class="fl"><div class="bk">?</div>
        <div class="fr"><div>${preview({ ...x })}</div><b>${x.name}</b><span class="rar">${RAR[x.rarity]}</span>
          ${x.dup ? html`<span class="dup">дубль → несо</span>` : ""}</div></div></div>`)}</div>
    ${r.refund ? html`<div class="center"><span class="coin">+${r.refund} за дубли</span></div>` : ""}
    ${r.lera ? html`<div style="display:flex;justify-content:center">${leraSays(r.lera)}</div>` : ""}
    <button class="btn wide" data-act="ok">забрать</button>`);
  document.body.append(el);
  el.querySelectorAll(".rv").forEach((c, i) => setTimeout(() => {
    c.classList.add("open");
    const rar = r.results[i].rarity;
    rar === "legendary" || rar === "epic" ? haptic.hard() : haptic.tap();
  }, 250 + i * 140));
  if (leg) setTimeout(haptic.ok, 300);
  on(el, { ok: () => el.remove() });
}

// ─── магазин / инвентарь ───
export function openShop() {
  screen("магазин", "// за несо", (b) => {
    let items = [], balance = 0;
    const load = async () => {
      try { const r = await api("/api/shop"); items = r.items; balance = r.balance; } catch (e) { return fail(e); }
      mount(b, html`<div class="pad" style="margin-bottom:14px"><div class="row"><span class="kicker grow">кошелёк</span><span class="coin" style="font-size:16px">${balance}</span></div></div>
        ${Object.entries(KIND).map(([k, t]) => {
          const list = items.filter((i) => i.kind === k);
          return list.length ? html`<div class="pad kicker" style="margin:6px 0 10px">${t}</div><div class="items">${list.map((it) => itemCard(it,
            it.owned ? html`<button class="btn sm dark" data-act="equip" data-id="${it.id}">${it.equipped ? "снять" : "надеть"}</button>`
              : balance < it.price ? html`<button class="btn sm dark" style="opacity:.5" data-act="poor"><span class="coin">${it.price}</span></button>`
              : html`<button class="btn sm" data-act="buy" data-id="${it.id}"><span class="coin">${it.price}</span></button>`))}</div>` : "";
        })}
        <div class="pad">${leraSays("Самое редкое тут не продаётся — только из гачи. Я предупредила.")}</div><div class="sp"></div>`);
    };
    load();
    return on(b, {
      buy: async (btn) => {
        btn.disabled = true;
        try { await api(`/api/shop/buy/${btn.dataset.id}`, { method: "POST" }); haptic.ok(); toast("Куплено!", "ok"); await api(`/api/inventory/equip/${btn.dataset.id}`, { method: "POST" }); await refreshMe(); load(); }
        catch (e) { fail(e); btn.disabled = false; }
      },
      equip: (btn) => equip(btn.dataset.id, load),
      poor: () => toast("Не хватает несо — забери ежедневку и квесты", "err"),
    });
  });
}

async function equip(id, after) {
  try { const r = await api(`/api/inventory/equip/${id}`, { method: "POST" }); haptic.sel(); toast(r.equipped ? "Надето" : "Снято"); await refreshMe(); after(); }
  catch (e) { fail(e); }
}

export function openInventory() {
  screen("инвентарь", "// твоя косметика", (b) => {
    const load = async () => {
      let items; try { items = (await api("/api/inventory")).items; } catch (e) { return fail(e); }
      if (!items.length) return mount(b, html`<div class="empty">${leraSays("Пусто. Загляни в магазин или крутани гачу — у тебя наверняка есть тикет.")}
        <div class="row"><button class="btn ghost" data-act="shop">магазин</button><button class="btn" data-act="gacha">гача</button></div></div>`);
      mount(b, html`${Object.entries(KIND).map(([k, t]) => {
        const list = items.filter((i) => i.kind === k);
        return list.length ? html`<div class="pad kicker" style="margin:6px 0 10px">${t}</div><div class="items">${list.map((it) => itemCard(it,
          html`<button class="btn sm ${it.equipped ? "" : "dark"}" data-act="equip" data-id="${it.id}">${it.equipped ? "надето ✓" : "надеть"}</button>`))}</div>` : "";
      })}`);
    };
    load();
    return on(b, { equip: (btn) => equip(btn.dataset.id, load), shop: openShop, gacha: openGacha });
  });
}

// ─── топ ───
export function openTop() {
  screen("топ", "// лучшие из лучших", (b) => {
    let by = "xp";
    const unit = { xp: "xp", streak: "дн.", likes: "❤" };
    const load = async () => {
      mount(b, html`<div class="pad"><div class="seg">${[["xp", "Опыт"], ["streak", "Стрик"], ["likes", "Лайки · 30д"]].map(([k, t]) =>
        html`<button class="${by === k ? "on" : ""}" data-act="by" data-v="${k}">${t}</button>`)}</div></div><div class="spinner"></div>`);
      let r; try { r = await api(`/api/leaderboard?by=${by}`); } catch (e) { return fail(e); }
      const [a, bb, c] = r.top;
      const pod = (p, n) => p ? html`<button class="pod p${n}" data-act="who" data-id="${p.tg_id}">${avatar(p, n === 1 ? 78 : 60)}<span class="nm ell">${nameEl(p)}</span>
        <div class="base"><b>${n}</b><span class="mono small">${p.score} ${unit[by]}</span></div></button>` : html`<div></div>`;
      b.querySelector(".spinner").outerHTML = r.top.length ? html`
        <div class="podium">${pod(bb, 2)}${pod(a, 1)}${pod(c, 3)}</div>
        <div class="pad"><div class="list">${r.top.slice(3).map((p, i) => html`<button class="li ${p.tg_id === r.me ? "me" : ""}" style="width:100%;text-align:left" data-act="who" data-id="${p.tg_id}">
          <span class="rank-n">${i + 4}</span>${avatar(p, 40)}<b class="grow ell">${nameEl(p)}</b><span class="mono small">${p.score} ${unit[by]}</span></button>`)}</div></div><div class="sp"></div>`.s
        : html`<div class="empty">${leraSays("Тут пока никого. Займи первое место, пока свободно.")}</div>`.s;
    };
    load();
    return on(b, { by: (btn) => { by = btn.dataset.v; haptic.sel(); load(); }, who: (btn) => openPerson(+btn.dataset.id) });
  });
}

// ─── вики ───
const CLS_COLOR = { "Стрелок": "#ffc64a", "Маг": "#b48cff", "Убийца": "#ff6fa5", "Боец": "#ff7a59", "Танк": "#7cc8ff", "Поддержка": "#5ef0c1" };
const wikiCache = {};
async function wikiData(game, fresh = false) {
  if (fresh || !wikiCache[game]) wikiCache[game] = await api(`/api/wiki?game=${game}`);
  return wikiCache[game];
}

export function openWiki() {
  const game = S.game, g = GI(game);
  screen(`вики ${g.short.toLowerCase()}`, `// ${g.name}`, (b) => {
    let tab = g.heroes ? "heroes" : "guides", q = "", cls = "", data = null;
    const draw = () => {
      if (!data) return mount(b, html`<div class="spinner"></div>`);
      const seg = g.heroes ? html`<div class="pad" style="margin-bottom:12px"><div class="seg">
        <button class="${tab === "heroes" ? "on" : ""}" data-act="tab" data-t="heroes">Герои</button>
        <button class="${tab === "guides" ? "on" : ""}" data-act="tab" data-t="guides">Гайды · ${data.guides.length}</button></div></div>` : "";
      if (tab === "guides") {
        return mount(b, html`${seg}<div class="pad"><button class="btn wide" data-act="write">${icon("edit")}написать гайд</button></div>
          ${data.guides.length ? html`<div class="pad"><div class="list" style="margin-top:8px">${data.guides.map((x) => html`
            <button class="li" style="width:100%;text-align:left;align-items:flex-start" data-act="guide" data-id="${x.id}">${icon("book", 'width="20" height="20" style="flex:none;margin-top:2px;color:var(--game)"')}
              <div class="grow" style="min-width:0"><b>${x.title}</b><div class="small muted" style="margin-top:3px">${x.preview}…</div>
              <div class="small muted mono" style="margin-top:6px">${x.author?.name || "?"} · ${x.views} просм.</div></div></button>`)}</div></div>`
            : html`<div class="empty">${leraSays(`Гайдов по ${g.short} ещё нет. Напиши первый — за опубликованный гайд дам 100 несо.`)}</div>`}<div class="sp"></div>`);
      }
      const mains = myGame(game)?.heroes || [];
      const f = data.heroes.filter((h) => (!cls || h.cls === cls) && (!q || h.name.toLowerCase().includes(q)));
      mount(b, html`${seg}<div class="pad"><input class="input" id="q" placeholder="Найти героя…" autocomplete="off" value="${q}">
        <div class="chips scroll" style="margin-top:12px"><button class="chip ${!cls ? "on" : ""}" data-act="cls" data-v="">Все</button>
        ${Object.keys(CLS_COLOR).map((c) => html`<button class="chip ${cls === c ? "on" : ""}" data-act="cls" data-v="${c}">${c}</button>`)}</div></div>
        <div class="pad">${f.length ? html`<div class="list" style="margin-top:8px">${f.map((h) => html`<div class="hero-row">
          <div class="hero-glyph" style="background:${CLS_COLOR[h.cls] || "var(--game)"}">${h.name.replace(/[^A-Za-z]/g, "").slice(0, 2)}</div>
          <div class="grow"><b>${h.name}</b><div class="small muted">${h.cls} · ${h.lane_name}${h.mains ? html` · <span style="color:var(--acc)">мейнят ${h.mains}</span>` : ""}</div></div>
          <button class="chip ${mains.includes(h.name) ? "on" : ""}" data-act="main" data-v="${h.name}">${mains.includes(h.name) ? "мейн ✓" : "мейн"}</button></div>`)}</div><div class="sp"></div>`
        : html`<p class="muted center" style="padding:30px">Никого не нашла</p>`}</div>`);
      const qi = b.querySelector("#q");
      qi.addEventListener("input", (e) => { q = e.target.value.trim().toLowerCase(); const pos = qi.selectionStart; draw(); const n = b.querySelector("#q"); n.focus(); n.setSelectionRange(pos, pos); });
    };
    wikiData(game).then((d) => { data = d; draw(); }).catch(fail);
    draw();
    return on(b, {
      tab: (x) => { tab = x.dataset.t; haptic.sel(); draw(); },
      cls: (x) => { cls = x.dataset.v; haptic.sel(); draw(); },
      guide: (x) => openGuide(+x.dataset.id),
      write: () => guideEditor(game, async () => { data = await wikiData(game, true); draw(); }),
      main: async (x) => {
        const mg = myGame(game);
        if (!mg) return toast(`Сначала добавь ${g.short} в профиль`, "err");
        const name = x.dataset.v;
        if (!mg.heroes.includes(name) && mg.heroes.length >= 5) return toast("Максимум 5 мейнов", "err");
        const heroes = mg.heroes.includes(name) ? mg.heroes.filter((h) => h !== name) : [...mg.heroes, name];
        try { await api(`/api/games/${game}`, { method: "PUT", body: { rank: mg.rank, roles: mg.roles, heroes, uid: mg.uid } }); await refreshMe(); haptic.sel(); draw(); }
        catch (e) { fail(e); }
      },
    });
  });
}

export function openGuide(id) {
  pushScreen((el, pop) => {
    mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><span class="kicker grow">гайд</span></div><div class="spinner"></div>`);
    let g = null;
    (async () => {
      try { g = await api(`/api/wiki/guides/${id}`); } catch (e) { fail(e); return pop(); }
      mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><span class="kicker grow">${GI(g.game).name}</span>
          ${g.author?.tg_id === S.me.tg_id || S.me.is_admin ? html`<button class="ibtn" data-act="del">${icon("trash")}</button>` : ""}</div>
        <div class="pad"><h1 class="h1" style="text-transform:none;font-size:26px;margin:8px 0 14px">${g.title}</h1>
          <button class="row" data-act="who" style="margin-bottom:18px">${avatar(g.author, 32)}<span class="small"><b>${g.author?.name}</b> · ${g.views} просмотров</span></button>
          <div class="guide-body">${g.body}</div><div class="sp"></div></div>`);
    })();
    return on(el, {
      back: pop,
      who: () => g?.author && openPerson(g.author),
      del: async () => {
        if (!(await confirmSheet("Удалить гайд?", "Насовсем.", "удалить", true))) return;
        try { await api(`/api/wiki/guides/${id}`, { method: "DELETE" }); toast("Удалено"); pop(); } catch (e) { fail(e); }
      },
    });
  });
}

function guideEditor(game, done) {
  pushScreen((el, pop) => {
    mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><h2 class="h2">новый гайд</h2></div>
      <div class="pad">${leraSays("Пиши по делу: билд, контрпики, тайминги, фишки. Гайд проверит модератор — за публикацию +100 несо.")}
        <div class="sp"></div>
        <div class="field"><label>заголовок</label><input class="input" id="t" maxlength="80" placeholder="Лес на Lam: тайминги и пути"></div>
        <div class="field"><label>текст</label><textarea class="input" id="b" maxlength="8000" style="min-height:280px" placeholder="Минимум пара абзацев"></textarea></div>
        <button class="btn wide" data-act="send">${icon("send")}отправить на модерацию</button></div>`);
    return on(el, {
      back: pop,
      send: async () => {
        const title = el.querySelector("#t").value.trim(), body = el.querySelector("#b").value.trim();
        if (title.length < 4) return toast("Заголовок слишком короткий", "err");
        if (body.length < 40) return toast("Напиши побольше — хотя бы пару предложений", "err");
        try {
          const r = await api("/api/wiki/guides", { method: "POST", body: { game, title, body } });
          haptic.ok(); toast(r.status === "approved" ? "Опубликовано" : "Отправлено на модерацию", "ok"); pop(); done?.();
        } catch (e) { fail(e); }
      },
    });
  });
}

export function heroPicker(game, selected, done) {
  let sel = [...selected], q = "";
  sheet((el, close) => {
    mount(el, html`<div class="row" style="margin-bottom:12px"><h2 class="h2 grow">мейны</h2><button class="btn sm" data-act="ok">готово</button></div>
      <input class="input" id="q" placeholder="Поиск…" autocomplete="off"><div id="hl" style="margin-top:12px"></div>`);
    let list = [];
    const draw = () => mount(el.querySelector("#hl"), html`<div class="chips">${list.filter((h) => !q || h.name.toLowerCase().includes(q)).map((h) =>
      html`<button class="chip ${sel.includes(h.name) ? "on" : ""}" data-act="h" data-v="${h.name}">${h.name}</button>`)}</div>`);
    wikiData(game).then((d) => { list = d.heroes || []; draw(); }).catch(fail);
    el.querySelector("#q").addEventListener("input", (e) => { q = e.target.value.trim().toLowerCase(); draw(); });
    on(el, {
      h: (b) => {
        const v = b.dataset.v;
        if (sel.includes(v)) sel = sel.filter((x) => x !== v);
        else if (sel.length >= 5) return toast("Максимум 5", "err");
        else sel.push(v);
        haptic.sel(); draw();
      },
      ok: () => { close(); done(sel); },
    });
  });
}

// ─── турниры ───
export function openTournaments() {
  const g = GI();
  screen("турниры", `// ${g.name}`, (b) => {
    const load = async () => {
      let r; try { r = await api(`/api/tournaments?game=${S.game}`); } catch (e) { return fail(e); }
      const { tourCard } = await import("./home.js");
      mount(b, html`${S.me.is_admin ? html`<div class="pad" style="margin-bottom:12px"><button class="btn wide dark" data-act="create">${icon("plus")}создать турнир</button></div>` : ""}
        ${r.tournaments.length ? html`<div class="pad stack">${r.tournaments.map(tourCard)}</div>`
          : html`<div class="empty">${leraSays(`Турниров по ${g.short} пока нет. Как только админ откроет регистрацию — я напишу в ленту.`)}</div>`}<div class="sp"></div>`);
    };
    load();
    return on(b, { tour: (x) => openTournament(+x.dataset.id, load), create: () => tourCreate(load) });
  });
}

export function openTournament(id, onChange) {
  pushScreen((el, pop) => {
    let t = null;
    const load = async () => {
      try { t = await api(`/api/tournaments/${id}`); } catch (e) { fail(e); return pop(); }
      draw();
    };
    const teamName = (tid) => t.teams.find((x) => x.id === tid)?.name || "—";
    function bracket() {
      if (!t.matches.length) return "";
      const rounds = [];
      for (let r = 1; r <= t.rounds; r++) rounds.push(t.matches.filter((m) => m.round === r));
      const rname = (r) => r === t.rounds ? "финал" : r === t.rounds - 1 ? "полуфинал" : `раунд ${r}`;
      return html`<div class="kicker pad" style="margin:22px 0 10px">сетка</div><div class="bracket">${rounds.map((ms, i) => html`
        <div class="b-round"><div class="kicker" style="margin-bottom:8px">${rname(i + 1)}</div>${ms.map((m) => html`
          <div class="b-match ${m.winner ? "done" : ""}">
            ${[m.team_a, m.team_b].map((tm) => html`<button class="b-team ${m.winner && m.winner === tm ? "win" : ""} ${tm && tm === t.my_team ? "mine" : ""}"
              ${S.me.is_admin && t.status === "live" && !m.winner && m.team_a && m.team_b ? raw(`data-act="win" data-m="${m.id}" data-t="${tm}"`) : ""}>
              <span class="ell">${tm ? teamName(tm) : i === 0 ? "—" : "…"}</span>${m.winner && m.winner === tm ? icon("check", 'width="14" height="14"') : ""}</button>`)}
          </div>`)}</div>`)}</div>
        ${S.me.is_admin && t.status === "live" ? html`<p class="pad muted small">Админ: тапни по команде в матче, чтобы отметить победителя.</p>` : ""}`;
    }
    function draw() {
      const g = GI(t.game), d = new Date(t.starts_at.replace(" ", "T") + "Z");
      const full = t.teams.length >= t.max_teams;
      const myTeam = t.teams.find((x) => x.id === t.my_team);
      const winner = t.teams.find((x) => x.id === t.winner);
      mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><span class="kicker grow">${g.name}</span>
          <button class="ibtn" data-act="share">${icon("share")}</button></div>
        <div class="pad">
          <div class="tour-hero" style="--gc:${g.color}">
            <div class="kicker" style="color:inherit;opacity:.7">${{ reg: "регистрация открыта", live: "турнир идёт", done: "завершён", cancelled: "отменён" }[t.status]}</div>
            <h1 class="h1" style="text-transform:none;font-size:28px;margin:8px 0 12px">${t.title}</h1>
            <div class="row wrap" style="gap:6px">
              <span class="tag">${d.toLocaleString("ru", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })}</span>
              <span class="tag">${t.team_size === 1 ? "соло" : `команды ${t.team_size}×${t.team_size}`}</span>
              <span class="tag">${t.teams.length}/${t.max_teams}</span>
              ${t.prize ? html`<span class="tag gold">приз ${t.prize} несо</span>` : ""}</div>
          </div>
          ${winner ? html`<div class="card" style="margin-top:12px;text-align:center"><div class="kicker">чемпион</div><div class="h2" style="margin-top:6px">🏆 ${winner.name}</div></div>` : ""}
          ${t.about ? html`<p style="white-space:pre-wrap;margin:16px 0 0">${t.about}</p>` : ""}
          <div class="sp"></div>
          ${t.status === "reg" ? (myTeam
            ? html`<div class="card line"><div class="kicker">ты в ${t.team_size === 1 ? "списке" : "команде"}</div><b style="display:block;margin:6px 0 12px">${myTeam.name}</b>
                ${t.team_size > 1 ? html`<p class="small muted" style="margin:0 0 12px">Позови тиммейтов: им нужно открыть турнир и нажать «вступить» у твоей команды.</p>` : ""}
                <button class="btn ghost wide sm" data-act="leave">выйти из турнира</button></div>`
            : full ? html`<button class="btn wide" disabled>мест нет</button>`
              : html`<button class="btn wide" data-act="reg">${icon("swords")}${t.team_size === 1 ? "участвовать" : "создать команду"}</button>`) : ""}
          ${S.me.is_admin && t.status === "reg" ? html`<div class="row" style="margin-top:10px"><button class="btn dark grow" data-act="start">запустить сетку</button>
            <button class="btn ghost" data-act="cancel">${icon("trash")}</button></div>` : ""}
        </div>
        ${bracket()}
        <div class="kicker pad" style="margin:22px 0 4px">участники · ${t.teams.length}</div>
        <div class="pad"><div class="list">${t.teams.map((tm) => html`<div class="li" style="align-items:flex-start">
          <div class="grow"><b>${tm.name}</b><div class="row wrap" style="gap:6px;margin-top:8px">${tm.members.map((m) => html`<button data-act="who" data-id="${m.tg_id}" class="row" style="gap:6px">${avatar(m, 26)}<span class="small">${m.name}</span></button>`)}</div></div>
          ${t.status === "reg" && t.team_size > 1 && !t.my_team && tm.members.length < t.team_size ? html`<button class="btn sm" data-act="join" data-id="${tm.id}">вступить</button>` : ""}
          ${t.team_size > 1 ? html`<span class="tag">${tm.members.length}/${t.team_size}</span>` : ""}</div>`)}</div></div><div class="sp"></div>`);
    }
    load();
    return on(el, {
      back: pop,
      who: (b) => openPerson(+b.dataset.id),
      share: () => {
        const link = `https://t.me/${S.dict.bot}?start=t${id}`;
        const url = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(`Турнир «${t?.title}» в Лере — го участвовать`)}`;
        tg?.openTelegramLink ? tg.openTelegramLink(url) : window.open(url);
      },
      reg: () => {
        if (t.team_size === 1) return doReg("");
        sheet((sh, close) => {
          mount(sh, html`<h2 class="h2" style="margin-bottom:14px">название команды</h2><input class="input" id="tn" maxlength="30" placeholder="Например, Ночные волки">
            <button class="btn wide" style="margin-top:14px" data-act="ok">создать</button>`);
          on(sh, { ok: () => { const v = sh.querySelector("#tn").value.trim(); if (!v) return toast("Придумай название", "err"); close(); doReg(v); } });
        });
      },
      join: async (b) => { try { await api(`/api/tournaments/${id}/teams/${b.dataset.id}/join`, { method: "POST" }); haptic.ok(); toast("Ты в команде!", "ok"); load(); onChange?.(); } catch (e) { fail(e); } },
      leave: async () => { if (!(await confirmSheet("Выйти из турнира?", "Место освободится для других.", "выйти", true))) return; try { await api(`/api/tournaments/${id}/leave`, { method: "POST" }); load(); onChange?.(); } catch (e) { fail(e); } },
      start: async () => { if (!(await confirmSheet("Запустить сетку?", "Регистрация закроется, участники получат уведомление.", "запустить"))) return; try { await api(`/api/tournaments/${id}/start`, { method: "POST" }); haptic.ok(); load(); } catch (e) { fail(e); } },
      cancel: async () => { if (!(await confirmSheet("Отменить турнир?", "Он пропадёт из списка.", "отменить", true))) return; try { await api(`/api/tournaments/${id}`, { method: "DELETE" }); onChange?.(); pop(); } catch (e) { fail(e); } },
      win: async (b) => {
        const name = teamName(+b.dataset.t);
        if (!(await confirmSheet(`Победа: ${name}?`, "Отменить нельзя.", "да"))) return;
        try { await api(`/api/tournaments/${id}/matches/${b.dataset.m}/winner`, { method: "POST", body: { team: +b.dataset.t } }); haptic.ok(); load(); } catch (e) { fail(e); }
      },
    });
    async function doReg(team_name) {
      try { await api(`/api/tournaments/${id}/register`, { method: "POST", body: { team_name } }); haptic.ok(); toast("Ты в турнире!", "ok"); load(); onChange?.(); }
      catch (e) { fail(e); }
    }
  });
}

function tourCreate(done) {
  const g = GI();
  const st = { team_size: 1, max_teams: 8 };
  sheet((el, close) => {
    const dflt = new Date(Date.now() + 2 * 864e5); dflt.setHours(19, 0, 0, 0);
    const iso = new Date(dflt - dflt.getTimezoneOffset() * 6e4).toISOString().slice(0, 16);
    const draw = () => {
      const keep = (id) => el.querySelector(id)?.value;
      const v = { t: keep("#tt") ?? "", a: keep("#ta") ?? "", p: keep("#tp") ?? "500", d: keep("#td") ?? iso };
      mount(el, html`<div class="row" style="margin-bottom:16px"><h2 class="h2 grow">новый турнир</h2>${gameBadge(S.game)}</div>
        <div class="field"><label>название</label><input class="input" id="tt" maxlength="60" value="${v.t}" placeholder="Кубок Леры #1"></div>
        <div class="field"><span class="lbl">формат</span><div class="seg">${[1, 2, 3, 5].map((n) => html`<button class="${st.team_size === n ? "on" : ""}" data-act="ts" data-v="${n}">${n === 1 ? "соло" : `${n}×${n}`}</button>`)}</div></div>
        <div class="field"><span class="lbl">участников (команд)</span><div class="seg">${[4, 8, 16, 32].map((n) => html`<button class="${st.max_teams === n ? "on" : ""}" data-act="mt" data-v="${n}">${n}</button>`)}</div></div>
        <div class="row" style="gap:10px"><div class="field grow"><label>старт (мск)</label><input class="input" id="td" type="datetime-local" value="${v.d}"></div>
          <div class="field" style="width:120px"><label>приз, несо</label><input class="input" id="tp" type="number" inputmode="numeric" value="${v.p}"></div></div>
        <div class="field"><label>правила / описание</label><textarea class="input" id="ta" maxlength="1000" placeholder="Режим, карта, как связаться с админом…">${v.a}</textarea></div>
        <button class="btn wide" data-act="go">${icon("swords")}открыть регистрацию</button>
        <p class="muted small" style="margin:10px 0 0">Анонс автоматически появится в ленте ${g.short}.</p>`);
    };
    draw();
    on(el, {
      ts: (b) => { st.team_size = +b.dataset.v; draw(); },
      mt: (b) => { st.max_teams = +b.dataset.v; draw(); },
      go: async () => {
        const body = { game: S.game, title: el.querySelector("#tt").value.trim(), about: el.querySelector("#ta").value.trim(),
          team_size: st.team_size, max_teams: st.max_teams, prize: +el.querySelector("#tp").value || 0, starts_at: el.querySelector("#td").value };
        if (body.title.length < 3) return toast("Нужно название", "err");
        try { const r = await api("/api/tournaments", { method: "POST", body }); haptic.ok(); close(); done?.(); openTournament(r.id, done); } catch (e) { fail(e); }
      },
    });
  });
}

// ─── Лерадл ───
export function openLeradle(onDone) {
  screen("лерадл", "// угадай героя hok дня", (b) => {
    let st = null, q = "";
    const H = { up: "↑", down: "↓", eq: "=" };
    const draw = () => {
      if (!st) return mount(b, html`<div class="spinner"></div>`);
      const used = new Set(st.guesses.map((x) => x.name));
      const sugg = q ? st.names.filter((n) => n.toLowerCase().includes(q) && !used.has(n)).slice(0, 8) : [];
      mount(b, html`<div class="pad">
        ${!st.over ? html`<p class="muted small" style="margin:0 0 12px">Вводи героев Honor of Kings. После каждой попытки — подсказки: класс, линия, длина имени и первая буква. ${st.max} попыток.</p>
          <input class="input" id="lq" placeholder="Имя героя…" autocomplete="off" value="${q}">
          ${sugg.length ? html`<div class="chips" style="margin-top:10px">${sugg.map((n) => html`<button class="chip" data-act="guess" data-v="${n}">${n}</button>`)}</div>` : ""}`
        : html`<div class="card center" style="border:2px solid ${st.solved ? "var(--acc)" : "var(--hot)"}">
            <div class="kicker">${st.solved ? "разгадано" : "не вышло"} · стрик ${st.streak}</div>
            <div class="h2" style="margin:10px 0 4px">${st.answer.name}</div><div class="small muted">${st.answer.cls} · ${st.answer.lane}</div>
            <div class="row" style="margin-top:14px;justify-content:center"><button class="btn sm" data-act="share">${icon("share")}поделиться</button></div></div>`}
        <div class="ldl-head"><span>герой</span><span>класс</span><span>линия</span><span>букв</span><span>буква</span></div>
        <div class="stack" style="margin-top:6px">${[...st.guesses].reverse().map((x) => html`<div class="ldl-row ${x.win ? "win" : ""}">
          <b class="ell">${x.name}</b><span class="${x.cls_ok ? "ok" : "no"}">${x.cls}</span><span class="${x.lane_ok ? "ok" : "no"}">${x.lane}</span>
          <span class="${x.len_hint === "eq" ? "ok" : "no"}">${x.len} ${H[x.len_hint]}</span><span class="${x.letter_hint === "eq" ? "ok" : "no"}">${x.letter} ${H[x.letter_hint]}</span></div>`)}</div>
        ${!st.over ? html`<div class="center muted small mono" style="margin-top:14px">попыток осталось: ${st.max - st.guesses.length}</div>` : ""}
        <div class="sp"></div>${leraSays("↑ — у загаданного героя длиннее имя или буква дальше по алфавиту. Новый герой каждый день в полночь по мск.")}<div class="sp"></div></div>`);
      const inp = b.querySelector("#lq");
      if (inp) {
        inp.addEventListener("input", (e) => { q = e.target.value.trim().toLowerCase(); draw(); const n = b.querySelector("#lq"); n.focus(); n.setSelectionRange(n.value.length, n.value.length); });
        inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { const n = st.names.find((x) => x.toLowerCase() === q); if (n) guess(n); } });
      }
    };
    async function guess(name) {
      try {
        st = await api("/api/leradle/guess", { method: "POST", body: { name } });
        q = "";
        if (st.reward) { haptic.ok(); toast(`Угадал! +${st.reward} несо`, "ok"); refreshMe(); }
        else if (st.over) haptic.err(); else haptic.tap();
        draw(); onDone?.();
      } catch (e) { fail(e); }
    }
    api("/api/leradle").then((r) => { st = r; draw(); }).catch(fail);
    draw();
    return on(b, {
      guess: (x) => guess(x.dataset.v),
      share: () => {
        const sq = st.guesses.map((x) => [x.cls_ok, x.lane_ok, x.len_hint === "eq", x.letter_hint === "eq"].map((o) => (o ? "🟩" : "⬛")).join("")).join("\n");
        const text = `Лерадл ${st.day} — ${st.solved ? `${st.guesses.length}/${st.max}` : "X/6"}\n${sq}\nhttps://t.me/${S.dict.bot}`;
        if (tg?.openTelegramLink) tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(`https://t.me/${S.dict.bot}`)}&text=${encodeURIComponent(text)}`);
        else navigator.clipboard?.writeText(text).then(() => toast("Скопировано", "ok"));
      },
    });
  });
}

// ─── ачивки ───
export function openAchievements() {
  screen("ачивки", "// за достижения дают несо", (b) => {
    (async () => {
      let r; try { r = await api("/api/achievements"); } catch (e) { return fail(e); }
      if (r.new.length) { haptic.ok(); toast(`Новая ачивка: ${r.new.join(", ")}!`, "ok"); refreshMe(); }
      mount(b, html`<div class="pad"><div class="row" style="margin-bottom:14px"><span class="kicker grow">открыто</span><b class="mono">${r.count} / ${r.total}</b></div>
        <div class="stack">${r.achievements.map((a) => {
          const pct = Math.round((a.progress / a.goal) * 100);
          return html`<div class="quest ${a.done ? "" : ""}" style="${a.done ? "box-shadow:inset 0 0 0 1.5px var(--acc)" : ""}">
            <div class="ring" style="--p:${pct}"><span>${a.done ? "✓" : `${pct}%`}</span></div>
            <div class="grow"><b>${a.name}</b><div class="small muted" style="margin-top:3px">${a.desc}${!a.done && a.goal > 1 ? ` · ${a.progress}/${a.goal}` : ""}</div></div>
            <span class="coin small">${a.reward}</span></div>`;
        })}</div><div class="sp"></div></div>`);
    })();
  });
}

// ─── отзывы ───
export function openRate() {
  screen("отзывы", "// кто с тобой играл", (b) => {
    const load = async () => {
      let r; try { r = await api("/api/review/candidates"); } catch (e) { return fail(e); }
      mount(b, r.people.length ? html`<div class="pad"><p class="muted small" style="margin:0 0 8px">Мэтчи за месяц и тиммейты из отрядов за 2 недели. Отзывы анонимные.</p>
        <div class="list">${r.people.map((p) => html`<div class="li">${avatar(p, 44)}<div class="grow"><b>${nameEl(p)}</b>
          <div class="small muted">${p.rep ? `репутация ${p.rep > 0 ? "+" : ""}${p.rep}` : "без отзывов"}</div></div>
          <button class="btn sm" data-act="rate" data-id="${p.tg_id}">оценить</button></div>`)}</div></div>`
        : html`<div class="empty">${leraSays("Пока некого оценивать. Сыграй с кем-нибудь из дуэта или отряда — и возвращайся.")}</div>`);
      b._people = r.people;
    };
    load();
    return on(b, {
      rate: async (x) => {
        const p = b._people.find((y) => y.tg_id === +x.dataset.id);
        const { reviewSheet } = await import("./person.js");
        reviewSheet(p, load);
      },
    });
  });
}

// ─── premium ───
export function openPremium() {
  screen("для своих", "// поддержи Леру", (b) => {
    const perks = [
      ["star", "5 суперлайков в день", "Вместо одного. Твоя анкета будет первой у того, кого ты суперлайкнул."],
      ["undo", "Отмена свайпа", "Смахнул не туда — вернул одним тапом."],
      ["coin", "×2 ежедневка", "Каждый день вдвое больше несо."],
      ["crown", "Рамка «Корона Premium»", "Эксклюзив, который нельзя выбить в гаче."],
      ["sparkle", "Золотая плашка", "В анкете, ленте и топах — все видят, кто тут свой."],
    ];
    const m = S.me;
    mount(b, html`<div class="prem-hero"><div class="kicker" style="position:relative">lera</div><div class="big" style="margin-top:8px">premium<span style="color:var(--ink)">.</span></div>
        <p class="muted" style="position:relative;margin:12px 0 0">${m.premium ? `Активен до ${new Date(m.premium_until.replace(" ", "T") + "Z").toLocaleDateString("ru")}. Спасибо, что ты с нами!` : "30 дней всего самого вкусного. Оплата звёздами Telegram."}</p></div>
      <div class="pad"><div class="list">${perks.map(([ic, t, d]) => html`<div class="perk"><div class="ic">${icon(ic)}</div><div><b>${t}</b><div class="small muted" style="margin-top:3px">${d}</div></div></div>`)}</div>
        <div class="sp"></div>
        <button class="btn wide" style="background:var(--gold);color:#1a1200" data-act="buy" data-p="premium30">${icon("star")}${m.premium ? "продлить" : "подключить"} · ${S.dict.premium_stars} ⭐</button>
        <div class="hr"></div>
        <div class="kicker" style="margin-bottom:10px">кошелёк</div>
        <button class="btn dark wide" data-act="buy" data-p="nesso1000"><span class="coin">1000 несо</span> · 49 ⭐</button>
        <div class="sp"></div></div>`);
    return on(b, {
      buy: async (btn) => {
        try {
          const { link } = await api("/api/pay/invoice", { method: "POST", body: { pack: btn.dataset.p } });
          if (!tg?.openInvoice) return window.open(link);
          tg.openInvoice(link, async (status) => {
            if (status === "paid") { haptic.ok(); toast("Оплачено! Спасибо ✨", "ok"); setTimeout(refreshMe, 1500); }
            else if (status === "failed") toast("Оплата не прошла", "err");
          });
        } catch (e) { fail(e); }
      },
    });
  });
}

// ─── рефералка ───
export function openInvite() {
  const link = `https://t.me/${S.dict.bot}?start=ref_${S.me.tg_id}`;
  sheet((el, close) => {
    mount(el, html`<div class="kicker">рефералка</div><h2 class="h2" style="margin:8px 0">позови тиммейта<span class="dot">.</span></h2>
      <p class="muted">Друг получит <b class="coin">100</b> на старте, ты — <b class="coin">150</b>, как только он откроет Леру.</p>
      <div class="input" style="display:flex;align-items:center;font:500 13px/1 var(--mono);overflow:hidden;white-space:nowrap">${link}</div>
      <div class="row" style="margin-top:12px"><button class="btn ghost grow" data-act="copy">копировать</button><button class="btn grow" data-act="share">${icon("share")}отправить</button></div>`);
    on(el, {
      copy: async () => { try { await navigator.clipboard.writeText(link); toast("Скопировано", "ok"); } catch { toast("Не вышло скопировать", "err"); } },
      share: () => {
        const url = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent("Го со мной в Леру — найдём тиммейтов в HoK 🎮")}`;
        tg?.openTelegramLink ? tg.openTelegramLink(url) : window.open(url); close();
      },
    });
  });
}

// ─── помощь ───
export function openHelp() {
  const faq = [
    ["Как переключить игру?", "Тапни по плашке игры в шапке «Главной» или «Тиммейтов». Дуэт, отряды, вики и турниры подстроятся под неё. Добавлять игры — там же или в профиле."],
    ["Что такое «Готов играть»?", "Кнопка на «Главной». Лера напишет в бота игрокам этой игры, что ты ищешь пати. Они жмут «го» — и у вас сразу открывается чат."],
    ["Что такое вайб?", "Число от 12 до 99 — насколько вы подходите: роли закрывают друг друга, близкий ранг, общее время игры, микрофон, город, общие игры и репутация."],
    ["Репутация и отзывы", "После мэтча или отряда можно оценить тиммейта 👍/👎 и выбрать теги. Сумма видна в анкете, хорошие теги — тоже."],
    ["Как попасть в турнир?", "«Главная» → турниры. Соло — жми «участвовать». Командный — создай команду, а друзья вступят в неё со страницы турнира."],
    ["Что такое Лерадл?", "Ежедневная загадка: угадай героя HoK за 6 попыток по подсказкам. Есть стрик и награды. Результатом можно поделиться."],
    ["Что такое несо и тикеты?", "Несо — валюта Леры: за ежедневку, квесты, Лерадл, ачивки, гайды и турниры. Тикет — бесплатная крутка в гаче за каждый 7-й день стрика. В выходные ежедневка и квесты ×2."],
    ["Мне пишут гадости", "Открой анкету или чат → «пожаловаться». Человек пропадёт у тебя отовсюду, а жалоба уйдёт админу."],
  ];
  screen("помощь", "// faq", (b) => {
    mount(b, html`<div class="pad stack">${faq.map(([q, a]) => html`<details class="faq"><summary>${q}</summary><p>${a}</p></details>`)}
      <div class="sp"></div>${leraSays("Не нашёл ответ? Напиши в бота — передам админу.")}<div class="sp"></div></div>`);
  });
}

// ─── админка ───
export function openAdmin() {
  screen("админка", "// только для своих", (b) => {
    const names = { users: "игроков", online: "онлайн", dau: "за сутки", matches: "мэтчей", squads_open: "отрядов открыто", posts: "постов", premium: "premium" };
    const load = async () => {
      let s, feeds, guides, sched;
      try {
        [s, feeds, guides, sched] = await Promise.all([api("/api/admin/stats"), api("/api/admin/feeds"), api("/api/admin/guides"), api("/api/admin/scheduled")]);
      } catch (e) { return fail(e); }
      mount(b, html`<div class="pad">
        <div class="stats" style="grid-template-columns:1fr 1fr 1fr">${Object.entries(s).map(([k, v]) => html`<div class="stat"><b>${v}</b><span class="kicker">${names[k] || k}</span></div>`)}</div>
        <div class="kicker" style="margin:24px 0 10px">создать</div>
        <div class="tiles" style="padding:0">
          <button class="tile" data-act="tour">${icon("swords")}<div><b>Турнир</b><div class="sub">для ${GI().short}</div></div></button>
          <button class="tile" data-act="poll">${icon("poll")}<div><b>Опрос дня</b><div class="sub">вместо авто</div></div></button>
          <button class="tile wide" data-act="post">${icon("feed")}<div class="grow"><b>Пост от Леры</b><div class="sub">сразу или по расписанию</div></div></button>
        </div>

        <div class="kicker" style="margin:24px 0 6px">гайды на модерации · <b>${guides.guides.length}</b></div>
        ${guides.guides.length ? html`<div class="list">${guides.guides.map((x) => html`<div class="li" style="align-items:flex-start">
          <div class="grow" style="min-width:0"><b>${x.title}</b><div class="small muted">${GI(x.game).short} · ${x.author?.name}</div>
            <details style="margin-top:6px"><summary class="small" style="color:var(--acc)">читать</summary><div class="guide-body small" style="margin-top:6px">${x.body}</div></details></div>
          <button class="ibtn" data-act="mod" data-id="${x.id}" data-ok="1" style="color:var(--acc)">${icon("check")}</button>
          <button class="ibtn" data-act="mod" data-id="${x.id}" data-ok="0" style="color:var(--hot)">${icon("x")}</button></div>`)}</div>`
          : html`<p class="muted small">Пусто.</p>`}

        <div class="kicker" style="margin:24px 0 6px">автопостинг (rss / atom)</div>
        <p class="muted small" style="margin:0 0 10px">Новости игр сами появятся в ленте. Для Telegram-каналов используй RSS-мост, например <span class="mono">rsshub.app/telegram/channel/имя</span>.</p>
        ${feeds.feeds.length ? html`<div class="list">${feeds.feeds.map((f) => html`<div class="li"><span class="grow" style="min-width:0">
          <b class="ell" style="display:block">${f.title || f.url}</b><span class="small muted ell" style="display:block">${f.game ? GI(f.game).short : "все игры"} · ${f.last_error ? `ошибка: ${f.last_error}` : "ок"}</span></span>
          <button class="ibtn" data-act="feed-del" data-id="${f.id}">${icon("trash")}</button></div>`)}</div>` : ""}
        <button class="btn dark wide" style="margin-top:10px" data-act="feed-add">${icon("rss")}добавить источник</button>

        ${sched.posts.length ? html`<div class="kicker" style="margin:24px 0 6px">запланировано</div><div class="list">${sched.posts.map((p) => html`<div class="li">
          <span class="grow small ell">${p.text}</span><span class="small mono muted">${new Date(p.publish_at.replace(" ", "T") + "Z").toLocaleString("ru", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</span></div>`)}</div>` : ""}
        <div class="sp"></div></div>`);
    };
    load();
    return on(b, {
      tour: () => tourCreate(load),
      poll: () => sheet((el, close) => {
        mount(el, html`<h2 class="h2" style="margin-bottom:14px">опрос дня</h2>
          <div class="field"><label>вопрос</label><input class="input" id="pq" maxlength="140"></div>
          <div class="field"><label>варианты · по одному на строку</label><textarea class="input" id="po" placeholder="Да\nНет\nНе знаю"></textarea></div>
          <button class="toggle" data-act="pg" style="width:100%;margin-bottom:14px"><span>Только для ${GI().short}</span><i class="sw" id="pgsw"></i></button>
          <button class="btn wide" data-act="ok">опубликовать на сегодня</button>`);
        let onlyGame = false;
        on(el, {
          pg: () => { onlyGame = !onlyGame; el.querySelector("#pgsw").classList.toggle("on", onlyGame); },
          ok: async () => {
            const options = el.querySelector("#po").value.split("\n").map((x) => x.trim()).filter(Boolean);
            try { await api("/api/admin/poll", { method: "POST", body: { question: el.querySelector("#pq").value, options, game: onlyGame ? S.game : null } }); toast("Опрос запущен", "ok"); close(); }
            catch (e) { fail(e); }
          },
        });
      }),
      post: () => sheet((el, close) => {
        mount(el, html`<h2 class="h2" style="margin-bottom:14px">пост от Леры</h2>
          <div class="field"><textarea class="input" id="pt" maxlength="1500" style="min-height:140px" placeholder="Текст новости"></textarea></div>
          <div class="field"><label>ссылка (необязательно)</label><input class="input" id="pl" placeholder="https://"></div>
          <div class="field"><label>когда опубликовать (мск) · пусто = сейчас</label><input class="input" id="pa" type="datetime-local"></div>
          <button class="toggle" data-act="pg" style="width:100%;margin-bottom:14px"><span>Только в ленту ${GI().short}</span><i class="sw" id="pgsw"></i></button>
          <button class="btn wide" data-act="ok">опубликовать</button>`);
        let onlyGame = false;
        on(el, {
          pg: () => { onlyGame = !onlyGame; el.querySelector("#pgsw").classList.toggle("on", onlyGame); },
          ok: async () => {
            const body = { text: el.querySelector("#pt").value, link: el.querySelector("#pl").value.trim() || null,
              publish_at: el.querySelector("#pa").value || null, game: onlyGame ? S.game : null };
            try { await api("/api/admin/post", { method: "POST", body }); toast(body.publish_at ? "Запланировано" : "Опубликовано", "ok"); close(); load(); }
            catch (e) { fail(e); }
          },
        });
      }),
      "feed-add": () => sheet((el, close) => {
        mount(el, html`<h2 class="h2" style="margin-bottom:14px">новый источник</h2>
          <div class="field"><label>rss / atom ссылка</label><input class="input" id="fu" placeholder="https://…"></div>
          <div class="field"><label>название</label><input class="input" id="ft" maxlength="60" placeholder="Новости HoK"></div>
          <div class="field"><span class="lbl">игра</span><div class="chips" id="fg">${[["", "Все игры"], ...Object.entries(S.dict.games).map(([k, g]) => [k, g.short])].map(([k, v]) => html`<button class="chip ${k === "" ? "on" : ""}" data-act="fg" data-v="${k}">${v}</button>`)}</div></div>
          <button class="btn wide" data-act="ok">подключить</button>`);
        let game = "";
        on(el, {
          fg: (x) => { game = x.dataset.v; el.querySelectorAll("#fg .chip").forEach((c) => c.classList.toggle("on", c === x)); },
          ok: async () => {
            try {
              const r = await api("/api/admin/feeds", { method: "POST", body: { url: el.querySelector("#fu").value.trim(), title: el.querySelector("#ft").value, game: game || null } });
              toast(r.feed?.last_error ? `Добавлено, но ошибка: ${r.feed.last_error}` : "Подключено — свежая новость уже в ленте", r.feed?.last_error ? "err" : "ok");
              close(); load();
            } catch (e) { fail(e); }
          },
        });
      }),
      "feed-del": async (x) => { try { await api(`/api/admin/feeds/${x.dataset.id}`, { method: "DELETE" }); load(); } catch (e) { fail(e); } },
      mod: async (x) => { try { await api(`/api/admin/guides/${x.dataset.id}`, { method: "POST", body: { approve: x.dataset.ok === "1" } }); toast(x.dataset.ok === "1" ? "Опубликовано" : "Отклонено"); load(); } catch (e) { fail(e); } },
    });
  });
}
