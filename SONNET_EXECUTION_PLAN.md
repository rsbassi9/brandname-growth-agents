# SONNET_EXECUTION_PLAN.md — brandname-growth-agents

**Prepared by:** Claude Fable 5 (full audit performed 2026-07-06: static review + live smoke test of the dashboard server in a Linux sandbox).
**Executor:** Claude Sonnet. This document is your ONLY source of truth. Follow it exactly, phase by phase, in order.

## EXECUTION STATUS (updated 2026-07-07 by Codex)

- ✅ **P0 COMPLETE** — commits `2f106e4` (P0-1 key rotation doc), `ad9b15e` (P0-2 dotenv fix), `61539ba` (P0-3 log cleanup), `afe75a1` (checkpoint), `146747f` (P0-5 tooling). GATE P0 passed.
- ✅ **P1 COMPLETE** — commit `e497450`: full `app/` backend (models, versioned `/api/v1` API, async job queue, legacy migration, ported services with defect fixes, two-tier model config incl. `BRAND_OPENAI_BASE_URL` for NVIDIA NIM/Ollama, nightly backup). **GATE P1 verified:** 47/47 tests pass; `uvicorn app.main:app` boots with no env vars, `/api/v1/system/health` → 200; migration idempotent (17 calendar items / 43 feedback events / 271 assets / 271 versions on both runs).
- ▶️ **P2 IN PROGRESS** — commits `c9b9511` (P2-1 React/Vite/Tailwind studio shell, fixed navigation, typed API client, React Query setup, job drawer, placeholder route surfaces, shell test), `073808d` (P2-2 Playground generate flow: typed form, persisted defaults, `/api/v1/generate`, SSE progress, result preview, session history, mocked flow test), `11c588d` (P2-3 Library filters, paginated/infinite loading, asset detail drawer, all-version compare, select-version, regenerate job progress, mocked filter/select test), and `7273eb7` (P2-4 Campaigns list/create/detail, grouped campaign assets, and Playground shortcut prefill). **Verified after P2-4:** `npm test` (4/4), `npm run build`, and backend `.venv\Scripts\python.exe -m pytest -q` (47/47) pass.
- **NEXT: P2-5** Calendar and Feed Grid against the new API. Then P2-6 → P6 in order.

---

## 0. BINDING RULES — READ FIRST, RE-READ EVERY PHASE

1. **Execute phases strictly in order (P0 → P6).** Never start a phase until the previous phase's Verification Gate passes.
2. **Do not invent scope.** If something seems missing or ambiguous, implement the literal instruction here and add a `TODO(fable-review):` comment. Do NOT design your own alternative.
3. **Never make paid external API calls** (OpenAI, Shopify, Google Drive) during development or tests. All tests must mock external clients. `LOCAL_ONLY_AGENT_RUNS=true` must be respected by EVERY execution path (see P1-4).
4. **Never print, copy, or commit secrets.** `.env`, `oauth_client.json`, `token.json` contain live credentials. They stay gitignored. Never echo their contents.
5. **No payments/billing features.** This is a single-user personal project. No auth beyond the existing optional basic-auth middleware.
6. **Preserve the prompt/context IP untouched:** `agent_instructions/*.md`, `brand_context/*.md`, `memory/*` contents are DATA, not code. Migrate/read them; never rewrite their prose.
7. **Commit discipline:** one commit per numbered task, message format `P<phase>-<task>: <summary>` (e.g. `P1-3: add SQLite models and migration for calendar items`). Run the phase's test command before every commit.
8. **Tech stack is fixed** (do not substitute): Python 3.11+/FastAPI/SQLAlchemy 2.x/SQLite/pytest; frontend React 18+ + Vite + TypeScript + Tailwind CSS + shadcn/ui + TanStack Query + React Router. Charting not required.
9. **Definition of Done for every task** = code + tests + Verification Gate command passing.

---

## 1. CURRENT STATE (verified by audit — trust this over the README)

