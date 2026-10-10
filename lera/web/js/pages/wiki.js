// Вики: хаб по каждой игре — обзор, герои/агенты/карты, тир-лист игроков, гайды, словарь; страница героя
import { S, api, html, mount, on, icon, avatar, pushScreen, sheet, toast, fail, haptic, leraSays, refreshMe, GI, myGame, confirmSheet, plural, ago } from "../core.js";
import { openPerson } from "./person.js";

const TIERS = ["S", "A", "B", "C", "D"];
const TIER_C = { S: "#ff5a36", A: "#ffc64a", B: "#d4ff3f", C: "#7cc8ff", D: "#8f897e" };
const CLS_COLOR = { "Стрелок": "#ffc64a", "Маг": "#b48cff", "Убийца": "#ff6fa5", "Боец": "#ff7a59", "Танк": "#7cc8ff", "Поддержка": "#5ef0c1",
  "Пиро": "#ff7a59", "Гидро": "#5aa8ff", "Анемо": "#5ef0c1", "Электро": "#b48cff", "Дендро": "#9be15d", "Крио": "#9ad0ff", "Гео": "#ffc64a",
  "Дуэлянт": "#ff6fa5", "Инициатор": "#5ef0c1", "Контроллер": "#b48cff", "Страж": "#7cc8ff" };
const PALETTE = ["#ffc64a", "#b48cff", "#ff6fa5", "#ff7a59", "#7cc8ff", "#5ef0c1", "#d4ff3f", "#ff9f43", "#9ad0ff"];
export const clsColor = (c) => CLS_COLOR[c] || PALETTE[[...(c || "")].reduce((a, ch) => a + ch.charCodeAt(0), 0) % PALETTE.length];
export const glyph = (n) => (n.match(/[A-Za-zА-Яа-яЁё0-9]/g) || ["?"]).slice(0, 2).join("");
const ENT1 = { "Герои": "героя", "Агенты": "агента", "Бойцы": "бойца", "Персонажи": "персонажа", "Карты": "карту" };
const nf = (n) => (n >= 1000 ? `${(n / 1000).toFixed(1).replace(".0", "")}к` : `${n || 0}`);

const cache = {};
export async function wikiData(game, fresh = false) {
  if (fresh || !cache[game]) cache[game] = await api(`/api/wiki?game=${game}`);
  return cache[game];
}

const tierBadge = (t, big = false) => t ? html`<span class="tier ${big ? "big" : ""}" style="--tc:${TIER_C[t]}">${t}</span>` : "";
const heroTile = (h, isMap) => html`<button class="htile" data-act="hero" data-v="${h.name}" style="--hc:${clsColor(h.cls)}">
  <div class="hg">${glyph(h.name)}${tierBadge(h.tier)}</div>
  <b class="ell">${h.name}</b><span class="small muted ell">${isMap ? (h.mains ? `любят ${h.mains}` : "карта") : h.lane_name || h.cls}</span></button>`;

async function toggleMain(game, name) {
  const mg = myGame(game), g = GI(game);
  if (!mg) { toast(`Сначала добавь ${g.short} в профиль`, "err"); return false; }
  if (!mg.heroes.includes(name) && mg.heroes.length >= 5) { toast("Максимум 5 мейнов", "err"); return false; }
  const heroes = mg.heroes.includes(name) ? mg.heroes.filter((h) => h !== name) : [...mg.heroes, name];
  try { await api(`/api/games/${game}`, { method: "PUT", body: { rank: mg.rank, roles: mg.roles, heroes, uid: mg.uid } }); await refreshMe(); haptic.sel(); return true; }
  catch (e) { fail(e); return false; }
}

