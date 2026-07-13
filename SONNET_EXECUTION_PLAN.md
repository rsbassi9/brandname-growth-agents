# SONNET_EXECUTION_PLAN.md — brandname-growth-agents

**Prepared by:** Claude Fable 5 (full audit performed 2026-07-06: static review + live smoke test of the dashboard server in a Linux sandbox).
**Executor:** Claude Sonnet. This document is your ONLY source of truth. Follow it exactly, phase by phase, in order.

## EXECUTION STATUS (updated 2026-07-08 by Codex)

- ✅ **P0 COMPLETE** — commits `2f106e4` (P0-1 key rotation doc), `ad9b15e` (P0-2 dotenv fix), `61539ba` (P0-3 log cleanup), `afe75a1` (checkpoint), `146747f` (P0-5 tooling). GATE P0 passed.
- ✅ **P1 COMPLETE** — commit `e497450`: full `app/` backend (models, versioned `/api/v1` API, async job queue, legacy migration, ported services with defect fixes, two-tier model config incl. `BRAND_OPENAI_BASE_URL` for NVIDIA NIM/Ollama, nightly backup). **GATE P1 verified:** 47/47 tests pass; `uvicorn app.main:app` boots with no env vars, `/api/v1/system/health` → 200; migration idempotent (17 calendar items / 43 feedback events / 271 assets / 271 versions on both runs).
- ✅ **P2-0 BINDING DESIGN SPEC ACTIVE** — all P2–P4 UI work must use `frontend/src/styles/tokens.css` first, then build components only from those CSS custom properties.
- ✅ **P2 COMPLETE** — commits `c9b9511` (P2-1 React/Vite/Tailwind studio shell, fixed navigation, typed API client, React Query setup, job drawer, placeholder route surfaces, shell test), `073808d` (P2-2 Playground generate flow: typed form, persisted defaults, `/api/v1/generate`, SSE progress, result preview, session history, mocked flow test), `11c588d` (P2-3 Library filters, paginated/infinite loading, asset detail drawer, all-version compare, select-version, regenerate job progress, mocked filter/select test), `7273eb7` (P2-4 Campaigns list/create/detail, grouped campaign assets, and Playground shortcut prefill), `24927d0` (P2-5 tokenized design layer, Calendar month CRUD, and Feed Grid reorder persistence), `5d837ec` (P2 UI compliance amendment: Ads nav/route, shell premium toggle, self-hosted token fonts, no-shadow drawers, coral selected states, Playground reference slots/filmstrip, Library aspect cards), `ca8c95d` (P2-6 Strategy Hub five lanes over context docs, calendar plan, draft build queue, manual ship checklist/caption card, and feedback learning form), and `b3852f7` (P2-7 frontend studio CI gate with `npm ci`, `npm run build`, `npm test`). **GATE P2 verified:** UI compliance scan clean, `npm test` (7/7), `npm run build`, backend `.venv\Scripts\python.exe -m pytest -q` (47/47), and live local-only smoke (`uvicorn app.main:app` on throwaway data dir → `POST /api/v1/generate` Copy → job succeeded → Library shows asset with version 1) pass.
- ✅ **P3-1 COMPLETE** — in-app daily workflow scheduler added via FastAPI lifespan asyncio timer, configurable in `settings_kv`, off by default, with System UI controls for enable/time/manual run. Local-only daily workflow outputs now persist into DB-backed draft assets with immutable version rows. **Verified:** backend pytest 51/51, `npm test` 8/8, UI compliance scan clean, `npm run build` pass.
- ✅ **P3-2 COMPLETE** — `.github/workflows/daily-growth.yml` now runs `python -m app.services.jobs run_daily_workflow`, uses read-only repo permissions, removes the generated-output commit/push step, and uploads `outputs/**` plus `data/app.db` as workflow artifacts. Added one-shot job CLI coverage and workflow regression checks. **Verified:** backend pytest 53/53; one-shot local-only CLI smoke passes with `GOOGLE_DRIVE_ENABLED=false`.
- ✅ **P3 COMPLETE** — P3-3 adds System workflow run reports backed by `jobs(kind=run_daily_workflow)`, parsed per-output steps, and Library links to created assets; Library now honors `?asset=<id>` deep links. Daily workflow persistence now also creates draft calendar items linked to generated assets. **GATE P3 verified:** live local-only System trigger on throwaway data dir completed, created 8 assets + 8 calendar items + 1 run report with 8 steps; backend pytest 53/53; `npm test` 8/8; UI compliance scan clean; `npm run build` pass.
- ✅ **P4-1 COMPLETE** — `video_script` now creates structured external video prompt packs with JSON + pretty UI; muapi.ai is the primary provider, with fal.ai, Runway, and Kling secondary tabs, and no Higgsfield integration. Packs can be generated from Playground, from an existing Library asset, or from a Calendar item; outputs remain manual-paste only. **Verified:** backend pytest 56/56; `npm test` 9/9; UI compliance scan clean; `npm run build` pass.
- ✅ **P4-2 COMPLETE** — `voiceover` is exposed in Playground and generates script-only versions in local/default mode with "TTS not configured" status notes. Optional ElevenLabs REST synthesis is gated behind `BRAND_TTS_PROVIDER=elevenlabs` + `BRAND_ELEVENLABS_API_KEY`, writes MP3 files under outputs, and is covered only with mocked HTTP in tests. Frontend test timeout is now explicit in `npm test` to keep the heavier UI suite stable. **Verified:** backend pytest 58/58; `npm test` 10/10; UI compliance scan clean; `npm run build` pass.
- ✅ **P4-3 COMPLETE** — Library versions can be critiqued, QA text is stored on version params, and Iterate queues a new immutable version with critique folded into the prompt. **Verified:** backend pytest 59/59; `npm test` 11/11; UI compliance scan clean; `npm run build` pass.
- ✅ **P4-4 COMPLETE** — added `source_assets` indexing for local folders, Drive, and Shopify image sources; Library now has a Source photos tab with local indexing; Playground can attach 1–4 indexed source assets as references; generation persists `source_asset_ids`, resolved `reference_paths`, and source context into immutable version params/prompts. **Verified:** backend pytest 62/62; `npm run type-check` pass; `npm test` 12/12; UI compliance scan clean; `npm run build` pass.
- ✅ **P4-5 COMPLETE** — Ads workspace now creates structured `ad_brief` assets through `/api/v1/ads/briefs` using the `ad_strategist` generation path. Briefs include objective, audience, placement, hook, 3 primary text variants, 3 headlines, CTA, recommended creative linked to a Library asset/source photo, and copy-to-clipboard export blocks for manual Meta Ads Manager entry. No Meta API integration was added. **Verified:** backend pytest 63/63; `npm run type-check` pass; `npm test` 13/13; UI compliance scan clean; `npm run build` pass.
- ✅ **GATE P4 COMPLETE** — full mocked-provider P4 flow set passes: `video_script`, script-only `voiceover`, `ad_brief`, Library critique/iterate, source photo indexing, and Playground reference attachment. **Verified:** backend pytest 63/63; `npm run type-check` pass; `npm test` 13/13; UI compliance scan clean; `npm run build` pass.
- ✅ **P5-1 COMPLETE** — removed the old `src/dashboard.py`, `dashboard/`, `pages/`, `site/`, `run_dashboard.cmd`, and `render.yaml` surfaces; README now documents the active `app.main:app` + `frontend/` studio, text architecture, env table, and verification commands. **Verified:** backend pytest 63/63 after deletion.
- ✅ **P5-2 COMPLETE** — pruned unused legacy-only `src/` modules after reference checks: `content_state`, `local_workflow`, `product_truth`, `shopify_service`, `strategy_memory`, `visual_compositor`, `visual_fingerprint`, and `visual_metadata`. Retained the `src.orchestrator` dependency island because `app.services.jobs` still imports it for the non-local live workflow fallback. **Verified:** backend compile/import sweep and pytest pass after deletion.
- ✅ **P5-3 COMPLETE** — `ruff check app --fix` is clean with the project FastAPI `Depends(...)` default rule exception recorded as `B008`; exact `except Exception: pass` scan in `app/` returns zero; untagged TODO scan returns zero outside this plan. Headless browser gate found and fixed a Playground saved-history crash (`D.map is not a function`) with a regression test. **Verified:** backend pytest 63/63; `npm test` 14/14.
- ✅ **GATE P5 COMPLETE** — dependency install, idempotent legacy migration, backend pytest, `npm ci`, `npm run build`, `npm test`, UI token scan, server boot/health, headless Edge built-studio render, and live local-only generate flow all pass. Browser recheck confirms Playground renders instead of the saved-history crash page.
- ✅ **P6 COMPLETE** — `docs/EXECUTION_REPORT.md` now records every P0-1 through P5-3 task with commit hashes and gate results, lists all `TODO(fable-review)` items, and notes no incomplete P0-P5 work.
- ✅ **P7-1 COMPLETE** — added Brand Brain ORM models and schemas for `brain_documents`, `brain_embeddings`, and immutable `brand_profile_versions`; verified table creation, uniqueness, nullable-ref append semantics, one-embedding-per-document, and profile version uniqueness. **Verified:** backend pytest 68/68.
- ✅ **P7-2 COMPLETE** — added `app/services/brain.py` with `BRAND_EMBED_MODEL`, OpenAI-compatible live embedding path through the existing wrapper, local-only deterministic 256-dim hashing vectorizer, float32 blob helpers, and numpy cosine search with kind filtering. **Verified:** backend pytest 73/73.
- ✅ **P7-3 COMPLETE** — added `brain_index` job kind, asset-version and feedback enqueue hooks, idempotent Brain document/embedding indexing, and `python -m app.services.brain backfill` covering asset versions, feedback, read-only Shopify products, and `brand_context/*.md` as data. **Verified:** backend pytest 76/76; real backfill CLI created 322 docs/embeddings with zero tracked data changes.
- ✅ **P7-4 COMPLETE** — generation now prepends an auditable "BRAND MEMORY" block from the latest brand profile plus top-5 similar Brain docs, boosting selected versions and positive feedback; persisted params record `memory_document_ids` and `brand_profile_version_no`; Playground renders a read-only memory-used disclosure under results. **Verified:** backend pytest 77/77; frontend `npm test` 14/14; `npm run type-check` pass; UI compliance scan clean; `npm run build` pass.
- ✅ **P7-5 COMPLETE** — added the Appendix A distillation prompt constant, `distill_brand_profile` job kind, disabled-by-default weekly scheduler settings in `settings_kv`, immutable profile-version writes with evidence ids in `distilled_from_json`, invalid-response drop behavior, `/strategy/brand-profile`, and Strategy Hub Know lane current-profile/history diff view. **Verified:** backend pytest 81/81; frontend `npm test` 14/14; `npm run type-check` pass; UI compliance scan clean; `npm run build` pass.
- ✅ **P7-6 COMPLETE / GATE P7 COMPLETE** — P7 has 21 focused Brain/Profile tests covering deterministic hashing, cosine ranking, winner boosting, ingestion hooks, idempotent backfill, auditable memory IDs in generated prompt snapshots, Appendix A prompt fidelity, mocked distillation immutable v2 creation, invalid-response drop, and local-only zero-network embedding behavior. **Gate verified:** backend pytest 84/84; frontend `npm test` 14/14; `npm run type-check` pass; UI compliance scan clean; `npm run build` pass; throwaway local-only smoke backfill → generate Copy → prompt_snapshot contained `BRAND MEMORY` + memory ids and `/strategy/brand-profile` showed profile v1.
- ✅ **P8-1 COMPLETE** — added `published_posts` and `post_metrics` ORM/schema contracts with nullable calendar/asset links, channel values, metric dedupe on `(published_post_id, captured_at)`, nullable metric columns, and insert-time engagement-rate computation that returns NULL for missing/zero reach. **Verified:** backend pytest 90/90; compileall app pass.
- ✅ **P8-2 COMPLETE** — added `/api/v1/performance/import` with dependency-free multipart/JSON CSV handling, alias-based Instagram/TikTok header detection including Meta legacy "Impressions", upsert/dedupe, K/M number parsing, unknown-column preservation in `meta_json`, detected-column 422 fallback for manual mapping, required fixtures, and a Learn-lane Performance import panel with file upload plus paste fallback. **Verified:** backend pytest 96/96; frontend `npm test` 14/14; `npm run type-check` pass; UI compliance scan clean; `npm run build` pass.
- ✅ **P8-3 COMPLETE** — imports now auto-link published posts to unambiguous calendar items by date ±1 day and channel, expose published-post list/link/unlink endpoints, provide Learn-lane manual link/unlink controls, and write top/bottom-quartile `metric_insight` Brain docs from imported engagement rates. **Verified:** backend pytest 99/99; frontend `npm test` 14/14; `npm run type-check` pass; UI compliance scan clean; `npm run build` pass.
- ✅ **P8-4 COMPLETE** — added deterministic `/api/v1/performance/best-times?channel=` aggregation using each post's latest metrics, grouping by channel/weekday/hour, filtering to n≥3 slots, and ranking by mean engagement rate with stable tie-breakers. **Verified:** backend pytest 101/101; compileall app pass.
- **P8-5 COMPLETE** - Learn lane now has `/performance/dashboard` backed by top posts, weekly engagement-rate trend, and engagement by linked asset type; Strategy Hub renders tokenized cards, table, and CSS bar rows with no chart library. **Verified:** backend pytest 102/102; frontend `npm test` 14/14; backend compileall pass; `npm run type-check` pass; UI compliance scan clean; `npm run build` pass.
- **P8-6 COMPLETE / GATE P8 COMPLETE** - P8 now has 16 focused performance tests covering header auto-detect for Instagram/TikTok/legacy Meta formats, idempotent re-import, ER math with zero/NULL reach, ambiguous auto-link handling, manual link/unlink, best-time threshold/determinism, dashboard summaries, and a dedicated gate fixture that imports ranked IG performance data, verifies visible posts/metrics, confirms expected best-time ranking, and asserts `metric_insight` Brain docs. **Verified:** backend pytest 103/103; frontend `npm test` 14/14; backend compileall pass; `npm run type-check` pass; UI compliance scan clean; `npm run build` pass.
- **P9-1 COMPLETE** - Calendar now has month/week modes, dnd-kit week-day drop zones, draggable item handles with keyboard sensor support, tokenized drop/drag states, optimistic date moves with rollback error messaging, and `PATCH /calendar/{id}` support for `{date, slot}` by persisting `slot` into item data. **Verified:** backend pytest 103/103; frontend `npm test` 14/14; backend compileall pass; `npm run type-check` pass; UI compliance scan clean; `npm run build` pass.
- **P9-2 COMPLETE** - Week calendar now includes a searchable/type-filterable unscheduled draft tray sourced from `GET /assets?status=draft`, excludes drafts already linked to calendar items, supports drag-to-day scheduling through the shared dnd-kit context, and provides a date-input fallback that creates a linked `calendar_item` optimistically. **Verified:** backend pytest 103/103; frontend `npm test` 14/14; backend compileall pass; `npm run type-check` pass; UI compliance scan clean; `npm run build` pass.
- **P9-3 COMPLETE** - Added muted channel hue tokens to `tokens.css` for Instagram, TikTok, Email, Facebook, and Manual/Other, then rendered token-only channel chips on calendar items while preserving coral strictly for selection/primary action. **Verified:** backend pytest 103/103; frontend `npm test` 14/14; backend compileall pass; `npm run type-check` pass; UI compliance scan clean; `npm run build` pass.
- **P9-4 COMPLETE** - Calendar week cards now consume `/performance/best-times`, render dashed suggested-slot controls only for matching item channel + weekday, and clicking or dropping onto a ghost slot patches `{date, slot}` without showing anything when no P8 qualifying cells exist. **Verified:** backend pytest 103/103; frontend `npm test` 14/14; backend compileall pass; `npm run type-check` pass; UI compliance scan clean; `npm run build` pass.
- **P9-5 COMPLETE** - Added `settings_kv`-backed calendar guardrails at `/system/calendar-guardrails` with default max 3 items/day/channel, plus week-view soft warning banners for day/channel overages and duplicate asset use in the same week. Warnings never block scheduling. **Verified:** backend pytest 104/104; frontend `npm test` 14/14; backend compileall pass; `npm run type-check` pass; UI compliance scan clean; `npm run build` pass.
- **P9-6 COMPLETE / GATE P9 COMPLETE** - P9 now has 12 focused calendar/guardrail tests: backend calendar/system coverage for CRUD, feed order, slot persistence, and `settings_kv` guardrails; frontend coverage for week reschedule PATCH payloads, tray-created linked items, mocked best-time ghost slots, guardrail warnings, rollback on API failure, and feed order persistence. **Verified:** backend pytest 104/104; frontend `npm test` 16/16; backend compileall pass; `npm run type-check` pass; UI compliance scan clean; `npm run build` pass.
- **P10-1 COMPLETE** - Added read-only Shopify SEO audit foundation: `seo_audits` table, pure weighted audit service over product preview data, `seo_audit` job kind, `POST /api/v1/seo/audit`, and `GET /api/v1/seo/audits`. No Shopify write path was added. **Verified:** focused SEO tests 3/3; backend pytest 107/107; backend compileall pass.
- **P10-2 COMPLETE** - Added grounded paste-ready SEO fix generation from audit rows: additive `seo_fix` asset type, `seo_fix` job kind, `/api/v1/seo/audits/{audit_id}/fix`, immutable version persistence, Brand Brain memory IDs, `memory/product_truth.json` excerpting, and manual copy blocks that keep Shopify writes disabled. **Verified:** focused SEO tests 6/6; backend pytest 110/110; backend compileall pass; frontend `npm test` 16/16; frontend `npm run type-check` pass; UI compliance scan clean. `npm run build` hit the known sandbox Node EPERM and the external approval gate was unavailable for the rerun.
- **NEXT: P10-3** SEO keyword & content plan.
- ℹ️ **P7–P11 registered** — appended 2026-07-07 by Fable: P7 Brand Brain (retrieval memory + compounding brand profile), P8 performance ingestion & best-time model, P9 drag-and-drop calendar planner, P10 SEO team, P11 repurposing pipelines + weekly standup (new FINAL gate). Execute after P6, in order.

