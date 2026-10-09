// Полная анкета игрока (bottom sheet) — используется в дуэте, ленте, чатах, топе
import { S, api, html, mount, on, sheet, icon, avatar, nameEl, safeUrl, tint, initial, rankName, roleName, toast, fail, haptic, confirmSheet, GI } from "../core.js";

export function cardInfo(p, { vibe = true } = {}) {
  return html`
    ${p.rep || p.rep_tags?.length ? html`<div class="rep-row ${p.rep < 0 ? "neg" : ""}">${icon("thumb", 'width="16" height="16"')}
      <b>${p.rep > 0 ? "+" : ""}${p.rep}</b><span class="muted small">репутация</span>
      ${(p.rep_tags || []).map((t) => html`<span class="chip acc" style="height:26px;font-size:12px">${S.dict.review_tags[t]}</span>`)}</div>` : ""}
    <div class="chips">
      ${p.voice ? html`<span class="chip">${icon("mic")}микро</span>` : ""}
      ${p.city ? html`<span class="chip">${p.city}</span>` : ""}
    </div>
    ${(p.games || []).length ? html`<div class="sp"></div><div class="kicker">игры</div><div class="games-list">${p.games.map((g) => html`
      <div class="gl-row" style="--gc:${GI(g.game).color}"><span class="gdot">${GI(g.game).short.slice(0, 2)}</span>
        <div class="grow" style="min-width:0"><b>${GI(g.game).name}</b>
          <div class="small muted">${[rankName(g.rank, g.game), ...g.roles.map((r) => roleName(r, g.game))].filter(Boolean).join(" · ")}</div>
          ${g.heroes.length ? html`<div class="small" style="margin-top:3px">мейны: ${g.heroes.join(", ")}</div>` : ""}</div>
        ${g.uid ? html`<button class="tag" data-act="copy-uid" data-v="${g.uid}">ID ${g.uid}</button>` : ""}</div>`)}</div>` : ""}
    ${vibe && p.vibe_why?.length ? html`<div class="sp"></div><div class="kicker">почему <b>вайб ${p.vibe}</b></div>
      <div class="chips" style="margin-top:8px">${p.vibe_why.map((w) => html`<span class="chip acc">${w}</span>`)}</div>` : ""}
    ${p.play_times?.length ? html`<div class="sp"></div><div class="kicker">играет</div>
      <div class="chips" style="margin-top:8px">${p.play_times.map((t) => html`<span class="chip">${S.dict.play_times[t]}</span>`)}</div>` : ""}`;
}

export function photoBg(p, idx = 0) {
  const src = safeUrl(p.photos?.[idx] || p.avatar);
  return src
    ? html`<img src="${src}" alt="" draggable="false">`
    : html`<div class="gen" style="background:${tint(p.tg_id)}"><b>${initial(p.name)}</b></div>`;
}

export async function openPerson(pOrId, { onLike, onPass } = {}) {
  let p = pOrId;
  if (typeof pOrId !== "object") {
    try { p = await api(`/api/user/${pOrId}`); } catch (e) { return fail(e); }
  }
  const isMe = p.tg_id === S.me.tg_id;
  sheet((el, close) => {
    let idx = 0;
    const draw = () => mount(el, html`
      <div class="swipe" style="position:relative;height:min(62vh,520px);box-shadow:none;cursor:default;touch-action:pan-y" data-act="photo">
        <div class="ph">${photoBg(p, idx)}</div>
        ${p.photos.length > 1 ? html`<div class="bars">${p.photos.map((_, i) => html`<i class="${i === idx ? "on" : ""}"></i>`)}</div>` : ""}
        <div class="shade"></div>
        <div class="info">
          <div class="row wrap" style="gap:6px;margin-bottom:10px">
            ${p.online ? html`<span class="tag on-dot">онлайн</span>` : ""}
            ${p.premium ? html`<span class="tag gold">premium</span>` : ""}
            ${p.title ? html`<span class="tag">${p.title}</span>` : ""}
            <span class="tag">ур. ${p.level}</span>
          </div>
          <div class="nm">${nameEl(p)}${p.age ? html`<span class="age">${p.age}</span>` : ""}</div>
        </div>
      </div>
      <div style="padding:16px 2px 4px">
        ${p.about ? html`<p style="margin:0 0 16px">${p.about}</p>` : ""}
        ${cardInfo(p, { vibe: !!p.vibe })}
        <div class="sp"></div>
        ${onLike ? html`<div class="row">
            <button class="btn ghost grow" data-act="pass">${icon("x")}мимо</button>
            <button class="btn grow" data-act="like">${icon("heart")}го катку</button></div>` : ""}
        ${!isMe && !p.lera ? html`<div class="row" style="margin-top:10px">
          <button class="btn dark grow sm" data-act="review">${icon("thumb")}оценить</button>
          <button class="btn dark grow sm" data-act="report">${icon("flag")}пожаловаться</button></div>` : ""}
      </div>`);
    draw();
    on(el, {
      photo: (t, ev) => {
        if (p.photos.length < 2) return;
        const r = t.getBoundingClientRect();
        idx = (idx + (ev.clientX - r.left > r.width / 2 ? 1 : -1) + p.photos.length) % p.photos.length;
        haptic.sel(); draw();
      },
      like: () => { close(); onLike(p); },
      pass: () => { close(); onPass?.(p); },
      report: () => { close(); reportSheet(p); },
      review: () => { close(); reviewSheet(p); },
      "copy-uid": async (b) => { try { await navigator.clipboard.writeText(b.dataset.v); toast("ID скопирован", "ok"); } catch { toast(b.dataset.v); } },
    });
  });
}