// ─── хаб ───
export function openWiki(game0) {
  pushScreen((el, pop) => {
    const mine = (S.me.games || []).map((x) => x.game);
    const order = [...new Set([...mine, ...Object.keys(S.dict.games)])];
    let game = game0 || S.game, tab = "home", data = null, q = "", cls = "", sort = "az", cat = "";

    const tabs = () => {
      const ent = data?.entity || "Герои";
      return [["home", "Обзор"], ...(data?.heroes ? [["heroes", ent], ["tier", "Тир-лист"]] : []), ["guides", `Гайды${data ? ` · ${data.guides.length}` : ""}`], ["dict", "Словарь"]];
    };

    function shell() {
      const g = GI(game);
      mount(el, html`<div class="wiki" style="--gc:${g.color}">
        <div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><span class="kicker grow" style="text-align:right">// вики</span></div>
        <div class="chips scroll wiki-games">${order.map((k) => html`<button class="chip ${k === game ? "on" : ""}" data-act="game" data-v="${k}" style="--gcc:${GI(k).color}">${GI(k).short}</button>`)}</div>
        <div class="wiki-hero">
          <div class="kicker">${mine.includes(game) ? "твоя игра" : "энциклопедия"}</div>
          <h1 class="h1">${g.name}<i>.</i></h1>
          ${data ? html`<p>${data.about}</p>
            <div class="wstats">
              <div><b>${nf(data.stats.players)}</b><span>${plural(data.stats.players, "игрок", "игрока", "игроков")} в Лере</span></div>
              ${data.heroes ? html`<div><b>${data.heroes.length}</b><span>${data.entity.toLowerCase()}</span></div>` : ""}
              <div><b>${data.guides.length}</b><span>гайдов</span></div>
              <div><b>${nf(data.stats.tips)}</b><span>советов</span></div></div>` : html`<div class="spinner"></div>`}
        </div>
        <div class="wiki-tabs"><div class="chips scroll">${tabs().map(([k, t]) => html`<button class="chip ${tab === k ? "on" : ""}" data-act="tab" data-t="${k}">${t}</button>`)}</div></div>
        <div id="wb"></div></div>`);
      body();
    }

    function body() {
      const b = el.querySelector("#wb");
      if (!b || !data) return;
      const isMap = data.entity === "Карты";
      if (tab === "home") {
        return mount(b, html`<div class="pad">
          <div class="wsec"><div class="kicker">роли</div>
            <div class="role-grid">${data.roles.map((r, i) => html`<button class="role-card" data-act="role" data-v="${r.key}">
              <span class="num mono">0${i + 1}</span><b>${r.name}</b><p>${r.desc}</p><span class="small muted">${r.players ? `${r.players} ${plural(r.players, "игрок", "игрока", "игроков")} в Лере` : "пока никого"}</span></button>`)}</div></div>
          <div class="wsec"><div class="kicker">ранги · ${data.ranks.length}</div>
            <div class="ladder">${data.ranks.map((r, i) => html`<div class="step" style="--i:${i / Math.max(1, data.ranks.length - 1)}"><i></i><span>${r}</span></div>`)}</div></div>
          <div class="wsec"><div class="kicker">режимы</div><div class="chips">${data.modes.map((m) => html`<span class="chip">${m}</span>`)}</div></div>
          ${data.basics.length ? html`<div class="wsec"><div class="kicker">база для новичков</div>
            <ol class="basics">${data.basics.map((x) => html`<li>${x}</li>`)}</ol></div>` : ""}
          ${data.heroes ? html`<div class="wsec"><div class="row"><div class="kicker grow">${isMap ? "любимые карты" : "популярные мейны"}</div><button class="tag" data-act="tab" data-t="heroes">все →</button></div>
            <div class="hgrid">${[...data.heroes].sort((a, b2) => b2.mains - a.mains || (a.score ?? 9) - (b2.score ?? 9)).slice(0, 6).map((h) => heroTile(h, isMap))}</div></div>` : ""}
          <div class="tiles" style="padding:0;margin-top:22px">
            <button class="tile" data-act="tab" data-t="guides">${icon("book")}<div><b>Гайды</b><div class="sub">${data.guides.length ? `${data.guides.length} от игроков` : "напиши первый"}</div></div></button>
            ${(S.dict.leradle_games || []).includes(game) ? html`<button class="tile" data-act="leradle">${icon("puzzle")}<div><b>Лерадл</b><div class="sub">угадай ${ENT1[data.entity]} дня</div></div></button>`
              : html`<button class="tile" data-act="tab" data-t="dict">${icon("help")}<div><b>Словарь</b><div class="sub">${data.glossary.length} терминов</div></div></button>`}
          </div><div class="sp"></div></div>`);
      }
      if (tab === "heroes") {
        const classes = [...new Set(data.heroes.map((h) => h.cls))];
        let f = data.heroes.filter((h) => (!cls || h.cls === cls || h.lane === cls) && (!q || h.name.toLowerCase().includes(q)));
        if (sort === "pop") f = [...f].sort((a, b2) => b2.mains - a.mains);
        if (sort === "tier") f = [...f].sort((a, b2) => (a.score ?? 9) - (b2.score ?? 9));
        if (sort === "az") f = [...f].sort((a, b2) => a.name.localeCompare(b2.name));
        mount(b, html`<div class="pad"><div class="search">${icon("search", 'width="18" height="18"')}<input class="input" id="q" placeholder="Найти ${ENT1[data.entity]}…" autocomplete="off" value="${q}"></div>
          ${classes.length > 1 || data.roles.some((r) => data.heroes.some((h) => h.lane === r.key)) ? html`<div class="chips scroll" style="margin-top:12px"><button class="chip ${!cls ? "on" : ""}" data-act="cls" data-v="">Все</button>
            ${classes.length > 1 ? classes.map((c) => html`<button class="chip ${cls === c ? "on" : ""}" data-act="cls" data-v="${c}"><i class="dotc" style="background:${clsColor(c)}"></i>${c}</button>`) : ""}
            ${data.roles.filter((r) => data.heroes.some((h) => h.lane === r.key) && !classes.includes(r.name)).map((r) => html`<button class="chip ${cls === r.key ? "on" : ""}" data-act="cls" data-v="${r.key}">${r.name}</button>`)}</div>` : ""}
          <div class="row" style="margin:14px 0 4px"><span class="small muted grow">${f.length} ${plural(f.length, "результат", "результата", "результатов")}</span>
            <div class="seg mini">${[["az", "А–Я"], ["pop", "мейны"], ["tier", "тир"]].map(([k, t]) => html`<button class="${sort === k ? "on" : ""}" data-act="sort" data-v="${k}">${t}</button>`)}</div></div>
          ${f.length ? html`<div class="hgrid">${f.map((h) => heroTile(h, isMap))}</div>` : html`<p class="muted center" style="padding:30px">Никого не нашла</p>`}<div class="sp"></div></div>`);
        const qi = b.querySelector("#q");
        qi.addEventListener("input", (e) => { q = e.target.value.trim().toLowerCase(); const pos = qi.selectionStart; body(); const n = b.querySelector("#q"); n.focus(); n.setSelectionRange(pos, pos); });
        return;
      }
      if (tab === "tier") {
        const rated = data.heroes.filter((h) => h.tier);
        return mount(b, html`<div class="pad">
          <p class="small muted" style="margin:0 0 14px">Тир-лист собирают игроки Леры: каждый оценивает ${ENT1[data.entity]} от S до D. ${data.stats.voters ? `Проголосовали ${data.stats.voters} ${plural(data.stats.voters, "игрок", "игрока", "игроков")}.` : ""}</p>
          <button class="btn wide" data-act="quick">${icon("bolt")}оценить быстро</button>
          <div class="tierlist">${TIERS.map((t) => {
            const hs = rated.filter((h) => h.tier === t).sort((a, b2) => a.score - b2.score);
            return html`<div class="trow"><div class="tl" style="--tc:${TIER_C[t]}">${t}</div>
              <div class="tc">${hs.length ? hs.map((h) => html`<button class="tchip" data-act="hero" data-v="${h.name}" style="--hc:${clsColor(h.cls)}"><i>${glyph(h.name)}</i>${h.name}</button>`) : html`<span class="small muted">—</span>`}</div></div>`;
          })}</div>
          ${rated.length < data.heroes.length ? html`<p class="small muted center" style="margin-top:14px">Ещё без оценки: ${data.heroes.length - rated.length}</p>` : ""}
          <div class="sp"></div></div>`);
      }
      if (tab === "guides") {
        const gs = data.guides.filter((x) => !cat || x.cat === cat);
        return mount(b, html`<div class="pad"><button class="btn wide" data-act="write">${icon("edit")}написать гайд · +100 несо</button>
          <div class="chips scroll" style="margin:14px 0 4px"><button class="chip ${!cat ? "on" : ""}" data-act="cat" data-v="">Все</button>
            ${Object.entries(data.cats).map(([k, v]) => html`<button class="chip ${cat === k ? "on" : ""}" data-act="cat" data-v="${k}">${v}</button>`)}</div>
          ${gs.length ? html`<div class="stack" style="margin-top:10px">${gs.map((x) => guideCard(x))}</div>`
            : html`<div class="empty">${leraSays(`Гайдов${cat ? " в этой категории" : ""} по ${GI(game).short} ещё нет. Напиши первый — за опубликованный дам 100 несо.`)}</div>`}<div class="sp"></div></div>`);
      }
      if (tab === "dict") {
        return mount(b, html`<div class="pad"><div class="gloss">${data.glossary.map(([t, d]) => html`<div class="term"><b>${t}</b><p>${d}</p></div>`)}</div>
          <div class="sp"></div>${leraSays("Не нашёл слово? Спроси меня на главной — «Спроси Леру» объяснит.")}<div class="sp"></div></div>`);
      }
    }

    const load = async (fresh = false) => {
      data = null; shell();
      try { data = await wikiData(game, fresh); } catch (e) { return fail(e); }
      if (!data.heroes && (tab === "heroes" || tab === "tier")) tab = "home";
      shell();
    };
    load();
    return on(el, {
      back: pop,
      game: (x) => { if (x.dataset.v === game) return; game = x.dataset.v; tab = "home"; q = cls = cat = ""; haptic.sel(); load(); },
      tab: (x) => { tab = x.dataset.t; haptic.sel(); shell(); el.querySelector(".wiki-tabs")?.scrollIntoView({ block: "start", behavior: "smooth" }); },
      role: (x) => { if (!data.heroes) return; tab = "heroes"; cls = x.dataset.v; haptic.sel(); shell(); },
      cls: (x) => { cls = x.dataset.v; haptic.sel(); body(); },
      sort: (x) => { sort = x.dataset.v; haptic.sel(); body(); },
      cat: (x) => { cat = x.dataset.v; haptic.sel(); body(); },
      hero: (x) => openHero(game, x.dataset.v, () => load(true)),
      guide: (x) => openGuide(+x.dataset.id, () => load(true)),
      write: () => guideEditor(game, null, () => load(true)),
      quick: () => quickRate(game, data, () => load(true)),
      leradle: async () => (await import("./more.js")).openLeradle(null, game),
    });
  });
}

