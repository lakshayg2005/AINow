# AINow

A weekly AI newsletter, written by an automated pipeline and reviewed by an
editor before it goes out. It reads ~20 sources (lab blogs, research feeds,
Hugging Face, GitHub, Hacker News, AI news outlets), groups articles into
stories, writes each newsletter section grounded only in what those sources
say, checks its own numbers and images, and never repeats a story from an
earlier issue except as a genuine update.

Every text call uses free-tier LLMs (Groq, Cerebras, Gemini, OpenRouter,
Hugging Face, or a local Ollama model), tried in that order, with an
extractive fallback if none are reachable — no paid API is required to run
it.

## Features

- **Continuous ingestion** — RSS, scraped pages, Hugging Face (papers, trending
  models/spaces), Hacker News and GitHub, deduplicated and merged by canonical
  URL.
- **Story clustering** — articles about the same launch or paper are merged
  into one story (embedding similarity + named-entity keys), then scored by
  importance, community buzz, source coverage and recency.
- **Grounded composition** — each section (Quick News, Research Spotlight,
  Paper of the Week, Deep Dive, Trends, Concept, Resources, Our Take,
  Sources) is written from retrieved source text only; sentences with
  numbers not found in the sources are stripped; every card cites its
  sources.
- **Freshness memory** — published stories are recorded so future issues
  only bring them back as an explicit update, never a repeat.
- **Image and quality checks** — card images are downloaded and measured to
  reject broken links, logos and headshots; a free-LLM editor review scores
  each draft and lists concrete fixes before it's published.
- **Interactive web + email** — issues render as an interactive page on the
  site and as a responsive HTML email with a plain-text part and one-click
  unsubscribe (RFC 8058).
- **Admin newsroom** (`/admin`) — trigger ingestion and drafting as
  background jobs, preview, re-check, test-send, publish and track delivery,
  all from the browser.
- **Archive search** — past issues are searchable by meaning (embeddings)
  and by exact name.
- **Optional scheduler** — runs ingestion and weekly drafting in-process; off
  by default, and never auto-publishes unless explicitly enabled.

## Architecture

```
ainow-backend/    FastAPI + PostgreSQL (pgvector) + SQLAlchemy 2
  app/ingest/      fetch, filter, enrich, chunk + embed sources
  app/stories/     cluster, score, triage, track freshness
  app/compose/     select stories, retrieve context (RAG), write sections,
                   verify, check images, review, persist
  app/services/    email delivery, archive search, publishing
  app/routes/      auth, subscriptions, newsletters, admin API
  app/jobs.py      background pipeline jobs (ingest/compose/deliver)
  app/scheduler.py optional in-process scheduler

ainow-frontend/   React 19 + Vite + Tailwind v4
  src/pages/        Home, Newsletters (archive + search), Newsletter detail,
                     Dashboard, Admin (Newsroom), auth pages
  src/components/   issue/ (interactive newsletter view), Navbar, Footer
```

Two loops run independently:

1. **Ingest loop** — fetch → filter → enrich → upsert → chunk/embed → cluster
   into stories → triage (LLM importance) → score.
2. **Compose loop** — select stories per section → retrieve grounded context
   (RAG over story chunks) → write each section → verify numbers → editorial
   pass → renumber sources → check images → review → save draft.

Both can run from the CLI (`python -m app.ingest`, `python -m app.compose`)
or as background jobs started from `/admin`.

## Getting started

### Prerequisites