---

## 0. BINDING RULES — READ FIRST, RE-READ EVERY PHASE

1. **Execute phases strictly in order (P0 → P11).** Never start a phase until the previous phase's Verification Gate passes.
2. **Do not invent scope.** If something seems missing or ambiguous, implement the literal instruction here and add a `TODO(fable-review):` comment. Do NOT design your own alternative.
3. **Never make paid external API calls** (OpenAI, Shopify, Google Drive) during development or tests. All tests must mock external clients. `LOCAL_ONLY_AGENT_RUNS=true` must be respected by EVERY execution path (see P1-4).
4. **Never print, copy, or commit secrets.** `.env`, `oauth_client.json`, `token.json` contain live credentials. They stay gitignored. Never echo their contents.
5. **No payments/billing features.** This is a single-user personal project. No auth beyond the existing optional basic-auth middleware.
6. **Preserve the prompt/context IP untouched:** `agent_instructions/*.md`, `brand_context/*.md`, `memory/*` contents are DATA, not code. Migrate/read them; never rewrite their prose.
7. **Commit discipline:** one commit per numbered task, message format `P<phase>-<task>: <summary>` (e.g. `P1-3: add SQLite models and migration for calendar items`). Run the phase's test command before every commit.
8. **Tech stack is fixed** (do not substitute): Python 3.11+/FastAPI/SQLAlchemy 2.x/SQLite/pytest; frontend React 18+ + Vite + TypeScript + Tailwind CSS + shadcn/ui + TanStack Query + React Router. Charting not required.
9. **Definition of Done for every task** = code + tests + Verification Gate command passing.
10. **UI carry-over (binding for every phase that touches `frontend/`):** components are built ONLY from `frontend/src/styles/tokens.css` custom properties. Before EVERY UI commit run the compliance scan (same one verified in `5d837ec`): `grep -rnE "#[0-9a-fA-F]{3,8}|box-shadow|linear-gradient" frontend/src --include="*.tsx" --include="*.css" | grep -v styles/tokens.css` — must return nothing. REUSE the existing studio inventory before writing anything new: app shell/top bar, premium toggle, job drawer + progress pill, compose panel, generation-history filmstrip, asset gallery aspect cards, caption card, status badges, skeletons, import-style wizards, video prompt-pack provider tabs. New-phase views COMPOSE these (P8 Performance tab = Learn-lane cards + CSS bar rows; P9 calendar items = existing chips/cards with dnd-kit wrappers; P10 SEO tab = audit table + issue chips + caption-card copy pattern; P11 Standup = report card + action buttons). A genuinely new component must obey all P2-0 latency rules (skeletons, optimistic mutations, lazy images with intrinsic aspect boxes, virtualization past 60 items, 150ms motion) and be APPENDED to this inventory list in the same commit. New tokens (e.g., P9-3 channel hues) are additive to tokens.css only — never inline values; coral stays selection/primary-action only.

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

