// Главная: «Готов играть», ежедневные поводы, опрос дня, турниры, вики
import { S, api, html, mount, on, icon, avatar, nameEl, sheet, toast, fail, haptic, leraSays, rankName, roleName, GI, myGame, left, plural, refreshMe, onState } from "../core.js";
import { gameSwitch, editGame } from "../games.js";
import { openPerson } from "./person.js";

const greet = () => {
  const h = new Date().getHours();
  return h < 5 ? "доброй ночи" : h < 12 ? "доброе утро" : h < 18 ? "привет" : "добрый вечер";
};

export function render(root) {
  let data = null;
  const g = GI();

  mount(root, html`<div class="top"><div style="min-width:0"><div class="kicker">// ${greet()}</div>
      <h1 class="h1 ell" style="margin-top:6px">${S.me.name.toLowerCase()}<i>.</i></h1></div>${gameSwitch()}</div>
    <div id="hb"><div class="pad"><div class="skel" style="height:180px"></div></div></div>`);
  const box = root.querySelector("#hb");

  async function load() {
    try { data = await api(`/api/home?game=${S.game}`); } catch (e) { return fail(e); }
    draw();
  }

  function readyBlock() {
    const r = data.ready, mine = r.mine && r.mine.game === S.game ? r.mine : null;
    const hasGame = !!myGame();
    return html`<div class="ready-card" style="--gc:${g.color}">
      <div class="row"><div class="grow"><div class="kicker" style="color:inherit;opacity:.7">${data.online} ${plural(data.online, "игрок", "игрока", "игроков")} онлайн в ${g.short}</div>
        <div class="h2" style="margin-top:6px">${mine ? "ты в поиске пати" : "готов играть?"}</div></div>
        <div class="pulse ${mine ? "on" : ""}"></div></div>
      ${mine ? html`<p style="margin:8px 0 14px;opacity:.8">ещё ${left(mine.until)}${mine.note ? ` · «${mine.note}»` : ""}. Лера уже позвала тиммейтов.</p>
          <button class="btn wide dark-on" data-act="ready-off">снять статус</button>`
        : html`<p style="margin:8px 0 14px;opacity:.8">Нажми — и Лера разошлёт клич всем, кто играет в ${g.short} под твой ранг.</p>
          <button class="btn wide dark-on" data-act="${hasGame ? "ready" : "add-game"}">${icon("fire")}${hasGame ? "кинуть клич" : `добавить ${g.short} в профиль`}</button>`}
    </div>
    ${r.players.length ? html`<div class="pad kicker" style="margin:18px 0 10px">готовы прямо сейчас · <b>${r.players.length}</b></div>
      <div class="hscroll">${r.players.map((p) => html`<div class="rp">
        <button data-act="who" data-id="${p.tg_id}" class="row" style="text-align:left;gap:10px">${avatar(p, 44, { online: true })}
          <div style="min-width:0"><b class="ell" style="display:block">${nameEl(p)}</b>
          <span class="small muted ell" style="display:block">${[rankName(p.rank, p.game), ...p.roles.map((x) => roleName(x, p.game))].filter(Boolean).join(" · ")}</span></div></button>
        ${p.note ? html`<div class="small rp-note">«${p.note}»</div>` : ""}
        <div class="row" style="margin-top:auto"><span class="small muted mono grow">${left(p.until)}</span>
          <button class="btn sm" data-act="invite" data-id="${p.tg_id}">го</button></div></div>`)}</div>` : ""}`;
  }

  function dailyBlock() {
    const L = data.leradle, m = S.me;
    return html`<div class="pad kicker" style="margin:24px 0 10px">каждый день${S.dict.weekend ? html` · <b>выходные ×2</b>` : ""}</div>
      <div class="tiles" style="padding-top:0;padding-bottom:0">
        <button class="tile ${m.checked_today ? "" : "acc"}" data-act="checkin">${icon("gift")}
          <div><b>${m.checked_today ? "Ежедневка забрана" : "Забрать ежедневку"}</b><div class="sub">стрик ${m.streak} ${plural(m.streak, "день", "дня", "дней")}</div></div></button>
        <button class="tile ${L.over ? "" : "acc2"}" data-act="leradle">${icon("puzzle")}
          <div><b>Лерадл</b><div class="sub">${L.solved ? `разгадан ✓ · стрик ${L.streak}` : L.over ? "не вышло, завтра новый" : L.tries ? `попыток: ${L.tries}/6` : "угадай героя дня"}</div></div></button>
        <button class="tile" data-act="quests">${icon("target")}<div><b>Квесты</b><div class="sub">${data.quests_ready ? `${data.quests_ready} готово забрать` : "награды за активность"}</div></div>
          ${data.quests_ready ? html`<i class="badge">${data.quests_ready}</i>` : ""}</button>
        <button class="tile" data-act="ach">${icon("medal")}<div><b>Ачивки</b><div class="sub">собери все</div></div></button>
      </div>`;
  }

  function pollBlock() {
    const p = data.poll;
    const voted = p.voted != null;
    return html`<div class="pad kicker" style="margin:24px 0 10px">опрос дня${voted ? html` · <b>${p.total} ${plural(p.total, "голос", "голоса", "голосов")}</b>` : ""}</div>
      <div class="card" style="margin:0 16px"><div class="h3" style="margin-bottom:12px">${p.question}</div>
        <div class="stack">${p.options.map((o, i) => {
          const pct = voted && p.total ? Math.round((p.counts[i] / p.total) * 100) : 0;
          return html`<button class="poll-opt ${voted ? "res" : ""} ${p.voted === i ? "mine" : ""}" data-act="vote" data-i="${i}" ${voted ? "disabled" : ""}>
            <i style="width:${pct}%"></i><span class="grow">${o}</span>${voted ? html`<b class="mono">${pct}%</b>` : ""}</button>`;
        })}</div></div>`;
  }

  function tourBlock() {
    const T = data.tournaments;
    return html`<div class="pad row" style="margin:24px 0 10px"><span class="kicker grow">турниры ${g.short}</span>
        <button class="kicker" data-act="tours" style="color:var(--acc)">все →</button></div>
      ${T.length ? html`<div class="pad stack">${T.map((t) => tourCard(t))}</div>`
        : html`<div class="pad"><button class="card line wide-card" data-act="tours">${icon("swords")}<span class="grow muted">Пока турниров нет. Загляни позже — или напиши админу, чтобы устроил.</span></button></div>`}
      <div class="tiles">
        <button class="tile" data-act="wiki">${icon("book")}<div><b>Вики ${g.short}</b><div class="sub">${g.heroes ? "герои и гайды" : "гайды игроков"}</div></div></button>
        <button class="tile" data-act="top">${icon("trophy")}<div><b>Топ игроков</b><div class="sub">xp, стрики, лайки</div></div></button>
        <button class="tile wide" data-act="rate">${icon("thumb")}<div class="grow"><b>Оцени тиммейтов</b><div class="sub">отзывы → репутация в анкете. +3 xp за каждый</div></div></button>
      </div>`;
  }

  function draw() {
    mount(box, html`<div class="pad">${readyBlock()}</div>${dailyBlock()}${pollBlock()}${tourBlock()}<div class="sp"></div>`);
  }

  async function lazy(name) { return import("./more.js").then((m) => m[name]); }

  const off = on(root, {
    ready: () => readySheet(load),
    "add-game": () => editGame(S.game, { onSaved: load }),
    "ready-off": async () => { try { await api("/api/ready", { method: "DELETE" }); haptic.sel(); load(); } catch (e) { fail(e); } },
    who: (b) => openPerson(+b.dataset.id),
    invite: async (b) => {
      try {
        const r = await api(`/api/ready/${b.dataset.id}/invite`, { method: "POST" });
        haptic.ok(); toast("Позвали! Пиши в чат", "ok");
        const { openMatch } = await import("./chats.js"); openMatch(r.match_id);
      } catch (e) { fail(e); }
    },
    checkin: async () => {
      if (S.me.checked_today) return toast("Уже забрано — приходи завтра");
      const { checkinFlow } = await import("./profile.js"); await checkinFlow(); load();
    },
    leradle: async () => (await lazy("openLeradle"))(load),
    quests: async () => (await lazy("openQuests"))(),
    ach: async () => (await lazy("openAchievements"))(),
    vote: async (b) => {
      try { data.poll = await api(`/api/poll/${data.poll.id}/vote`, { method: "POST", body: { option: +b.dataset.i } }); haptic.sel(); draw(); } catch (e) { fail(e); }
    },
    tours: async () => (await lazy("openTournaments"))(),
    tour: async (b) => (await lazy("openTournament"))(+b.dataset.id),
    wiki: async () => (await lazy("openWiki"))(),
    top: async () => (await lazy("openTop"))(),
    rate: async () => (await lazy("openRate"))(),
  });
  const unsub = onState(() => data && draw());
  load();
  return () => { off(); unsub(); };
}

