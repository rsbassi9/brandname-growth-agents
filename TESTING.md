# The functional-testing contract — every project, not just one

**Doctrine.** Unit tests prove the code. Code review proves the intent. Neither
runs the application — and the application is what the user touches. The reference system this doctrine is ported from hit
exactly this: an Internal Server Error reached production through a
fully green gate: metadata that parsed, linted, and reviewed clean broke the
running app on rebuild. The gap is structural, so the fix is structural: every
repo that ships a runnable app carries an **ephemeral functional cycle**, and
the gate runs it. Prod is never the first place a change runs.

This file is installed by `provision-repo.sh` into every provisioned repo.
The gate (`scripts/gate.sh`) enforces it: a repo with app markers (compose
file, Dockerfile, `deploy/`) and no `FUNCTIONAL_CMD` fails until the cycle is
wired or deliberately waived (`GATE_ALLOW_MISSING_FUNCTIONAL=1` — for
pure-library and docs repos only, and that waiver is worker-locked like every
gate.conf decision).

`tests/pipeline_harness.py` is installed beside it for the failure-prone test
boundaries: copy fixtures rather than mutating sources, preserve executable
modes, keep byte protocols as bytes, use a real PTY when terminal semantics are
under test, run subprocesses in owned process groups, make teardown
unconditional, and fail explicitly when bubblewrap isolation is unavailable.
Use these primitives instead of one-off harness code.

## The verb contract

Every app repo ships `scripts/test-stack.sh` implementing these verbs, so the
gate, the workers, and Rajvir drive every project's testing the same way
regardless of stack:

| verb | contract |
|---|---|
| `up` | boot a fresh, throwaway instance of the app (ephemeral state, throwaway creds, its own port). NEVER touches prod state. |
| `apply` | install this repo's config/schema/build into that instance **using the same mechanism prod uses** (same script, same argv). If apply breaks the fresh instance, it would have broken prod — that is the single highest-value check. |
| `seed` | mint test credentials/data shaped like prod's (same auth type, same scope level), written to a gitignored `.test-stack.env`. |
| `integration` | backend suite against the instance's API. Asserts the repo's *contracts*: schema/fixture parity, CRUD round-trips on every enum/state value, ACL scoping (what the token must NOT be able to do). |
| `e2e` | browser suite (Playwright) against the same instance, with the **error recorders** (below) attached to every page. |
| `smoke` | the minimal read-mostly checks safe to run against PROD post-deploy. |
| `down` | destroy the instance and wipe its volumes. |
| `ci` | `up → apply → seed → integration → e2e → down`, teardown guaranteed, non-zero on any failure. Support `--no-e2e`. This is what `FUNCTIONAL_CMD` runs. |

Scaffold from `scripts/test-stack.sh.example`.

## The two error recorders (non-negotiable in every e2e suite)

Attach to every page, fail the test on either, even when its own asserts pass:

1. **any HTTP response ≥ 500** observed by the browser;
2. **any uncaught page error / console.error** (with a short, explicit
   ignore-list for known noise like favicon 404s).

This is the mechanism that turns "a human found a 500 by clicking around" into
a red gate before merge. A screen-walk test (visit every core route, assert it
renders) plus these recorders catches the whole white-screen/500 class with a
handful of tests.

## What each suite must cover, minimum

- **integration**: every externally-visible state/enum value round-trips
  (create → read back); every fixture-defined contract is asserted
  character-exact against live metadata/config; the automation credential is
  probed for what it must NOT do (admin surfaces → 403); the endpoints the UI
  bootstraps from all serve 200 after `apply`.
- **e2e**: login (renders / rejects wrong creds / accepts right ones); a
  screen-walk of every core route with the recorders on; one real create-flow
  round-trip through the UI per core entity.
- **smoke**: auth works, credential still correctly scoped, one read per
  critical surface. Runs against prod AFTER deploy, never as the primary bed.

## Parity rules — what keeps green-tests-broken-prod impossible-ish

1. The ephemeral instance runs the **same image/version pins** as prod. Bump
   both in the same PR, always.
2. `apply` uses the **same install mechanism** as the prod deploy script —
   shared code path, not a parallel reimplementation.
3. Tests authenticate with the **same credential shape** prod automation uses
   (plus an explicitly-admin client only where the check needs it).
4. Known parity gaps (an extension installed on prod but absent from the base
   image, a service stubbed out) are **listed in the repo's docs/testing.md**
   and covered by the prod smoke instead. An unlisted gap is a defect.

## Workflow rules (bind the workers)

- **DoD**: any card that changes runtime behaviour of an app must carry a DoD
  that exercises the app — `bash scripts/test-stack.sh ci` or a targeted
  integration/e2e test — not only unit tests. A unit-only DoD for app-visible
  behaviour is decoration (planner soul, TASKS section).
- **Tests-first** applies to these suites too: the failing integration/e2e
  test that encodes the DoD is written and committed RED before implementing,
  same as any other test.
- **New screen/entity/journey ⇒ same PR extends the suites**: a route in the
  screen-walk, a contract assert, a round-trip. The reviewer of the PR (and
  the gate's coverage-on-changed-lines) treat a behaviour change without a
  suite change as suspect.
- Keep `ci` under ~10 minutes. If e2e pushes past that, gate on
  `ci --no-e2e` per-card and run full `ci` on the chain's last card /
  pre-deploy — never less than up+apply+integration per card.