function guideCard(x) {
  return html`<button class="gcard" data-act="guide" data-id="${x.id}">
    <div class="row" style="gap:6px"><span class="tag acc">${S.dict.guide_cats?.[x.cat] || "Гайд"}</span>${x.hero ? html`<span class="tag">${x.hero}</span>` : ""}</div>
    <b>${x.title}</b><p>${x.preview}…</p>
    <div class="row small muted mono" style="gap:12px">${avatar(x.author, 22)}<span class="grow ell">${x.author?.name || "?"}</span>
      <span>${icon("eye", 'width="14" height="14"')} ${x.views}</span><span style="${x.liked ? "color:var(--love)" : ""}">${icon("heart", 'width="14" height="14"')} ${x.likes}</span></div></button>`;
}

function quickRate(game, data, done) {
  let queue = [...data.heroes].sort(() => Math.random() - 0.5), i = 0, n = 0;
  sheet((el, close) => {
    const draw = () => {
      const h = queue[i];
      if (!h) return mount(el, html`<div class="center"><h2 class="h2">готово!</h2><p class="muted">Оценено: ${n}</p><button class="btn wide" data-act="end">к тир-листу</button></div>`);
      mount(el, html`<div class="row"><span class="kicker grow">быстрая оценка · ${n}</span><button class="tag" data-act="end">хватит</button></div>
        <div class="qr-hero" style="--hc:${clsColor(h.cls)}"><div class="hg big">${glyph(h.name)}</div><h2 class="h2">${h.name}</h2>
          <span class="small muted">${h.cls}${h.lane_name ? ` · ${h.lane_name}` : ""}${h.tier ? ` · сейчас ${h.tier}` : ""}</span></div>
        <div class="tier-pick">${TIERS.map((t, k) => html`<button data-act="t" data-v="${k}" style="--tc:${TIER_C[t]}">${t}</button>`)}</div>
        <button class="btn ghost wide sm" style="margin-top:10px" data-act="skip">не знаю — дальше</button>`);
    };
    draw();
    on(el, {
      t: async (b) => { try { await api("/api/wiki/tier", { method: "POST", body: { game, hero: queue[i].name, tier: +b.dataset.v } }); n++; haptic.tap(); i++; draw(); } catch (e) { fail(e); } },
      skip: () => { i++; draw(); },
      end: () => { close(); if (n) done?.(); },
    });
  });
}

