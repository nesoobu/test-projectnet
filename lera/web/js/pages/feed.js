import { S, api, html, mount, on, icon, avatar, nameEl, ago, sheet, leraSays, fail, toast, haptic, safeUrl, confirmSheet, pushScreen } from "../core.js";
import { openPerson } from "./person.js";

export async function uploadImage(file) {
  const fd = new FormData();
  fd.append("file", file);
  return (await api("/api/upload", { method: "POST", form: fd })).url;
}

export function postHtml(p) {
  return html`<article class="post" data-pid="${p.id}">
    <div class="row">
      <button data-act="who" data-id="${p.author?.tg_id}">${avatar(p.author, 40, { online: true })}</button>
      <div class="grow"><b>${nameEl(p.author)}</b>${p.author?.title ? html` <span class="tag" style="margin-left:4px">${p.author.title}</span>` : ""}
        <div class="small muted mono">${ago(p.created_at)}</div></div>
      ${p.own || S.me.is_admin ? html`<button class="ibtn" style="background:none;width:32px;height:32px" data-act="del" data-id="${p.id}">${icon("trash", 'width="17" height="17"')}</button>` : ""}
    </div>
    <p class="txt">${p.text}</p>
    ${safeUrl(p.image) ? html`<div class="img"><img src="${safeUrl(p.image)}" alt="" loading="lazy"></div>` : ""}
    <div class="bar">
      <button class="${p.liked ? "liked" : ""}" data-act="like" data-id="${p.id}">${icon("heart")}<span>${p.likes || ""}</span></button>
      <button data-act="comments" data-id="${p.id}">${icon("chat")}<span>${p.comments || ""}</span></button>
    </div>
  </article>`;
}

export function render(root) {
  let tab = "new", posts = [], end = false, loading = false;
  mount(root, html`<div class="top"><div><div class="kicker">// что на линиях</div><h1 class="h1" style="margin-top:6px">лента<i>.</i></h1></div></div>
    <div class="pad" style="margin-bottom:12px"><div class="seg" id="seg"></div></div>
    <button class="compose-card" data-act="compose">${avatar(S.me, 36)}<span class="grow">Что нового? Хайлайт, мысль, поиск пати…</span>${icon("image", 'width="20" height="20"')}</button>
    <div id="posts"></div><div id="more"></div>`);
  const box = root.querySelector("#posts"), more = root.querySelector("#more");

  const drawSeg = () => mount(root.querySelector("#seg"), html`
    <button class="${tab === "new" ? "on" : ""}" data-act="tab" data-t="new">Свежее</button>
    <button class="${tab === "top" ? "on" : ""}" data-act="tab" data-t="top">Топ недели</button>`);

  async function load(reset = true) {
    if (loading) return;
    loading = true;
    if (reset) { posts = []; end = false; mount(box, html`<div class="spinner"></div>`); }
    try {
      const before = !reset && posts.length ? posts[posts.length - 1].id : 0;
      const r = await api(`/api/feed?top=${tab === "top" ? 1 : 0}&before=${tab === "top" ? 0 : before}`);
      posts = reset ? r.posts : posts.concat(r.posts);
      end = r.posts.length < 20 || tab === "top";
    } catch (e) { fail(e); }
    loading = false;
    draw();
  }

  function draw() {
    drawSeg();
    if (!posts.length) {
      mount(box, html`<div class="empty"><h2 class="h2">пока тихо<span class="dot">.</span></h2>${leraSays("Напиши первый пост — я лично лайкну. Ну, мысленно.")}</div>`);
    } else mount(box, posts.map(postHtml));
    mount(more, end ? html`<div class="sp"></div>` : html`<div class="pad" style="padding:16px"><button class="btn ghost wide" data-act="more">ещё</button></div>`);
  }

  const off = on(root, {
    tab: (b) => { tab = b.dataset.t; haptic.sel(); load(); },
    more: () => load(false),
    compose: () => composeSheet((p) => { posts.unshift(p); draw(); }),
    ...postActions(() => posts, (fn) => { posts = fn(posts); draw(); }),
  });
  load();
  return off;
}

export function postActions(getPosts, update) {
  return {
    who: (b) => b.dataset.id && openPerson(+b.dataset.id),
    like: async (b) => {
      const id = +b.dataset.id;
      haptic.tap();
      try {
        const r = await api(`/api/feed/${id}/like`, { method: "POST" });
        update((ps) => ps.map((p) => p.id === id ? { ...p, liked: r.liked, likes: r.likes } : p));
      } catch (e) { fail(e); }
    },
    comments: (b) => openComments(+b.dataset.id, (n) => update((ps) => ps.map((p) => p.id === +b.dataset.id ? { ...p, comments: n } : p))),
    del: async (b) => {
      if (!(await confirmSheet("Удалить пост?", "Вместе с лайками и комментариями.", "удалить", true))) return;
      try { await api(`/api/feed/${b.dataset.id}`, { method: "DELETE" }); update((ps) => ps.filter((p) => p.id !== +b.dataset.id)); } catch (e) { fail(e); }
    },
  };
}

