# Progress

Run: 2026-11-23 overnight — days 1–3 straight through (user request). Day 4 (web + screenshots) not started.

## Day 1 — server + tests + Render
- [ ] Repo skeleton, requirements, CLAUDE.md, docs
- [ ] Server against FakeSupabase (all six routes)
- [ ] Real Supabase client (HttpSupabase) per current docs
- [ ] Tests 3, 4, 5 green
- [ ] render.yaml + docs/DEPLOY.md (actual deploy = user action, see BLOCKED.md)

## Day 2 — desktop GUI shell
- [ ] ApiClient, SessionStore, LoginDialog
- [ ] Table with 5 columns, hideable except Name (ViewSettings)
- [ ] NameTypeProxyModel sort A–Z/Z–A + filter All / .cpp+.png; tests 1, 2 green
- [ ] PreviewPane (.js text, .png image, else "Preview unavailable")
- [ ] Delete with confirmation

## Day 3 — transfers, drag-and-drop, sync
- [ ] TransferTask/TransferQueue/TransferController upload + download
- [ ] Drag files in -> upload; drag rows out -> download
- [ ] SyncPlanner + FolderWatcher + SyncController

## Log
