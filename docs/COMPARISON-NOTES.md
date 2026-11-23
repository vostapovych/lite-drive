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
