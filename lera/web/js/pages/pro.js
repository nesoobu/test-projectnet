// Турниры: про-сцена (матчи с PandaScore / Liquipedia) + турниры Леры
import { S, tg, api, html, mount, on, icon, pushScreen, sheet, toast, fail, haptic, leraSays, refreshMe, GI, confirmSheet, plural } from "../core.js";

const STATUS = { live: "LIVE", done: "завершён", cancelled: "отменён" };
const FLAG = (cc) => cc && /^[A-Z]{2}$/.test(cc) ? String.fromCodePoint(...[...cc].map((c) => 0x1f1a5 + c.charCodeAt(0))) : "";
const dt = (s) => new Date(s.replace(" ", "T") + "Z");
const hm = (s) => dt(s).toLocaleTimeString("ru", { hour: "2-digit", minute: "2-digit" });
const dayKey = (s) => dt(s).toLocaleDateString("ru", { weekday: "long", day: "numeric", month: "long" });
const gameLabel = (m) => m.game ? GI(m.game).short : (m.game_name || "киберспорт");
const gameColor = (m) => m.game ? GI(m.game).color : "#8f897e";

function logo(m, side, size = 34) {
  const url = m[`logo_${side}`], acr = m[`acr_${side}`] || "?";
  return url ? html`<img class="pm-logo" src="${url}" alt="" loading="lazy" style="--s:${size}px" onerror="this.replaceWith(Object.assign(document.createElement('i'),{className:'pm-logo txt',textContent:'${acr.replace(/'/g, "")}'}))">`
    : html`<i class="pm-logo txt" style="--s:${size}px">${acr.slice(0, 4)}</i>`;
}

export function pmCard(m, compact = false) {
  const live = m.status === "live", done = m.status === "done";
  const sc = (s) => (m[`score_${s}`] ?? "") === "" ? "" : m[`score_${s}`];
  const win = (s) => done && m.winner === s;
  return html`<button class="pm-card ${live ? "live" : ""} ${compact ? "compact" : ""}" data-act="pro" data-id="${m.id}" style="--gc:${gameColor(m)}">
    <div class="pm-wm"><span>${m.acr_a || ""}</span><span>${m.acr_b || ""}</span></div>
    <div class="pm-top"><span class="pm-league ell">${m.league || m.tournament || gameLabel(m)}</span>
      <span class="pm-st ${live ? "live" : ""}">${live ? html`<i></i>LIVE` : STATUS[m.status] || hm(m.begin_at)}</span></div>
    ${["a", "b"].map((s) => html`<div class="pm-team ${win(s) ? "win" : done && m.winner ? "lose" : ""}">${logo(m, s)}
      <b class="ell grow">${FLAG(m[`flag_${s}`])} ${m[`team_${s}`]}</b>${m.status !== "upcoming" ? html`<span class="pm-sc">${sc(s)}</span>` : ""}
      ${m.my_pick === s ? html`<span class="tag acc" title="твой прогноз">🔮</span>` : ""}</div>`)}
    <div class="pm-foot mono"><span>${hm(m.begin_at)}</span><span>·</span><span style="color:var(--gc)">${gameLabel(m)}</span><span>·</span><span>Bo${m.best_of}</span>
      ${m.streams?.length ? html`<span>·</span><span>${icon("eye", 'width="12" height="12"')} стрим</span>` : ""}${m.followed ? html`<span class="grow"></span>${icon("bell", 'width="13" height="13"')}` : ""}</div>
  </button>`;
}