// ─── страница героя ───
export function openHero(game, name, onChange) {
  pushScreen((el, pop) => {
    let h = null, changed = false;
    const load = async () => {
      try { h = await api(`/api/wiki/hero?game=${game}&name=${encodeURIComponent(name)}`); } catch (e) { fail(e); return pop(); }
      draw();
    };
    function draw() {
      const g = GI(game), isMap = h.cls === "Карта";
      const mineMain = (myGame(game)?.heroes || []).includes(h.name);
      const maxD = Math.max(1, ...h.dist);
      mount(el, html`<div class="wiki" style="--gc:${g.color};--hc:${clsColor(h.cls)}">
        <div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><span class="kicker grow" style="text-align:right">${g.name}</span></div>
        <div class="hero-banner">
          <div class="hg huge">${glyph(h.name)}${tierBadge(h.tier, true)}</div>
          <div class="grow" style="min-width:0"><h1 class="h1">${h.name}</h1>
            <div class="row wrap" style="gap:6px;margin-top:10px"><span class="tag">${h.cls}</span>${h.lane_name ? html`<span class="tag">${h.lane_name}</span>` : ""}
              ${h.mains_total ? html`<span class="tag">${isMap ? "любят" : "мейнят"} ${h.mains_total}</span>` : ""}</div></div>
        </div>
        <div class="pad">
          <button class="btn wide ${mineMain ? "dark" : ""}" data-act="main">${icon(mineMain ? "check" : "star")}${mineMain ? (isMap ? "моя карта" : "мой мейн") : (isMap ? "люблю эту карту" : "это мой мейн")}</button>
          ${h.role_desc ? html`<div class="card" style="margin-top:14px"><div class="kicker">${h.lane_name}</div><p style="margin:8px 0 0">${h.role_desc}</p></div>` : ""}

          <div class="wsec"><div class="row"><div class="kicker grow">тир по мнению игроков</div><span class="small muted">${h.votes} ${plural(h.votes, "голос", "голоса", "голосов")}</span></div>
            <div class="dist">${TIERS.map((t, k) => html`<div class="dcol"><div class="dbar"><i style="height:${Math.round((h.dist[k] / maxD) * 100)}%;background:${TIER_C[t]}"></i></div><span>${t}</span></div>`)}</div>
            <div class="small muted" style="margin:14px 0 8px">твоя оценка</div>
            <div class="tier-pick">${TIERS.map((t, k) => html`<button class="${h.my_tier === k ? "on" : ""}" data-act="tier" data-v="${k}" style="--tc:${TIER_C[t]}">${t}</button>`)}</div></div>

          ${h.mains.length ? html`<div class="wsec"><div class="kicker">${isMap ? "любят эту карту" : "мейнят в Лере"}</div>
            <div class="mains">${h.mains.map((p) => html`<button data-act="who" data-id="${p.tg_id}">${avatar(p, 52, { online: true })}<span class="ell">${p.name}</span></button>`)}</div>
            <p class="small muted" style="margin:8px 0 0">Тапни — откроется анкета, можно позвать в катку.</p></div>` : ""}

          <div class="wsec"><div class="kicker">советы игроков · ${h.tips.length}</div>
            <div class="tip-new"><textarea class="input" id="tip" rows="2" maxlength="280" placeholder="${isMap ? "Позиция, раскидка, фишка карты…" : "Билд, контрпик, комбо, фишка…"}"></textarea>
              <button class="ibtn send" data-act="tipsend">${icon("send")}</button></div>
            ${h.tips.length ? html`<div class="stack" style="margin-top:12px">${h.tips.map((t) => html`<div class="tip">
              <p>${t.text}</p>
              <div class="row small muted" style="gap:8px"><button class="row" style="gap:6px" data-act="who" data-id="${t.author?.tg_id}">${avatar(t.author, 22)}<span class="ell">${t.author?.name}</span></button>
                <span class="grow mono">${ago(t.created_at)}</span>
                ${t.mine || S.me.is_admin ? html`<button class="ibtn sm" data-act="tipdel" data-id="${t.id}">${icon("trash", 'width="15" height="15"')}</button>` : ""}
                <button class="like ${t.liked ? "on" : ""}" data-act="tiplike" data-id="${t.id}" ${t.mine ? "disabled" : ""}>${icon("heart", 'width="15" height="15"')}${t.likes}</button></div></div>`)}</div>`
              : html`<p class="small muted" style="margin:10px 0 0">Пока пусто. Поделись первым — лучшие советы поднимаются наверх.</p>`}</div>

          <div class="wsec"><div class="row"><div class="kicker grow">гайды · ${h.guides.length}</div><button class="tag" data-act="write">+ написать</button></div>
            ${h.guides.length ? html`<div class="stack" style="margin-top:10px">${h.guides.map(guideCard)}</div>` : html`<p class="small muted" style="margin:10px 0 0">Гайдов по ${h.name} нет — напиши первый, за публикацию 100 несо.</p>`}</div>

          ${h.similar.length ? html`<div class="wsec"><div class="kicker">${isMap ? "другие карты" : `ещё ${h.cls.toLowerCase()}`}</div>
            <div class="chips" style="margin-top:10px">${h.similar.map((n) => html`<button class="chip" data-act="sim" data-v="${n}">${n}</button>`)}</div></div>` : ""}
          <div class="sp"></div></div></div>`);
    }
    load();
    const off = on(el, {
      back: pop,
      who: (b) => b.dataset.id && openPerson(+b.dataset.id),
      main: async () => { if (await toggleMain(game, h.name)) { changed = true; load(); } },
      tier: async (b) => {
        const v = +b.dataset.v;
        try { await api("/api/wiki/tier", { method: "POST", body: { game, hero: h.name, tier: h.my_tier === v ? -1 : v } }); haptic.sel(); changed = true; load(); } catch (e) { fail(e); }
      },
      tipsend: async () => {
        const ta = el.querySelector("#tip"), text = ta.value.trim();
        if (text.length < 8) return toast("Чуть подробнее — хотя бы пара слов", "err");
        try { await api("/api/wiki/tips", { method: "POST", body: { game, hero: h.name, text } }); haptic.ok(); toast("Совет опубликован · +3 xp", "ok"); changed = true; load(); } catch (e) { fail(e); }
      },
      tiplike: async (b) => { try { await api(`/api/wiki/tips/${b.dataset.id}/like`, { method: "POST" }); haptic.tap(); load(); } catch (e) { fail(e); } },
      tipdel: async (b) => { if (!(await confirmSheet("Удалить совет?", "", "удалить", true))) return; try { await api(`/api/wiki/tips/${b.dataset.id}`, { method: "DELETE" }); changed = true; load(); } catch (e) { fail(e); } },
      guide: (b) => openGuide(+b.dataset.id, load),
      write: () => guideEditor(game, h.name, () => { changed = true; load(); }),
      sim: (b) => openHero(game, b.dataset.v, onChange),
    });
    return () => { off(); if (changed) onChange?.(); };
  });
}