**P2-0 (DESIGN SPEC — binding for ALL UI work in EVERY phase, P2 through P11 and any future phase).** Aesthetic: light editorial "gallery studio" — the photoshoots ARE the interface. Implement as CSS custom properties in `frontend/src/styles/tokens.css` and use ONLY tokens:
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

**GATE P5:** fresh clone simulation — `pip install -r requirements.txt -r requirements-dev.txt`, `pytest -q` green, `python -m app.services.migrate_legacy`, `uvicorn app.main:app` boots, `npm ci && npm run build && npm test` in `frontend/` green, and the local-only end-to-end generate flow works in a browser.

## PHASE P6 — Report

Write `docs/EXECUTION_REPORT.md`: table of every task P0-1 … P5-3 with commit hash and gate results; list of every `TODO(fable-review)`; anything you could not complete and exactly why. Do not mark this plan complete if any gate failed.

## PHASE P7 — Brand Brain: retrieval memory + compounding brand profile

This phase makes the platform LEARN: everything digested (photos, products, feedback, context files) and produced (versions, captions) becomes retrievable memory that grounds every future generation. Rules 3, 6 apply in full — no paid calls in tests, context files are data.

**P7-1. Tables** (models + schemas): `brain_documents` (id, kind enum: asset_version|feedback|product|context_file|metric_insight, ref_id nullable, text TEXT, meta_json, created_at; UNIQUE(kind, ref_id) where ref_id is set); `brain_embeddings` (id, document_id FK UNIQUE, model, dim INT, vector BLOB float32 little-endian, created_at); `brand_profile_versions` (id, version_no, profile_md TEXT, distilled_from_json, created_at) — immutable, same discipline as `asset_versions`.
**P7-2. Embedding service** `app/services/brain.py`: `embed_texts(list[str])` through the existing OpenAI client wrapper (`BRAND_EMBED_MODEL` setting, honors `BRAND_OPENAI_BASE_URL` so NIM/Ollama endpoints work). When `LOCAL_ONLY_AGENT_RUNS=true`: deterministic hashing vectorizer (feature-hash tokens → 256-dim float32, L2-normalized; identical input → identical vector) — tests use ONLY this path. `search(query, k=5, kinds=None)` = cosine similarity in numpy over vectors loaded from SQLite. No vector DB (corpus is thousands of docs); tag `TODO(fable-review)` if it ever exceeds ~50k.
**P7-3. Ingestion:** (a) hooks — on `asset_versions` insert and `feedback_events` insert, enqueue a new job kind `brain_index`; (b) backfill CLI `python -m app.services.brain backfill` — idempotent via the UNIQUE constraint — covering existing versions, feedback, Shopify products (ported `shopify.py`, read-only), and `brand_context/*.md` (ingest as data; never modify — Rule 6).
**P7-4. Retrieval-grounded generation:** `services/generation.py` prepends a "BRAND MEMORY" block to every generation prompt: latest `brand_profile_versions` profile + top-5 similar docs, ranking winners first (is_selected versions and positive feedback). Injected document ids MUST be recorded in `prompt_snapshot`/params so every generation is auditable. Playground shows a read-only "memory used" disclosure row under results.
**P7-5. Profile distillation:** weekly scheduled job on the P3-1 scheduler (cadence in `settings_kv`, off by default) `distill_brand_profile`: agent reads recent feedback_events + selected-vs-unselected version pairs → writes a NEW `brand_profile_versions` row. Prompt (binding): use APPENDIX A verbatim — do not paraphrase or extend it. Strategy Hub "Know" lane renders the current profile + version history with a diff view. Old versions are never deleted.
**P7-6. Tests** (min 15): hashing vectorizer determinism; cosine ranking golden fixture; both ingestion hooks fire; backfill idempotent; injected memory ids recorded in prompt_snapshot; distillation with mocked agent creates an immutable new version; local-only mode makes zero network calls (assert at the wrapper).

