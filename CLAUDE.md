# Lite Drive — working notes for Claude

University lab, Stages 2–4: one FastAPI server, a PySide6 desktop client, a Jinja2+HTMX web client.
Grading: Stage 2 desktop (13 + 5 bonus drag-and-drop), Stage 3 web (13 + 5 bonus public URL), Stage 4 comparison (2).
Correctness and a clean demo beat extras. Progress log: `docs/PROGRESS.md`. Open questions: `docs/BLOCKED.md`.

## Stack
Python 3.12 · FastAPI + Pydantic v2 + Uvicorn · Supabase (Auth, Postgres via PostgREST, Storage) over httpx ·
PySide6 + httpx + watchdog (desktop) · Jinja2 + HTMX (web, same FastAPI app) · pytest.

## Layout
- `server/` — FastAPI app (`server.app:app`), services, Supabase client (+ FakeSupabase)
- `client_desktop/` — PySide6 app (`python -m client_desktop`)
- `client_web/` — templates/static + page routes mounted on the same app (Day 4)
- `tests/` — pytest, headless (`QT_QPA_PLATFORM=offscreen`, `LITEDRIVE_FAKE_SUPABASE=1` set in conftest)
- `docs/` — PROGRESS, BLOCKED, COMPARISON-NOTES, DEPLOY, supabase.sql; `tools/` — screenshot scripts

Requirements are split: `requirements.txt` (server+web, what Render installs), `requirements-desktop.txt`, `requirements-dev.txt`.

## Approved design (stage 1) — do not redesign
- Desktop: DriveWindow, LoginDialog(exec, onSubmit), FileTableView(filesDropped, rowsDraggedOut), PreviewPane(show, render),
  FileListController(refresh, delete), SyncController(bind, synchronise), TransferController(upload, download),
  TransferQueue(submit), TransferTask(run), SyncPlanner(plan(binding, local, remote)), FolderWatcher(scan, start, changed),
  SessionStore(save, bearer, clear), ApiClient(login, logout, listFiles, requestUpload, commit, downloadUrl, fetch, delete),
  NameTypeProxyModel(lessThan, filterAcceptsRow), ViewSettings.
- Server: AuthRouter, FilesRouter, TransfersRouter -> AuthService(login, verify, logout), FileService(list, reserve, commit, delete),
  TransferService(uploadUrl, downloadUrl) -> SupabaseClient(signIn, verifyJwt, signUpload, signDownload, removeObject, userNames);
  CurrentUser.resolve; FileRow (table) vs FileOut (response).
- Routes: POST /auth/login, GET /files, POST /uploads, POST /files/{id}/commit, GET /files/{id}/download-url, DELETE /files/{id}.
  (+ POST /auth/logout, GET /healthz.) Web pages get their own page routes but NO special API endpoints.

## Hard rules
- File bytes go client <-> Storage via signed URL, never through FastAPI. Two-phase upload: reserve, PUT, commit.
- Owner always comes from the verified token, never from the request body. Every query filters by owner.
- SyncPlanner is pure (no I/O). Newer modifiedAt wins, equal -> SKIP, NEVER delete. After download set local mtime = server value.
- Sort/filter is client-side (QSortFilterProxyModel / in-page JS), never server query params.
- Supabase: NEW keys only. `sb_publishable_...` for client-facing calls (sign-in, /auth/v1/user), `sb_secret_...` server-side only,
  both sent in the `apikey` header (not as Bearer). Token verification: JWKS `/auth/v1/.well-known/jwks.json`, fallback `/auth/v1/user`.
- Secrets only in `.env` (gitignored) and Render env vars. Never write uploads to local disk on the server (Render FS is ephemeral).
- `LITEDRIVE_FAKE_SUPABASE=1` -> in-memory FakeSupabase; signed URLs point at the dev-only `/_fake_storage/...` mount.

## Working style
- Don't read files you don't need; read ranges, not whole files.
- After each milestone: `.venv/Scripts/python -m pytest -q`, update `docs/PROGRESS.md`, commit.
- Append Stage 4 observations to `docs/COMPARISON-NOTES.md` as they come up.