// ─── гайды ───
export function openGuide(id, onChange) {
  pushScreen((el, pop) => {
    mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><span class="kicker grow">гайд</span></div><div class="spinner"></div>`);
    let g = null, changed = false;
    const draw = () => mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><span class="kicker grow">${GI(g.game).name}</span>
        ${g.author?.tg_id === S.me.tg_id || S.me.is_admin ? html`<button class="ibtn" data-act="del">${icon("trash")}</button>` : ""}</div>
      <div class="pad"><div class="row" style="gap:6px;margin-top:4px"><span class="tag acc">${g.cat_name || "Гайд"}</span>${g.hero ? html`<button class="tag" data-act="hero">${g.hero} →</button>` : ""}</div>
        <h1 class="h1" style="text-transform:none;font-size:26px;margin:12px 0 14px">${g.title}</h1>
        <button class="row" data-act="who" style="margin-bottom:18px">${avatar(g.author, 32)}<span class="small"><b>${g.author?.name}</b> · ${g.views} просмотров</span></button>
        <div class="guide-body">${g.body}</div>
        <button class="btn wide ${g.liked ? "" : "dark"}" style="margin-top:24px" data-act="like">${icon("heart")}${g.liked ? "полезно" : "полезный гайд"} · ${g.likes}</button>
        <div class="sp"></div></div>`);
    const load = async () => { try { g = await api(`/api/wiki/guides/${id}`); } catch (e) { fail(e); return pop(); } draw(); };
    load();
    const off = on(el, {
      back: pop,
      who: () => g?.author && openPerson(g.author),
      hero: () => openHero(g.game, g.hero),
      like: async () => { try { const r = await api(`/api/wiki/guides/${id}/like`, { method: "POST" }); g.liked = r.liked; g.likes += r.liked ? 1 : -1; changed = true; haptic.tap(); draw(); } catch (e) { fail(e); } },
      del: async () => {
        if (!(await confirmSheet("Удалить гайд?", "Насовсем.", "удалить", true))) return;
        try { await api(`/api/wiki/guides/${id}`, { method: "DELETE" }); toast("Удалено"); changed = true; pop(); } catch (e) { fail(e); }
      },
    });
    return () => { off(); if (changed) onChange?.(); };
  });
}