- **Works:** `pip install -r requirements.txt` succeeds; `uvicorn src.dashboard:app` boots; `GET /`, `/healthz`, `/api/days`, `/api/calendar`, `/api/outputs` return 200 with real data. Path traversal is correctly blocked by `_safe_output_path` (src/dashboard.py:5274).
- **Backend:** `src/dashboard.py` is a 5,279-line god module with ~90 routes (calendar CRUD, feed grid, highlights, shoot planner, Shopify SEO, strategy hub, image QA/iterate, media proxy). Models, services, rendering, and auth all live in this one file.
- **Agents:** `src/agents.py` (33 lines) builds 10 `openai-agents` SDK agents from `agent_instructions/*.md`: orchestrator, content_strategist, content_creator, content_candidate, creative_composer, seo, analytics, ad_strategist, visual_designer, feed_curator. Plain prompt-in/text-out, no tools, no structured output.
- **Pipeline:** `python -m src.orchestrator` → `run_daily_workflow` (src/orchestrator.py:223) → `build_shared_context` (lines 57–115 concatenate ~15 context files into one mega-prompt) → sequential agent calls → markdown/PNG files in `outputs/`. GitHub Actions cron (`.github/workflows/daily-growth.yml`) runs it daily and commits outputs to git.
- **Frontend:** `dashboard/static/index.html` (433 lines) + `dashboard/static/app.js` (3,802 lines vanilla JS, 17 sidebar modes) + `styles.css`. No framework, no build.
- **State:** NO database. Flat JSON/JSONL in `memory/` (`content_calendar.json`, `feedback.jsonl`, `campaign_memory.json`, `product_truth.json`, visual metadata) with unlocked read-modify-write.
- **Known defects:** `src/settings.py:9` uses `load_dotenv(override=True)` (repo .env beats real env); `src/image_concepts.py:209` hardcodes `model="gpt-5.4-mini"`; `image_concepts.py:216-217` and `:250-251` swallow exceptions silently; `/api/run` (dashboard.py:993–1000) runs the multi-minute workflow synchronously inside a request via `asyncio.run`; `python -m src.orchestrator` ignores `LOCAL_ONLY_AGENT_RUNS`; zero tests; ~55 untracked + many modified files uncommitted; duplicated static apps in `pages/`, `site/`, `dashboard/static/`; stray logs (`local-dashboard.log`, `dashboard/*.log`) and `.cache/hosted-data-test/`.
- **Reusable, high-value modules (port, don't rewrite logic):** `src/image_concepts.py` (prompt engineering, product-truth constraints), `src/visual_renderer.py` + `src/visual_compositor.py` + `fonts/` (Pillow carousel rendering), `src/web.py` + `src/shopify_service.py` (Shopify catalog), `src/drive_service.py`, `src/learning.py` (feedback loop), `docs/strategy_hub_implementation_plan.md` (owner's vision: Know / Plan / Build / Ship Manually / Learn lanes, manual publishing, external prompt packs for fal.ai/Runway/Kling).

## 2. TARGET (what "ElevenLabs-grade" means here — from July 2026 product research)

The benchmark patterns to replicate, translated to marketing content:

| ElevenLabs pattern | This project's equivalent |
|---|---|
| Playground vs Studio Projects split | **Playground** (one-off generation: caption, image concept, carousel) vs **Campaigns** (multi-asset projects) |
| Per-paragraph generation history, restore/lock/compare takes | **Per-asset generation history**: every generation persisted, list takes, restore any, mark one as "selected" |
| Snapshot versioning | Immutable `asset_versions` rows; never overwrite a generation |
| Async convert job + poll/webhook | `POST /api/v1/generate` → job id → SSE progress → result |
| Voice/model panel with saved defaults | Model + brand-context + template picker panel, defaults persisted |
| Asset library ("mine vs explore") | **Library**: searchable, filterable (type/campaign/status/date) view of all generated assets |
| Multi-modal suite (TTS, music, SFX, video) | Copy, image concepts, rendered carousels, video scripts + prompt packs (muapi.ai primary; fal.ai/Runway/Kling secondary), optional TTS voiceover via ElevenLabs-compatible API stub (P5) |

