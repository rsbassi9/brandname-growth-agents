# Brandname Growth Agents

Local-first growth studio for BRAND NAME / brandnamedesign.co. The app creates review-ready marketing assets, campaign plans, calendar items, video prompt packs, voiceover scripts, source-photo-grounded image prompts, manual Meta ad briefs, read-only SEO suggestions, performance insights, repurpose drafts, and weekly standups without auto-publishing or spending ad budget.

## Current App

The active product is the FastAPI backend in `app/` plus the React studio in `frontend/`.

```text
React Studio (frontend/)
  -> /api/v1 FastAPI app (app/main.py)
    -> SQLite data/app.db via SQLAlchemy models
    -> in-process job queue for generation/workflow jobs
    -> Brand Brain retrieval memory + immutable brand profile versions
    -> local-only deterministic generation by default in tests/dev gates
    -> optional OpenAI-compatible provider through BRAND_OPENAI_BASE_URL
    -> optional Google Drive, Shopify read-only, and ElevenLabs helpers
```

Legacy data folders remain as source material:

```text
agent_instructions/   agent prompts used by live providers
brand_context/        brand and strategy context
memory/               legacy calendar/feedback import source
outputs/              generated output archive and new local artifacts
fonts/                local typography assets
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env
cd frontend
npm ci
```

## Run Locally

Backend:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --port 8765
```

Frontend dev server:

```powershell
cd frontend
npm run dev
```

Open the Vite URL shown in the terminal. For a built single-server preview:

```powershell
cd frontend
npm run build
cd ..
python -m uvicorn app.main:app --reload --port 8765
```

Then open `http://127.0.0.1:8765`.

## Core Workflows

- Playground: generate copy, image concept prompt packs, carousels, video scripts, voiceovers, and source-grounded takes. Every generated version records memory evidence when Brand Brain context is used.
- Library: filter assets, inspect immutable versions, select takes, critique/iterate versions, generate video prompt packs, and index source photos.
- Campaigns: create campaigns and launch scoped generation shortcuts.
- Calendar and Feed Grid: plan and reorder manual publishing work, drag drafts from the unscheduled tray, use suggested best-time slots, and see soft guardrail warnings.
- Ads & SEO: create structured `ad_brief` assets for manual Meta Ads Manager entry, run read-only Shopify SEO audits, generate paste-ready `seo_fix` assets, and create `seo_plan` keyword/content maps. No Meta API integration or Shopify write path is included.
- Strategy Hub: read strategy context and brand profile versions, plan work, ship draft copy manually, import performance CSVs, link posts to calendar items, review dashboard insights, submit feedback into the learning loop, and review weekly standups.
- Repurposing: `repurpose_shoot` turns 1-10 indexed source assets into a campaign with copy, reel script, story copy, ad brief, and product refresh drafts; failed child draft assets can be retried individually.
- Recycling: an off-by-default monthly job drafts unscheduled remixes from top-quartile older posts. It never auto-schedules.
- Weekly Standup: an off-by-default weekly job writes `standup_reports`; the Learn lane shows what published, top/bottom performer, next week's plan, and exactly three recommendation actions that create draft tray assets.
- System: configure and run local daily workflow jobs, brand profile distillation cadence, recycling cadence, weekly standup cadence, and calendar guardrails.

For section-by-section operating instructions, see `docs/USER_GUIDE.md`.

## Environment Variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `BRAND_DATABASE_URL` | SQLAlchemy database URL. | `sqlite:///data/app.db` |
| `DATA_DIR` | Runtime data root for SQLite, backups, and generated files. | `data/` |
| `LOCAL_ONLY_AGENT_RUNS` | Blocks paid/provider calls and uses deterministic local generation paths. | `false` |
| `BRAND_NAME` | Brand label shown in prompts/UI. | `BRAND NAME` |
| `BRAND_SHOPIFY_URL` | Store URL included in prompts. | `brandnamedesign.co` |
| `BRAND_MODEL_DEFAULT` | Default text model for live provider calls. | provider default |
| `BRAND_MODEL_PREMIUM` | Optional premium model when the UI toggle is enabled. | empty |
| `BRAND_OPENAI_API_KEY` / `OPENAI_API_KEY` | API key for OpenAI-compatible providers. | empty |
| `BRAND_OPENAI_BASE_URL` | OpenAI-compatible base URL, e.g. NVIDIA NIM/Ollama gateway. | empty |
| `BRAND_EMBED_MODEL` | Embedding model for Brand Brain when not in local-only mode. | provider default |
| `GOOGLE_DRIVE_ENABLED` | Enables read-only Drive inventory/indexing when auth is configured. | `false` |
| `GOOGLE_DRIVE_ROOT_FOLDER_ID` | Drive root folder for raw content inventory. | empty |
| `GOOGLE_AUTH_MODE` | `oauth` or `service_account`. | `oauth` |
| `GOOGLE_OAUTH_CLIENT_FILE` | OAuth client JSON path. | `oauth_client.json` |
| `GOOGLE_OAUTH_TOKEN_FILE` | OAuth token JSON path. | `token.json` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Service account credential path. | empty |
| `SHOPIFY_STORE_DOMAIN` | Shopify store domain for read-only previews/image indexing. | empty |
| `SHOPIFY_ADMIN_ACCESS_TOKEN` | Shopify Admin token. | empty |
| `SHOPIFY_WRITE_ENABLED` | Enables future write helpers; keep false unless explicitly needed. | `false` |
| `BRAND_TTS_PROVIDER` | Set to `elevenlabs` to enable voiceover MP3 synthesis. | empty |
| `BRAND_ELEVENLABS_API_KEY` | ElevenLabs API key. | empty |
| `BRAND_ELEVENLABS_VOICE_ID` | Optional ElevenLabs voice id. | default voice |
| `BACKUP_ENABLED` | Enables nightly SQLite backup loop. | `false` |

Secrets stay local and gitignored. Do not commit `.env`, OAuth tokens, or API keys.

## Data And Migration

Initialize/import legacy data:

```powershell
python -m app.services.migrate_legacy
```

Index local source photos:

```powershell
python -m app.services.source_assets local --path "C:\path\to\photoshoot" --tag drop-one
```

Run one daily workflow job from the CLI:

```powershell
python -m app.services.jobs run_daily_workflow
```

Backfill Brand Brain memory:

```powershell
python -m app.services.brain backfill
```

Run one scheduled job kind from the CLI:

```powershell
python -m app.services.jobs distill_brand_profile
python -m app.services.jobs recycle_top_posts
python -m app.services.jobs weekly_standup
```

Import performance data from the UI:

```text
Strategy Hub -> Learn -> Performance -> upload or paste a Meta Business Suite / TikTok Studio CSV.
```

Use cadence controls from the UI:

```text
System -> daily workflow, brand profile distillation, recycling, weekly standup, and calendar guardrails.
```

All cadence settings are stored in `settings_kv` and are off by default unless explicitly enabled.

## Verification

Backend:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

Frontend:

```powershell
cd frontend
npm run type-check
npm test
npm run build
```

UI token compliance scan:

```powershell
rg "#[0-9a-fA-F]{3,8}|box-shadow|linear-gradient" frontend/src -g "*.tsx" -g "*.css"
```

The scan should return no matches.

## Deployment Note

The old `src.dashboard` app, static mirror, GitHub Pages artifacts, and Render blueprint have been removed in P5. Deploy the active app as a normal FastAPI service serving `frontend/dist` after `npm run build`, with persistent storage for `DATA_DIR`.