export function guideEditor(game, hero0, done) {
  pushScreen((el, pop) => {
    let cat = hero0 ? "hero" : "start", hero = hero0 || null;
    const draw = () => {
      const keep = (s) => el.querySelector(s)?.value ?? "";
      const t = keep("#t"), b = keep("#b");
      const cats = S.dict.guide_cats || {};
      mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><h2 class="h2">новый гайд · ${GI(game).short}</h2></div>
        <div class="pad">${leraSays("Пиши по делу: билд, контрпики, тайминги, фишки. Гайд проверит модератор — за публикацию +100 несо.")}
          <div class="sp"></div>
          <div class="field"><span class="lbl">категория</span><div class="chips">${Object.entries(cats).map(([k, v]) => html`<button class="chip ${cat === k ? "on" : ""}" data-act="cat" data-v="${k}">${v}</button>`)}</div></div>
          ${GI(game).heroes ? html`<div class="field"><span class="lbl">про кого</span><button class="chip ${hero ? "on" : ""}" data-act="pick">${hero || "выбрать (необязательно)"}</button></div>` : ""}
          <div class="field"><label>заголовок</label><input class="input" id="t" maxlength="80" placeholder="Например: как не умирать в первые 5 минут" value="${t}"></div>
          <div class="field"><label>текст</label><textarea class="input" id="b" maxlength="8000" style="min-height:260px" placeholder="Минимум пара абзацев">${b}</textarea></div>
          <button class="btn wide" data-act="send">${icon("send")}отправить на модерацию</button><div class="sp"></div></div>`);
    };
    draw();
    return on(el, {
      back: pop,
      cat: (x) => { cat = x.dataset.v; haptic.sel(); draw(); },
      pick: async () => {
        const d = await wikiData(game);
        sheet((sh, close) => {
          mount(sh, html`<h2 class="h2" style="margin-bottom:12px">про кого гайд</h2><div class="chips"><button class="chip" data-act="h" data-v="">без героя</button>
            ${d.heroes.map((x) => html`<button class="chip ${hero === x.name ? "on" : ""}" data-act="h" data-v="${x.name}">${x.name}</button>`)}</div>`);
          on(sh, { h: (x) => { hero = x.dataset.v || null; if (hero) cat = cat === "start" ? "hero" : cat; close(); draw(); } });
        });
      },
      send: async () => {
        const title = el.querySelector("#t").value.trim(), body = el.querySelector("#b").value.trim();
        if (title.length < 4) return toast("Заголовок слишком короткий", "err");
        if (body.length < 40) return toast("Напиши побольше — хотя бы пару предложений", "err");
        try {
          const r = await api("/api/wiki/guides", { method: "POST", body: { game, title, body, hero, cat } });
          haptic.ok(); toast(r.status === "approved" ? "Опубликовано" : "Отправлено на модерацию", "ok"); pop(); done?.();
        } catch (e) { fail(e); }
      },
    });
  });
}
