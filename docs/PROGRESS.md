# Progress

Run: 2026-11-23 overnight — days 1–3 straight through (user request). Day 4 (web + screenshots) not started.

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
- [ ] TransferTask/TransferQueue/TransferController upload + download
- [ ] Drag files in -> upload; drag rows out -> download
- [ ] SyncPlanner + FolderWatcher + SyncController

## Log
- Day 1 done: 19 tests green, committed (da79eb9). Demo users (FakeSupabase): alice@example.com / alice123, bob@example.com / bob123.
- Day 2 done: desktop shell (login dialog, table, hideable columns, sort A-Z/Z-A, filter, preview, delete+confirm). Tests 1 & 2 green. Run: `LITEDRIVE_FAKE_SUPABASE=1 .venv/Scripts/python -m uvicorn server.app:app` then `.venv/Scripts/python -m client_desktop`.