// ─── хаб турниров ───
export function openTournaments(mode = "pro") {
  pushScreen((el, pop) => {
    let tab = "live", game = "all", data = null, auto = true;
    const games = [...new Set([...(S.me.games || []).map((x) => x.game)])];

    function frame() {
      mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><span class="kicker grow" style="text-align:right">// киберспорт и турниры</span>
          ${S.me.is_admin && mode === "pro" ? html`<button class="ibtn" data-act="admin">${icon("sliders")}</button>` : ""}</div>
        <div class="pad" style="margin:4px 0 14px"><h1 class="h1">турниры<i>.</i></h1></div>
        <div class="pad"><div class="seg"><button class="${mode === "pro" ? "on" : ""}" data-act="mode" data-v="pro">${icon("trophy", 'width="15" height="15"')} про-сцена</button>
          <button class="${mode === "lera" ? "on" : ""}" data-act="mode" data-v="lera">${icon("swords", 'width="15" height="15"')} турниры Леры</button></div></div>
        <div id="tb"></div>`);
      mode === "pro" ? loadPro() : loadLera();
    }

    async function loadLera() {
      const b = el.querySelector("#tb");
      mount(b, html`<div class="spinner"></div>`);
      let r; try { r = await api(`/api/tournaments?game=${S.game}`); } catch (e) { return fail(e); }
      const { tourCard } = await import("./home.js");
      const g = GI();
      mount(b, html`<div class="pad" style="margin-top:14px">${leraSays("Турниры внутри Леры: регистрация, сетка, чек-ин, призы в несо. Капитаны сами отправляют результат.")}</div>
        ${S.me.is_admin ? html`<div class="pad" style="margin:12px 0"><button class="btn wide dark" data-act="create">${icon("plus")}создать турнир</button></div>` : ""}
        ${r.tournaments.length ? html`<div class="pad stack" style="margin-top:12px">${r.tournaments.map(tourCard)}</div>`
          : html`<div class="empty">${leraSays(`Турниров по ${g.short} пока нет. Как только админ откроет регистрацию — я напишу в ленту.`)}</div>`}<div class="sp"></div>`);
    }

    async function loadPro() {
      const b = el.querySelector("#tb");
      if (!data) mount(b, html`<div class="spinner"></div>`);
      try { data = await api(`/api/pro?tab=${tab}&game=${game}`); } catch (e) { return fail(e); }
      // ничего не идёт — показать ближайшие прямо под сообщением
      data.next = [];
      if (tab === "live" && !data.matches.length && data.counts.soon) {
        try { data.next = (await api(`/api/pro?tab=soon&game=${game}`)).matches.slice(0, 5); } catch {}
      }
      auto = false;
      drawPro();
    }

    function drawPro() {
      const b = el.querySelector("#tb");
      if (!b || !data) return;
      const groups = [];
      for (const m of data.matches) {
        const k = dayKey(m.begin_at);
        let g = groups.find((x) => x.k === k);
        if (!g) groups.push(g = { k, ms: [] });
        g.ms.push(m);
      }
      const gchips = [["all", "Все"], ...(games.length ? [["mine", "Мои игры"]] : []), ...(data.my_teams.length ? [["teams", `Мои команды · ${data.my_teams.length}`]] : []),
        ...data.games.map((k) => [k, GI(k).short]), ...(data.other ? [["other", "Другие"]] : [])];
      const empty = { live: "Сейчас никто не играет.", soon: "Ближайших матчей пока нет.", past: "За две недели матчей нет." }[tab];
      mount(b, html`<div class="pad" style="margin-top:14px">
          <div class="pm-tabs">${[["live", "Идут"], ["soon", "Скоро"], ["past", "Прошедшие"]].map(([k, t]) => html`<button class="${tab === k ? "on" : ""} ${k === "live" && data.counts.live ? "has-live" : ""}" data-act="tab" data-v="${k}">
            ${k === "live" && data.counts.live ? html`<i></i>` : ""}${t}${k !== "past" && data.counts[k] ? html` <span class="mono">${data.counts[k]}</span>` : ""}</button>`)}</div>
          <div class="chips scroll" style="margin-top:12px">${gchips.map(([k, t]) => html`<button class="chip ${game === k ? "on" : ""}" data-act="game" data-v="${k}">${t}</button>`)}</div></div>
        ${groups.length ? groups.map((g) => html`<div class="pad pm-day"><span>${g.k}</span><span class="mono">${g.ms.length}</span></div>
          <div class="pad stack">${g.ms.map((m) => pmCard(m))}</div>`)
          : data.next?.length ? html`<div class="pad" style="margin-top:18px">${leraSays(`${empty} Ближайшие матчи:`)}</div>
              <div class="pad stack" style="margin-top:12px">${data.next.map((m) => pmCard(m))}</div>
              <div class="pad" style="margin-top:10px"><button class="btn dark wide" data-act="tab" data-v="soon">все ближайшие · ${data.counts.soon}</button></div>`
          : html`<div class="empty">${leraSays(`${empty} ${data.sources.length ? "" : "Источники ещё загружаются — первые матчи появятся в течение 15 минут после запуска."}`)}</div>`}
        <p class="pad small muted center" style="margin-top:20px">🔮 Прогнозы на несо до начала матча · 🔔 уведомления о старте и результате<br>
          данные: ${data.sources.includes("pandascore") ? "PandaScore, " : ""}Liquipedia (CC-BY-SA)</p><div class="sp"></div>`);
    }

    frame();
    const timer = setInterval(() => { if (mode === "pro" && !document.hidden && el.isConnected) loadPro(); }, 60000);
    const off = on(el, {
      back: pop,
      mode: (x) => { mode = x.dataset.v; haptic.sel(); frame(); },
      tab: (x) => { tab = x.dataset.v; haptic.sel(); loadPro(); },
      game: (x) => { game = x.dataset.v; haptic.sel(); loadPro(); },
      pro: (x) => openPro(+x.dataset.id, loadPro),
      tour: async (x) => (await import("./more.js")).openTournament(+x.dataset.id, loadLera),
      create: async () => (await import("./more.js")).tourCreate(loadLera),
      admin: () => adminSheet(loadPro),
    });
    return () => { off(); clearInterval(timer); };
  });
}

// ─── матч ───
export function openPro(id, onChange) {
  pushScreen((el, pop) => {
    let m = null;
    const load = async () => {
      try { m = await api(`/api/pro/m/${id}`); } catch (e) { fail(e); return pop(); }
      draw();
    };
    function draw() {
      const live = m.status === "live", done = m.status === "done";
      const d = dt(m.begin_at);
      const pa = m.pool.a || 0, pb = m.pool.b || 0, tot = pa + pb;
      const odds = (s) => { const mine = s === "a" ? pa : pb; return tot && mine ? (tot / mine).toFixed(2) : "—"; };
      const form = (arr) => arr.length ? html`<div class="form">${arr.map((x) => html`<i class="${x === "W" ? "w" : "l"}">${x === "W" ? "В" : "П"}</i>`)}</div>` : html`<span class="small muted">нет данных</span>`;
      mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><span class="kicker grow ell">${gameLabel(m)}</span>
          <button class="ibtn ${m.followed ? "on-acc" : ""}" data-act="follow">${icon("bell")}</button><button class="ibtn" data-act="share">${icon("share")}</button></div>
        <div class="pm-hero" style="--gc:${gameColor(m)}">
          <div class="pm-wm big"><span>${m.acr_a || ""}</span><span>${m.acr_b || ""}</span></div>
          <div class="kicker" style="color:var(--gc)">${m.league || ""}</div>
          ${m.tournament && m.tournament !== m.league ? html`<div class="small muted" style="margin-top:4px">${m.tournament}</div>` : ""}
          <div class="pm-vs">
            ${["a", "b"].map((s, i) => html`${i ? html`<div class="pm-mid">${m.status === "upcoming" ? html`<b class="mono">${hm(m.begin_at)}</b><span>${d.toLocaleDateString("ru", { day: "numeric", month: "short" })}</span>`
                : html`<b class="pm-big">${m.score_a ?? 0}<em>:</em>${m.score_b ?? 0}</b><span class="${live ? "live" : ""}">${live ? "● LIVE" : STATUS[m.status]}</span>`}<span class="mono">Bo${m.best_of}</span></div>` : ""}
              <button class="pm-side ${done && m.winner === s ? "win" : ""}" data-act="team" data-s="${s}">${logo(m, s, 64)}<b>${m[`team_${s}`]}</b>
                <span class="tag ${m.team_followed[s] ? "acc" : ""}">${m.team_followed[s] ? "★ слежу" : "☆ следить"}</span></button>`)}
          </div>
        </div>
        <div class="pad">
          ${m.streams.length ? html`<div class="kicker" style="margin:4px 0 10px">трансляции</div><div class="chips">${m.streams.map((s) => html`<button class="chip ${s.main ? "on" : ""}" data-act="stream" data-v="${s.url}">${icon("eye")}${s.url.replace(/^https?:\/\/(www\.)?/, "").slice(0, 32)}${s.lang ? ` · ${s.lang}` : ""}</button>`)}</div>` : ""}

          <div class="card pm-pred">
            <div class="row"><div class="kicker grow">🔮 прогнозы игроков Леры</div><span class="small muted">${(m.pool.na || 0) + (m.pool.nb || 0)} ставок</span></div>
            <div class="pm-bar"><i style="width:${tot ? Math.round((pa / tot) * 100) : 50}%"></i></div>
            <div class="row small mono" style="margin-top:6px"><span class="grow">${pa} · ×${odds("a")}</span><span>×${odds("b")} · ${pb}</span></div>
            ${m.my ? html`<div class="pm-mine">Твой прогноз: <b>${m[`team_${m.my.pick}`]}</b> · ${m.my.stake} несо
                ${m.my.payout != null ? html` → <b style="color:${m.my.payout > m.my.stake ? "var(--acc)" : "var(--hot)"}">${m.my.payout ? `+${m.my.payout}` : "мимо"}</b>` : ""}</div>`
              : m.can_predict ? html`<div class="row" style="gap:8px;margin-top:12px">${["a", "b"].map((s) => html`<button class="btn grow sm dark" data-act="pick" data-s="${s}">${m[`team_${s}`]}</button>`)}</div>
                <p class="small muted" style="margin:10px 0 0">Ставка несо до начала. Угадавшие делят ставки проигравших + 10% бонуса от Леры.</p>`
              : html`<p class="small muted" style="margin:10px 0 0">${m.status === "upcoming" ? "Прогнозы закрыты." : "Прогнозы принимаются только до начала матча."}</p>`}
          </div>

          <div class="kicker" style="margin:20px 0 8px">форма · последние матчи</div>
          <div class="pm-forms" style="margin-top:0">
            ${["a", "b"].map((s) => html`<div class="card"><div class="small muted ell">${m[`team_${s}`]}</div><div style="margin-top:8px">${form(m.form[s])}</div></div>`)}
          </div>
          ${m.h2h.length ? html`<div class="kicker" style="margin:20px 0 8px">личные встречи</div><div class="list">${m.h2h.map((x) => html`<div class="li"><div class="grow"><b>${x.team_a} ${x.score_a}:${x.score_b} ${x.team_b}</b>
            <div class="small muted">${x.league || ""} · ${dt(x.begin_at).toLocaleDateString("ru")}</div></div></div>`)}</div>` : ""}

          <button class="btn wide" style="margin-top:18px" data-act="chat">${icon("chat")}обсуждение${m.comments ? ` · ${m.comments}` : ""}</button>
          ${S.me.is_admin ? html`<button class="btn ghost wide sm" style="margin-top:10px" data-act="result">админ: выставить счёт</button>` : ""}
          <p class="small muted center" style="margin-top:16px">${d.toLocaleString("ru", { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })} · источник: ${m.source}</p>
          <div class="sp"></div></div>`);
    }
    load();
    const t = setInterval(() => { if (m?.status === "live" && !document.hidden) load(); }, 30000);
    const off = on(el, {
      back: pop,
      follow: async () => { try { const r = await api(`/api/pro/m/${id}/follow`, { method: "POST" }); haptic.sel(); toast(r.followed ? "Напомню о старте и результате" : "Уведомления выключены", "ok"); load(); onChange?.(); } catch (e) { fail(e); } },
      team: async (b) => {
        const team = m[`team_${b.dataset.s}`];
        try { const r = await api("/api/pro/team", { method: "POST", body: { team } }); haptic.sel(); toast(r.followed ? `Слежу за ${team}: напишу перед каждым матчем` : `Больше не слежу за ${team}`, "ok"); load(); } catch (e) { fail(e); }
      },
      stream: (b) => (tg?.openLink ? tg.openLink(b.dataset.v) : window.open(b.dataset.v, "_blank")),
      share: () => {
        const link = `https://t.me/${S.dict.bot}?start=x${id}`;
        const url = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(`${m.team_a} vs ${m.team_b} — смотрим и ставим прогнозы в Лере`)}`;
        tg?.openTelegramLink ? tg.openTelegramLink(url) : window.open(url);
      },
      pick: (b) => {
        const s = b.dataset.s;
        let stake = 50;
        sheet((sh, close) => {
          const d2 = () => mount(sh, html`<h2 class="h2" style="margin-bottom:6px">победит ${m[`team_${s}`]}</h2>
            <p class="small muted" style="margin:0 0 14px">Баланс: <span class="coin">${S.me.balance}</span> · вернуть ставку нельзя</p>
            <div class="seg">${[10, 50, 100, 250, 500, 1000].map((v) => html`<button class="${stake === v ? "on" : ""}" data-act="st" data-v="${v}">${v}</button>`)}</div>
            <button class="btn wide" style="margin-top:16px" data-act="ok">${icon("sparkle")}поставить ${stake} несо</button>`);
          d2();
          on(sh, {
            st: (x) => { stake = +x.dataset.v; haptic.sel(); d2(); },
            ok: async () => {
              try { await api(`/api/pro/m/${id}/predict`, { method: "POST", body: { pick: s, stake } }); haptic.ok(); toast("Прогноз принят! Напишу, когда матч закончится", "ok"); close(); refreshMe(); load(); onChange?.(); }
              catch (e) { fail(e); }
            },
          });
        });
      },
      chat: () => pushScreen((ce, cpop) => {
        let stop = () => {};
        import("./chats.js").then(({ chatRoom }) => {
          stop = chatRoom(ce, {
            head: () => html`<div class="grow" style="min-width:0"><b class="ell" style="display:block">${m.team_a} vs ${m.team_b}</b><span class="small muted">обсуждение матча</span></div>`,
            load: async (after) => ({ messages: (await api(`/api/pro/m/${id}/comments?after=${after}`)).messages }),
            send: (text) => api(`/api/pro/m/${id}/comments`, { method: "POST", body: { text } }),
            empty: () => leraSays("Кто вывезет? Пиши прогнозы, реакции на моменты и ссылки на клипы."),
            back: cpop, group: true, poll: 5000,
          });
        });
        return () => stop();
      }, { flex: true }),
      result: () => sheet((sh, close) => {
        mount(sh, html`<h2 class="h2" style="margin-bottom:12px">счёт матча</h2>
          <div class="row" style="gap:10px"><input class="input grow" id="sa" type="number" value="${m.score_a ?? 0}"><b>:</b><input class="input grow" id="sb" type="number" value="${m.score_b ?? 0}"></div>
          <div class="stack" style="margin-top:14px"><button class="btn wide" data-act="s" data-v="done">завершить</button><button class="btn dark wide" data-act="s" data-v="live">идёт</button>
          <button class="btn ghost wide" data-act="s" data-v="cancelled">отменён (вернуть ставки)</button></div>`);
        on(sh, { s: async (x) => { try { await api(`/api/admin/pro/${id}`, { method: "POST", body: { score_a: +sh.querySelector("#sa").value || 0, score_b: +sh.querySelector("#sb").value || 0, status: x.dataset.v } }); close(); load(); } catch (e) { fail(e); } } });
      }),
    });
    return () => { off(); clearInterval(t); };
  });
}

function adminSheet(done) {
  sheet(async (el, close) => {
    mount(el, html`<div class="spinner"></div>`);
    let r; try { r = await api("/api/admin/pro"); } catch (e) { return fail(e); }
    const dflt = new Date(Date.now() + 864e5); dflt.setMinutes(0, 0, 0);
    const iso = new Date(dflt - dflt.getTimezoneOffset() * 6e4).toISOString().slice(0, 16);
    mount(el, html`<h2 class="h2">источники</h2>
      <p class="small muted">Матчей в базе: ${r.total} · PandaScore: ${r.pandascore ? "токен есть" : "нет токена (PANDASCORE_TOKEN в .env)"} · Liquipedia: ${r.liquipedia ? "вкл" : "выкл"}</p>
      <div class="list">${r.sources.map((s) => html`<div class="li"><div class="grow"><b>${s.name}</b>
        <div class="small ${s.err_at && (!s.ok_at || s.err_at > s.ok_at) ? "" : "muted"}" style="${s.err_at && (!s.ok_at || s.err_at > s.ok_at) ? "color:var(--hot)" : ""}">${s.ok_at ? `ок ${s.ok_at} · ${s.count} матчей` : "ещё не было успешной загрузки"}${s.err_at && (!s.ok_at || s.err_at > s.ok_at) ? ` · ошибка: ${s.err}` : ""}</div></div></div>`)}</div>
      <h2 class="h2" style="margin:20px 0 10px">добавить матч вручную</h2>
      <div class="field"><label>лига / турнир</label><input class="input" id="lg" placeholder="Кубок СНГ"></div>
      <div class="row" style="gap:8px"><input class="input grow" id="ta" placeholder="Команда 1"><input class="input grow" id="tb2" placeholder="Команда 2"></div>
      <div class="row" style="gap:8px;margin-top:10px"><input class="input grow" id="dt" type="datetime-local" value="${iso}"><input class="input" style="width:90px" id="bo" type="number" value="3"></div>
      <div class="field" style="margin-top:10px"><label>ссылка на стрим</label><input class="input" id="st" placeholder="https://twitch.tv/…"></div>
      <button class="btn wide" data-act="add">добавить для ${GI().short}</button>`);
    on(el, {
      add: async () => {
        const body = { game: S.game, league: el.querySelector("#lg").value.trim(), team_a: el.querySelector("#ta").value.trim(), team_b: el.querySelector("#tb2").value.trim(),
          begin_at: el.querySelector("#dt").value, best_of: +el.querySelector("#bo").value || 1, stream: el.querySelector("#st").value.trim() };
        try { await api("/api/admin/pro", { method: "POST", body }); toast("Матч добавлен", "ok"); close(); done?.(); } catch (e) { fail(e); }
      },
    });
  });
}
