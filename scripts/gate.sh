#!/usr/bin/env bash
# gate.sh — the authoritative quality gate. Stage 2.2. Runs as a Stop hook.
#
# Order is deliberate: cheapest signal first, so a broken build never waits on a
# coverage run.
#
#   1. lint
#   2. typecheck
#   3. tripwires: bare excepts, duplication delta, diff size ceiling
#   4. new-dependency tripwire
#   ── fail-fast checkpoint: if 1-4 found anything, report and stop here ──
#   5. full test suite
#   6. functional cycle (FUNCTIONAL_CMD) — the app, not just the code
#   7. changed-lines coverage >= COVERAGE_MIN (default 80)
#
# Steps 3-4 read only the diff and finish in well under a second, so they belong
# in front of the multi-minute stages, not behind them.
#
# Why the checkpoint (2026-07-30): tripwires used to run LAST, after ~12 min of
# tests and coverage, and the gate collected every failure before reporting
# anything — so a worker learned a sub-second duplication verdict 12m39s after
# the gate already knew it. On card t_e95c7b77 a worker sat waiting on exactly
# that, hit its iteration cap one minute after opening the PR, and signed off
# with "duplication tripwire fixed" — a prediction, not a result. CI reported
# red 13 minutes later and the card's six-deep chain stalled overnight.
#
# The tradeoff is accepted deliberately: when a cheap check fails you no longer
# get test/coverage results in the same run. Cheap failures are near-always
# mechanical and independent of the expensive stages, so one extra cycle there
# beats paying ~12 minutes on every cycle.
#
# Config lives in `.claude/gate.conf`, which the worker CANNOT edit (see
# protect-paths.sh). Commands are declared there per repo, because "adapt to the
# stack" written in a soul is a wish, and written in a config is a fact.
#
# A GATE THAT SKIPS A CHECK IT CANNOT RUN IS NOT A GATE.
# If COVERAGE_CMD is unset, this fails. The only way to proceed without coverage
# is to set GATE_ALLOW_MISSING_COVERAGE=1 in gate.conf — a deliberate, reviewable,
# worker-inaccessible decision. Silence is never taken as success.
#
# Exit 0 = pass. Exit 2 = fail, with a terse summary on stderr (Claude Code feeds
# stderr back to the agent, which is exactly the failure artifact the implementer
# needs for its retry).

set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$REPO" || { echo "gate: cannot cd to $REPO" >&2; exit 2; }

# The gate toolchain (ruff/pytest/coverage/playwright) lives ONLY in the hermes
# venv (docs/testing.md) — system python3 has none of it. Kanban workers inherit
# the venv on PATH from the gateway, but any other caller (interactive claude -p,
# a planner's plan-engine subprocess) does not: its run then loops on "toolchain
# not importable" until killed, which reads as a model hang (J4 run 43,
# 2026-07-19 — two engine attempts burned). Bootstrap PATH here so the gate
# resolves its own interpreter instead of trusting the caller's environment.
HERMES_VENV="$HOME/.hermes/hermes-agent/venv"
if [ -x "$HERMES_VENV/bin/python3" ]; then
  export PATH="$HERMES_VENV/bin:$PATH"
fi

# A Stop hook can re-fire after the agent responds to it. Without this guard the
# agent and the gate ping-pong forever.
if [ "${1:-}" = "--stop-hook" ]; then
  active="$(cat | python3 -c 'import json,sys;print(json.load(sys.stdin).get("stop_hook_active", False))' 2>/dev/null || echo False)"
  [ "$active" = "True" ] && exit 0
fi

# --base <ref>: the pre-push hook has always passed this
# and gate.sh silently ignored it. CLI beats conf beats the smart default.
_CLI_BASE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --base)
      # A bare trailing --base used to make `shift 2` a no-op ($#=1, no -e),
      # spinning this loop forever inside a pre-push/Stop hook (2026-08-18).
      [ $# -ge 2 ] || { echo "gate: --base requires a value" >&2; exit 2; }
      _CLI_BASE="$2"; shift 2 ;;
    --base=*)
      _CLI_BASE="${1#--base=}"; shift ;;
    *) shift ;;
  esac