**Owner directives (2026-07-06, binding):**
- The brand is **BRAND NAME** (streetwear), Shopify store: `https://www.brandnamedesign.co/`. Use these as setting defaults (`BRAND_NAME="BRAND NAME"`, `BRAND_SHOPIFY_URL="https://www.brandnamedesign.co/"`). Never hardcode either string outside settings defaults.
- Product mission: an **all-in-one marketing agent** — Meta ads suggestions, content creation (posts/reels/ads), and SEO optimization — that grounds generation in the owner's **raw photoshoots and product images** so output quality is campaign-ready.
- **Cost policy:** run as cheap as possible with the best achievable results. Free/cheap providers first: muapi.ai for image/video generation prompt packs, local LLMs (Ollama or any OpenAI-compatible endpoint) and NVIDIA NIM (`https://integrate.api.nvidia.com/v1`) for text. Higgsfield is explicitly EXCLUDED (too expensive). Implement a two-tier model config: `BRAND_MODEL_DEFAULT` (cheap/local) used everywhere by default, `BRAND_MODEL_PREMIUM` (optional) selectable per-generation in the UI ("Use premium model" toggle). All OpenAI-SDK calls go through one client wrapper honoring `BRAND_OPENAI_BASE_URL` + `BRAND_OPENAI_API_KEY`.

**Honest positioning (do not oversell in UI copy):** this project's *workflow* (brand context → strategy → calendar → asset → feedback learning) is deeper than ElevenLabs' per-asset flow; its *platform* (DB, jobs, history, UI polish) is what's being built here.

---

## PHASE P0 — Security & repo hygiene

**P0-1.** Create `docs/KEY_ROTATION.md` containing exactly: a checklist telling the owner to rotate the OpenAI API key in `.env`, the Google OAuth client secret in `oauth_client.json`, and to re-issue `token.json`; and that this must be done manually at platform.openai.com / console.cloud.google.com. Do NOT include any key material. Do not modify the secret files themselves.
**P0-2.** In `src/settings.py` line 9: change `load_dotenv(override=True)` → `load_dotenv(override=False)`.
**P0-3.** Delete from working tree and add to `.gitignore`: `local-dashboard.log`, `dashboard-server.err.log`, `dashboard-server.out.log`, `.cache/`, `dashboard/*.log`. Do not delete `outputs/` or `memory/`.
**P0-4.** Commit the entire current working tree first (`chore: checkpoint pre-refactor working state`) so nothing on disk is lost, THEN apply P0-1..P0-3 as separate commits.
**P0-5.** Add dev tooling: `pyproject.toml` with `ruff` config and `pytest` config (`testpaths = ["tests"]`), create empty `tests/` package, add `requirements-dev.txt` (pytest, pytest-asyncio, httpx, ruff).

**GATE P0:** `git status` clean; `ruff check src/` runs (warnings allowed, record count); `pytest` collects 0 tests without error.

## PHASE P1 — Backend re-architecture (new package `app/`, old code kept as reference)

Create a new package `app/` — do NOT delete `src/` until P6. Structure (exact):

```
app/
  main.py            # FastAPI factory, mounts routers, serves frontend build
  settings.py        # pydantic-settings; env prefix BRAND_; LOCAL_ONLY_AGENT_RUNS honored
  db.py              # SQLAlchemy engine/session, SQLite at data/app.db
  models.py          # ORM models (below)
  schemas.py         # Pydantic v2 request/response contracts
  services/
    agents.py        # port of src/agents.py agent construction
    generation.py    # generation service: copy, image concept, carousel render, video script
    images.py        # port of src/image_concepts.py — fix defects listed below
    rendering.py     # port of visual_renderer/visual_compositor
    shopify.py       # port of shopify_service/web.py
    drive.py         # port of drive_service.py
    learning.py      # port of learning.py feedback loop
    jobs.py          # job runner (below)
    migrate_legacy.py# one-shot importer: memory/*.json + outputs/ → DB
  routers/
    playground.py, campaigns.py, assets.py, calendar.py, feed.py,
    strategy.py, jobs.py, library.py, system.py
```

