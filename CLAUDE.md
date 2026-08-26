# CLAUDE.md — brandname-growth-agents

Brand growth agents: content strategy, generation, and a studio dashboard.
Python FastAPI backend (`app/`, routers + services + SQLAlchemy models) with
a frontend (`frontend/`). Provisioned for autonomous work by
`hermes-agent-build`'s `provision-repo.sh`.

## Commands

Toolchain lives in `.venv/` (Python 3.12, `uv pip install -r requirements.txt
-r requirements-dev.txt` + `coverage` installed separately — neither
requirements file declares it). Always invoke via the venv, not a bare
`python3`/`ruff` on PATH — nothing installs these system-wide.

- **Lint**: `.venv/bin/ruff check .`
- **Tests**: `.venv/bin/python3 -m coverage run -m pytest tests`
- **Coverage report**: `.venv/bin/python3 -m coverage json -o coverage.json`
- No typecheck tool configured — `TYPECHECK_CMD` is intentionally empty in
  `.claude/gate.conf`.

These exactly match `.claude/gate.conf` — that file is the source of truth if
they ever drift; it's a protected path no agent may edit.

**Known state as of provisioning (2026-08-26): `ruff check .` currently
reports 111 pre-existing lint errors** (103 auto-fixable with `ruff check
--fix`) — not introduced by any card, this is the repo's state at the moment
the gate was wired up. The gate will fail on these until a card fixes them;
that's expected honesty, not a broken gate.

## Functional testing

No `FUNCTIONAL_CMD` is wired yet, and — unlike TradingAgents-Workspace —
this repo genuinely ships a real HTTP service (`app/main.py`, FastAPI +
uvicorn + SQLAlchemy) that `provision-repo.sh`'s auto-detection did NOT flag
as needing one, because that detection only looks for a Dockerfile/compose
file/`deploy/`, none of which this repo has. A functional cycle (boot the
API, hit a few routes, assert real responses) would likely be genuinely
valuable here — building `scripts/test-stack.sh` from the template's
`.example` per `TESTING.md` is real, repo-specific work. Ask before assuming
either way (build it, or waive deliberately with
`GATE_ALLOW_MISSING_FUNCTIONAL=1`).

## Git / branching

- **This repo's base branch is `feat/openai-growth-agents`, not `main`** —
  pinned as `BASE_REF` in `.claude/gate.conf`. Never commit or push directly
  to it. Always work on a feature branch off it
  (`git switch -c feat/<card-id>`), enforced by `protect-paths.sh` and
  `guard-git.py` regardless of what's said here.
- **This repo IS in `guard-git.py`'s `AUTONOMOUS_OWNERS`** (owned by
  `rsbassi9`, same as the pipeline operator) — a worker may push its feature
  branch, open a PR, and merge its own PR without a human-issued token. That
  autonomy applies to the branch → PR → merge path, not to the base branch
  itself: landing changes always goes through a PR.
- Coverage minimum: 80% on changed lines (`COVERAGE_MIN` in `.claude/gate.conf`).
- Diff ceiling: 600 changed lines before a card should be decomposed
  (`DIFF_MAX`).
