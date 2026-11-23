# Deploy: Supabase project + Render (free tier)

## A. Supabase (one-time)
1. supabase.com -> **New project** (any region near you; save the DB password).
2. **SQL Editor -> New query**, paste `docs/supabase.sql`, **Run**. This creates the `files` table and the private `drive` bucket.
3. **Authentication -> Users -> Add user -> Create new user**: create 2 test users (tick *Auto Confirm User*), e.g. `alice@example.com` and `bob@example.com`.
4. **Project Settings -> API Keys**:
   - copy the **Publishable key** (`sb_publishable_...`)
   - on the *Secret keys* tab copy / create a **secret key** (`sb_secret_...`)
   - **Project Settings -> API -> Project URL** (`https://xxxx.supabase.co`)
   Do NOT use the legacy `anon` / `service_role` keys.

## B. GitHub
Push this repo to GitHub (`.env` is gitignored; never commit keys).

## C. Render
1. render.com -> **New + -> Web Service** -> connect GitHub -> pick the repo.
2. Settings: **Runtime** Python 3 | **Branch** main | **Instance type** Free
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn server.app:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path:** `/healthz`
3. **Environment -> Add Environment Variable** (all four; leave LITEDRIVE_FAKE_SUPABASE unset):

| Key | Value |
|---|---|
| `PYTHON_VERSION` | `3.12.1` |
| `SUPABASE_URL` | `https://xxxx.supabase.co` |
| `SUPABASE_PUBLISHABLE_KEY` | `sb_publishable_...` |
| `SUPABASE_SECRET_KEY` | `sb_secret_...` |
| `SUPABASE_BUCKET` | `drive` |

4. **Create Web Service**. When it is live open `https://<name>.onrender.com/healthz` -> `{"status":"ok"}`, and `/docs` for the API.
5. Web client: open `https://<name>.onrender.com/` (same service; this is the public URL for the Stage 3 bonus).
6. Desktop client: enter `https://<name>.onrender.com` as the server URL in the login dialog.

## Notes for the report
- Free services **sleep after 15 min idle**; the first request afterwards is a **cold start (~30-60 s)**. Hit `/healthz` before a demo.
- Render's filesystem is **ephemeral**: the server never writes uploads to disk. Bytes go straight client <-> Supabase Storage via signed URLs.
- Secrets live only in Render env vars and a local gitignored `.env`.