export function tourCard(t) {
  const st = { reg: ["регистрация", "acc"], live: ["идёт", "love"], done: ["завершён", ""] }[t.status] || ["", ""];
  const d = new Date(t.starts_at.replace(" ", "T") + "Z");
  return html`<button class="tour" data-act="tour" data-id="${t.id}" style="--gc:${GI(t.game).color}">
    <div class="tour-date"><b>${d.getDate()}</b><span>${d.toLocaleDateString("ru", { month: "short" })}</span></div>
    <div class="grow" style="min-width:0"><div class="row" style="gap:6px"><span class="tag ${st[1]}">${st[0]}</span>${t.joined ? html`<span class="tag">ты участвуешь</span>` : ""}</div>
      <b class="ell" style="display:block;margin-top:6px">${t.title}</b>
      <span class="small muted">${t.team_size === 1 ? "соло" : `${t.team_size}×${t.team_size}`} · ${t.teams}/${t.max_teams} · ${d.toLocaleTimeString("ru", { hour: "2-digit", minute: "2-digit" })}</span></div>
    ${t.prize ? html`<span class="coin">${t.prize}</span>` : ""}</button>`;
}

function readySheet(done) {
  const g = GI();
  let minutes = 60;
  sheet((el, close) => {
    const draw = () => {
      const note = el.querySelector("#note")?.value || "";
      mount(el, html`<div class="kicker">${g.name}</div><h2 class="h2" style="margin:6px 0 16px">кинуть клич<span class="dot">.</span></h2>
        <div class="field"><span class="lbl">сколько готов ждать</span><div class="seg">${[30, 60, 120, 180].map((m) => html`<button class="${minutes === m ? "on" : ""}" data-act="m" data-v="${m}">${m < 60 ? `${m} мин` : `${m / 60} ч`}</button>`)}</div></div>
        <div class="field"><label>пара слов (необязательно)</label><input class="input" id="note" maxlength="80" value="${note}" placeholder="Нужен саппорт, апаем рейт, без токсиков"></div>
        <button class="btn wide" data-act="go">${icon("fire")}позвать тиммейтов</button>
        <p class="muted small" style="margin:12px 0 0">Лера напишет игрокам ${g.short} в бота. Не чаще раза в 30 минут — чтобы не спамить.</p>`);
    };
    draw();
    on(el, {
      m: (b) => { minutes = +b.dataset.v; haptic.sel(); draw(); },
      go: async () => {
        try {
          const r = await api("/api/ready", { method: "POST", body: { game: S.game, minutes, note: el.querySelector("#note").value } });
          haptic.ok(); close();
          toast(r.notified ? `Клич ушёл ${r.notified} ${plural(r.notified, "игроку", "игрокам", "игрокам")}` : "Ты в списке «готовы играть»", "ok");
          done?.();
        } catch (e) { fail(e); }
      },
    });
  });
}
