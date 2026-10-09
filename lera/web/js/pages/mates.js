// Вкладка «Тиммейты»: дуэт и отряды под выбранную игру
import { S, html, mount, on, haptic } from "../core.js";
import { gameSwitch } from "../games.js";
import * as duet from "./duet.js";
import * as squads from "./squads.js";
import * as clans from "./clans.js";

let lastTab = "duet";

export function render(root, arg) {
  let tab = arg === "squads" || arg === "clans" ? arg : arg === "likes" || arg === "duet" ? "duet" : lastTab;
  let sub = null;
  root.classList.add("noscroll");
  root.innerHTML = `<div class="top mates-top" id="mt"></div><div id="mb" class="mates-body"></div>`;
  const top = root.querySelector("#mt"), body = root.querySelector("#mb");

  const drawTop = () => mount(top, html`<div class="words">
      <button class="${tab === "duet" ? "on" : ""}" data-act="mt" data-t="duet">дуэт</button>
      <button class="${tab === "squads" ? "on" : ""}" data-act="mt" data-t="squads">отряды</button>
      <button class="${tab === "clans" ? "on" : ""}" data-act="mt" data-t="clans">кланы</button></div>
    ${gameSwitch()}`) && top.querySelector(".words .on")?.scrollIntoView({ inline: "nearest", block: "nearest" });

  function open(a) {
    if (typeof sub === "function") sub();
    lastTab = tab;
    body.innerHTML = "";
    body.className = "mates-body " + (tab === "duet" ? "flexcol" : "scroll");
    sub = ({ duet, squads, clans }[tab]).render(body, a) || null;
    drawTop();
  }

  const off = on(top, { mt: (b) => { if (b.dataset.t === tab) return; tab = b.dataset.t; haptic.sel(); open(); } });
  open(arg);
  return () => { off(); if (typeof sub === "function") sub(); };
}
