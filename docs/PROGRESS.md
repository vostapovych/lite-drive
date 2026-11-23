# Progress

Run: 2026-11-23 overnight — days 1–3 straight through (user request). Day 4 (web + screenshots) done.

## Day 1 — server + tests + Render
- [x] Repo skeleton, requirements, CLAUDE.md, docs
- [x] Server against FakeSupabase (all six routes + logout + healthz)
- [x] Real Supabase client (HttpSupabase) per current docs — UNTESTED against a live project (see BLOCKED B1)
- [x] Tests 3, 4, 5 green
- [x] render.yaml + docs/DEPLOY.md written; actual deploy = user action (BLOCKED B1)

## Day 2 — desktop GUI shell
- [x] ApiClient, SessionStore, LoginDialog
- [x] Table with 5 columns, hideable except Name (ViewSettings)
- [x] NameTypeProxyModel sort A–Z/Z–A + filter All / .cpp+.png; tests 1, 2 green
- [x] PreviewPane (.js text, .png image, else "Preview unavailable")
- [x] Delete with confirmation

## Day 3 — transfers, drag-and-drop, sync
- [x] TransferTask/TransferQueue/TransferController upload + download
- [x] Drag files in -> upload; drag rows out -> download
- [x] SyncPlanner + FolderWatcher + SyncController

## Log
- Day 1 done: 19 tests green, committed (da79eb9). Demo users (FakeSupabase): alice@example.com / alice123, bob@example.com / bob123.
- Day 2 done: desktop shell (login dialog, table, hideable columns, sort A-Z/Z-A, filter, preview, delete+confirm). Tests 1 & 2 green. Run: `LITEDRIVE_FAKE_SUPABASE=1 .venv/Scripts/python -m uvicorn server.app:app` then `.venv/Scripts/python -m client_desktop`.
- Day 3 done: upload/download (signed URLs, 3-worker pool), drag files in -> upload, drag rows out -> temp-dir download + QDrag, folder bind + watchdog auto-sync + Sync now. 41 tests green.

## What to check (manual, needs a display)
1. `.venv/Scripts/python -m uvicorn server.app:app` with `LITEDRIVE_FAKE_SUPABASE=1` (PowerShell: `$env:LITEDRIVE_FAKE_SUPABASE=1`), then `.venv/Scripts/python -m client_desktop`; log in as alice@example.com / alice123.
2. **Real drag-out to Explorer** is the only thing automated tests can't cover (QDrag.exec blocks headless) — try dragging a row onto the desktop.
3. Real Supabase path (`HttpSupabase`) has never run against a live project: do docs/DEPLOY.md, then log in/upload/download once.
4. Stage 4 report text is not written (notes only, in docs/COMPARISON-NOTES.md).

## Day 4 — web client + screenshots
- [x] Web client: Jinja2 page routes (`/`, `/login`) + vendored HTMX on the same app; no new API endpoints (test asserts it)
- [x] Login, list, hideable columns, sort A-Z/Z-A, filter, preview (.js/.png/other), upload (button + drag-and-drop), download, delete with confirm. No folder sync (browser limitation — say so in the Stage 3 report)
- [x] Playwright e2e tests (tests/test_web_e2e.py, skipped if Chromium is missing); found+fixed a real `hidden` CSS bug
- [x] `tools/make_screenshots.py` -> screenshots/desktop (19 shots), `tools/make_web_screenshots.py` -> screenshots/web (18 shots); each folder has a generated README index
- Fixed while screenshotting: desktop status bar lost the Upload/Sync/Delete result because the follow-up refresh overwrote it; date columns were truncated.
- Desktop shots need a real display (`--offscreen` Qt has no fonts -> text renders as boxes; the flag exists but is not for report images).
- 52 tests green (`pytest`); web e2e needs `playwright install chromium`.
