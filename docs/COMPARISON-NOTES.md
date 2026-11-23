# Stage 4 comparison notes (appended as we go)

## Shared / reusable
- One REST API serves both clients; the web client gets no special endpoints.
- Server-side isolation (owner from verified token) protects both clients equally.

## Desktop (PySide6) — what the GUI technology forced
- **Threading**: Qt widgets live on the GUI thread, so every HTTP call runs on a QThreadPool worker and results return via queued signals (`workers.run_async`). A blocking login would freeze the window — and a sleeping Render server takes up to ~60 s to wake, so this is visible, not theoretical.
- **State lives in the client**: the bearer token is held in memory (SessionStore), view prefs (hidden columns, filter) in QSettings, the file list in a QAbstractTableModel. The browser equivalent is cookie/localStorage + the DOM.
- **Sort/filter** are free with QSortFilterProxyModel (`lessThan`, `filterAcceptsRow`) — the model/view split makes "client-side" natural; the source model is never reordered.
- **Preview** needs the bytes: signed URL -> `fetch` -> QPlainTextEdit / QPixmap. Stale results (user clicked another file) must be discarded by name check.
- **Relative signed URLs** (FakeSupabase dev mount) have to be joined with the base URL in ApiClient; real Supabase URLs are absolute.

## Desktop — transfers, drag-and-drop, sync
- **Local filesystem is the whole point of sync**: scanning a folder, reading/writing bytes, and `os.utime` to set a downloaded file's mtime to the server's value are things only the desktop client can do. A browser has no folder access, so Stage 3 has no sync (File System Access API is Chromium-only and needs a user gesture per session; out of scope).
- **Transfers**: reserve -> PUT signed URL -> commit on a QThreadPool (3 workers); the GUI thread only sees queued signals. The browser can do the same PUT with `fetch`, but cannot read a path — it only gets File objects the user picked/dropped.
- **Drag-in** is a few lines (`dropEvent` + local URLs). **Drag-out** is the awkward direction: QDrag needs real files *before* the drag starts, so rows are downloaded synchronously to a temp dir inside `startDrag` (blocking, fine for small files). A browser can only do this for a single file via the non-standard `DownloadURL` drag type (Chromium).
- **Change detection**: watchdog runs on its own thread; events are marshalled to the GUI thread through a signal and debounced (700 ms) so a half-written file isn't uploaded. Downloads write files, which re-trigger the watcher -> converges because equal mtimes plan SKIP.
- **Reusable across clients**: the REST API, server isolation, signed-URL flow, and the *rules* in SyncPlanner/preview mapping. Not reusable: all Qt code. The web client re-implements sort/filter/preview in JS.
- **Testing**: Qt offscreen + a real uvicorn thread over the in-memory fake made the whole GUI testable without network; the one thing not testable headless is the OS-level QDrag.exec (we test the data it is given).

## Web (Jinja2 + HTMX) — what the browser forced
- **Same API, no special endpoints**: pages are plain HTML shells (`/`, `/login`); `tests/test_web_pages.py` asserts the OpenAPI paths are exactly the desktop's. Consequence: the REST API returns JSON, so **HTMX cannot swap server-rendered fragments of user data** (that would need new HTML endpoints). HTMX is used for the request lifecycle (load/refresh triggers, loading indicator, bearer header via `htmx:configRequest`) and ~300 lines of vanilla JS render the JSON. An honest finding for Stage 4: HTMX shines with HTML-returning endpoints; against a JSON API it adds little.
- **State lives in the page**: token in `sessionStorage` (per tab, readable by any script on the origin = XSS exposure; the desktop keeps it in process memory), hidden columns in `localStorage`, file list/selection/sort/filter in a JS object + DOM. Reload keeps the login, closing the tab drops it.
- **Sort/filter/preview** had to be re-implemented in JS (`toLowerCase` compare vs Python `casefold`, `extOf` vs `posixpath.splitext`) — logic is not shared with the desktop, only specified identically; both are covered by tests (pytest for Qt, Playwright for the browser).
- **Transfers**: the browser does the same reserve -> PUT signed URL -> commit with `fetch`, in parallel via `Promise.allSettled`, no thread pool needed. Cross-origin to real Supabase it depends on Storage's CORS (needs `x-upsert` header allowed); same-origin with the fake it just works. Download is an `<a download>` click; the cross-origin `download` attribute is ignored, so the signed URL carries `&download=<name>` for Content-Disposition.
- **Drag-and-drop in** is cheap (`dragenter/over/drop` + `dataTransfer.files`, skip directories via `webkitGetAsEntry`). **Drag-out** to the desktop is not feasible portably. **Folder sync is impossible** (no local folder access).
- **Native `<dialog>`** gives an accessible modal confirmation for free; Qt needs a QMessageBox and an injectable hook to test it.
- **Bug class unique to the web**: `.preview img {display:block}` overrode the `hidden` attribute, so a stale image stayed visible behind “Preview unavailable” — found by the Playwright test, fixed with `[hidden]{display:none!important}`.
- **Testing cost**: Playwright + a Chromium download (~150 MB) vs Qt offscreen needing nothing extra; but Qt offscreen has no fonts, so screenshots need a real display, while headless Chromium renders text fine.
- **Public URL (bonus)**: the web client is served by the same Render service, so deploying the server publishes the web UI too; free-tier cold start (~30-60 s) is visible on the login page.
