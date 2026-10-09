// Квесты, гача, магазин, инвентарь, топ, вики, premium, рефералка, помощь, админка
import { rt, S, tg, api, html, raw, mount, on, icon, avatar, nameEl, refreshMe, pushScreen, sheet, toast, fail, haptic, leraSays, rankName, emit, GI, myGame, gameBadge, confirmSheet, plural } from "../core.js";
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

// ─── вики (см. wiki.js) ───
import { wikiData } from "./wiki.js";
export { openWiki, openGuide, openHero } from "./wiki.js";

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

// ─── турниры (хаб и про-сцена — pro.js) ───
export { openTournaments, openPro } from "./pro.js";

export function openTournament(id, onChange) {
  pushScreen((el, pop) => {
    let t = null, preds = {};
    const load = async () => {
      try {
        t = await api(`/api/tournaments/${id}`);
        preds = t.status === "live" || t.status === "done" ? (await api(`/api/tournaments/${id}/predictions`)).predictions : {};
      } catch (e) { fail(e); return pop(); }
      draw();
    };
    function predLine(m) {
      const p = preds[m.id];
      const a = p?.teams?.[m.team_a]?.stake || 0, b2 = p?.teams?.[m.team_b]?.stake || 0;
      const open = t.status === "live" && !m.winner && m.team_a && m.team_b;
      const mineTeam = t.my_team === m.team_a || t.my_team === m.team_b;
      if (!open && !p) return "";
      return html`<div class="b-pred">${a + b2 ? html`<div class="b-pool"><i style="width:${Math.round((a / (a + b2)) * 100)}%"></i></div>
          <span class="mono">${a} : ${b2}</span>` : html`<span class="muted">пул пуст</span>`}
        ${p?.mine ? html`<span class="tag ${p.mine.payout ? "acc" : ""}">${p.mine.payout != null ? (p.mine.payout ? `+${p.mine.payout}` : "мимо") : `ставка ${p.mine.stake}`}</span>`
          : open && !mineTeam ? html`<button class="tag acc" data-act="predict" data-m="${m.id}">прогноз</button>` : ""}</div>`;
    }
    const teamName = (tid) => t.teams.find((x) => x.id === tid)?.name || "—";
    function bracket() {
      if (!t.matches.length) return "";
      const rounds = [];
      for (let r = 1; r <= t.rounds; r++) rounds.push(t.matches.filter((m) => m.round === r));
      const rname = (r) => r === t.rounds ? "финал" : r === t.rounds - 1 ? "полуфинал" : `раунд ${r}`;
      return html`<div class="kicker pad" style="margin:22px 0 10px">сетка</div><div class="bracket">${rounds.map((ms, i) => html`
        <div class="b-round"><div class="kicker" style="margin-bottom:8px">${rname(i + 1)}</div>${ms.map((m) => html`
          <div class="b-match ${m.winner ? "done" : ""} ${m.disputed && !m.winner ? "disputed" : ""}">
            ${m.score || (m.disputed && !m.winner) ? html`<div class="b-score mono">${m.disputed && !m.winner ? "⚖️ спор" : m.score}</div>` : ""}
            ${[m.team_a, m.team_b].map((tm) => html`<button class="b-team ${m.winner && m.winner === tm ? "win" : ""} ${tm && tm === t.my_team ? "mine" : ""}"
              ${S.me.is_admin && t.status === "live" && !m.winner && m.team_a && m.team_b ? raw(`data-act="win" data-m="${m.id}" data-t="${tm}"`) : ""}>
              <span class="ell">${tm ? teamName(tm) : i === 0 ? "—" : "…"}</span>${m.winner && m.winner === tm ? icon("check", 'width="14" height="14"') : ""}</button>`)}
            ${predLine(m)}
          </div>`)}</div>`)}</div>
        ${t.status === "live" ? html`<p class="pad muted small">🔮 Прогнозы: ставь несо на победителя матча. Проигравшие ставки делятся между угадавшими.</p>` : ""}
        ${S.me.is_admin && t.status === "live" ? html`<p class="pad muted small">Админ: тапни по команде в матче, чтобы отметить победителя.</p>` : ""}`;
    }
    function myMatch() {
      if (t.status !== "live" || !t.my_team) return "";
      const m = t.matches.find((x) => !x.winner && x.team_a && x.team_b && (x.team_a === t.my_team || x.team_b === t.my_team));
      if (!m) {
        const out = t.matches.some((x) => x.winner && x.winner !== t.my_team && (x.team_a === t.my_team || x.team_b === t.my_team));
        return html`<div class="card line" style="margin-top:12px"><div class="kicker">${out ? "ты выбыл" : "ждём соперника"}</div>
          <p class="small muted" style="margin:6px 0 0">${out ? "Можно смотреть сетку и ставить прогнозы на другие матчи." : "Следующий соперник определится, когда закончится параллельный матч. Я напишу."}</p></div>`;
      }
      const me = m.team_a === t.my_team ? "a" : "b", opp = me === "a" ? m.team_b : m.team_a;
      const mine = m[`report_${me}`], theirs = m[`report_${me === "a" ? "b" : "a"}`];
      let state = "";
      if (m.disputed) state = html`<p class="small" style="margin:10px 0 0;color:var(--hot)">⚖️ Результаты не совпали — матч решит админ. Скрины кидай в чат турнира.</p>`;
      else if (mine) state = html`<p class="small muted" style="margin:10px 0 0">Ты отметил победу: <b>${teamName(mine)}</b>. Ждём подтверждения соперника — через 30 минут засчитается само.</p>`;
      else if (theirs) state = html`<p class="small" style="margin:10px 0 0">Соперник заявил: победил <b>${teamName(theirs)}</b>.</p>
        ${t.my_captain ? html`<div class="row" style="margin-top:10px;gap:8px"><button class="btn sm grow" data-act="confirm" data-m="${m.id}" data-t="${theirs}">${icon("check")}подтвердить</button>
          <button class="btn sm hot grow" data-act="report" data-m="${m.id}">оспорить</button></div>` : ""}`;
      return html`<div class="card my-match" style="margin-top:12px">
        <div class="kicker">твой матч · Bo${t.best_of}</div>
        <div class="vs"><b class="ell">${teamName(t.my_team)}</b><span>vs</span><b class="ell">${teamName(opp)}</b></div>
        <div class="lobby ${m.lobby ? "" : "empty"}">${m.lobby ? html`<span class="kicker">лобби</span><code class="grow">${m.lobby}</code><button class="ibtn" data-act="copy" data-v="${m.lobby}">${icon("copy")}</button>`
          : html`<span class="small muted grow">Код лобби пока не задан</span>`}
          ${t.my_captain || S.me.is_admin ? html`<button class="tag" data-act="lobby" data-m="${m.id}">${m.lobby ? "сменить" : "задать"}</button>` : ""}</div>
        ${state}
        ${t.my_captain && !mine && !theirs && !m.disputed ? html`<button class="btn wide" style="margin-top:12px" data-act="report" data-m="${m.id}">${icon("flag")}отправить результат</button>` : ""}
        ${!t.my_captain && !m.disputed && !mine && !theirs ? html`<p class="small muted" style="margin:10px 0 0">Результат отправляет капитан команды.</p>` : ""}
      </div>`;
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
              <span class="tag">Bo${t.best_of}</span>
              ${t.entry_fee ? html`<span class="tag">взнос ${t.entry_fee}</span>` : ""}
              ${t.checkin ? html`<span class="tag">чек-ин</span>` : ""}</div>
            ${t.pool ? html`<div class="pool"><div><span class="kicker" style="color:inherit;opacity:.7">призовой фонд</span><b class="coin">${t.pool}</b></div>
              <div class="places">${t.payouts.map((v, i) => v ? html`<span>${["🥇", "🥈"][i]} ${v}</span>` : "")}</div></div>` : ""}
          </div>
          ${winner ? html`<div class="card" style="margin-top:12px;text-align:center"><div class="kicker">чемпион</div><div class="h2" style="margin-top:6px">🏆 ${winner.name}</div></div>` : ""}
          ${myMatch()}
          ${t.my_team || S.me.is_admin ? html`<button class="btn dark wide" style="margin-top:12px" data-act="chat">${icon("chat")}чат турнира</button>` : ""}
          ${t.about ? html`<p style="white-space:pre-wrap;margin:16px 0 0">${t.about}</p>` : ""}
          ${t.rules ? html`<details class="faq" style="margin-top:12px"><summary>Правила</summary><p style="white-space:pre-wrap">${t.rules}</p></details>` : ""}
          <div class="sp"></div>
          ${t.status === "reg" ? (myTeam
            ? html`<div class="card line"><div class="kicker">ты в ${t.team_size === 1 ? "списке" : "команде"}</div><b style="display:block;margin:6px 0 12px">${myTeam.name}</b>
                ${t.checkin ? (myTeam.checked_in ? html`<div class="tag acc" style="margin-bottom:12px">✓ чек-ин пройден</div>`
                  : t.checkin_open ? html`<button class="btn wide" style="margin-bottom:10px" data-act="checkin">${icon("check")}я на месте — чек-ин</button>`
                  : html`<p class="small muted" style="margin:0 0 12px">⏰ За 30 минут до старта откроется чек-ин. Не отметишься — снимут с турнира${t.entry_fee ? ", взнос вернётся" : ""}.</p>`) : ""}
                ${t.team_size > 1 ? html`<p class="small muted" style="margin:0 0 12px">Позови тиммейтов: им нужно открыть турнир и нажать «вступить» у твоей команды.</p>` : ""}
                <button class="btn ghost wide sm" data-act="leave">выйти из турнира</button></div>`
            : full ? html`<button class="btn wide" disabled>мест нет</button>`
              : html`<button class="btn wide" data-act="reg">${icon("swords")}${t.team_size === 1 ? "участвовать" : "создать команду"}${t.entry_fee ? ` · ${t.entry_fee} несо` : ""}</button>`) : ""}
          ${S.me.is_admin && t.status === "reg" ? html`<div class="row" style="margin-top:10px"><button class="btn dark grow" data-act="start">запустить сетку</button>
            <button class="btn ghost" data-act="cancel">${icon("trash")}</button></div>` : ""}
        </div>
        ${bracket()}
        <div class="kicker pad" style="margin:22px 0 4px">участники · ${t.teams.length}</div>
        <div class="pad"><div class="list">${t.teams.map((tm) => html`<div class="li" style="align-items:flex-start">
          <div class="grow"><b>${tm.name}</b>${t.checkin && t.status === "reg" && tm.checked_in ? html` <span class="tag acc" style="margin-left:6px">✓</span>` : ""}<div class="row wrap" style="gap:6px;margin-top:8px">${tm.members.map((m) => html`<button data-act="who" data-id="${m.tg_id}" class="row" style="gap:6px">${avatar(m, 26)}<span class="small">${m.name}</span></button>`)}</div></div>
          ${t.status === "reg" && t.team_size > 1 && !t.my_team && tm.members.length < t.team_size ? html`<button class="btn sm" data-act="join" data-id="${tm.id}">вступить</button>` : ""}
          ${t.team_size > 1 ? html`<span class="tag">${tm.members.length}/${t.team_size}</span>` : ""}</div>`)}</div></div><div class="sp"></div>`);
    }
    load();
    const offRt = rt.on("tour", (ev) => { if (ev.tid === id) load(); });
    const act = async (path, body, msg) => {
      try { const r = await api(`/api/tournaments/${id}${path}`, { method: "POST", body }); haptic.ok(); if (msg) toast(typeof msg === "function" ? msg(r) : msg, "ok"); load(); return r; } catch (e) { fail(e); }
    };
    const offAct = on(el, {
      checkin: () => act("/checkin", {}, "Чек-ин пройден!"),
      copy: (b) => { navigator.clipboard?.writeText(b.dataset.v).then(() => toast("Скопировано", "ok")); },
      chat: () => openTourChat(id, t.title),
      confirm: async (b) => {
        if (!(await confirmSheet(`Победил ${teamName(+b.dataset.t)}?`, "Матч закроется, сетка пойдёт дальше.", "подтвердить"))) return;
        act(`/matches/${b.dataset.m}/report`, { team: +b.dataset.t }, "Результат засчитан");
      },
      lobby: (b) => sheet((sh, close) => {
        mount(sh, html`<h2 class="h2" style="margin-bottom:6px">код лобби</h2><p class="small muted" style="margin:0 0 14px">Номер комнаты, пароль или ник хоста — что нужно сопернику, чтобы зайти.</p>
          <input class="input" id="lc" maxlength="80" placeholder="Например, 4821 / пароль lera"><button class="btn wide" style="margin-top:14px" data-act="ok">отправить обеим командам</button>`);
        on(sh, { ok: () => { const v = sh.querySelector("#lc").value.trim(); if (!v) return; close(); act(`/matches/${b.dataset.m}/lobby`, { code: v }, "Лобби отправлено"); } });
      }),
      report: (b) => {
        const m = t.matches.find((x) => x.id === +b.dataset.m);
        let team = null;
        const scores = t.best_of === 1 ? [] : t.best_of === 3 ? ["2:0", "2:1"] : ["3:0", "3:1", "3:2"];
        let score = scores[0] || "";
        sheet((sh, close) => {
          const d2 = () => mount(sh, html`<h2 class="h2" style="margin-bottom:6px">кто победил?</h2>
            <p class="small muted" style="margin:0 0 14px">Если соперник отметит то же — матч закроется сразу. Не совпадёт — решит админ.</p>
            <div class="stack">${[m.team_a, m.team_b].map((x) => html`<button class="btn wide ${team === x ? "" : "dark"}" data-act="tm" data-v="${x}">${teamName(x)}</button>`)}</div>
            ${scores.length ? html`<div class="field" style="margin-top:16px"><span class="lbl">счёт по картам</span><div class="seg">${scores.map((v) => html`<button class="${score === v ? "on" : ""}" data-act="sc" data-v="${v}">${v}</button>`)}</div></div>` : ""}
            <div class="field" style="margin-top:12px"><label>ссылка на скрин (необязательно)</label><input class="input" id="pf" maxlength="300" placeholder="https://…"></div>
            <button class="btn wide" data-act="ok" ${team ? "" : "disabled"}>${icon("send")}отправить</button>`);
          d2();
          on(sh, {
            tm: (x) => { team = +x.dataset.v; haptic.sel(); d2(); },
            sc: (x) => { score = x.dataset.v; haptic.sel(); d2(); },
            ok: async () => {
              const proof = sh.querySelector("#pf").value.trim();
              close();
              act(`/matches/${m.id}/report`, { team, score, proof }, (r) => ({ done: "Матч закрыт", waiting: "Ждём подтверждения соперника", disputed: "Не совпало — передала админу" })[r.status]);
            },
          });
        });
      },
    });
    const offMain = on(el, {
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
      predict: (b) => {
        const m = t.matches.find((x) => x.id === +b.dataset.m);
        let team = m.team_a, stake = 50;
        sheet((sh, close) => {
          const draw2 = () => mount(sh, html`<h2 class="h2" style="margin-bottom:6px">прогноз на матч</h2>
            <p class="muted small" style="margin:0 0 14px">Угадаешь — заберёшь долю ставок проигравших. Баланс: <span class="coin">${S.me.balance}</span></p>
            <div class="stack">${[m.team_a, m.team_b].map((x) => html`<button class="btn wide ${team === x ? "" : "dark"}" data-act="tm" data-v="${x}">${teamName(x)}</button>`)}</div>
            <div class="field" style="margin-top:16px"><span class="lbl">ставка</span><div class="seg">${[10, 50, 100, 250, 500].map((v) => html`<button class="${stake === v ? "on" : ""}" data-act="st" data-v="${v}">${v}</button>`)}</div></div>
            <button class="btn wide" data-act="ok">${icon("sparkle")}поставить ${stake} несо</button>`);
          draw2();
          on(sh, {
            tm: (x) => { team = +x.dataset.v; haptic.sel(); draw2(); },
            st: (x) => { stake = +x.dataset.v; haptic.sel(); draw2(); },
            ok: async () => {
              try { await api(`/api/tournaments/${id}/matches/${m.id}/predict`, { method: "POST", body: { team, stake } }); haptic.ok(); toast("Прогноз принят!", "ok"); close(); refreshMe(); load(); }
              catch (e) { fail(e); }
            },
          });
        });
      },
      win: async (b) => {
        const m = t.matches.find((x) => x.id === +b.dataset.m);
        const name = teamName(+b.dataset.t);
        const rep = m.report_a || m.report_b ? `Капитаны: ${m.report_a ? teamName(m.report_a) : "—"} / ${m.report_b ? teamName(m.report_b) : "—"}. ` : "";
        if (!(await confirmSheet(`Победа: ${name}?`, `${rep}${m.proof ? `Пруф: ${m.proof}. ` : ""}Отменить нельзя.`, "да"))) return;
        try { await api(`/api/tournaments/${id}/matches/${b.dataset.m}/winner`, { method: "POST", body: { team: +b.dataset.t, score: m.score || "" } }); haptic.ok(); load(); } catch (e) { fail(e); }
      },
    });
    return () => { offMain(); offRt(); offAct(); };
    async function doReg(team_name) {
      try { await api(`/api/tournaments/${id}/register`, { method: "POST", body: { team_name } }); haptic.ok(); toast("Ты в турнире!", "ok"); load(); onChange?.(); }
      catch (e) { fail(e); }
    }
  });
}

export function openTourChat(id, title) {
  pushScreen((el, pop) => {
    let stop = () => {};
    import("./chats.js").then(({ chatRoom }) => {
      stop = chatRoom(el, {
        head: () => html`<div class="grow"><b class="ell" style="display:block">${title}</b><span class="small muted">чат турнира · участники и орг</span></div>`,
        load: async (after) => ({ messages: (await api(`/api/tournaments/${id}/chat?after=${after}`)).messages }),
        send: (text) => api(`/api/tournaments/${id}/chat`, { method: "POST", body: { text } }),
        empty: () => leraSays("Здесь договариваются о времени, кидают коды лобби и скрины результатов. Орг тоже тут."),
        back: pop, key: `t${id}`, group: true,
      });
    });
    return () => stop();
  }, { flex: true });
}

export function tourCreate(done) {
  const g = GI();
  const st = { team_size: 1, max_teams: 8, best_of: 1, split: "70/30", checkin: true, auto_start: true };
  sheet((el, close) => {
    const dflt = new Date(Date.now() + 2 * 864e5); dflt.setHours(19, 0, 0, 0);
    const iso = new Date(dflt - dflt.getTimezoneOffset() * 6e4).toISOString().slice(0, 16);
    const draw = () => {
      const keep = (id) => el.querySelector(id)?.value;
      const v = { t: keep("#tt") ?? "", a: keep("#ta") ?? "", p: keep("#tp") ?? "500", d: keep("#td") ?? iso, f: keep("#tf") ?? "0", r: keep("#tr") ?? "" };
      mount(el, html`<div class="row" style="margin-bottom:16px"><h2 class="h2 grow">новый турнир</h2>${gameBadge(S.game)}</div>
        <div class="field"><label>название</label><input class="input" id="tt" maxlength="60" value="${v.t}" placeholder="Кубок Леры #1"></div>
        <div class="field"><span class="lbl">формат</span><div class="seg">${[1, 2, 3, 5].map((n) => html`<button class="${st.team_size === n ? "on" : ""}" data-act="ts" data-v="${n}">${n === 1 ? "соло" : `${n}×${n}`}</button>`)}</div></div>
        <div class="field"><span class="lbl">участников (команд)</span><div class="seg">${[4, 8, 16, 32].map((n) => html`<button class="${st.max_teams === n ? "on" : ""}" data-act="mt" data-v="${n}">${n}</button>`)}</div></div>
        <div class="field"><span class="lbl">матчи</span><div class="seg">${[1, 3, 5].map((n) => html`<button class="${st.best_of === n ? "on" : ""}" data-act="bo" data-v="${n}">Bo${n}</button>`)}</div></div>
        <div class="field"><label>старт (мск)</label><input class="input" id="td" type="datetime-local" value="${v.d}"></div>
        <div class="row" style="gap:10px"><div class="field grow"><label>приз от Леры, несо</label><input class="input" id="tp" type="number" inputmode="numeric" value="${v.p}"></div>
          <div class="field grow"><label>взнос, несо</label><input class="input" id="tf" type="number" inputmode="numeric" value="${v.f}"></div></div>
        <div class="field"><span class="lbl">делёж фонда (приз + взносы)</span><div class="seg">${["100", "70/30", "60/40"].map((x) => html`<button class="${st.split === x ? "on" : ""}" data-act="sp" data-v="${x}">${x === "100" ? "всё 1-му" : x}</button>`)}</div></div>
        <div class="stack" style="gap:8px;margin-bottom:14px">
          <button class="toggle-row ${st.checkin ? "on" : ""}" data-act="tg" data-k="checkin"><span class="grow">Чек-ин за 30 мин до старта</span><i class="sw ${st.checkin ? "on" : ""}"></i></button>
          <button class="toggle-row ${st.auto_start ? "on" : ""}" data-act="tg" data-k="auto_start"><span class="grow">Автостарт сетки по времени</span><i class="sw ${st.auto_start ? "on" : ""}"></i></button></div>
        <div class="field"><label>описание</label><textarea class="input" id="ta" maxlength="1000" placeholder="Режим, карта, формат стрима…">${v.a}</textarea></div>
        <div class="field"><label>правила</label><textarea class="input" id="tr" maxlength="2000" placeholder="Опоздание 10 минут — тех. поражение. Скрин результата в чат турнира…">${v.r}</textarea></div>
        <button class="btn wide" data-act="go">${icon("swords")}открыть регистрацию</button>
        <p class="muted small" style="margin:10px 0 0">Анонс автоматически появится в ленте ${g.short}.</p>`);
    };
    draw();
    on(el, {
      ts: (b) => { st.team_size = +b.dataset.v; draw(); },
      mt: (b) => { st.max_teams = +b.dataset.v; draw(); },
      bo: (b) => { st.best_of = +b.dataset.v; draw(); },
      sp: (b) => { st.split = b.dataset.v; draw(); },
      tg: (b) => { st[b.dataset.k] = !st[b.dataset.k]; draw(); },
      go: async () => {
        const body = { game: S.game, title: el.querySelector("#tt").value.trim(), about: el.querySelector("#ta").value.trim(),
          team_size: st.team_size, max_teams: st.max_teams, prize: +el.querySelector("#tp").value || 0, starts_at: el.querySelector("#td").value,
          best_of: st.best_of, entry_fee: +el.querySelector("#tf").value || 0, checkin: st.checkin, auto_start: st.auto_start,
          prize_split: st.split.split("/").map(Number), rules: el.querySelector("#tr").value.trim() };
        if (body.title.length < 3) return toast("Нужно название", "err");
        try { const r = await api("/api/tournaments", { method: "POST", body }); haptic.ok(); close(); done?.(); openTournament(r.id, done); } catch (e) { fail(e); }
      },
    });
  });
}

// ─── Лерадл ───
const ENT1 = { "Герои": ["героя", "Имя героя…"], "Агенты": ["агента", "Имя агента…"], "Бойцы": ["бойца", "Имя бойца…"], "Персонажи": ["персонажа", "Имя персонажа…"] };
export function openLeradle(onDone, game0) {
  screen("лерадл", "// угадай по подсказкам", (b) => {
    let st = null, q = "";
    let game = game0 || ((S.dict.leradle_games || ["hok"]).includes(S.game) ? S.game : "hok");
    const H = { up: "↑", down: "↓", eq: "=" };
    const draw = () => {
      if (!st) return mount(b, html`<div class="spinner"></div>`);
      const used = new Set(st.guesses.map((x) => x.name));
      const [who, ph] = ENT1[st.entity] || ENT1["Герои"];
      const gs = st.games || [];
      const sugg = q ? st.names.filter((n) => n.toLowerCase().includes(q) && !used.has(n)).slice(0, 8) : [];
      mount(b, html`<div class="pad">
        ${gs.length > 1 ? html`<div class="chips scroll" style="margin-bottom:14px">${gs.map((x) => html`<button class="chip ${x === st.game ? "on" : ""}" data-act="g" data-v="${x}" style="${x === st.game ? `--acc:${GI(x).color}` : ""}">${GI(x).short}</button>`)}</div>` : ""}
        ${!st.over ? html`<p class="muted small" style="margin:0 0 12px">Угадай ${who} ${GI(st.game).name} дня. После каждой попытки — подсказки: тип, роль, длина имени и первая буква. ${st.max} попыток. У каждой игры своя загадка.</p>
          <input class="input" id="lq" placeholder="${ph}" autocomplete="off" value="${q}">
          ${sugg.length ? html`<div class="chips" style="margin-top:10px">${sugg.map((n) => html`<button class="chip" data-act="guess" data-v="${n}">${n}</button>`)}</div>` : ""}`
        : html`<div class="card center" style="border:2px solid ${st.solved ? "var(--acc)" : "var(--hot)"}">
            <div class="kicker">${st.solved ? "разгадано" : "не вышло"} · стрик ${st.streak}</div>
            <div class="h2" style="margin:10px 0 4px">${st.answer.name}</div><div class="small muted">${st.answer.cls} · ${st.answer.lane}</div>
            <div class="row" style="margin-top:14px;justify-content:center"><button class="btn sm" data-act="share">${icon("share")}поделиться</button></div></div>`}
        <div class="ldl-head"><span>${who.replace(/а$|я$/, "")}</span><span>тип</span><span>роль</span><span>букв</span><span>буква</span></div>
        <div class="stack" style="margin-top:6px">${[...st.guesses].reverse().map((x) => html`<div class="ldl-row ${x.win ? "win" : ""}">
          <b class="ell">${x.name}</b><span class="${x.cls_ok ? "ok" : "no"}">${x.cls}</span><span class="${x.lane_ok ? "ok" : "no"}">${x.lane}</span>
          <span class="${x.len_hint === "eq" ? "ok" : "no"}">${x.len} ${H[x.len_hint]}</span><span class="${x.letter_hint === "eq" ? "ok" : "no"}">${x.letter} ${H[x.letter_hint]}</span></div>`)}</div>
        ${!st.over ? html`<div class="center muted small mono" style="margin-top:14px">попыток осталось: ${st.max - st.guesses.length}</div>` : ""}
        <div class="sp"></div>${leraSays(`↑ — у загаданного ${who} длиннее имя или буква дальше по алфавиту. Новая загадка каждый день в полночь по мск.`)}<div class="sp"></div></div>`);
      const inp = b.querySelector("#lq");
      if (inp) {
        inp.addEventListener("input", (e) => { q = e.target.value.trim().toLowerCase(); draw(); const n = b.querySelector("#lq"); n.focus(); n.setSelectionRange(n.value.length, n.value.length); });
        inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { const n = st.names.find((x) => x.toLowerCase() === q); if (n) guess(n); } });
      }
    };
    async function guess(name) {
      try {
        st = await api("/api/leradle/guess", { method: "POST", body: { name, game } });
        q = "";
        if (st.reward) { haptic.ok(); toast(`Угадал! +${st.reward} несо`, "ok"); refreshMe(); }
        else if (st.over) haptic.err(); else haptic.tap();
        draw(); onDone?.();
      } catch (e) { fail(e); }
    }
    const load = () => api(`/api/leradle?game=${game}`).then((r) => { st = r; game = r.game; draw(); }).catch(fail);
    load(); draw();
    return on(b, {
      g: (x) => { game = x.dataset.v; st = null; q = ""; haptic.sel(); draw(); load(); },
      guess: (x) => guess(x.dataset.v),
      share: () => {
        const sq = st.guesses.map((x) => [x.cls_ok, x.lane_ok, x.len_hint === "eq", x.letter_hint === "eq"].map((o) => (o ? "🟩" : "⬛")).join("")).join("\n");
        const text = `Лерадл ${GI(st.game).short} ${st.day} — ${st.solved ? `${st.guesses.length}/${st.max}` : "X/6"}\n${sq}\nhttps://t.me/${S.dict.bot}`;
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
    ["Что такое Лерадл?", "Ежедневная загадка: угадай героя, агента или бойца дня за 6 попыток по подсказкам. Своя загадка для HoK, MLBB, Dota 2, Valorant, Brawl Stars и Genshin. Есть стрик и награды."],
    ["Что такое несо и тикеты?", "Несо — валюта Леры: за ежедневку, квесты, Лерадл, ачивки, гайды и турниры. Тикет — бесплатная крутка в гаче за каждый 7-й день стрика. В выходные ежедневка и квесты ×2."],
    ["Мне пишут гадости", "Открой анкету или чат → «пожаловаться». Человек пропадёт у тебя отовсюду, а жалоба уйдёт админу."],
  ];
  screen("помощь", "// faq", (b) => {
    mount(b, html`<div class="pad stack">${faq.map(([q, a]) => html`<details class="faq"><summary>${q}</summary><p>${a}</p></details>`)}
      <div class="sp"></div>${leraSays("Не нашёл ответ? Напиши в бота — передам админу.")}<div class="sp"></div></div>`);
  });
}

// ─── боевой пропуск ───
const REWARD_IC = { nesso: "coin", ticket: "gift", item: "sparkle" };
function rewardLabel(r) {
  return r.kind === "nesso" ? `${r.value}` : r.kind === "ticket" ? `${r.value} тикет` : r.name;
}

export function openPass(onDone) {
  pushScreen((el, pop) => {
    let p = null;
    const load = async () => { try { p = await api("/api/pass"); } catch (e) { fail(e); return pop(); } draw(); };
    function cell(l, track) {
      const r = l[track], open = l.level <= p.level, locked = track === "premium" && !p.unlocked;
      const can = open && !r.claimed && !locked;
      return html`<button class="bp-cell ${track} ${r.claimed ? "got" : can ? "can" : ""} ${locked ? "locked" : ""} ${r.rarity ? `r-${r.rarity}` : ""}"
        ${can ? raw(`data-act="claim" data-l="${l.level}" data-t="${track}"`) : ""}>
        ${r.kind === "item" ? html`<div class="bp-item">${preview({ id: r.value, kind: r.item_kind, name: r.name })}</div>` : icon(REWARD_IC[r.kind], 'width="20" height="20"')}
        <span class="bp-val">${rewardLabel(r)}${r.kind === "nesso" ? " несо" : ""}</span>
        ${r.claimed ? html`<i class="bp-ok">${icon("check", 'width="12" height="12" stroke-width="3"')}</i>` : locked ? html`<i class="bp-ok lock">🔒</i>` : ""}</button>`;
    }
    function draw() {
      const inLvl = p.level >= p.max ? p.per_level : p.xp % p.per_level;
      const left = Math.max(0, Math.ceil((new Date(p.ends_at) - Date.now()) / 864e5));
      mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><span class="kicker grow">сезон ${p.season_name} · ещё ${left} ${plural(left, "день", "дня", "дней")}</span></div>
        <div class="pad">
          <div class="bp-hero">
            <div class="kicker" style="color:inherit;opacity:.7">боевой пропуск</div>
            <div class="row" style="align-items:flex-end;margin-top:8px"><div class="bp-lvl">${p.level}</div><div class="grow" style="padding-bottom:8px">
              <div class="small" style="opacity:.75">уровень из ${p.max}</div>
              <div class="bp-track"><i style="width:${Math.round((inLvl / p.per_level) * 100)}%"></i></div>
              <div class="small mono" style="opacity:.75;margin-top:6px">${p.level >= p.max ? "максимум!" : `${inLvl} / ${p.per_level} xp до ${p.level + 1}`}</div></div></div>
          </div>
          ${p.ready ? html`<button class="btn wide" style="margin-top:12px" data-act="all">${icon("gift")}забрать всё · ${p.ready}</button>` : ""}
          ${!p.unlocked ? html`<button class="btn wide" style="margin-top:10px;background:var(--gold);color:#1a1200" data-act="buy">${icon("crown")}открыть премиум-линейку · ${p.stars} ⭐</button>
            <p class="muted small" style="margin:8px 0 0">С Lera Premium премиум-линейка открыта бесплатно. Награды за уже пройденные уровни можно забрать сразу.</p>` : ""}
          <p class="muted small" style="margin:12px 0 0">Опыт пропуска — это любой xp в Лере: ежедневка, квесты, Лерадл, мэтчи, отряды, посты, турниры.</p>
        </div>
        <div class="bp-grid-head pad"><span></span><span class="kicker">бесплатно</span><span class="kicker" style="color:var(--gold)">премиум</span></div>
        <div class="pad bp-grid">${p.levels.map((l) => html`<div class="bp-row ${l.level <= p.level ? "open" : ""} ${l.level === p.level + 1 ? "next" : ""}">
          <span class="bp-n">${l.level}</span>${cell(l, "free")}${cell(l, "premium")}</div>`)}</div><div class="sp"></div>`);
    }
    load();
    return on(el, {
      back: () => { pop(); onDone?.(); },
      claim: async (b) => {
        try { const r = await api("/api/pass/claim", { method: "POST", body: { level: +b.dataset.l, track: b.dataset.t } }); haptic.ok(); toast(`+ ${r.got.join(", ")}`, "ok"); refreshMe(); load(); }
        catch (e) { fail(e); }
      },
      all: async () => {
        try { const r = await api("/api/pass/claim", { method: "POST", body: { track: "all" } }); haptic.ok(); toast(r.got.length ? `Получено наград: ${r.got.length}` : "Нечего забирать", "ok"); refreshMe(); load(); }
        catch (e) { fail(e); }
      },
      buy: async () => {
        try {
          const { link } = await api("/api/pay/invoice", { method: "POST", body: { pack: "pass" } });
          if (!tg?.openInvoice) return window.open(link);
          tg.openInvoice(link, (status) => { if (status === "paid") { haptic.ok(); toast("Премиум-линейка открыта!", "ok"); setTimeout(load, 1500); } });
        } catch (e) { fail(e); }
      },
    });
  });
}

// ─── админка ───
const bars = (rows, color = "var(--acc)") => {
  const max = Math.max(1, ...rows.map((r) => r.n));
  return html`<div class="chart">${rows.map((r) => html`<div class="bar-col" title="${r.day}: ${r.n}"><span class="mono">${r.n || ""}</span>
    <i style="height:${Math.max(2, Math.round((r.n / max) * 100))}%;background:${color}"></i><em>${r.day.slice(8)}</em></div>`)}</div>`;
};

export function openAdmin() {
  screen("админка", "// только для своих", (b) => {
    let tab = "overview";
    const TABS = [["overview", "Обзор"], ["users", "Игроки"], ["reports", "Жалобы"], ["content", "Контент"], ["mail", "Рассылка"], ["promo", "Промо"], ["log", "Журнал"]];
    mount(b, html`<div class="pad"><div class="chips scroll" id="at" style="margin-bottom:14px"></div></div><div id="ab"></div>`);
    const body = b.querySelector("#ab");
    const drawTabs = () => mount(b.querySelector("#at"), TABS.map(([k, v]) => html`<button class="chip ${tab === k ? "on" : ""}" data-act="atab" data-t="${k}">${v}</button>`));
    let offInner = null;
    function show() {
      drawTabs();
      if (offInner) offInner();
      body.innerHTML = '<div class="spinner"></div>';
      offInner = ({ overview: aOverview, users: aUsers, reports: aReports, content: aContent, mail: aMail, promo: aPromo, log: aLog })[tab](body) || null;
    }
    show();
    const off = on(b, { atab: (x) => { tab = x.dataset.t; haptic.sel(); show(); } });
    return () => { off(); offInner?.(); };
  });
}

function aOverview(b) {
  const names = { users: "игроков", online: "онлайн", dau: "сегодня", wau: "за 7 дней", new_today: "новых сегодня", premium: "premium",
    stars_30d: "⭐ за 30 дн", nesso_total: "несо у игроков", matches: "мэтчей", clans: "кланов", reports: "жалоб", banned: "в бане" };
  (async () => {
    let o; try { o = await api("/api/admin/overview"); } catch (e) { return fail(e); }
    mount(b, html`<div class="pad">
      <div class="stats" style="grid-template-columns:repeat(3,1fr)">${Object.entries(o.cards).map(([k, v]) => html`<div class="stat"><b>${v}</b><span class="kicker">${names[k] || k}</span></div>`)}</div>
      <div class="kicker" style="margin:22px 0 8px">активные игроки · 14 дней</div>${bars(o.dau)}
      <div class="kicker" style="margin:22px 0 8px">регистрации · 14 дней</div>${bars(o.reg, "var(--sky)")}
      <div class="kicker" style="margin:22px 0 8px">игры</div>
      <div class="list">${o.games.map((g) => html`<div class="li"><span class="grow">${GI(g.game)?.name || g.game}</span><b class="mono">${g.n}</b></div>`)}</div>
      <div class="kicker" style="margin:22px 0 8px">экономика · 7 дней</div>
      <div class="list">${o.economy.map((e) => html`<div class="li"><span class="grow mono small">${e.r}</span><span class="small muted">${e.n}×</span>
        <b class="mono" style="color:${e.s >= 0 ? "var(--acc)" : "var(--hot)"}">${e.s > 0 ? "+" : ""}${e.s}</b></div>`)}</div><div class="sp"></div></div>`);
  })();
}

function aUsers(b) {
  let q = "", filter = "", sort = "recent";
  mount(b, html`<div class="pad"><input class="input" id="uq" placeholder="Ник, @username или ID" autocomplete="off">
    <div class="chips scroll" id="uf" style="margin-top:10px"></div></div><div id="ul"></div>`);
  const draw = () => mount(b.querySelector("#uf"), html`${[["", "Все"], ["reported", "С жалобами"], ["banned", "Бан"], ["premium", "Premium"]].map(([k, v]) => html`<button class="chip ${filter === k ? "on" : ""}" data-act="uf" data-v="${k}">${v}</button>`)}
    <span style="width:8px;flex:none"></span>${[["recent", "Недавние"], ["new", "Новые"], ["xp", "По xp"], ["balance", "По несо"]].map(([k, v]) => html`<button class="chip ${sort === k ? "acc" : ""}" data-act="us" data-v="${k}">${v}</button>`)}`);
  const load = async () => {
    draw();
    let r; try { r = await api(`/api/admin/users?q=${encodeURIComponent(q)}&filter=${filter}&sort=${sort}`); } catch (e) { return fail(e); }
    mount(b.querySelector("#ul"), html`<div class="pad"><div class="list">${r.users.map((u) => html`<button class="li" style="width:100%;text-align:left" data-act="user" data-id="${u.tg_id}">
      ${avatar(u, 40, { online: true })}<div class="grow" style="min-width:0"><b class="ell" style="display:block">${u.name}${u.username ? html` <span class="muted small">@${u.username}</span>` : ""}</b>
      <span class="small muted mono">${u.tg_id} · ${u.balance} несо · ${u.xp} xp</span></div>
      ${u.banned ? html`<span class="tag" style="background:var(--hot);color:#fff">бан</span>` : u.premium ? html`<span class="tag gold">prem</span>` : ""}</button>`)}</div>
      ${!r.users.length ? html`<p class="muted">Никого</p>` : ""}</div>`);
  };
  let t;
  b.querySelector("#uq").addEventListener("input", (e) => { q = e.target.value.trim(); clearTimeout(t); t = setTimeout(load, 300); });
  load();
  return on(b, {
    uf: (x) => { filter = x.dataset.v; load(); },
    us: (x) => { sort = x.dataset.v; load(); },
    user: (x) => adminUser(+x.dataset.id, load),
  });
}

export function adminUser(uid, onChange) {
  pushScreen((el, pop) => {
    let d = null;
    const load = async () => { try { d = await api(`/api/admin/users/${uid}`); } catch (e) { fail(e); return pop(); } draw(); };
    function draw() {
      const u = d.user, c = d.card;
      mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><span class="kicker grow mono">id ${u.tg_id}</span>
          <button class="ibtn" data-act="profile">${icon("eye")}</button></div>
        <div class="pad">
          <div class="row" style="gap:14px">${avatar(c, 64)}<div class="grow" style="min-width:0"><h2 class="h2 ell">${c.name}</h2>
            <div class="small muted">${u.username ? `@${u.username} · ` : ""}с ${u.created_at.slice(0, 10)} · был ${u.last_seen.slice(0, 16)}</div>
            ${u.banned ? html`<div class="tag" style="background:var(--hot);color:#fff;margin-top:6px">бан${u.ban_reason ? `: ${u.ban_reason}` : ""}</div>` : ""}</div></div>
          <div class="stats" style="grid-template-columns:repeat(3,1fr)">
            <div class="stat"><b>${u.balance}</b><span class="kicker">несо</span></div><div class="stat"><b>${u.tickets}</b><span class="kicker">тикетов</span></div>
            <div class="stat"><b>${u.xp}</b><span class="kicker">xp</span></div>
            ${Object.entries({ posts: "постов", matches: "мэтчей", squads: "отрядов", messages: "сообщений", days_active: "дней в Лере" }).map(([k, v]) => html`<div class="stat"><b>${d.stats[k]}</b><span class="kicker">${v}</span></div>`)}
            <div class="stat"><b>${u.premium_until && new Date(u.premium_until.replace(" ", "T") + "Z") > new Date() ? u.premium_until.slice(0, 10) : "—"}</b><span class="kicker">premium до</span></div></div>
          <div class="kicker" style="margin:22px 0 10px">выдать</div>
          <div class="chips">${[["nesso", "несо"], ["ticket", "тикеты"], ["premium", "premium (дни)"], ["xp", "xp"], ["item", "предмет"]].map(([k, v]) => html`<button class="chip" data-act="grant" data-k="${k}">${icon("plus")}${v}</button>`)}
            <button class="chip" data-act="take">${icon("x")}списать несо</button></div>
          <div class="kicker" style="margin:22px 0 10px">модерация</div>
          <div class="chips">
            ${u.banned ? html`<button class="chip acc" data-act="unban">разбанить</button>` : html`<button class="chip" style="color:var(--hot)" data-act="ban">${icon("flag")}забанить</button>`}
            ${[["photos", "удалить фото"], ["about", "стереть «о себе»"], ["nick", "сбросить ник"], ["posts", "удалить посты"]].map(([k, v]) => html`<button class="chip" data-act="wipe" data-w="${k}">${v}</button>`)}</div>
          ${d.reports.length ? html`<div class="kicker" style="margin:22px 0 6px">жалобы на игрока · ${d.reports.length}</div>
            <div class="list">${d.reports.map((r) => html`<div class="li small"><span class="grow">${r.reason}</span><span class="muted mono">${r.created_at.slice(5, 16)}</span>${r.resolved ? html`<span class="tag">✓</span>` : ""}</div>`)}</div>` : ""}
          ${d.payments.length ? html`<div class="kicker" style="margin:22px 0 6px">оплаты</div>
            <div class="list">${d.payments.map((p) => html`<div class="li small"><span class="grow mono">${p.payload.split(":")[0]}</span><b>${p.stars} ⭐</b><span class="muted mono">${p.created_at.slice(0, 10)}</span></div>`)}</div>` : ""}
          <div class="kicker" style="margin:22px 0 6px">последние операции</div>
          <div class="list">${d.transactions.map((t) => html`<div class="li small"><span class="grow mono">${t.reason}</span>
            <b class="mono" style="color:${t.amount >= 0 ? "var(--acc)" : "var(--hot)"}">${t.amount > 0 ? "+" : ""}${t.amount}</b><span class="muted mono">${t.created_at.slice(5, 16)}</span></div>`)}</div>
          <div class="sp"></div></div>`);
    }
    async function grantSheet(kind, negative = false) {
      let items = [];
      if (kind === "item") { try { items = (await api("/api/admin/items")).items; } catch (e) { return fail(e); } }
      sheet((sh, close) => {
        let item = items[0]?.id;
        const draw2 = () => mount(sh, html`<h2 class="h2" style="margin-bottom:14px">${negative ? "списать несо" : `выдать: ${kind}`}</h2>
          ${kind === "item" ? html`<div class="chips" style="max-height:240px;overflow:auto">${items.map((i) => html`<button class="chip ${item === i.id ? "on" : ""}" data-act="it" data-v="${i.id}">${i.name}</button>`)}</div>`
            : html`<div class="field"><label>${kind === "premium" ? "сколько дней" : "сколько"}</label><input class="input" id="gv" type="number" inputmode="numeric" value="${kind === "premium" ? 30 : 100}"></div>`}
          <div class="field" style="margin-top:12px"><label>комментарий (увидит игрок)</label><input class="input" id="gn" maxlength="200" placeholder="${negative ? "Причина" : "За победу в конкурсе"}"></div>
          <button class="toggle" data-act="nt" style="width:100%;margin-bottom:14px"><span>Уведомить в боте</span><i class="sw on" id="ntsw"></i></button>
          <button class="btn wide ${negative ? "hot" : ""}" data-act="ok">${negative ? "списать" : "выдать"}</button>`);
        let ntf = true;
        draw2();
        on(sh, {
          it: (x) => { item = x.dataset.v; draw2(); },
          nt: () => { ntf = !ntf; sh.querySelector("#ntsw").classList.toggle("on", ntf); },
          ok: async () => {
            const value = kind === "item" ? item : String((negative ? -1 : 1) * Math.abs(+sh.querySelector("#gv").value || 0));
            try {
              const r = await api(`/api/admin/users/${uid}/grant`, { method: "POST", body: { kind, value, note: sh.querySelector("#gn").value, notify_user: negative ? false : ntf } });
              haptic.ok(); toast(`Готово: ${r.got}`, "ok"); close(); load(); onChange?.();
            } catch (e) { fail(e); }
          },
        });
      });
    }
    load();
    return on(el, {
      back: pop,
      profile: () => openPerson(d.card),
      grant: (x) => grantSheet(x.dataset.k),
      take: () => grantSheet("nesso", true),
      ban: () => sheet((sh, close) => {
        mount(sh, html`<h2 class="h2" style="margin-bottom:14px">забанить ${d.card.name}?</h2>
          <div class="field"><label>причина (увидит игрок)</label><input class="input" id="br" maxlength="200" placeholder="Спам / токсичность / мошенничество"></div>
          <p class="muted small">Игрок потеряет доступ к Лере, анкета пропадёт из дуэта, жалобы закроются.</p>
          <button class="btn hot wide" data-act="ok">забанить</button>`);
        on(sh, { ok: async () => { try { await api(`/api/admin/users/${uid}/ban`, { method: "POST", body: { reason: sh.querySelector("#br").value } }); close(); toast("Забанен"); load(); onChange?.(); } catch (e) { fail(e); } } });
      }),
      unban: async () => { try { await api(`/api/admin/users/${uid}/unban`, { method: "POST" }); toast("Разбанен", "ok"); load(); onChange?.(); } catch (e) { fail(e); } },
      wipe: async (x) => {
        if (!(await confirmSheet("Точно?", "Это нельзя отменить.", "да", true))) return;
        try { await api(`/api/admin/users/${uid}/wipe`, { method: "POST", body: { what: x.dataset.w } }); toast("Готово"); load(); } catch (e) { fail(e); }
      },
    });
  });
}

function aReports(b) {
  const load = async () => {
    let r; try { r = await api("/api/admin/reports"); } catch (e) { return fail(e); }
    mount(b, r.reports.length ? html`<div class="pad"><div class="list">${r.reports.map((x) => html`<div class="li" style="align-items:flex-start">
      ${avatar(x.user, 40)}<button class="grow" style="text-align:left;min-width:0" data-act="user" data-id="${x.to_id}"><b>${x.user?.name || x.to_id}</b>
        <span class="tag" style="background:var(--hot);color:#fff;margin-left:6px">${x.n}</span>
        <div class="small muted" style="margin-top:4px">${x.reasons}</div></button>
      <div class="stack" style="flex:none"><button class="btn sm hot" data-act="ban" data-id="${x.to_id}">бан</button>
        <button class="btn sm dark" data-act="ok" data-id="${x.to_id}">ок</button></div></div>`)}</div></div>`
      : html`<div class="empty">${leraSays("Жалоб нет. Тишина и порядок.")}</div>`);
  };
  load();
  return on(b, {
    user: (x) => adminUser(+x.dataset.id, load),
    ok: async (x) => { try { await api(`/api/admin/reports/${x.dataset.id}/dismiss`, { method: "POST" }); load(); } catch (e) { fail(e); } },
    ban: async (x) => { try { await api(`/api/admin/users/${x.dataset.id}/ban`, { method: "POST", body: { reason: "жалобы игроков" } }); toast("Забанен"); load(); } catch (e) { fail(e); } },
  });
}

function aMail(b) {
  let game = "", days = 30;
  const load = async () => {
    let r; try { r = await api("/api/admin/broadcasts"); } catch (e) { return fail(e); }
    const text = b.querySelector("#mt")?.value || "";
    mount(b, html`<div class="pad">
      <div class="field"><label>текст рассылки · можно &lt;b&gt;жирный&lt;/b&gt; и &lt;i&gt;курсив&lt;/i&gt;</label><textarea class="input" id="mt" maxlength="3500" style="min-height:140px">${text}</textarea></div>
      <div class="field"><span class="lbl">кому</span><div class="chips">${[["", "Всем"], ...Object.entries(S.dict.games).map(([k, g]) => [k, g.short])].map(([k, v]) => html`<button class="chip ${game === k ? "on" : ""}" data-act="mg" data-v="${k}">${v}</button>`)}</div></div>
      <div class="field"><span class="lbl">заходили за последние</span><div class="seg">${[7, 30, 90, 3650].map((n) => html`<button class="${days === n ? "on" : ""}" data-act="md" data-v="${n}">${n > 365 ? "всё время" : `${n} дн`}</button>`)}</div></div>
      <div class="row"><button class="btn ghost" data-act="test">себе</button><button class="btn grow" data-act="send">${icon("send")}разослать</button></div>
      <p class="muted small">≈20 сообщений в секунду. Кнопка «Открыть Леру» добавится сама.</p>
      ${r.broadcasts.length ? html`<div class="kicker" style="margin:20px 0 6px">история</div><div class="list">${r.broadcasts.map((x) => html`<div class="li small" style="align-items:flex-start">
        <span class="grow" style="min-width:0"><span class="ell" style="display:block">${x.text}</span><span class="muted mono">${x.created_at.slice(5, 16)}</span></span>
        <span class="mono">${x.sent}/${x.total}${x.failed ? html` <span style="color:var(--hot)">−${x.failed}</span>` : ""}</span>
        <span class="tag ${x.status === "done" ? "acc" : ""}">${x.status === "done" ? "готово" : "идёт"}</span></div>`)}</div>` : ""}
      <div class="sp"></div></div>`);
  };
  load();
  const send = async (test) => {
    const text = b.querySelector("#mt").value.trim();
    if (!text) return toast("Пустой текст", "err");
    if (!test && !(await confirmSheet("Разослать?", game ? `Всем игрокам ${S.dict.games[game].short}, кто заходил за ${days} дн.` : `Всем, кто заходил за ${days} дн.`, "разослать"))) return;
    try { const r = await api("/api/admin/broadcast", { method: "POST", body: { text, game: game || null, days, test } }); toast(`Отправляется: ${r.total}`, "ok"); setTimeout(load, 1500); }
    catch (e) { fail(e); }
  };
  return on(b, {
    mg: (x) => { game = x.dataset.v; load(); }, md: (x) => { days = +x.dataset.v; load(); },
    test: () => send(true), send: () => send(false),
  });
}

function aPromo(b) {
  const KINDS = { nesso: "несо", ticket: "тикеты", premium: "premium (дни)", item: "предмет" };
  const load = async () => {
    let r; try { r = await api("/api/admin/promos"); } catch (e) { return fail(e); }
    mount(b, html`<div class="pad"><button class="btn wide" data-act="new">${icon("plus")}новый промокод</button>
      <div class="list" style="margin-top:12px">${r.promos.map((p) => html`<div class="li">
        <div class="grow" style="min-width:0"><b class="mono">${p.code}</b><div class="small muted">${KINDS[p.kind]}: ${p.value} · ${p.uses}/${p.max_uses}${p.expires_at ? ` · до ${p.expires_at.slice(0, 10)}` : ""}</div></div>
        <button class="ibtn" data-act="copy" data-v="${p.code}">${icon("share")}</button><button class="ibtn" data-act="del" data-v="${p.code}">${icon("trash")}</button></div>`)}</div>
      ${!r.promos.length ? html`<p class="muted">Промокодов пока нет. Раздавай их в канале, на стримах и за конкурсы.</p>` : ""}</div>`);
  };
  load();
  return on(b, {
    copy: async (x) => { try { await navigator.clipboard.writeText(x.dataset.v); toast("Скопировано", "ok"); } catch { toast(x.dataset.v); } },
    del: async (x) => { if (!(await confirmSheet(`Удалить ${x.dataset.v}?`, "", "удалить", true))) return; try { await api(`/api/admin/promos/${x.dataset.v}`, { method: "DELETE" }); load(); } catch (e) { fail(e); } },
    new: async () => {
      let items = [];
      try { items = (await api("/api/admin/items")).items; } catch {}
      sheet((sh, close) => {
        const st = { kind: "nesso", item: items[0]?.id };
        const draw = () => {
          const keep = (id, d) => sh.querySelector(id)?.value ?? d;
          const v = { code: keep("#pc", ""), val: keep("#pv", "100"), uses: keep("#pu", "100"), days: keep("#pd", "30") };
          mount(sh, html`<h2 class="h2" style="margin-bottom:14px">промокод</h2>
            <div class="field"><label>код · пусто = случайный</label><input class="input mono" id="pc" maxlength="32" value="${v.code}" style="text-transform:uppercase" placeholder="LERA2026"></div>
            <div class="field"><span class="lbl">что даёт</span><div class="chips">${Object.entries(KINDS).map(([k, t]) => html`<button class="chip ${st.kind === k ? "on" : ""}" data-act="k" data-v="${k}">${t}</button>`)}</div></div>
            ${st.kind === "item" ? html`<div class="chips" style="max-height:180px;overflow:auto;margin-bottom:14px">${items.map((i) => html`<button class="chip ${st.item === i.id ? "on" : ""}" data-act="it" data-v="${i.id}">${i.name}</button>`)}</div>`
              : html`<div class="field"><label>${st.kind === "premium" ? "дней premium" : "сколько"}</label><input class="input" id="pv" type="number" inputmode="numeric" value="${v.val}"></div>`}
            <div class="row" style="gap:10px"><div class="field grow"><label>активаций</label><input class="input" id="pu" type="number" inputmode="numeric" value="${v.uses}"></div>
              <div class="field grow"><label>живёт, дней · 0 = вечно</label><input class="input" id="pd" type="number" inputmode="numeric" value="${v.days}"></div></div>
            <button class="btn wide" data-act="ok">создать</button>`);
        };
        draw();
        on(sh, {
          k: (x) => { st.kind = x.dataset.v; draw(); }, it: (x) => { st.item = x.dataset.v; draw(); },
          ok: async () => {
            const body = { code: sh.querySelector("#pc").value, kind: st.kind, value: st.kind === "item" ? st.item : sh.querySelector("#pv").value,
              max_uses: +sh.querySelector("#pu").value || 1, days: +sh.querySelector("#pd").value || 0 };
            try { const r = await api("/api/admin/promos", { method: "POST", body }); toast(`Создан ${r.code}`, "ok"); close(); load(); } catch (e) { fail(e); }
          },
        });
      });
    },
  });
}

function aLog(b) {
  (async () => {
    let r; try { r = await api("/api/admin/log"); } catch (e) { return fail(e); }
    mount(b, html`<div class="pad"><div class="list">${r.log.map((x) => html`<div class="li small" style="align-items:flex-start">
      <span class="mono muted" style="flex:none">${x.at.slice(5, 16)}</span><span class="grow"><b>${x.admin_name}</b> · ${x.action}${x.target_name ? ` → ${x.target_name}` : ""}
      ${x.details ? html`<div class="muted">${x.details}</div>` : ""}</span></div>`)}</div>${!r.log.length ? html`<p class="muted">Пусто</p>` : ""}</div>`);
  })();
}

function aContent(b) {
  const names = { users: "игроков", online: "онлайн", dau: "за сутки", matches: "мэтчей", squads_open: "отрядов открыто", posts: "постов", premium: "premium" };
  const load = async () => {
    let s, feeds, guides, sched, disp;
    try {
      [disp, feeds, guides, sched] = await Promise.all([api("/api/admin/disputes"), api("/api/admin/feeds"), api("/api/admin/guides"), api("/api/admin/scheduled")]);
    } catch (e) { return fail(e); }
    mount(b, html`<div class="pad">
      <div class="kicker" style="margin:0 0 10px">создать</div>
      <div class="tiles" style="padding:0">
        <button class="tile" data-act="tour">${icon("swords")}<div><b>Турнир</b><div class="sub">для ${GI().short}</div></div></button>
        <button class="tile" data-act="poll">${icon("poll")}<div><b>Опрос дня</b><div class="sub">вместо авто</div></div></button>
        <button class="tile wide" data-act="post">${icon("feed")}<div class="grow"><b>Пост от Леры</b><div class="sub">сразу или по расписанию</div></div></button>
      </div>

      ${disp.disputes.length ? html`<div class="kicker" style="margin:24px 0 6px;color:var(--hot)">⚖️ споры в турнирах · <b>${disp.disputes.length}</b></div>
        <div class="list">${disp.disputes.map((x) => html`<button class="li" style="width:100%;text-align:left" data-act="dispute" data-id="${x.tid}">
          <div class="grow" style="min-width:0"><b class="ell" style="display:block">${x.a_name} vs ${x.b_name}</b><div class="small muted ell">${GI(x.game).short} · ${x.title}${x.proof ? " · есть пруф" : ""}</div></div>${icon("send", 'width="16" height="16"')}</button>`)}</div>` : ""}
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
    dispute: (x) => openTournament(+x.dataset.id, load),
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
}
