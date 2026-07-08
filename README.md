# Brandname Growth Agents

Local-first growth studio for BRAND NAME / brandnamedesign.co. The app creates review-ready marketing assets, campaign plans, calendar items, video prompt packs, voiceover scripts, source-photo-grounded image prompts, and manual Meta ad briefs without auto-publishing or spending ad budget.

## Current App

The active product is the FastAPI backend in `app/` plus the React studio in `frontend/`.

```text
React Studio (frontend/)
  -> /api/v1 FastAPI app (app/main.py)
    -> SQLite data/app.db via SQLAlchemy models
    -> in-process job queue for generation/workflow jobs
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

- Playground: generate copy, image concept prompt packs, carousels, video scripts, voiceovers, and source-grounded takes.
- Library: filter assets, inspect immutable versions, select takes, critique/iterate versions, generate video prompt packs, and index source photos.
- Campaigns: create campaigns and launch scoped generation shortcuts.
- Calendar and Feed Grid: plan and reorder manual publishing work.
- Ads: create structured `ad_brief` assets with copy blocks for manual Meta Ads Manager entry. No Meta API integration is included.
- Strategy Hub: read strategy context, plan work, and submit feedback into the learning loop.
- System: configure and run local daily workflow jobs.

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
