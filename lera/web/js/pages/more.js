// Квесты, гача, магазин, инвентарь, топ, вики, premium, рефералка, помощь, админка
import { S, tg, api, html, mount, on, icon, avatar, nameEl, refreshMe, pushScreen, sheet, toast, fail, haptic, leraSays, rankName, emit } from "../core.js";
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
let heroCache = null;
async function heroes() { return heroCache || (heroCache = (await api("/api/wiki/heroes")).heroes); }

export function openWiki() {
  screen("вики", "// герои honor of kings", (b) => {
    let q = "", cls = "", list = [];
    mount(b, html`<div class="pad"><input class="input" id="q" placeholder="Найти героя…" autocomplete="off">
      <div class="chips scroll" id="cls" style="margin-top:12px"></div></div><div class="pad" id="hl"></div>`);
    const draw = () => {
      mount(b.querySelector("#cls"), html`<button class="chip ${!cls ? "on" : ""}" data-act="cls" data-v="">Все</button>
        ${Object.keys(CLS_COLOR).map((c) => html`<button class="chip ${cls === c ? "on" : ""}" data-act="cls" data-v="${c}">${c}</button>`)}`);
      const f = list.filter((h) => (!cls || h.cls === cls) && (!q || h.name.toLowerCase().includes(q)));
      mount(b.querySelector("#hl"), f.length ? html`<div class="list" style="margin-top:8px">${f.map((h) => {
        const mine = S.me.heroes.includes(h.name);
        return html`<div class="hero-row"><div class="hero-glyph" style="background:${CLS_COLOR[h.cls]}">${h.name.replace(/[^A-Za-z]/g, "").slice(0, 2)}</div>
          <div class="grow"><b>${h.name}</b><div class="small muted">${h.cls} · ${h.lane_name}${h.mains ? html` · <span style="color:var(--acc)">мейнят ${h.mains}</span>` : ""}</div></div>
          <button class="chip ${mine ? "on" : ""}" data-act="main" data-v="${h.name}">${mine ? "мейн ✓" : "мейн"}</button></div>`;
      })}</div><div class="sp"></div>` : html`<p class="muted center" style="padding:30px">Никого не нашла</p>`);
    };
    heroes().then((h) => { list = h; draw(); }).catch(fail);
    b.querySelector("#q").addEventListener("input", (e) => { q = e.target.value.trim().toLowerCase(); draw(); });
    return on(b, {
      cls: (btn) => { cls = btn.dataset.v; haptic.sel(); draw(); },
      main: async (btn) => {
        const { profilePayload } = await import("./profile.js");
        const name = btn.dataset.v;
        const cur = S.me.heroes;
        if (!cur.includes(name) && cur.length >= 5) return toast("Максимум 5 мейнов", "err");
        const next = cur.includes(name) ? cur.filter((x) => x !== name) : [...cur, name];
        try { await api("/api/profile", { method: "PUT", body: profilePayload(S.me, { heroes: next }) }); S.me.heroes = next; haptic.sel(); draw(); refreshMe(); }
        catch (e) { fail(e); }
      },
    });
  });
}

export function heroPicker(selected, done) {
  let sel = [...selected], q = "";
  sheet((el, close) => {
    mount(el, html`<div class="row" style="margin-bottom:12px"><h2 class="h2 grow">мейны</h2><button class="btn sm" data-act="ok">готово</button></div>
      <input class="input" id="q" placeholder="Поиск…" autocomplete="off"><div id="hl" style="margin-top:12px"></div>`);
    let list = [];
    const draw = () => mount(el.querySelector("#hl"), html`<div class="chips">${list.filter((h) => !q || h.name.toLowerCase().includes(q)).map((h) =>
      html`<button class="chip ${sel.includes(h.name) ? "on" : ""}" data-act="h" data-v="${h.name}">${h.name}</button>`)}</div>`);
    heroes().then((h) => { list = h; draw(); }).catch(fail);
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
    ["Что такое вайб?", "Число от 12 до 99 — насколько вы подходите друг другу: роли, которые закрывают друг друга, близкий ранг, общее время игры, микрофон, город и мейны. Чем выше — тем вероятнее, что катка зайдёт."],
    ["Как работает дуэт?", "Свайп вправо — лайк, влево — мимо, вверх — суперлайк. Если лайк взаимный — мэтч и личный чат. Тап по нижней части карточки раскрывает подробности, по фото — листает снимки."],
    ["Где увидеть, кто меня лайкнул?", "Дуэт → вкладка «Лайки». Лайкни в ответ — и сразу мэтч."],
    ["Как собрать отряд?", "Отряды → «собрать». Укажи режим, ранг и кого ищешь. Отряд живёт несколько часов, а когда наберётся — я пришлю всем уведомление."],
    ["Что такое несо и тикеты?", "Несо — валюта Леры: за ежедневку, квесты и друзей. Тикет — бесплатная крутка в гаче, даётся за каждый 7-й день подряд."],
    ["Гарант в гаче?", "Каждые 50 круток без легендарки — следующая гарантированно легендарная. В десятке всегда есть минимум редкий предмет. Дубли возвращаются в несо."],
    ["Мне пишут гадости", "Открой анкету или чат → «пожаловаться». Человек пропадёт у тебя отовсюду, а жалоба уйдёт админу."],
  ];
  screen("помощь", "// faq", (b) => {
    mount(b, html`<div class="pad stack">${faq.map(([q, a]) => html`<details class="faq"><summary>${q}</summary><p>${a}</p></details>`)}
      <div class="sp"></div>${leraSays("Не нашёл ответ? Напиши в бота — передам админу.")}<div class="sp"></div></div>`);
  });
}

// ─── админка ───
export function openAdmin() {
  screen("админка", "// только для своих", async (b) => {
    const names = { users: "игроков", online: "онлайн", dau: "за сутки", matches: "мэтчей", squads_open: "отрядов открыто", posts: "постов", premium: "premium" };
    try {
      const s = await api("/api/admin/stats");
      mount(b, html`<div class="pad"><div class="stats" style="grid-template-columns:1fr 1fr">${Object.entries(s).map(([k, v]) => html`<div class="stat"><b>${v}</b><span class="kicker">${names[k] || k}</span></div>`)}</div></div>`);
    } catch (e) { fail(e); }
  });
}