done

CONF="$REPO/.claude/gate.conf"
[ -f "$CONF" ] || { echo "gate: missing $CONF — this repo is not provisioned for autonomous work" >&2; exit 2; }
# shellcheck disable=SC1090
. "$CONF"
[ -n "$_CLI_BASE" ] && BASE_REF="$_CLI_BASE"
_base_src="--base"
if [ -z "$_CLI_BASE" ]; then
  if [ -n "${BASE_REF:-}" ]; then _base_src="conf/env"; else _base_src="computed"; fi
fi
if [ -z "${BASE_REF:-}" ]; then
  if git -C "$REPO" rev-parse --verify -q origin/main >/dev/null 2>&1; then
    git -C "$REPO" fetch -q origin main 2>/dev/null || true   # offline → stale but usable
    BASE_REF=origin/main
  else
    BASE_REF=main
  fi
fi
# Validation covers EVERY source — CLI, conf, env, and the computed default
# (round-5: the default path could assign an unresolvable `main` unvalidated
# and every diff-scoped stage measured an empty diff, green about nothing).
git -C "$REPO" rev-parse --verify --quiet "$BASE_REF^{commit}" >/dev/null 2>&1 \
  || { echo "gate: BASE_REF '$BASE_REF' ($_base_src) does not resolve to a commit" >&2; exit 2; }
echo "gate: base $BASE_REF ($_base_src)"
_mb="$(git -C "$REPO" merge-base "$BASE_REF" HEAD 2>/dev/null || true)"
_hd="$(git -C "$REPO" rev-parse HEAD 2>/dev/null || true)"
if [ -z "$_mb" ] || [ -z "$_hd" ]; then
  echo "gate: WARNING cannot relate BASE_REF to HEAD — diff-scoped stages may measure nothing" >&2
elif [ "$_mb" = "$_hd" ]; then
  echo "gate: WARNING base equals HEAD — diff-scoped stages have nothing to measure" >&2
fi

fails=()

# ── Gate honesty (2026-07-11): once the stack is scaffolded (package.json exists), the
# pre-scaffold stubs and the coverage waiver are VOID. A gate that passes on `echo stub`
# or a blanket waiver is theatre — T2 shipped stub lint/coverage + a fake metafile proof
# straight through it. Fail loudly until real tooling is wired.
if [ -f "$REPO/package.json" ]; then
  [ "${GATE_ALLOW_MISSING_COVERAGE:-0}" = "1" ] && fails+=("gate-honesty: package.json exists but coverage is still WAIVED — the pre-scaffold waiver is void; set a real COVERAGE_CMD and remove GATE_ALLOW_MISSING_COVERAGE in .claude/gate.conf.")
  for s in lint typecheck test coverage; do
    scr="$(python3 -c "import json;print((json.load(open('$REPO/package.json')).get('scripts') or {}).get('$s',''))" 2>/dev/null)"
    printf '%s' "$scr" | grep -qiE "stub|^[[:space:]]*echo\b|^[[:space:]]*true\b" \
      && fails+=("gate-honesty: package.json '$s' script is a no-op stub (\"$scr\") — a check that always exits 0 is not a check; wire a real command.")
  done
fi

run() { # run <label> <cmd>
  local label="$1" cmd="$2"
  [ -z "$cmd" ] && return 0
  if out="$(eval "$cmd" 2>&1)"; then
    echo "  ✓ $label"
  else
    echo "  ✗ $label"
    fails+=("$label: $(printf '%s' "$out" | tail -n 6)")
    metric_gate "$label"
  fi
}
metric_gate() { [ -x "$HOME/bin/metric.sh" ] && "$HOME/bin/metric.sh" loop gate_failure 1 "$1" >/dev/null 2>&1 || true; }

