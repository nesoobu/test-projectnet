// Глобальный поиск: игроки, герои всех игр, гайды, кланы, про-команды
import { api, html, mount, on, icon, avatar, nameEl, pushScreen, fail, GI, rankName } from "../core.js";

export function openSearch() {
  pushScreen((el, pop) => {
    let q = "", timer = null, seq = 0;
    mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button>
        <div class="search grow">${icon("search", 'width="18" height="18"')}<input class="input" id="sq" placeholder="Игроки, герои, гайды, кланы, команды…" autocomplete="off"></div></div>
      <div id="sr"></div>`);
    const box = el.querySelector("#sr"), inp = el.querySelector("#sq");
    setTimeout(() => inp.focus(), 250);
    const hint = () => mount(box, html`<div class="empty" style="padding-top:40px"><p class="muted center">Начни вводить — минимум 2 буквы.<br>Ищу по-русски и по-английски.</p></div>`);
    hint();
    async function run() {
      const my = ++seq;
      if (q.length < 2) return hint();
      let r; try { r = await api(`/api/search?q=${encodeURIComponent(q)}`); } catch (e) { return fail(e); }
      if (my !== seq) return;
      const sec = (title, items, row) => items.length ? html`<div class="kicker pad" style="margin:18px 0 8px">${title} · ${items.length}</div><div class="pad"><div class="list">${items.map(row)}</div></div>` : "";
      const total = r.players.length + r.heroes.length + r.guides.length + r.clans.length + r.teams.length;
      mount(box, total ? html`
        ${sec("игроки", r.players, (p) => html`<button class="li" style="width:100%;text-align:left" data-act="who" data-id="${p.tg_id}">${avatar(p, 44, { online: true })}
          <div class="grow" style="min-width:0"><b class="ell" style="display:block">${nameEl(p)}</b><span class="small muted ell">${p.game ? `${GI(p.game).short} · ${rankName(p.rank, p.game) || ""}` : ""}</span></div></button>`)}
        ${sec("герои", r.heroes, (h) => html`<button class="li" style="width:100%;text-align:left" data-act="hero" data-g="${h.game}" data-v="${h.name}">
          <span class="s-hero">${h.img ? html`<img src="${h.img}" alt="">` : (h.ru || h.name).slice(0, 2)}</span>
          <div class="grow"><b>${h.ru || h.name}</b><div class="small muted">${h.ru ? `${h.name} · ` : ""}${GI(h.game).short} · ${h.cls}</div></div></button>`)}
        ${sec("гайды", r.guides, (g) => html`<button class="li" style="width:100%;text-align:left" data-act="guide" data-id="${g.id}">${icon("book", 'width="20" height="20"')}
          <div class="grow"><b>${g.title}</b><div class="small muted">${GI(g.game).short}</div></div></button>`)}
        ${sec("кланы", r.clans, (c) => html`<button class="li" style="width:100%;text-align:left" data-act="clan" data-id="${c.id}">
          <div class="emblem" style="--cc:${c.color};--s:40px"><span>${c.tag}</span></div><div class="grow"><b>${c.name}</b><div class="small muted">[${c.tag}]</div></div></button>`)}
        ${sec("про-команды", r.teams, (t) => html`<button class="li" style="width:100%;text-align:left" data-act="team" data-v="${t}">${icon("trophy", 'width="20" height="20"')}<b class="grow">${t}</b></button>`)}
        <div class="sp"></div>` : html`<div class="empty" style="padding-top:40px"><p class="muted center">Ничего не нашла по «${q}»</p></div>`);
    }
    inp.addEventListener("input", () => { q = inp.value.trim(); clearTimeout(timer); timer = setTimeout(run, 250); });
    return on(el, {
      back: pop,
      who: async (b) => (await import("./person.js")).openPerson(+b.dataset.id),
      hero: async (b) => (await import("./wiki.js")).openHero(b.dataset.g, b.dataset.v),
      guide: async (b) => (await import("./wiki.js")).openGuide(+b.dataset.id),
      clan: async (b) => (await import("./clans.js")).openClan(+b.dataset.id),
      team: async (b) => (await import("./pro.js")).openTeam(b.dataset.v),
    });
  });
}