- Python 3.13, Node 18+
- PostgreSQL with the [pgvector](https://github.com/pgvector/pgvector)
  extension (`CREATE EXTENSION vector;`)
- At least one free LLM API key (Groq's free tier is the easiest —
  [console.groq.com](https://console.groq.com))

### Backend

```bash
cd ainow-backend
python -m venv venv
venv\Scripts\activate        # venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env         # fill in DATABASE_URL, JWT_SECRET_KEY, GROQ_API_KEY, SMTP_*
uvicorn app.main:app --reload
```

Tables and columns are created/patched automatically on startup
(`app/db/schema_patches.py` — there's no separate migration step yet).

Make your account an admin so you can reach `/admin`:

```bash
python -m app.admin make-admin you@example.com
```

### Frontend

```bash
cd ainow-frontend
npm install
cp .env.example .env   # set VITE_API_URL if the backend isn't on 127.0.0.1:8000
npm run dev
```

### Run the pipeline

```bash
# from ainow-backend, with venv active
python -m app.ingest              # fetch + cluster (add --no-stories to skip clustering)
python -m app.compose              # compose + save a draft (--dry-run, --refresh, --out, --json)
```

Or trigger both as background jobs from **Fetch latest news** / **Generate
new draft** in `/admin`, then preview, re-check, test-send and publish from
there.

### Tests

```bash
cd ainow-backend
pytest -q
```

## Configuration

See [`ainow-backend/.env.example`](ainow-backend/.env.example) and
[`ainow-frontend/.env.example`](ainow-frontend/.env.example) for every
setting, including the scheduler, SMTP/Brevo and the free-LLM provider chain.

## Deployment (free tier)

Phase 1 — get it running on the internet on free plans throughout. All
pieces are independent, so this order works but isn't required.

**1. Database — [Supabase](https://supabase.com) (hosted Postgres, pgvector
   built in)**
1. Create a project (pick a region close to wherever the backend ends up).
2. **Project Settings → Database → Connection string**, choose the
   **Transaction pooler** (port 6543) — recommended over the direct
   connection since the app opens many short-lived connections.
3. Set it as `DATABASE_URL`, changing the scheme to
   `postgresql+psycopg://...` and keeping (or adding) `?sslmode=require`.
4. Nothing else to run by hand — `CREATE EXTENSION vector` and every table
   are created automatically the first time the backend starts.

[Neon](https://neon.tech) works just as well and is set up the same way
(pooled connection string, same `postgresql+psycopg://...?sslmode=require`
format) if you'd rather use that instead.

**2. Backend — [Render](https://render.com) (Docker web service, free tier)**
1. New → Web Service → connect this repo.
2. Root directory: `ainow-backend`. Runtime: **Docker** (uses the
   [`Dockerfile`](ainow-backend/Dockerfile) here). Plan: Free.
3. Health check path: `/health`.
4. Add every variable from
   [`.env.example`](ainow-backend/.env.example) as an environment variable —
   at minimum `DATABASE_URL`, `JWT_SECRET_KEY` (a long random string),
   `HF_TOKEN`, `GROQ_API_KEY`, `EMAIL_FROM` + `BREVO_API_KEY` (or the
   `SMTP_*` vars), `FRONTEND_URL` (step 3's URL) and `API_URL` (this
   service's own URL — Render shows it after the first deploy; add it and
   redeploy). Leave `SCHEDULER_ENABLED=false` (see step 5).
5. Deploy. The free tier sleeps after 15 minutes idle — the first request
   after a sleep takes ~30–50s to wake it, which is fine for a weekly
   newsletter and is exactly what the GitHub Actions workflow in step 5
   accounts for.
6. Make your account an admin from a shell with `DATABASE_URL` pointed at
   Supabase: `python -m app.admin make-admin you@example.com`.

Railway is a fine alternative to Render if you'd rather use it — same
Dockerfile, just check its current free-tier terms, which change more often
than Render's.

> **Resume/portfolio tip:** Render's and Netlify's free plans are completely
> normal to link from a resume — plenty of real projects run on them. The
> one thing worth knowing: after 15 minutes with no visitors, Render puts
> the backend to sleep, so if a recruiter's first click is the very first
> visitor in a while, the page can take ~30–50s to load before it feels
> instant. A free uptime pinger (e.g. [cron-job.org](https://cron-job.org),
> UptimeRobot) hitting `<your-backend>/health` every ~10 minutes keeps it
> awake if that matters to you — or just visit the site yourself a couple
> of minutes before showing anyone.

**3. Frontend — [Netlify](https://netlify.com)**
1. New site from Git → this repo. Base directory: `ainow-frontend`. Build
   command: `npm run build`. Publish directory: `ainow-frontend/dist`.
2. Environment variable: `VITE_API_URL` = the Render backend URL from step
   2. [`public/_redirects`](ainow-frontend/public/_redirects) is already in
   place so client-side routes (e.g. `/newsletters/12`) don't 404 on
   refresh.
3. Deploy, then go back to Render and set `FRONTEND_URL` to this Netlify
   URL if you hadn't already.

**4. Email — [Brevo](https://www.brevo.com) (free, 300/day)**
1. Create an account, then verify your sender address under **Senders,
   Domains & Dedicated IPs → Senders** (a confirmation email, no domain
   needed).
2. Create an API key (**SMTP & API → API Keys**) and set it as
   `BREVO_API_KEY` on Render. `get_email_provider()` picks Brevo
   automatically whenever that's set; Gmail SMTP (`SMTP_*`) is only used as
   a fallback if it's unset.

**5. Automation — GitHub Actions**
Render's free tier can't run the in-process scheduler reliably (it sleeps,
and the scheduler needs one always-on worker), so
[`.github/workflows/pipeline.yml`](.github/workflows/pipeline.yml) calls the
same `/admin/jobs/ingest` and `/admin/jobs/compose` endpoints on a schedule
instead — a plain HTTP request, so it wakes a sleeping backend on its own,
and it works the same way whether the backend runs on one instance or many.
1. Mint a token: `python -m app.admin create-token you@example.com`.
2. In the GitHub repo, add two **Actions secrets**: `API_URL` (the Render
   URL) and `ADMIN_TOKEN` (the token just printed).
3. That's it — it fetches news every 6 hours and drafts a new issue every
   Sunday. `auto_publish` stays off, so drafts still wait for you to
   review and publish them from `/admin`. Run it once by hand from the
   repo's **Actions** tab (**Run workflow**) to check it end to end.

### Phase 2 (later): scaling

Nothing above blocks this. A few notes for when it's needed:
- The scheduler is already off the critical path (step 5 uses HTTP calls,
  not in-process state), so the backend can run as multiple instances
  behind a load balancer without any change to how jobs are triggered.
- Rate limiting fits as ordinary FastAPI middleware (e.g. `slowapi`) in
  front of the existing routes.
- Neon supports read replicas and native Postgres partitioning if the
  `raw_items`/`item_chunks` tables get large; sharding would be a bigger
  change and isn't a near-term need at newsletter scale.
- A cache (Redis) would sit in front of the read-heavy public endpoints
  (`/newsletters`, `/newsletters/search`) first, since those get the most
  traffic and change only weekly.

## License

No license file yet — all rights reserved by the author.