**GATE P7:** `pytest -q` green; local-only smoke: backfill → generate a Copy asset → its prompt_snapshot lists injected memory ids; Know lane shows profile v1.

## PHASE P8 — Performance ingestion & best-time model (no platform APIs)

Engagement data enters ONLY via file import (manual CSV export or paste). Meta/TikTok/Instagram APIs are explicitly OUT of scope in this phase.

**P8-1. Tables:** `published_posts` (id, calendar_item_id FK nullable, asset_id FK nullable, channel enum: instagram|tiktok|facebook|other, external_ref nullable, permalink nullable, published_at, created_at); `post_metrics` (id, published_post_id FK, captured_at, impressions/reach/likes/comments/shares/saves/clicks — all nullable INT, engagement_rate REAL computed at insert as (likes+comments+shares+saves)/reach, NULL when reach is 0/NULL). Dedupe key (published_post_id, captured_at).
**P8-2. Import:** `POST /api/v1/performance/import` (multipart CSV + channel): auto-detect Instagram and TikTok export header formats per the pinned import spec below (unknown headers → response lists detected columns for the UI's manual-mapping step). Rows upsert `published_posts` by (channel, permalink or external_ref) and append `post_metrics`. UI: import wizard in a new "Performance" tab of the Learn lane (upload → mapping preview table → confirm), plus a paste-a-table fallback; visual target for the whole tab: `docs/design-targets/performance-tab.html` (P2-0 token variables).

> **P8-2 pinned import spec (researched 2026-07; binding):**
>
> **Verified export paths** (document these in the wizard help text): Instagram = Meta Business Suite → Insights → Content → Export Data → CSV (max 90-day window per export). TikTok = TikTok Studio (studio.tiktok.com) or Business Center → Analytics → Content → Download data → CSV (max 60-day range per export).
>
> **Canonical schema** (what `post_metrics` stores): posted_at, external_ref (permalink / video link; fall back to title+date hash when absent), title_or_caption, post_type, views, reach, likes, comments, shares, saves, follows_from_post. Any canonical field absent from the file is NULL (unavailable, never 0 — same rule as everywhere else).
>
> **Header matching:** normalize before lookup (lowercase, trim, collapse spaces/underscores). Alias maps live in code as data, one per source. They MUST include both pre- and post-April-2025 Meta vocabulary (Meta replaced "Impressions" with "Views" as the primary metric): e.g. views ← {views, plays, impressions}; posted_at ← {publish time, post date, date, post time, posted date, create time}; external_ref ← {permalink, post url, video link, video url}; saves ← {saved, saves, favorites}; reach ← {reach, accounts reached}. Do NOT invent aliases beyond plausible vendor vocabulary; every alias must be exercised by a fixture or unit test.
>
> **Import contract:** minimum viable row = posted_at + (external_ref OR title_or_caption) + at least one engagement metric; files failing this return 422 with the full list of detected headers (feeds the manual-mapping UI). Extra/unknown columns are preserved in `meta_json`, never silently dropped. Numbers may contain thousands separators and "1.2K"/"3.4M" suffixes — parse both; unparseable cell → NULL + row-level warning in the response.
>
> **Fixtures (binding):** check in `tests/fixtures/perf_import/mbs_instagram_content_sample.csv` and `tiktok_studio_content_sample.csv` with representative header shapes (one Meta pre-2025 variant with "Impressions" as a third fixture). Parser tests run ONLY on fixtures — zero network. Since vendors reshape exports without notice, a failed auto-detect must NEVER hard-fail the wizard: it degrades to the manual-mapping step. Tag `TODO(fable-review)` if a real user file surfaces headers no alias covers.
**P8-3. Linking + insights:** auto-match published_posts to calendar_items by (date ±1 day, channel) only where unambiguous; manual link/unlink UI on both sides. On each import, write `metric_insight` docs into the Brand Brain (P7) for top- and bottom-quartile posts ("{type} with hook '{first line}' achieved {ER}% on {channel}") — future generations learn from real performance.
**P8-4. Best-time model:** pure aggregation, NO ML: mean engagement_rate by (channel, weekday, hour) using each post's latest metrics; only cells with n ≥ 3 qualify. `GET /api/v1/performance/best-times?channel=` → ranked slots + sample sizes. Deterministic on fixture data.
**P8-5. Learn-lane dashboard:** top posts table, weekly ER trend, performance by asset type — shadcn cards + CSS bar rows only (Rule 8: no chart library).
**P8-6. Tests** (min 12): header auto-detect for both formats; upsert/dedupe on re-import; ER math incl. zero/NULL reach; ambiguous auto-link stays unlinked; best-times threshold + determinism; quartile insights written to brain_documents.

**GATE P8:** import a fixture IG CSV through the UI → posts + metrics visible; best-times returns the expected ranking from the fixture; insight docs exist in `brain_documents`.

## PHASE P9 — Calendar planner v2: drag-and-drop

**Rule 8 amendment (owner-approved 2026-07-07): `@dnd-kit/core` + `@dnd-kit/sortable` are the ONLY new frontend dependencies permitted for this phase.**

**P9-1. Views + drag:** Calendar gains a week view alongside month (visual target: `docs/design-targets/calendar-dnd.html` — match its layout, drag/ghost/drop states, and component composition, implemented with the P2-0 token variables). Every item draggable to another day/slot via dnd-kit → optimistic update + `PATCH /api/v1/calendar/{id}` {date, slot}; roll back with an error toast on failure. Keep dnd-kit default keyboard sensors (accessibility).
**P9-2. Unscheduled tray:** right rail listing draft assets that have no calendar item (existing assets API filter), searchable by type. Dragging one onto a day creates a calendar_item linked to that asset (POST, optimistic).
**P9-3. Channel color coding:** extend `tokens.css` with muted channel hues derived from the P2-0 neutral palette — coral remains selection/primary-action ONLY. Channel chip on every calendar item.
**P9-4. Suggested slots:** ghost chips (dashed hairline outline, "Suggested · Thu 18:00") rendered from P8-4 best-times for the item's channel; dropping on a ghost (or clicking it) schedules that slot. Hidden entirely when P8 has no qualifying cells.
**P9-5. Guardrails:** `settings_kv` max items/day/channel (default 3) → soft warning banner on exceed, never a hard block; duplicate-asset-same-week warning.
**P9-6. Tests** (min 10): move/reschedule handlers + PATCH payloads unit-tested directly (if jsdom drag simulation is flaky, test the handlers and state transitions — do NOT ship flaky tests); tray drop creates a linked item; rollback on API failure; ghost slots from mocked best-times; guardrail warnings.

**GATE P9:** manual smoke — drag an item to a new day, reload, it persisted; drag a draft from the tray onto a day, item created and linked; `npm test` + `npm run build` green.

## PHASE P10 — SEO team: catalog audit + content plan (read-only Shopify)

**P10-1. Audit service** `app/services/seo_audit.py` — pure functions over the read-only catalog from ported `shopify.py`. Per-product checks: title length 50–60 chars; meta description present and 140–160 chars; every image has alt text; target keyword present in title/description (keyword source: P10-3 map when it exists, else product type); duplicate titles across the catalog. New table `seo_audits` (id, product_handle, score INT 0–100 weighted across checks — document weights in code, issues_json, audited_at). `POST /api/v1/seo/audit` (job) + `GET /api/v1/seo/audits`.
**P10-2. Fix generator:** per audited product, agent generates paste-ready fixes (new title, meta description, alt text per image) stored as new asset type `seo_fix` (additive enum migration; existing assets untouched), grounded through the Brand Brain retrieval path (P7-4) + `memory/product_truth.json`. **NO Shopify writes ever** — `SHOPIFY_WRITE_ENABLED` stays false; output is copy-to-clipboard blocks.
**P10-3. Keyword & content plan:** agent produces a `seo_plan` asset: keyword map (product/collection → primary + secondary keywords) and a blog plan (post title, outline, target keyword, internal links to specific product URLs). Regenerable; versions immutable as always.
**P10-4. UI:** rename the Ads nav entry to "Ads & SEO"; SEO tab = audit table (product, score, issue chips, "Generate fix"), fix detail with per-field copy buttons, plan view.
**P10-5. Tests** (min 12): every audit rule with pass/fail fixtures; exact score weighting; duplicate detection; fix/plan generation with mocked agent + grounding recorded; enum migration additive.

**GATE P10:** audit over a fixture catalog yields deterministic scores; a `seo_fix` and a `seo_plan` asset created end-to-end in local-only mode from the UI.

## PHASE P11 — Repurposing pipelines, recycling, weekly standup — FINAL

**P11-1. Repurpose pipeline:** new job kind `repurpose_shoot`: input = 1–10 `source_assets` (P4-4) → creates a campaign + fan-out child jobs: post copy, reel `video_script` (P4-1 pack), story set (3-frame copy), `ad_brief` (P4-5), and a product-page refresh suggestion (`seo_fix`, when a product is linked). Progress aggregates in the job drawer; partial failure keeps completed assets and leaves failed steps individually retryable.
**P11-2. Recycling:** monthly scheduled job (off by default): top-quartile ER posts (P8) older than 45 days → draft "remix" assets (meta_json.remix_of set). NEVER auto-schedules — remixes land in the P9 unscheduled tray.
**P11-3. Weekly standup:** scheduled job → new table `standup_reports` (id, week_start, report_md, recommendations_json, created_at) + "Standup" tab in the Learn lane: what published (P8 links), top/bottom performer, next week's plan (calendar), and exactly 3 agent recommendations grounded in Brand Brain + metrics — each with an "Add to calendar as draft" button (creates a draft asset + tray entry).
**P11-4. Docs:** extend `docs/EXECUTION_REPORT.md` with rows P7-1 … P11-5; update README (Performance import, Brand Brain, standup/recycle cadence settings).
**P11-5. Tests** (min 12): fan-out orchestration incl. partial failure + retry; recycle window + quartile selection math; standup assembly with mocked agent; add-to-calendar action.

**GATE P11 (FINAL):** full P5-gate fresh-clone simulation PLUS, in local-only mode with zero network calls: brain backfill, fixture metrics import, `repurpose_shoot` on fixture source assets, and a generated standup report visible in the UI.
---

## APPENDIX A — Brand profile distillation prompt (binding; P7-5 uses this VERBATIM)

Store as a module-level constant in the distillation job module. `{placeholders}` are filled by code; nothing else may be altered.

**SYSTEM:**

> You are the brand strategist for BRAND NAME, a streetwear label. You distill observed evidence into an operating brand profile that other agents follow when generating content. You work ONLY from the evidence provided — no generic marketing advice, no invented rules.
>
> OUTPUT CONTRACT: respond with ONLY markdown containing exactly these five H2 sections, in this order: `## Voice rules`, `## Banned phrases`, `## Visual codes`, `## Proven hooks`, `## Audience notes`.
>
> HARD CONSTRAINTS:
> 1. Every bullet must cite the evidence ids it derives from, in parentheses at the end (e.g. `(fb_123, pair_45)`). A bullet with no citation is invalid.
> 2. Prefer patterns from SELECTED versions and positive feedback; a pattern appearing only in unselected/negative material may ONLY appear under Banned phrases or as a "avoid" rule.
> 3. Carry forward rules from the current profile unless newer evidence contradicts them; when reversing or removing a rule, add a bullet noting the reversal with the contradicting ids.
> 4. Banned phrases must actually appear in rejected or negatively-received material — never ban speculatively.
> 5. Maximum 40 bullets total across all sections; each bullet at most 2 sentences, written as an imperative instruction.
> 6. If a section has insufficient evidence this period, write exactly: `Insufficient evidence this period.` — never pad with plausible-sounding filler.

**USER (template):**

> CURRENT PROFILE (v{version_no}): {current_profile_md}
> FEEDBACK EVENTS since {since_date} (id, target, sentiment, text): {feedback_events}
> SELECTED vs UNSELECTED version pairs (pair id, selected text/params, unselected text/params): {version_pairs}
> METRIC INSIGHTS (if any): {metric_insights}
>
> Write the new profile markdown now.

**Wiring (binding):** the job records every evidence id passed into the prompt in `distilled_from_json`, so each profile version is auditable against exactly what it saw. Responses missing any of the five H2 sections are logged and dropped — the job does NOT write a profile version that period. The P7-6 distillation test asserts the constant matches this appendix text and that a mocked five-section response creates an immutable new version.