function composeSheet(done) {
  let image = null, busy = false;
  sheet((el, close) => {
    const draw = () => {
      const t = el.querySelector("#tx")?.value || "";
      mount(el, html`<div class="row" style="margin-bottom:14px">${avatar(S.me, 40)}<b class="grow">${nameEl(S.me)}</b></div>
        <textarea class="input" id="tx" maxlength="1500" placeholder="Что нового?" style="min-height:140px">${t}</textarea>
        ${image ? html`<div class="post" style="padding:0;border:0"><div class="img" style="position:relative"><img src="${safeUrl(image)}" alt="">
          <button class="ibtn" data-act="rm" style="position:absolute;top:8px;right:8px;background:rgba(0,0,0,.7)">${icon("x")}</button></div></div>` : ""}
        <div class="row" style="margin-top:14px">
          <label class="ibtn" style="cursor:pointer">${icon("image")}<input type="file" accept="image/*" id="file" hidden></label>
          <span class="grow"></span>
          <button class="btn" data-act="post" ${busy ? "disabled" : ""}>опубликовать</button></div>`);
      el.querySelector("#file").addEventListener("change", async (e) => {
        const f = e.target.files[0]; if (!f) return;
        busy = true; draw();
        try { image = await uploadImage(f); } catch (err) { fail(err); }
        busy = false; draw();
      });
    };
    draw();
    setTimeout(() => el.querySelector("#tx")?.focus(), 300);
    on(el, {
      rm: () => { image = null; draw(); },
      post: async () => {
        const text = el.querySelector("#tx").value.trim();
        if (!text) return toast("Напиши что-нибудь", "err");
        try { const p = await api("/api/feed", { method: "POST", body: { text, image } }); haptic.ok(); close(); done(p); } catch (e) { fail(e); }
      },
    });
  });
}

export function openComments(pid, onCount) {
  pushScreen((el, pop) => {
    let post = null, list = [];
    mount(el, html`<div class="backbar"><button class="ibtn" data-act="back">${icon("back")}</button><h2 class="h2">обсуждение</h2></div>
      <div id="post"></div><div class="pad" id="cm"></div>
      <div class="composer" style="position:sticky;bottom:0"><textarea id="ta" rows="1" placeholder="Комментарий…" maxlength="1000"></textarea>
        <button class="ibtn send" data-act="send">${icon("send")}</button></div>`);
    const draw = () => {
      if (post) mount(el.querySelector("#post"), postHtml(post));
      mount(el.querySelector("#cm"), list.length ? html`<div class="list">${list.map((c) => html`<div class="li" style="align-items:flex-start">
          <button data-act="who" data-id="${c.author?.tg_id}">${avatar(c.author, 34)}</button>
          <div class="grow"><div class="row"><b class="small">${nameEl(c.author)}</b><span class="small muted mono">${ago(c.created_at)}</span></div>
          <div style="white-space:pre-wrap;word-wrap:break-word;margin-top:2px">${c.text}</div></div></div>`)}</div>`
        : html`<p class="muted center" style="padding:24px 0">Комментариев пока нет. Будь первым.</p>`);
    };
    (async () => {
      try {
        const [feed, cm] = await Promise.all([api(`/api/feed?before=${pid + 1}`), api(`/api/feed/${pid}/comments`)]);
        post = feed.posts.find((p) => p.id === pid) || null;
        list = cm.comments;
        if (!post) { toast("Пост удалён", "err"); return pop(); }
        draw();
      } catch (e) { fail(e); }
    })();
    const ta = el.querySelector("#ta");
    return on(el, {
      back: pop,
      ...postActions(() => (post ? [post] : []), (fn) => { const r = fn(post ? [post] : []); post = r[0] || null; if (!post) pop(); else draw(); }),
      comments: () => ta.focus(),
      send: async () => {
        const text = ta.value.trim(); if (!text) return;
        ta.value = "";
        try { const c = await api(`/api/feed/${pid}/comments`, { method: "POST", body: { text } }); list.push(c); if (post) post.comments = list.length; onCount?.(list.length); draw(); el.scrollTop = el.scrollHeight; }
        catch (e) { fail(e); ta.value = text; }
      },
    });
  });
}
