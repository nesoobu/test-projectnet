// ИИ-Лера: чат-помощник по играм
import { S, api, html, mount, on, icon, pushScreen, fail, haptic, leraSays, confirmSheet, GI } from "../core.js";

const STARTERS = () => {
  const g = GI();
  return [`Как апнуть ранг в ${g.short}?`, "Какую роль мне попробовать?", "Как не тильтовать после лузстрика?", "Что умеет Лера?"];
};

export function openAI() {
  pushScreen((el, pop) => {
    let st = null, busy = false;
    mount(el, html`<div class="chat-head"><button class="ibtn" data-act="back" style="background:none;margin-left:-10px">${icon("back")}</button>
        <div class="row grow"><div class="lera"><div class="face">Л</div></div><div><b>Лера</b><div class="small muted" id="aisub">ИИ-помощник</div></div></div>
        <button class="ibtn" data-act="clear">${icon("trash")}</button></div>
      <div class="msgs" id="am"><div class="spinner"></div></div>
      <div class="ice" id="ai-ice"></div>
      <div class="composer"><textarea id="ta" rows="1" placeholder="Спроси про игру или приложение…" maxlength="1000"></textarea>
        <button class="ibtn send" data-act="send">${icon("send")}</button></div>`);
    el.classList.add("flex");
    const box = el.querySelector("#am"), ta = el.querySelector("#ta");

    function draw() {
      if (!st.enabled) {
        mount(box, html`<div class="empty" style="margin:auto">${leraSays("Мой ИИ-режим ещё не включён — админ должен добавить ключ. А пока загляни в вики и «Помощь».")}</div>`);
        el.querySelector(".composer").style.display = "none";
        return;
      }
      mount(el.querySelector("#aisub"), `${st.left} из ${st.limit} вопросов на сегодня`);
      mount(box, st.messages.length ? html`${st.messages.map((m) => html`<div class="msg ${m.role === "user" ? "me" : "ai"}">${m.text}</div>`)}
          ${busy ? html`<div class="msg ai typing"><i></i><i></i><i></i></div>` : ""}`
        : html`<div class="empty" style="margin:auto">${leraSays("Я Лера. Спрашивай про роли, героев, тактику, тильт или как тут всё устроено — отвечу коротко и по делу.")}</div>`);
      mount(el.querySelector("#ai-ice"), st.messages.length ? "" : STARTERS().map((t) => html`<button class="chip" data-act="ice">${t}</button>`));
      box.scrollTop = box.scrollHeight;
    }

    async function send(text) {
      text = text.trim();
      if (!text || busy) return;
      if (st.left <= 0) return fail(new Error(S.me.premium ? "На сегодня вопросы кончились" : "На сегодня вопросы кончились. С Premium их больше"));
      ta.value = ""; ta.style.height = "";
      busy = true;
      st.messages.push({ role: "user", text });
      draw(); haptic.tap();
      try {
        const r = await api("/api/ai", { method: "POST", body: { text } });
        st.messages.push(r.reply); st.left = r.left; haptic.ok();
      } catch (e) { st.messages.pop(); ta.value = text; fail(e); }
      busy = false; draw();
    }

    (async () => { try { st = await api("/api/ai"); draw(); } catch (e) { fail(e); pop(); } })();
    ta.addEventListener("input", () => { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 120) + "px"; });
    ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && matchMedia("(pointer:fine)").matches) { e.preventDefault(); send(ta.value); } });
    return on(el, {
      back: pop,
      send: () => send(ta.value),
      ice: (b) => send(b.textContent),
      clear: async () => {
        if (!(await confirmSheet("Очистить диалог?", "Лера забудет, о чём вы говорили.", "очистить", true))) return;
        try { await api("/api/ai", { method: "DELETE" }); st.messages = []; draw(); } catch (e) { fail(e); }
      },
    });
  }, { flex: true });
}
