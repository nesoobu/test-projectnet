import { S, api, html, mount, on, icon, avatar, nameEl, refreshMe, pushScreen, sheet, toast, fail, haptic, safeUrl, leraSays, rankName, roleName, onState, applyAccent, plural } from "../core.js";
import { uploadImage } from "./feed.js";
import * as more from "./more.js";

const ACCENTS = ["#d4ff3f", "#ff6fa5", "#7cc8ff", "#ffc64a", "#b48cff", "#ff7a59", "#5ef0c1", "#efeae0"];
const DAY_REWARD = [20, 30, 40, 50, 60, 70, 80];

export function profilePayload(me, patch = {}) {
  return {
    nickname: me.name, age: me.age, city: me.city, gender: me.gender, about: me.about, rank: me.rank,
    roles: me.roles, heroes: me.heroes, play_times: me.play_times, voice: me.voice, photos: me.photos,
    accent: me.accent, duet_visible: me.duet_visible, ...patch,
  };
}

export function render(root) {
  const draw = () => {
    const m = S.me;
    const lv = m.level;
    const pct = Math.round(((lv.xp - lv.from) / Math.max(1, lv.to - lv.from)) * 100);
    const cycle = m.checked_today ? ((m.streak - 1) % 7) + 1 : m.streak % 7;
    mount(root, html`
      <div class="p-head">
        <div class="p-banner ${m.banner || "banner_none"}"></div>
        <div class="p-id">
          <button data-act="edit">${avatar(m, 96)}</button>
          <div class="grow" style="padding-bottom:6px;min-width:0">
            <div class="row wrap" style="gap:6px;margin-bottom:8px">
              ${m.premium ? html`<span class="tag gold">${icon("crown", 'width="11" height="11"')} premium</span>` : ""}
              ${m.title ? html`<span class="tag">${m.title}</span>` : ""}
            </div>
            <h1 class="p-name">${nameEl(m)}</h1>
          </div>
        </div>
        <div class="chips" style="margin-top:14px">
          ${rankName(m.rank) ? html`<span class="chip on">${rankName(m.rank)}</span>` : ""}
          ${m.roles.map((r) => html`<span class="chip">${roleName(r)}</span>`)}
          ${!m.profile_done ? html`<button class="chip acc" data-act="edit">${icon("edit")}заполни анкету</button>` : ""}
        </div>
        <div class="lvl"><div class="row"><span class="kicker grow">уровень <b>${lv.level}</b></span><span class="kicker mono">${lv.xp} / ${lv.to} xp</span></div>
          <div class="track"><i style="width:${pct}%"></i></div></div>
        <div class="stats">
          <button class="stat" data-act="shop" style="text-align:left"><b class="coin" style="font:700 20px/1 var(--display)">${m.balance}</b><span class="kicker">несо</span></button>
          <div class="stat"><b>${m.streak}</b><span class="kicker">${plural(m.streak, "день", "дня", "дней")} подряд</span></div>
          <button class="stat" data-act="gacha" style="text-align:left"><b>${m.tickets}</b><span class="kicker">${plural(m.tickets, "тикет", "тикета", "тикетов")}</span></button>
        </div>
      </div>

      <div class="daily ${m.checked_today ? "done" : ""}">
        <div class="row"><div class="grow"><div class="kicker">${m.checked_today ? "до завтра" : "ежедневка"}</div>
          <div class="h2" style="margin-top:6px">${m.checked_today ? "забрано" : `+${(DAY_REWARD[cycle] ?? 20) * (m.premium ? 2 : 1)} несо`}</div></div>
          ${m.premium ? html`<span class="tag" style="background:rgba(0,0,0,.15)">×2</span>` : ""}</div>
        <div class="days">${DAY_REWARD.map((r, i) => html`<i class="${i < cycle ? "done" : i === cycle && !m.checked_today ? "next" : ""}">${i === 6 ? "🎟" : r}</i>`)}</div>
        ${m.checked_today ? html`<div class="small muted">7-й день подряд — бесплатный тикет в гачу.</div>`
          : html`<button class="btn wide" data-act="checkin">забрать</button>`}
      </div>

      <div class="tiles">
        <button class="tile wide acc" data-act="edit">${icon("edit")}<div class="grow"><b>Анкета дуэта</b><div class="sub">${m.duet_visible ? "видна в поиске" : "скрыта из поиска"} · фото ${m.photos.length}/4</div></div>${icon("send")}</button>
        <button class="tile" data-act="quests">${icon("target")}<div><b>Квесты</b><div class="sub">награды каждый день</div></div><i class="badge" id="qb" style="display:none"></i></button>
        <button class="tile" data-act="gacha">${icon("sparkle")}<div><b>Гача</b><div class="sub">гарант через ${Math.max(0, 50 - m.pity)}</div></div></button>
        <button class="tile" data-act="shop">${icon("bag")}<div><b>Магазин</b><div class="sub">рамки, ники, титулы</div></div></button>
        <button class="tile" data-act="inv">${icon("box")}<div><b>Инвентарь</b><div class="sub">надеть и снять</div></div></button>
        <button class="tile" data-act="top">${icon("trophy")}<div><b>Топ</b><div class="sub">xp, стрики, лайки</div></div></button>
        <button class="tile" data-act="wiki">${icon("book")}<div><b>Вики</b><div class="sub">герои и мейны</div></div></button>
        <button class="tile wide gold" data-act="premium">${icon("crown")}<div class="grow"><b>${m.premium ? "Premium активен" : "Lera Premium"}</b><div class="sub">${m.premium ? `до ${new Date(m.premium_until.replace(" ", "T") + "Z").toLocaleDateString("ru")}` : "суперлайки, отмена свайпа, ×2 ежедневка"}</div></div></button>
        <button class="tile" data-act="invite">${icon("gift")}<div><b>Позвать друга</b><div class="sub">+150 несо за каждого</div></div></button>
        <button class="tile" data-act="help">${icon("help")}<div><b>Помощь</b><div class="sub">как всё устроено</div></div></button>
        ${m.is_admin ? html`<button class="tile wide" data-act="admin">${icon("eye")}<div class="grow"><b>Админка</b><div class="sub">статистика</div></div></button>` : ""}
      </div>`);
    api("/api/quests").then((r) => {
      const n = r.quests.filter((q) => q.progress >= q.goal && !q.claimed).length;
      const b = root.querySelector("#qb");
      if (b && n) { b.textContent = n; b.style.display = ""; }
    }).catch(() => {});
  };

  const off = on(root, {
    edit: () => openEditor(),
    checkin: async (b) => {
      b.disabled = true;
      try {
        const r = await api("/api/checkin", { method: "POST" });
        haptic.ok();
        await refreshMe();
        sheet((el, close) => {
          mount(el, html`<div class="center" style="padding:10px 0 4px">
            <div class="kicker">день ${r.streak}</div>
            <div style="font:900 64px/1 var(--display);letter-spacing:-.05em;color:var(--acc);margin:10px 0">+${r.reward}</div>
            ${r.ticket ? html`<div class="tag gold" style="margin-bottom:12px">+1 тикет в гачу</div>` : ""}
            <div style="display:flex;justify-content:center;margin:12px 0 20px">${leraSays(r.lera)}</div>
            <button class="btn wide" data-act="ok">кайф</button></div>`);
          on(el, { ok: close });
        });
      } catch (e) { fail(e); b.disabled = false; }
    },
    quests: more.openQuests, gacha: more.openGacha, shop: more.openShop, inv: more.openInventory,
    top: more.openTop, wiki: more.openWiki, premium: more.openPremium, invite: more.openInvite,
    help: more.openHelp, admin: more.openAdmin,
  });
  const unsub = onState(draw);
  draw();
  return () => { off(); unsub(); };
}

