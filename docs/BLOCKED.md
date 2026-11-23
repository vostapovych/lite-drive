# Blocked / needs your input

Items here did not stop the run; work continued on independent tasks.

## B1 — Render + Supabase deploy needs you (not blocking code work)
I can't create accounts/projects or hold your keys. Follow `docs/DEPLOY.md` (Supabase SQL, 2 users, Render service, 4 env vars).
Until then everything runs offline against FakeSupabase. HttpSupabase is written per current Supabase docs but **untested against a real project** — please run a login/upload/download once after deploying and tell me about any failure.

## B2 — browser upload to real Supabase Storage is unverified
The web client PUTs the raw file body (with `Content-Type` and `x-upsert: true`) to the signed upload URL, same as the desktop. supabase-js itself sends multipart FormData to that endpoint; I believe raw bodies are accepted but could not check without a live project, and cross-origin PUT also depends on Storage CORS allowing `x-upsert`. If the browser upload fails after deploying while the desktop one works, that is the place to look (switch `uploadOne` in client_web/static/app.js to FormData with a `file` field).
