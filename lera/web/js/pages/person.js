// Полная анкета игрока (bottom sheet) — используется в дуэте, ленте, чатах, топе
import { S, api, html, mount, on, sheet, icon, avatar, nameEl, safeUrl, tint, initial, rankName, roleName, toast, fail, haptic, confirmSheet } from "../core.js";

export function cardInfo(p, { vibe = true } = {}) {
  return html`
    <div class="chips">
      ${rankName(p.rank) ? html`<span class="chip on">${rankName(p.rank)}</span>` : ""}
      ${p.roles.map((r) => html`<span class="chip">${roleName(r)}</span>`)}
      ${p.voice ? html`<span class="chip">${icon("mic")}микро</span>` : ""}
      ${p.city ? html`<span class="chip">${p.city}</span>` : ""}
    </div>
    ${vibe && p.vibe_why?.length ? html`<div class="sp"></div><div class="kicker">почему <b>вайб ${p.vibe}</b></div>
      <div class="chips" style="margin-top:8px">${p.vibe_why.map((w) => html`<span class="chip acc">${w}</span>`)}</div>` : ""}
    ${p.heroes?.length ? html`<div class="sp"></div><div class="kicker">мейны</div>
      <div class="chips" style="margin-top:8px">${p.heroes.map((h) => html`<span class="chip">${h}</span>`)}</div>` : ""}
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
        ${!isMe ? html`<button class="btn dark wide sm" style="margin-top:10px" data-act="report">${icon("flag")}пожаловаться / скрыть</button>` : ""}
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