export function reviewSheet(p, done) {
  const tags = S.dict.review_tags;
  const NEG = ["toxic", "afk", "noob"];
  let thumb = 0, sel = [];
  sheet((el, close) => {
    const draw = () => mount(el, html`<div class="row" style="margin-bottom:14px">${avatar(p, 44)}<div class="grow"><div class="kicker">отзыв о тиммейте</div><b>${p.name}</b></div></div>
      <div class="row">
        <button class="btn grow ${thumb === 1 ? "" : "dark"}" data-act="t" data-v="1">👍 зашло</button>
        <button class="btn grow ${thumb === -1 ? "hot" : "dark"}" data-act="t" data-v="-1">👎 не зашло</button></div>
      ${thumb ? html`<div class="kicker" style="margin:18px 0 8px">что скажешь · до трёх</div><div class="chips">
        ${Object.entries(tags).filter(([k]) => NEG.includes(k) === (thumb < 0)).map(([k, v]) => html`<button class="chip ${sel.includes(k) ? "on" : ""}" data-act="tag" data-v="${k}">${v}</button>`)}</div>
        <button class="btn wide" style="margin-top:18px" data-act="send">отправить</button>` : ""}
      <p class="muted small" style="margin:14px 0 0">Отзывы анонимные. Из них складывается репутация в анкете.</p>`);
    draw();
    on(el, {
      t: (b) => { thumb = +b.dataset.v; sel = []; haptic.sel(); draw(); },
      tag: (b) => { const v = b.dataset.v; sel = sel.includes(v) ? sel.filter((x) => x !== v) : sel.length < 3 ? [...sel, v] : sel; haptic.sel(); draw(); },
      send: async () => {
        try { await api("/api/review", { method: "POST", body: { to: p.tg_id, thumb, tags: sel } }); haptic.ok(); toast("Спасибо! Отзыв учтён", "ok"); close(); done?.(); }
        catch (e) { fail(e); }
      },
    });
  });
}

export function reportSheet(p) {
  const reasons = ["Спам или реклама", "Оскорбления / токсичность", "Фейковая анкета", "18+ контент", "Просто не хочу видеть"];
  sheet((el, close) => {
    mount(el, html`<h2 class="h2">Что не так с ${p.name}?</h2>
      <p class="muted small">Игрок пропадёт из дуэта, ленты и чатов. Жалоба уйдёт админу.</p>
      <div class="stack">${reasons.map((r) => html`<button class="btn dark wide" data-act="r" data-r="${r}">${r}</button>`)}</div>`);
    on(el, {
      r: async (b) => {
        close();
        const reason = b.dataset.r === reasons[4] ? "" : b.dataset.r;
        if (!(await confirmSheet("Скрыть игрока?", "Отменить это нельзя.", "скрыть", true))) return;
        try { await api("/api/block", { method: "POST", body: { to: p.tg_id, reason } }); toast("Готово. Больше не увидишь", "ok"); }
        catch (e) { fail(e); }
      },
    });
  });
}