# Print accumulated failures to stderr and exit 2. Called from the fail-fast
# checkpoint and again at the end of a full run.
report_fails() {
  {
    echo "GATE FAILED (${#fails[@]} check(s)). Fix these, then stop again."
    for f in "${fails[@]}"; do
      echo ""
      echo "── $f"
    done
    echo ""
    echo "Do NOT edit tests, gate.sh, or any lint/coverage config to make this pass."
    echo "Those paths are blocked. If a test is genuinely wrong, kanban_block and ask."
  } >&2
  exit 2
}

echo "gate: $REPO"

run lint      "${LINT_CMD:-}"
run typecheck "${TYPECHECK_CMD:-}"

# ── tripwires ────────────────────────────────────────────────────────────
# Optional pass-through: a repo can scope diff-size checks (docs-phase work,
# generated files, etc.) via DIFF_EXCLUDE / DIFF_TOTAL_MAX in its gate.conf.
tw_args=(--base "$BASE_REF" --diff-max "$DIFF_MAX")
[ -n "${DIFF_EXCLUDE:-}" ]   && tw_args+=(--diff-exclude "$DIFF_EXCLUDE")
[ -n "${DIFF_TOTAL_MAX:-}" ] && tw_args+=(--diff-total-max "$DIFF_TOTAL_MAX")
if tw="$(python3 "$REPO/scripts/gate-tripwires.py" "${tw_args[@]}" 2>&1)"; then
  echo "  ✓ tripwires"
else
  echo "  ✗ tripwires"
  fails+=("tripwires: $tw")
  # gate-tripwires.py records its own typed metrics (bare_except|duplication|diff_size)
fi

# ── new-dependency tripwire (Stage 2.4) ──────────────────────────────────
# Only fires when the diff touches a dependency manifest. Written natively rather
# than wrapping supply-chain-guard: that skill detected the 2026 axios RAT in its
# own fixture and still printed "[VERDICT] CLEAR" with exit 0 (its findings are
# echoed from subshells and never reach _EXIT_CODE). See gate-newdeps.py's header.
if [ -f "$REPO/scripts/gate-newdeps.py" ]; then
  if nd="$(python3 "$REPO/scripts/gate-newdeps.py" --base "$BASE_REF" --repo "$REPO" 2>&1)"; then
    [ -n "$nd" ] && echo "  ✓ new-deps"
  else
    echo "  ✗ new-deps"
    fails+=("new-deps: $nd")
  fi
fi

# ── fail-fast checkpoint ─────────────────────────────────────────────────
# Everything above reads the diff or the config and costs under a second.
# Everything below boots the fixture CRM and costs ~12 minutes. If the cheap
# checks already found something, the expensive stages cannot change the verdict.
if [ "${#fails[@]}" -ne 0 ]; then
  echo "  … skipping tests/functional/coverage: cheap checks already failed"
  report_fails
fi

run tests     "${TEST_CMD:-}"

# ── functional gate (2026-07-17, ported from repo-template) ──────────────
# Unit tests prove the code; FUNCTIONAL_CMD proves the APPLICATION — boot an
# ephemeral instance, apply this repo's config/schema the way prod applies it,
# interrogate it through its API. Doctrine in docs/testing.md.
# Origin: the 2026-07-17 prod 500 — an invalid stage-enum shape passed lint
# and review because nothing ever ran the application.
#
# Optional: a repo can diff-gate the functional cycle via FUNCTIONAL_PATHS.
# TEST_CMD already boots the fixture CRM (schema apply + rebuild) on every
# card, so the full test-stack cycle is mandatory only when the diff touches
# paths that change what the running app serves. Matching is by PATH PREFIX.
# Unset/empty FUNCTIONAL_PATHS = template semantics: always run.
if [ -n "${FUNCTIONAL_CMD:-}" ]; then
  func_hit="(always: FUNCTIONAL_PATHS unset)"
  if [ -n "${FUNCTIONAL_PATHS:-}" ]; then
    func_hit=""
    func_changed="$( { git diff --name-only "$BASE_REF" -- 2>/dev/null; git ls-files --others --exclude-standard; } )"
    for f in $func_changed; do
      for p in $FUNCTIONAL_PATHS; do
        case "$f" in "$p"*) func_hit="$f"; break 2 ;; esac
      done
    done
  fi
  if [ -n "$func_hit" ]; then
    echo "  … functional cycle: $FUNCTIONAL_CMD (trigger: $func_hit)"
    if out="$(eval "$FUNCTIONAL_CMD" 2>&1)"; then
      echo "  ✓ functional"
    else
      echo "  ✗ functional"
      fails+=("functional: $(printf '%s' "$out" | tail -n 30)")
      metric_gate functional
    fi
  else
    echo "  ✓ functional (skipped: diff touches none of FUNCTIONAL_PATHS)"
  fi