**ORM models (exact tables):** `campaigns` (id, name, goal, status, created_at); `assets` (id, campaign_id nullable, type enum: copy|image_concept|carousel|video_script|voiceover, title, status enum: draft|selected|archived, created_at); `asset_versions` (id, asset_id, version_no, prompt_snapshot TEXT, params_json, content_text nullable, file_path nullable, model_used, created_at, is_selected bool) — **immutable, never UPDATE content**; `calendar_items` (migrated from `memory/content_calendar.json`, keep all existing fields in a `data_json` column plus first-class id/date/status/asset_id); `feedback_events` (from `feedback.jsonl`); `jobs` (id, kind, status enum: queued|running|succeeded|failed, progress_pct, message, payload_json, result_json, created_at, finished_at); `settings_kv`.

**P1-1.** Implement `db.py`, `models.py`, `schemas.py`, plus `services/migrate_legacy.py` with CLI `python -m app.services.migrate_legacy` that imports `memory/content_calendar.json`, `memory/feedback.jsonl`, and indexes every file in `outputs/` into `assets`/`asset_versions` (type inferred from path/extension; one version each). Must be idempotent (re-run = no duplicates; use natural keys).
**P1-2.** Port `src/image_concepts.py` → `app/services/images.py` with these mandatory fixes: (a) model comes from settings `BRAND_IMAGE_MODEL` (default `"gpt-image-1"`), never hardcoded; (b) replace both silent exception blocks (old lines 216-217, 250-251) with `logger.exception(...)` + raised typed `GenerationError`; (c) all OpenAI calls behind a client wrapper that raises `LocalOnlyModeError` when `LOCAL_ONLY_AGENT_RUNS=true`.
**P1-3.** Port rendering, shopify, drive, learning, agents modules. Keep function signatures; change only imports/settings/error handling. Every broad `except Exception: pass` becomes log + raise or log + explicit fallback with a comment.
**P1-4.** `services/jobs.py`: an in-process async job queue — `asyncio.Queue` + single worker task started in FastAPI lifespan. API: `enqueue(kind, payload) -> job_id`; worker updates `jobs` row (progress/message); results written to DB. Job kinds: `generate_asset`, `run_daily_workflow`, `render_carousel`, `image_iterate`. The daily workflow job must check `LOCAL_ONLY_AGENT_RUNS` and use the deterministic fallback from `src/local_workflow.py` (port it) when true — this closes the defect where `python -m src.orchestrator` ignored the flag.
**P1-5.** Routers, versioned under `/api/v1`: 
- `POST /api/v1/generate` {type, campaign_id?, brief, params} → creates asset (if new) + enqueues job → `{job_id, asset_id}`.
- `GET /api/v1/jobs/{id}`, `GET /api/v1/jobs/{id}/events` (SSE: progress/message/completion).
- `GET /api/v1/assets` (filters: type, campaign_id, status, q, date range; paginated `?limit=&offset=`), `GET /api/v1/assets/{id}` (with versions), `POST /api/v1/assets/{id}/versions/{version_no}/select`, `POST /api/v1/assets/{id}/regenerate` (same params, new version).
- Calendar/feed/strategy routers: re-expose the legacy dashboard's calendar CRUD, feed-grid, and strategy-hub reads against the DB (port handler logic from `src/dashboard.py`, split by concern).
- `GET /api/v1/system/health`, `GET /api/v1/system/mode` (reports local-only flag).
**P1-6.** Tests (all external clients mocked): migration idempotency; generate→job→version happy path; regenerate creates version 2 and version 1 unchanged; select-version; asset filters; SSE emits completion; local-only mode blocks OpenAI wrapper; settings override defect stays fixed (env beats .env). Minimum 25 tests.

**GATE P1:** `pytest -q` all green; `uvicorn app.main:app` boots with NO env vars set; `curl /api/v1/system/health` → 200; `python -m app.services.migrate_legacy` run twice yields identical row counts.

## PHASE P2 — Frontend studio (new `frontend/` directory)

Scaffold: `npm create vite@latest frontend -- --template react-ts`, add Tailwind, shadcn/ui, React Router, TanStack Query. Dev proxy to `:8000`; production served by FastAPI from `frontend/dist`.

**Layout (fixed):** left sidebar nav — Playground, Campaigns, Library, Calendar, Feed Grid, Ads, Strategy Hub, System. Top bar: brand name, local-only-mode badge (amber when on), global job indicator (spinner + count of running jobs, click → job drawer).

