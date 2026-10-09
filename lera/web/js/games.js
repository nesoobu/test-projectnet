// Выбор игры, профиль игры (ранг/роли/мейны/ID), переключатель в шапке
import { S, api, html, mount, on, icon, sheet, toast, fail, haptic, refreshMe, GI, setGame, myGame, confirmSheet } from "./core.js";

export const gameSwitch = () => {
  const g = GI();
  return html`<button class="gswitch" data-act="game-switch" style="--gc:${g.color}">
    <i></i><span>${g.short}</span>${icon("down")}</button>`;
};

// один глобальный обработчик — кнопка работает на любом экране
document.addEventListener("click", (e) => {
  if (e.target.closest('[data-act="game-switch"]')) { haptic.sel(); openGamePicker(); }
});

let statsCache = null;

export function openGamePicker({ onPick } = {}) {
  sheet(async (el, close) => {
    const draw = () => {
      const mine = S.me.games.map((x) => x.game);
      const others = Object.keys(S.dict.games).filter((k) => !mine.includes(k));
      const row = (k, own) => {
        const g = GI(k), st = statsCache?.[k], mg = myGame(k);
        return html`<button class="grow-row ${S.game === k ? "on" : ""}" data-act="${own ? "pick" : "add"}" data-g="${k}" style="--gc:${g.color}">
          <span class="gdot">${g.short.slice(0, 2)}</span>
          <span class="grow" style="min-width:0"><b class="ell" style="display:block">${g.name}</b>
            <span class="small muted">${own ? [g.ranks[mg?.rank], (mg?.roles || []).map((r) => g.roles[r]).join(", ")].filter(Boolean).join(" · ") || "заполни профиль игры"
              : st ? `${st.players} игроков · ${st.online} онлайн` : "добавить в профиль"}</span></span>
          ${own ? html`<span class="ibtn" style="width:34px;height:34px" data-act="edit" data-g="${k}">${icon("edit", 'width="16" height="16"')}</span>`
            : html`<span class="chip" style="height:28px">${icon("plus")}</span>`}
        </button>`;
      };
      mount(el, html`<h2 class="h2" style="margin-bottom:6px">игры<span class="dot">.</span></h2>
        <p class="muted small" style="margin:0 0 14px">Дуэт, отряды, вики и турниры подстраиваются под выбранную игру.</p>
        ${mine.length ? html`<div class="kicker" style="margin-bottom:8px">мои</div><div class="stack">${mine.map((k) => row(k, true))}</div>` : ""}
        ${others.length ? html`<div class="kicker" style="margin:18px 0 8px">ещё игры</div><div class="stack">${others.map((k) => row(k, false))}</div>` : ""}`);
    };
    draw();
    if (!statsCache) api("/api/games/stats").then((s) => { statsCache = s; draw(); }).catch(() => {});
    on(el, {
      pick: (b, ev) => {
        if (ev.target.closest('[data-act="edit"]')) return;
        close(); setGame(b.dataset.g); onPick?.(b.dataset.g);
      },
      edit: (b) => { close(); editGame(b.dataset.g); },
      add: (b) => { close(); editGame(b.dataset.g, { onSaved: (g) => { setGame(g); onPick?.(g); } }); },
    });
  });
}

export function editGame(game, { onSaved } = {}) {
  const g = GI(game);
  const cur = myGame(game);
  const st = { rank: cur?.rank ?? null, roles: [...(cur?.roles || [])], heroes: [...(cur?.heroes || [])], uid: cur?.uid || "" };
  sheet((el, close) => {
    const draw = () => {
      st.uid = el.querySelector("#guid")?.value ?? st.uid;
      mount(el, html`<div class="row" style="margin-bottom:16px;--gc:${g.color}"><span class="gdot">${g.short.slice(0, 2)}</span>
          <h2 class="h2 grow">${g.name}</h2></div>
        <div class="field"><span class="lbl">ранг</span><div class="chips">${g.ranks.map((r, i) => html`<button class="chip ${st.rank === i ? "on" : ""}" data-act="rank" data-v="${i}">${r}</button>`)}</div></div>
        <div class="field"><span class="lbl">роли · до трёх</span><div class="chips">${Object.entries(g.roles).map(([k, v]) => html`<button class="chip ${st.roles.includes(k) ? "on" : ""}" data-act="role" data-v="${k}">${v}</button>`)}</div></div>
        ${g.heroes ? html`<div class="field"><span class="lbl">мейны · до пяти</span><div class="chips">${st.heroes.map((h) => html`<button class="chip on" data-act="rmh" data-v="${h}">${h} ×</button>`)}
          ${st.heroes.length < 5 ? html`<button class="chip" data-act="heroes">${icon("plus")}добавить</button>` : ""}</div></div>` : ""}
        <div class="field"><label>игровой ID / ник (необязательно)</label><input class="input" id="guid" maxlength="40" value="${st.uid}" placeholder="Чтобы тебя могли добавить в друзья"></div>
        <div class="row">${cur ? html`<button class="btn ghost" data-act="del">${icon("trash")}</button>` : ""}
          <button class="btn grow" data-act="save">${icon("check")}${cur ? "сохранить" : "добавить игру"}</button></div>`);
    };
    draw();
    on(el, {
      rank: (b) => { st.rank = +b.dataset.v; haptic.sel(); draw(); },
      role: (b) => {
        const v = b.dataset.v;
        if (st.roles.includes(v)) st.roles = st.roles.filter((x) => x !== v);
        else if (st.roles.length >= 3) return toast("Максимум 3 роли", "err");
        else st.roles.push(v);
        haptic.sel(); draw();
      },
      rmh: (b) => { st.heroes = st.heroes.filter((h) => h !== b.dataset.v); draw(); },
      heroes: async () => {
        st.uid = el.querySelector("#guid").value;
        const { heroPicker } = await import("./pages/more.js");
        heroPicker(game, st.heroes, (list) => { st.heroes = list; draw(); });
      },
      del: async () => {
        close();
        if (!(await confirmSheet(`Убрать ${g.short}?`, "Анкета этой игры пропадёт из дуэта.", "убрать", true))) return;
        try { await api(`/api/games/${game}`, { method: "DELETE" }); await refreshMe(); toast("Игра убрана"); } catch (e) { fail(e); }
      },
      save: async () => {
        st.uid = el.querySelector("#guid").value;
        if (st.rank == null) return toast("Выбери ранг", "err");
        if (!st.roles.length) return toast("Выбери хотя бы одну роль", "err");
        try {
          await api(`/api/games/${game}`, { method: "PUT", body: st });
          await refreshMe(); haptic.ok(); close();
          toast(cur ? "Сохранено" : `${g.short} в профиле!`, "ok");
          onSaved?.(game);
        } catch (e) { fail(e); }
      },
    });
  });
}
