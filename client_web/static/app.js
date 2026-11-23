// Lite Drive web client. Talks to the same REST API as the desktop client (Bearer token).
// Sort / filter / preview-kind run in the page, mirroring the desktop's proxy model and preview mapping.
(() => {
  "use strict";
  const COLUMNS = [
    { key: "name", title: "Name" },
    { key: "createdAt", title: "Created" },
    { key: "modifiedAt", title: "Modified" },
    { key: "uploadedBy", title: "Uploaded by" },
    { key: "lastEditedBy", title: "Last edited by" },
  ];
  const $ = (id) => document.getElementById(id);
  const store = (area, k, v) => { try { return v === undefined ? area.getItem(k) : area.setItem(k, v); } catch (_) { return null; } };
  const token = () => store(sessionStorage, "litedrive.token");
  if (!token()) { location.replace("/login"); return; }

  const state = {
    files: [], selected: new Set(), order: "asc", filter: "all",
    hidden: new Set(JSON.parse(store(localStorage, "litedrive.hidden") || "[]").filter((k) => k !== "name")),
    previewSeq: 0,
  };

  // ---------- API ----------
  class ApiError extends Error { constructor(status, msg) { super(msg); this.status = status; } }
  function signOut() { store(sessionStorage, "litedrive.token", ""); try { sessionStorage.clear(); } catch (_) {} location.replace("/login"); }
  async function api(path, opts = {}) {
    const r = await fetch(path, { ...opts, headers: { ...(opts.headers || {}), Authorization: `Bearer ${token()}` } });
    if (r.status === 401) { signOut(); throw new ApiError(401, "Session expired"); }
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new ApiError(r.status, body.detail || `Request failed (${r.status})`);
    }
    return r.status === 204 ? null : r.json();
  }
  const abs = (url) => new URL(url, location.origin).toString();

  // ---------- pure helpers (same rules as the desktop) ----------
  const extOf = (name) => { const i = name.lastIndexOf("."); return i > 0 ? name.slice(i).toLowerCase() : ""; };
  const previewKind = (name) => ({ ".js": "text", ".png": "image" })[extOf(name)] || "unavailable";
  const cmpName = (a, b) => {
    const x = a.name.toLowerCase(), y = b.name.toLowerCase();
    return x < y ? -1 : x > y ? 1 : a.name < b.name ? -1 : a.name > b.name ? 1 : 0;
  };
  const visibleFiles = () => {
    let list = state.filter === "cpp_png" ? state.files.filter((f) => [".cpp", ".png"].includes(extOf(f.name))) : state.files.slice();
    list.sort(cmpName);
    if (state.order === "desc") list.reverse();
    return list;
  };
  const pad = (n) => String(n).padStart(2, "0");
  const fmtDate = (iso) => { const d = new Date(iso); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  window.__liteDrive = { previewKind, cmpName, extOf, state };  // for tests / debugging

  // ---------- rendering ----------
  function setStatus(text) { $("status").textContent = text; }
  function renderHead() {
    const tr = $("head-row"); tr.replaceChildren();
    for (const c of COLUMNS) {
      if (state.hidden.has(c.key)) continue;
      const th = document.createElement("th");
      th.textContent = c.title;
      th.dataset.col = c.key;
      if (c.key === "name") {
        th.classList.add("sortable");
        th.textContent = c.title + (state.order === "asc" ? " ▲" : " ▼");
        th.addEventListener("click", () => setOrder(state.order === "asc" ? "desc" : "asc"));
      }
      tr.appendChild(th);
    }
  }
  function renderRows() {
    const tbody = $("rows"); tbody.replaceChildren();
    const list = visibleFiles();
    for (const f of list) {
      const tr = document.createElement("tr");
      tr.dataset.id = f.id;
      if (state.selected.has(f.id)) tr.classList.add("selected");
      for (const c of COLUMNS) {
        if (state.hidden.has(c.key)) continue;
        const td = document.createElement("td");
        td.textContent = c.key === "createdAt" || c.key === "modifiedAt" ? fmtDate(f[c.key]) : f[c.key];
        tr.appendChild(td);
      }
      tr.addEventListener("click", (ev) => selectRow(f, ev.ctrlKey || ev.metaKey));
      tbody.appendChild(tr);
    }
    $("empty").hidden = list.length > 0;
    const sel = state.selected.size;
    $("btn-download").disabled = $("btn-delete").disabled = sel === 0;
    setStatus(`${list.length} of ${state.files.length} file(s) shown`);
  }
  function renderControls() {
    $("sort-asc").setAttribute("aria-pressed", String(state.order === "asc"));
    $("sort-desc").setAttribute("aria-pressed", String(state.order === "desc"));
    $("filter").value = state.filter;
  }
  function renderAll() { renderHead(); renderRows(); renderControls(); }

  function buildColumnsMenu() {
    const box = $("columns-list"); box.replaceChildren();
    for (const c of COLUMNS) {
      const label = document.createElement("label");
      const cb = document.createElement("input");
      cb.type = "checkbox"; cb.checked = !state.hidden.has(c.key); cb.disabled = c.key === "name"; cb.dataset.col = c.key;
      cb.addEventListener("change", () => {
        if (cb.checked) state.hidden.delete(c.key); else state.hidden.add(c.key);
        store(localStorage, "litedrive.hidden", JSON.stringify([...state.hidden]));
        renderAll();
      });
      label.append(cb, document.createTextNode(c.title));
      box.appendChild(label);
    }
  }

  // ---------- actions ----------
  function setOrder(o) { state.order = o; renderAll(); }
  function selectRow(f, additive) {
    if (additive) { state.selected.has(f.id) ? state.selected.delete(f.id) : state.selected.add(f.id); }
    else state.selected = new Set([f.id]);
    renderRows();
    if (state.selected.size === 1 && state.selected.has(f.id)) showPreview(f); else if (!state.selected.size) clearPreview();
  }
  const selectedFiles = () => state.files.filter((f) => state.selected.has(f.id));

  function clearPreview(msg = "Select a file to preview") {
    $("preview-text").hidden = true; $("preview-image").hidden = true;
    $("preview-image").removeAttribute("src");
    const m = $("preview-message"); m.textContent = msg; m.hidden = false;
  }
  async function showPreview(f) {
    const seq = ++state.previewSeq;
    const kind = previewKind(f.name);
    if (kind === "unavailable") return clearPreview("Preview unavailable");
    clearPreview("Loading…");
    try {
      const { url } = await api(`/files/${encodeURIComponent(f.id)}/download-url`);
      if (kind === "text") {
        const r = await fetch(abs(url)); if (!r.ok) throw new Error(`Download failed (${r.status})`);
        const text = await r.text();
        if (seq !== state.previewSeq) return;
        $("preview-text").textContent = text; $("preview-text").hidden = false; $("preview-message").hidden = true; $("preview-image").hidden = true;
      } else {
        const img = $("preview-image");
        img.onload = () => { if (seq === state.previewSeq) { img.hidden = false; $("preview-message").hidden = true; $("preview-text").hidden = true; } };
        img.onerror = () => { if (seq === state.previewSeq) clearPreview("Image could not be loaded"); };
        img.alt = f.name; img.src = abs(url);
      }
    } catch (e) { if (seq === state.previewSeq) clearPreview(`Preview failed: ${e.message}`); }
  }

  async function download() {
    for (const f of selectedFiles()) {
      try {
        const { url, name } = await api(`/files/${encodeURIComponent(f.id)}/download-url`);
        const a = document.createElement("a");
        a.href = abs(url); a.download = name; a.rel = "noopener";
        document.body.appendChild(a); a.click(); a.remove();
        setStatus(`Downloading ${name}…`);
        await new Promise((r) => setTimeout(r, 250));
      } catch (e) { setStatus(`Download failed: ${e.message}`); }
    }
  }

  function confirmDelete(text) {
    const dlg = $("confirm-dialog");
    $("confirm-text").textContent = text;
    return new Promise((resolve) => {
      dlg.addEventListener("close", () => resolve(dlg.returnValue === "ok"), { once: true });
      dlg.returnValue = "cancel"; dlg.showModal();
    });
  }
  async function remove() {
    const files = selectedFiles();
    if (!files.length) return;
    const text = files.length === 1 ? `Delete “${files[0].name}” from your drive? This cannot be undone.` : `Delete ${files.length} files from your drive? This cannot be undone.`;
    if (!(await confirmDelete(text))) return;
    const results = await Promise.allSettled(files.map((f) => api(`/files/${encodeURIComponent(f.id)}`, { method: "DELETE" })));
    const failed = results.filter((r) => r.status === "rejected").length;
    state.selected.clear(); clearPreview();
    await refresh(failed ? `Deleted ${files.length - failed}, ${failed} failed` : `Deleted ${files.map((f) => f.name).join(", ")}`);
  }

  async function uploadOne(file) {
    const r = await api("/uploads", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: file.name, size: file.size }) });
    // bytes go straight to Storage via the signed URL, never through the API
    const put = await fetch(abs(r.uploadUrl), { method: "PUT", body: file, headers: { "Content-Type": file.type || "application/octet-stream", "x-upsert": "true" } });
    if (!put.ok) throw new Error(`Storage rejected ${file.name} (${put.status})`);
    await api(`/files/${encodeURIComponent(r.fileId)}/commit`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ size: file.size }) });
  }
  async function upload(fileList) {
    const files = [...fileList];
    if (!files.length) return;
    setStatus(`Uploading ${files.length} file(s)…`);
    const results = await Promise.allSettled(files.map(uploadOne));
    const failed = results.filter((r) => r.status === "rejected");
    await refresh(failed.length ? `Upload: ${files.length - failed.length} ok, ${failed.length} failed (${failed[0].reason.message})` : `Uploaded ${files.length} file(s)`);
  }

  function applyList(rows, msg) {
    state.files = rows;
    const ids = new Set(rows.map((r) => r.id));
    state.selected = new Set([...state.selected].filter((id) => ids.has(id)));
    renderAll();
    if (msg) setStatus(`${$("status").textContent}   |   ${msg}`);
  }
  // refresh() asks HTMX to re-run the #loader request; htmx:afterRequest below renders the JSON
  let pendingMsg = "";
  function refresh(msg = "") {
    pendingMsg = msg;
    return new Promise((resolve) => { refreshDone = resolve; htmx.trigger(document.body, "refresh"); });
  }
  let refreshDone = null;

  // ---------- HTMX wiring: bearer header + JSON -> state ----------
  document.body.addEventListener("htmx:configRequest", (ev) => { ev.detail.headers["Authorization"] = `Bearer ${token()}`; });
  document.body.addEventListener("htmx:afterRequest", (ev) => {
    if (ev.detail.elt.id !== "loader") return;
    const xhr = ev.detail.xhr;
    if (xhr.status === 401) return signOut();
    if (ev.detail.successful) {
      try { applyList(JSON.parse(xhr.responseText), pendingMsg); } catch (e) { setStatus(`Bad response: ${e.message}`); }
    } else setStatus(`Error loading files (${xhr.status || "network"})`);
    pendingMsg = "";
    if (refreshDone) { refreshDone(); refreshDone = null; }
  });

  // ---------- events ----------
  $("whoami").textContent = store(sessionStorage, "litedrive.email") || "";
  $("logout").addEventListener("click", async () => { try { await api("/auth/logout", { method: "POST" }); } catch (_) {} signOut(); });
  $("btn-refresh").addEventListener("click", () => refresh("Refreshed"));
  $("btn-upload").addEventListener("click", () => $("file-input").click());
  $("file-input").addEventListener("change", (e) => { upload(e.target.files); e.target.value = ""; });
  $("btn-download").addEventListener("click", download);
  $("btn-delete").addEventListener("click", remove);
  $("sort-asc").addEventListener("click", () => setOrder("asc"));
  $("sort-desc").addEventListener("click", () => setOrder("desc"));
  $("filter").addEventListener("change", (e) => { state.filter = e.target.value; renderAll(); });

  const dz = $("dropzone");
  let depth = 0;
  const hasFiles = (e) => e.dataTransfer && [...e.dataTransfer.types].includes("Files");
  dz.addEventListener("dragenter", (e) => { if (hasFiles(e)) { e.preventDefault(); depth++; dz.classList.add("dragover"); } });
  dz.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
  dz.addEventListener("dragleave", () => { if (--depth <= 0) { depth = 0; dz.classList.remove("dragover"); } });
  dz.addEventListener("drop", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault(); depth = 0; dz.classList.remove("dragover");
    const files = [...e.dataTransfer.files].filter((f, i) => {
      const entry = e.dataTransfer.items[i] && e.dataTransfer.items[i].webkitGetAsEntry && e.dataTransfer.items[i].webkitGetAsEntry();
      return !(entry && entry.isDirectory);  // flat drive: skip folders
    });
    upload(files);
  });

  buildColumnsMenu();
  renderAll();
})();