**P2-0 (DESIGN SPEC — binding for all P2–P4 UI work).** Aesthetic: light editorial "gallery studio" — the photoshoots ARE the interface. Implement as CSS custom properties in `frontend/src/styles/tokens.css` and use ONLY tokens:
- Surfaces: white base, warm neutrals `#F1EFE8`/`#D3D1C7` for placeholders/chips, ink `#2C2C2A`; hairline 0.5px borders; generous whitespace (24px section padding minimum); radius 8–12px; no shadows/gradients.
- One accent: coral `#D85A30` (light fill `#FAECE7`, deep text `#4A1B0C`) — used ONLY for selection state and primary generation actions.
- Type: serif display face (self-hosted, from `fonts/`) for brand/campaign headings with letter-spacing; 12–13px sans UI text; uppercase 10px letter-spaced labels on imagery.
- Signature components: top bar with "Premium model" toggle (two-tier config from P1-8) + live job progress pill; Playground compose panel (asset-type chips, brief textarea, reference-photo attachment slots from source assets, dark ink Generate button); generation-history filmstrip (v1/v2/v3 takes, selected take coral-ringed with ✓); asset gallery in true aspect ratios (4:5, 9:16) with status badges; caption card with one-click copy; action row (muapi.ai prompt pack / Meta ad brief / Schedule).
- Latency rules (mandatory): skeletons matching final layout; optimistic mutations; SSE job progress streams into the pill and filmstrip without blocking; images lazy-loaded with intrinsic aspect boxes (zero layout shift); library grid virtualized past 60 items.
- Motion: 150ms ease-out on state changes only.

**P2-1.** App shell, routing, API client (typed from `schemas.py` shapes), job drawer with SSE subscription.
**P2-2.** **Playground**: left panel = input (type selector: Copy / Image Concept / Carousel / Video Script; brief textarea; params: model, tone, template; defaults persisted to localStorage) → Generate button → right panel = live progress then result preview (text rendered as styled card; images/carousels as gallery). Below: session history strip of this playground's generations, each restorable into the editor. This mirrors ElevenLabs' playground pattern exactly.
**P2-3.** **Library**: grid of assets, filter bar (type, status, campaign, search, date), infinite scroll on the paginated API; asset detail drawer showing ALL versions side-by-side with "Select this take" and "Regenerate" — the generation-history pattern. Selected version gets a badge.
**P2-4.** **Campaigns**: list + create; campaign detail = its assets grouped by type, plus "Generate in campaign" shortcut into Playground pre-filled.
**P2-5.** **Calendar** and **Feed Grid**: rebuild the two highest-value legacy modes against the new API — calendar month view with item CRUD + link to asset; feed grid = 3-column IG-style drag-to-reorder preview (persist order). Port behavior from `dashboard/static/app.js`, do not port its code.
**P2-6.** **Strategy Hub**: implement the five lanes from `docs/strategy_hub_implementation_plan.md` — Know / Plan / Build / Ship Manually / Learn — as tabbed read/write views over brand context (read-only render of `brand_context/*.md`), calendar plan, build queue (assets in draft), ship checklist (manual-publish checklist per selected asset incl. copy-to-clipboard caption + download image), and Learn (feedback form posting `feedback_events` + summary of `learning.py` insights).
**P2-7.** Frontend tests: vitest + testing-library; minimum: shell renders, playground generate flow with mocked API, library filter, version select. Add `npm run build` to CI expectations.

**GATE P2:** `npx tsc -b` clean; `npm run build` succeeds; `npm test` green; with backend running, manual smoke: generate a Copy asset in local-only mode end-to-end (uses deterministic fallback), see it appear in Library with version 1.

## PHASE P3 — Daily workflow & automation

**P3-1.** Move the daily pipeline in-app: APScheduler (or asyncio timer) in FastAPI lifespan enqueues `run_daily_workflow` at a configurable time (`settings_kv`), off by default. Outputs land in DB as assets, not as git commits.
**P3-2.** Rework `.github/workflows/daily-growth.yml`: keep the cron but make it call the orchestrator through the new job service in a one-shot mode (`python -m app.services.jobs run_daily_workflow`), and STOP committing `outputs/` back to the repo (delete the commit step, lines ~45–51). Outputs uploaded as workflow artifacts instead.
**P3-3.** Workflow run report page in System: list of past daily runs (jobs of kind `run_daily_workflow`) with per-step status and links to created assets.