export function openEditor(first = false) {
  pushScreen((el, pop) => {
    const m = S.me;
    const g = {
      nickname: m.name || "", age: m.age || "", city: m.city || "", gender: m.gender || "", about: m.about || "",
      rank: m.rank, roles: [...m.roles], heroes: [...m.heroes], play_times: [...m.play_times], voice: m.voice,
      photos: [...m.photos], accent: m.accent || ACCENTS[0], duet_visible: m.duet_visible,
    };
    let uploading = false;
    const read = () => {
      const v = (id) => el.querySelector(id)?.value;
      if (el.querySelector("#nick")) {
        g.nickname = v("#nick"); g.age = v("#age"); g.city = v("#city"); g.about = v("#about");
      }
    };
    const draw = () => {
      read();
      const st = el.scrollTop;
      mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><h2 class="h2">${first ? "давай знакомиться" : "анкета"}</h2></div>
      <div class="pad">
        ${first ? html`<div style="margin:6px 0 20px">${leraSays("Привет, я Лера! Заполни анкету — и я начну подбирать тебе тиммейтов по роли, рангу и времени игры.")}</div>` : ""}
        <div class="field"><span class="lbl">фото · первое — аватар</span><div class="photos">
          ${[0, 1, 2, 3].map((i) => g.photos[i]
            ? html`<div class="photo-slot"><img src="${safeUrl(g.photos[i])}" alt="">${i === 0 ? html`<span class="tag acc first">аватар</span>` : html`<button class="tag first" data-act="main" data-i="${i}">сделать главным</button>`}
                <button class="x" data-act="rmph" data-i="${i}">${icon("x")}</button></div>`
            : html`<label class="photo-slot" style="cursor:pointer">${uploading && i === g.photos.length ? html`<div class="spinner" style="margin:0"></div>` : icon("plus", 'width="22" height="22"')}
                <input type="file" accept="image/*" hidden data-up></label>`)}</div></div>
        <div class="field"><label>ник</label><input class="input" id="nick" maxlength="24" value="${g.nickname}" placeholder="Как тебя звать в игре"></div>
        <div class="row" style="gap:10px">
          <div class="field grow"><label>возраст</label><input class="input" id="age" type="number" inputmode="numeric" min="14" max="80" value="${g.age}"></div>
          <div class="field grow"><label>город</label><input class="input" id="city" maxlength="40" value="${g.city}"></div>
        </div>
        <div class="field"><span class="lbl">пол</span><div class="seg">${[["f", "Девушка"], ["m", "Парень"], ["", "Не скажу"]].map(([k, t]) => html`<button class="${g.gender === k ? "on" : ""}" data-act="gender" data-v="${k}">${t}</button>`)}</div></div>
        <div class="field"><span class="lbl">ранг</span><div class="chips scroll">${S.dict.ranks.map((r, i) => html`<button class="chip ${g.rank === i ? "on" : ""}" data-act="rank" data-v="${i}">${r}</button>`)}</div></div>
        <div class="field"><span class="lbl">роли · до трёх</span><div class="chips">${Object.entries(S.dict.roles).map(([k, v]) => html`<button class="chip ${g.roles.includes(k) ? "on" : ""}" data-act="role" data-v="${k}">${v}</button>`)}</div></div>
        <div class="field"><span class="lbl">когда играешь</span><div class="chips">${Object.entries(S.dict.play_times).map(([k, v]) => html`<button class="chip ${g.play_times.includes(k) ? "on" : ""}" data-act="time" data-v="${k}">${v}</button>`)}</div></div>
        <div class="field"><span class="lbl">мейны · до пяти</span><div class="chips">${g.heroes.map((h) => html`<button class="chip on" data-act="rmhero" data-v="${h}">${h} ×</button>`)}
          ${g.heroes.length < 5 ? html`<button class="chip" data-act="heroes">${icon("plus")}добавить</button>` : ""}</div></div>
        <div class="field"><label>о себе</label><textarea class="input" id="about" maxlength="300" placeholder="Чем берёшь, кого ищешь, какой у тебя вайб">${g.about}</textarea></div>
        <div class="field"><button class="toggle" data-act="voice"><span>Играю с микрофоном</span><i class="sw ${g.voice ? "on" : ""}"></i></button></div>
        <div class="field"><button class="toggle" data-act="vis"><span>Показывать меня в дуэте</span><i class="sw ${g.duet_visible ? "on" : ""}"></i></button></div>
        <div class="field"><span class="lbl">цвет приложения</span><div class="swatches">${ACCENTS.map((c) => html`<button class="swatch ${g.accent === c ? "on" : ""}" style="background:${c}" data-act="acc" data-v="${c}"></button>`)}</div></div>
        <button class="btn wide" data-act="save" ${uploading ? "disabled" : ""}>${icon("check")}сохранить</button>
      </div>`);
      el.scrollTop = st;
      el.querySelectorAll("[data-up]").forEach((inp) => inp.addEventListener("change", async (e) => {
        const f = e.target.files[0]; if (!f) return;
        read(); uploading = true; draw();
        try { g.photos.push(await uploadImage(f)); haptic.ok(); } catch (err) { fail(err); }
        uploading = false; draw();
      }));
    };
    const toggle = (arr, v, max) => arr.includes(v) ? arr.filter((x) => x !== v) : arr.length >= max ? (toast(`Максимум ${max}`, "err"), arr) : [...arr, v];
    draw();
    const off = on(el, {
      back: pop,
      gender: (b) => { read(); g.gender = b.dataset.v; haptic.sel(); draw(); },
      rank: (b) => { read(); g.rank = +b.dataset.v; haptic.sel(); draw(); },
      role: (b) => { read(); g.roles = toggle(g.roles, b.dataset.v, 3); haptic.sel(); draw(); },
      time: (b) => { read(); g.play_times = toggle(g.play_times, b.dataset.v, 4); haptic.sel(); draw(); },
      voice: () => { read(); g.voice = !g.voice; haptic.sel(); draw(); },
      vis: () => { read(); g.duet_visible = !g.duet_visible; haptic.sel(); draw(); },
      acc: (b) => { read(); g.accent = b.dataset.v; applyAccent(g.accent); haptic.sel(); draw(); },
      rmph: (b) => { read(); g.photos.splice(+b.dataset.i, 1); draw(); },
      main: (b) => { read(); const [p] = g.photos.splice(+b.dataset.i, 1); g.photos.unshift(p); haptic.sel(); draw(); },
      rmhero: (b) => { read(); g.heroes = g.heroes.filter((h) => h !== b.dataset.v); draw(); },
      heroes: () => { read(); more.heroPicker(g.heroes, (list) => { g.heroes = list; draw(); }); },
      save: async () => {
        read();
        if (!g.nickname.trim()) return toast("Нужен ник", "err");
        if (g.rank == null) return toast("Выбери ранг", "err");
        if (!g.roles.length) return toast("Выбери хотя бы одну роль", "err");
        const body = { ...g, age: g.age ? +g.age : null, city: g.city || null, gender: g.gender || null };
        try {
          await api("/api/profile", { method: "PUT", body });
          await refreshMe(); haptic.ok(); toast("Сохранено", "ok"); pop();
          if (first) { const { go } = await import("../app.js"); go("duet"); }
        } catch (e) { fail(e); }
      },
    });
    return () => { off(); applyAccent(S.me.accent); };
  });
}
