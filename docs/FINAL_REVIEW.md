# Final Review

Updated: 2026-07-13

## Decision

`feat/openai-growth-agents` is ready for owner review and a fresh deployment decision.

The P0-P11 roadmap is complete on this branch. The final gate passed with local-only coverage for Brand Brain backfill, performance import, repurpose shoot, standup generation, Strategy API visibility, backend tests, frontend tests, type-check, production build, and the UI token scan.

## Current Head

- Branch: `feat/openai-growth-agents`
- Final gate commit: `c7f895b` (`test: complete P11 final gate`)
- Previous docs checkpoint: `7b46f64` (`docs: update P11 execution report`)

## Verified Gates

```text
Focused P11 tests: 15/15
Backend pytest: 138/138
Backend compileall: pass
Frontend Vitest: 17/17
Frontend type-check: pass
Frontend build: pass
UI token scan: clean
```

## Deployment Shape

Deploy the active FastAPI app, not the removed legacy dashboard:

```powershell
cd frontend
npm ci
npm run build
cd ..
python -m pip install -r requirements.txt
python -m app.services.migrate_legacy
python -m uvicorn app.main:app --host 0.0.0.0 --port 8765
```

Use persistent storage for `DATA_DIR`. Keep `.env`, OAuth tokens, API keys, and SQLite runtime data out of git.

## Pre-Launch Operator Checks

- Rotate any exposed provider keys per `docs/KEY_ROTATION.md`.
- Set `LOCAL_ONLY_AGENT_RUNS=true` for no-provider dry runs; set it to `false` only after provider credentials are intentionally configured.
- Keep `SHOPIFY_WRITE_ENABLED=false` unless a future write workflow is explicitly designed and reviewed.
- Configure `BRAND_OPENAI_BASE_URL` for OpenAI-compatible providers such as NVIDIA NIM/Ollama gateways when using live generation.
- Run `python -m app.services.brain backfill` after importing/migrating meaningful legacy data.
- Enable cadence settings from System only after review: daily workflow, brand profile distillation, recycling, weekly standup, and calendar guardrails.

## Known Review Items

The only first-party `TODO(fable-review)` items are already listed in `docs/EXECUTION_REPORT.md`:

- `app/services/drive.py`: temporary reuse of `src.asset_design_roles` as a pure helper.
- `app/services/images.py`: temporary reuse of `src.product_inventory` as a data helper.
- `app/services/jobs.py`: live non-local daily workflow still falls back to `src.orchestrator`.

These are not blocking for the completed local-first P0-P11 gate, but they are the right starting points for the next architecture pass.