fi

# functional honesty (template, verbatim): a repo that ships a RUNNABLE APP
# with no functional cycle is the same lie as a waived coverage gate.
if [ -z "${FUNCTIONAL_CMD:-}" ] && [ "${GATE_ALLOW_MISSING_FUNCTIONAL:-0}" != "1" ]; then
  app_markers=()
  for m in docker-compose.yml docker-compose.yaml compose.yml compose.yaml Dockerfile; do
    [ -e "$REPO/$m" ] || [ -e "$REPO/deploy/$m" ] && app_markers+=("$m")
  done
  [ -d "$REPO/deploy" ] && app_markers+=("deploy/")
  [ -f "$REPO/scripts/test-stack.sh" ] && app_markers+=("scripts/test-stack.sh (harness exists but is NOT wired into the gate)")
  if [ "${#app_markers[@]}" -gt 0 ]; then
    fails+=("functional-honesty: this repo ships a runnable app (${app_markers[*]}) but FUNCTIONAL_CMD is not set in .claude/gate.conf. A gate that never runs the application is not a gate. Wire scripts/test-stack.sh per docs/testing.md and set FUNCTIONAL_CMD, or waive deliberately with GATE_ALLOW_MISSING_FUNCTIONAL=1.")
    metric_gate functional
  fi
elif [ -z "${FUNCTIONAL_CMD:-}" ] && [ "${GATE_ALLOW_MISSING_FUNCTIONAL:-0}" = "1" ]; then
  echo "  ⚠ functional gate DISABLED in gate.conf (GATE_ALLOW_MISSING_FUNCTIONAL=1)"
fi

# ── coverage on CHANGED LINES ────────────────────────────────────────────
if [ -n "${COVERAGE_CMD:-}" ]; then
  if out="$(eval "$COVERAGE_CMD" 2>&1)"; then
    if cov="$(python3 "$REPO/scripts/gate-coverage.py" --base "$BASE_REF" --min "$COVERAGE_MIN" 2>&1)"; then
      echo "  ✓ changed-lines coverage ($cov)"
    else
      echo "  ✗ changed-lines coverage"
      fails+=("coverage: $cov")
      metric_gate coverage
    fi
  else
    echo "  ✗ coverage run"
    fails+=("coverage run: $(printf '%s' "$out" | tail -n 4)")
    metric_gate coverage
  fi
elif [ "${GATE_ALLOW_MISSING_COVERAGE:-0}" = "1" ]; then
  echo "  ⚠ coverage gate DISABLED in gate.conf (GATE_ALLOW_MISSING_COVERAGE=1)"
else
  echo "  ✗ coverage"
  fails+=("coverage: COVERAGE_CMD is not set in .claude/gate.conf. A gate that skips a check it cannot run is not a gate. Set COVERAGE_CMD, or set GATE_ALLOW_MISSING_COVERAGE=1 deliberately.")
  metric_gate coverage
fi

if [ "${#fails[@]}" -eq 0 ]; then
  echo "gate: PASS"
  exit 0
fi

report_fails
