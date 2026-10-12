// Клипы: сетка в ленте, вертикальный плеер, загрузка
import { S, api, html, mount, on, icon, avatar, nameEl, ago, sheet, leraSays, fail, toast, haptic, safeUrl, confirmSheet, pushScreen, GI, gameBadge } from "../core.js";
import { openPerson } from "./person.js";

export function clipsGrid(box, { scope = "game" } = {}) {
  let sort = "new", clips = [];
  const load = async () => {
    mount(box, html`<div class="spinner"></div>`);
    try { clips = (await api(`/api/clips?sort=${sort}&game=${scope === "game" ? S.game : ""}`)).clips; } catch (e) { return fail(e); }
    draw();
  };
  const draw = () => mount(box, html`<div class="pad row" style="margin-bottom:12px">
      <div class="chips grow"><button class="chip ${sort === "new" ? "on" : ""}" data-act="cs" data-v="new">Новые</button>
        <button class="chip ${sort === "top" ? "on" : ""}" data-act="cs" data-v="top">Топ недели</button></div>
      <button class="btn sm" data-act="upload">${icon("plus")}клип</button></div>
    ${clips.length ? html`<div class="clip-grid">${clips.map((c, i) => html`<button class="clip-th" data-act="play" data-i="${i}">
        <video src="${safeUrl(c.video)}#t=0.5" preload="metadata" muted playsinline></video>
        <span class="clip-meta">${icon("heart", 'width="13" height="13"')} ${c.likes} · ${icon("eye", 'width="13" height="13"')} ${c.views}</span></button>`)}</div>`
      : html`<div class="empty">${leraSays("Клипов пока нет. Залей свой эйс или фейл — лучший за неделю получит 300 несо.")}</div>`}<div class="sp"></div>`);
  load();
  return on(box, {
    cs: (b) => { sort = b.dataset.v; haptic.sel(); load(); },
    play: (b) => openPlayer(clips, +b.dataset.i, load),
    upload: () => uploadSheet(load),
  });
}

function openPlayer(list, start, onChange) {
  pushScreen((el, pop) => {
    el.classList.add("clip-screen");
    mount(el, html`<button class="ibtn clip-close" data-act="back">${icon("x")}</button>
      <div class="clip-feed">${list.map((c, i) => html`<section class="clip-slide" data-i="${i}">
        <video src="${safeUrl(c.video)}" loop playsinline preload="${Math.abs(i - start) < 2 ? "auto" : "none"}" data-act="toggle"></video>
        <div class="clip-info"><button class="row" data-act="who" data-id="${c.author?.tg_id}" style="gap:10px;text-align:left">${avatar(c.author, 38)}
            <div><b>${nameEl(c.author)}</b><div class="small" style="opacity:.7">${ago(c.created_at)}${c.game ? " · " : ""}${c.game ? gameBadge(c.game) : ""}</div></div></button>
          ${c.caption ? html`<p style="margin:10px 0 0">${c.caption}</p>` : ""}</div>
        <div class="clip-side">
          <button data-act="like" data-i="${i}" class="${c.liked ? "liked" : ""}">${icon("heart")}<span>${c.likes}</span></button>
          <button data-act="share" data-i="${i}">${icon("share")}<span>&nbsp;</span></button>
          ${c.own || S.me.is_admin ? html`<button data-act="del" data-i="${i}">${icon("trash")}<span>&nbsp;</span></button>` : ""}
        </div></section>`)}</div>`);
    const feed = el.querySelector(".clip-feed");
    const viewed = new Set();
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        const v = e.target.querySelector("video");
        if (e.isIntersecting && e.intersectionRatio > 0.6) {
          v.preload = "auto"; v.play().catch(() => {});
          const c = list[+e.target.dataset.i];
          if (!viewed.has(c.id)) { viewed.add(c.id); api(`/api/clips/${c.id}/view`, { method: "POST" }).catch(() => {}); }
          const next = e.target.nextElementSibling?.querySelector("video"); if (next) next.preload = "auto";
        } else v.pause();
      });
    }, { root: feed, threshold: [0, 0.6, 1] });
    el.querySelectorAll(".clip-slide").forEach((s) => io.observe(s));
    requestAnimationFrame(() => { feed.scrollTop = start * feed.clientHeight; });
    const off = on(el, {
      back: pop,
      toggle: (v) => { v.paused ? v.play() : v.pause(); },
      who: (b) => b.dataset.id && openPerson(+b.dataset.id),
      like: async (b) => {
        const c = list[+b.dataset.i];
        haptic.tap();
        try { const r = await api(`/api/clips/${c.id}/like`, { method: "POST" }); c.liked = r.liked; c.likes = r.likes; b.classList.toggle("liked", r.liked); b.querySelector("span").textContent = r.likes; }
        catch (e) { fail(e); }
      },
      share: (b) => {
        const c = list[+b.dataset.i];
        const url = location.origin + c.video;
        navigator.clipboard?.writeText(url).then(() => toast("Ссылка на клип скопирована", "ok")).catch(() => toast(url));
      },
      del: async (b) => {
        const c = list[+b.dataset.i];
        if (!(await confirmSheet("Удалить клип?", "Насовсем.", "удалить", true))) return;
        try { await api(`/api/clips/${c.id}`, { method: "DELETE" }); toast("Удалено"); pop(); onChange?.(); } catch (e) { fail(e); }
      },
    });
    return () => { off(); io.disconnect(); el.querySelectorAll("video").forEach((v) => { v.pause(); v.removeAttribute("src"); v.load(); }); };
  });
}

function uploadSheet(done) {
  sheet((el, close) => {
    let file = null, busy = false;
    const draw = () => {
      const cap = el.querySelector("#cc")?.value || "";
      mount(el, html`<h2 class="h2" style="margin-bottom:6px">новый клип</h2>
        <p class="muted small" style="margin:0 0 14px">mp4 или webm до 40 МБ — хайлайт, эйс, фейл, смешной момент. Игра: ${gameBadge(S.game)}</p>
        <label class="photo-slot" style="aspect-ratio:16/9;cursor:pointer;margin-bottom:14px">
          ${file ? html`<video src="${URL.createObjectURL(file)}" muted playsinline autoplay loop style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"></video>`
            : html`<div class="center">${icon("plus", 'width="28" height="28"')}<div class="small">выбрать видео</div></div>`}
          <input type="file" accept="video/mp4,video/webm,video/quicktime" hidden id="cf"></label>
        <div class="field"><label>подпись</label><input class="input" id="cc" maxlength="200" value="${cap}" placeholder="Эйс на Арли в последние секунды"></div>
        <button class="btn wide" data-act="go" ${!file || busy ? "disabled" : ""}>${busy ? "загружаю…" : "опубликовать"}</button>`);
      el.querySelector("#cf").addEventListener("change", (e) => {
        const f = e.target.files[0]; if (!f) return;
        if (f.size > 40 * 1024 * 1024) return toast("Больше 40 МБ — обрежь покороче", "err");
        file = f; draw();
      });
    };
    draw();
    on(el, {
      go: async () => {
        const fd = new FormData();
        fd.append("file", file); fd.append("caption", el.querySelector("#cc").value); fd.append("game", S.game);
        busy = true; draw();
        try { await api("/api/clips", { method: "POST", form: fd }); haptic.ok(); toast("Клип опубликован!", "ok"); close(); done?.(); }
        catch (e) { busy = false; draw(); fail(e); }
      },
    });
  });
}