**GATE P3:** trigger daily workflow from UI in local-only mode → completes, creates calendar items + assets; workflow YAML passes `actionlint` or at minimum valid YAML parse.

## PHASE P4 — Multi-modal expansion

**P4-1.** **Video prompt packs**: for a calendar item or asset, generate a structured pack (JSON + pretty view): hook, shot list, on-screen text, and ready-to-paste prompts formatted for **muapi.ai (primary)** plus fal.ai/Runway/Kling (secondary tabs) — external generation, manual paste, per `docs/strategy_hub_implementation_plan.md`. Do NOT integrate Higgsfield. New asset type `video_script` uses this.
**P4-2.** **Voiceover (stub-first)**: asset type `voiceover`: generate script via agents; if `BRAND_TTS_PROVIDER=elevenlabs` and `BRAND_ELEVENLABS_API_KEY` set, call ElevenLabs TTS REST (`POST /v1/text-to-speech/{voice_id}`), store MP3 as version file; otherwise store script-only version with status note "TTS not configured". Never call the API in tests.
**P4-3.** Image iterate/QA flow from legacy (`/api/calendar/{id}/qa`, iterate endpoints in old dashboard.py) rebuilt as: version → "Critique" (agent QA text stored on version) → "Iterate" (new version with critique folded into prompt). Wire into Library detail drawer.
**P4-4.** **Photoshoot ingestion & reference-grounded generation**: new table `source_assets` (id, origin enum: drive|local|shopify, path/url, tags_json, product_handle nullable, created_at). CLI + endpoint to index raw photoshoot folders (via existing `drive.py` service) and Shopify product images (via `shopify.py`). In Playground and image-generation flows, user can attach 1–4 source assets as reference images — pass them through the existing reference-image roles in the ported `images.py` prompt logic. Library gets a "Source photos" tab.
**P4-5.** **Ads workspace (Meta ads suggestions)**: page + router where the `ad_strategist` agent produces structured briefs (Pydantic schema: objective, audience, placement, hook, primary text ×3 variants, headline ×3, CTA, recommended creative = linked asset/source photo) stored as asset type `ad_brief`. Export as copy-to-clipboard blocks for manual entry into Meta Ads Manager. No Meta API integration (read or write) in this phase.

**GATE P4:** all flows pass tests with mocked providers; a `video_script`, a script-only `voiceover`, and an `ad_brief` asset can be created in local-only mode from the UI; a source photo can be indexed and attached as a reference.

## PHASE P5 — Cutover & cleanup

**P5-1.** Delete `src/dashboard.py`, `dashboard/` static app, `pages/`, `site/`, `run_dashboard.cmd`, `render.yaml` (hosting was for the old static mirror). Update README: new run instructions (`uvicorn app.main:app` + `cd frontend && npm run dev`), architecture diagram (text), env var table.
**P5-2.** Keep `src/` modules that P1 ported ONLY if `app/` still imports them; otherwise delete. `agent_instructions/`, `brand_context/`, `memory/` (now legacy data source), `outputs/`, `fonts/` all stay.
**P5-3.** Final sweep: `ruff check app/ --fix` clean; no `except Exception: pass` anywhere in `app/` (grep must return zero); no TODOs without `TODO(fable-review)` tag.

**GATE P5 (FINAL):** fresh clone simulation — `pip install -r requirements.txt -r requirements-dev.txt`, `pytest -q` green, `python -m app.services.migrate_legacy`, `uvicorn app.main:app` boots, `npm ci && npm run build && npm test` in `frontend/` green, and the local-only end-to-end generate flow works in a browser.

## PHASE P6 — Report

Write `docs/EXECUTION_REPORT.md`: table of every task P0-1 … P5-3 with commit hash and gate results; list of every `TODO(fable-review)`; anything you could not complete and exactly why. Do not mark this plan complete if any gate failed.
