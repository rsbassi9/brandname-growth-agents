#!/usr/bin/env bash
# protect-paths.sh — PreToolUse hook. Stage 2.2.
#
# Blocks the implementer from editing the things that judge it.
#
# WHY BOTH THIS AND deny RULES: `permissions.deny` in settings.json stops the
# Edit/Write tools, but a worker with Bash can still `sed -i` a test file or
# `git checkout` over gate.sh. This hook is belt; deny rules are braces. Neither
# alone is enough, and the measured stakes are high: 30.4% reward-hacking when
# the agent can touch the scorer vs 0.7% when it cannot (METR, 43x).
#
# Two classes of protection:
#
#   ALWAYS      the scorer itself — gate config, lint/typecheck/coverage config,
#               .claude/settings.json, the hooks, .git/hooks. Never editable.
#
#   AFTER-TESTS test files, once the tests-first commit exists on this branch
#               (a commit whose subject starts `tests: `). Before that commit the
#               worker is SUPPOSED to be writing tests. After it, changing a test
#               is changing the target after the arrow has left the bow.
#
# If the implementation genuinely requires a test change, the worker must
# kanban_block and ask. That is the intended escape hatch — not a bypass.
#
# Contract: read hook JSON on stdin. Exit 0 to allow. Exit 2 to BLOCK, with the
# reason on stderr (Claude Code shows stderr to the agent). Any other exit code
# is treated as a non-blocking error, so we never fail open by accident — we
# exit 2 on our own bugs too.

set -uo pipefail

payload="$(cat)"

field() { printf '%s' "$payload" | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print(''); raise SystemExit
cur=d
for k in '$1'.split('.'):
    cur = (cur or {}).get(k) if isinstance(cur, dict) else None
print(cur if isinstance(cur,str) else '')"; }

tool="$(field tool_name)"
cwd="$(field cwd)"
path="$(field tool_input.file_path)"
[ -z "$path" ] && path="$(field tool_input.path)"
repo="${cwd:-$PWD}"

block() {
  echo "BLOCKED by protect-paths hook: $1" >&2
  echo "" >&2
  echo "You may not edit the thing that grades you. If the implementation genuinely" >&2
  echo "requires this change, stop and call:" >&2
  echo "  kanban_block(kind=\"needs_input\", reason=\"protected path needs a change: <path> — <why>\")" >&2
  exit 2
}

# ── Branch + workspace enforcement (Stage 2 carry-over). ─────────────────
# Phase G: an implementer committed to `main`, pre-approval, outside its assigned
# worktree — despite its SOUL.md forbidding all three. Soul text is a wish; a hook
# is a fact. The push-approval human gate stays as the LAST line, not the only one.
#
# `git commit` on a protected branch is blocked for EVERYONE, agent or human:
#   every repo's CLAUDE.md already says never commit to main.
# Workspace + branch on Edit/Write is enforced only for a KANBAN WORKER
#   (HERMES_KANBAN_TASK is exported by the dispatcher). A human editing on main in
#   their own checkout is not the failure mode we are guarding against, and
#   blocking it would just teach everyone to disable the hook.

protected_branch() {
  case "$1" in main|master|dev|prod|develop|production) return 0 ;; *) return 1 ;; esac
}

branch="$(git -C "$repo" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"

# Resolve the assigned worktree even if HERMES_KANBAN_WORKSPACE wasn't exported to the env
# (2026-07-11: a worker without it wrote build files into the MAIN checkout via the plugin
# symlink — the isolation checks below were silently skipped). Fall back to the task's
# worktree from git so the checks fire regardless of env propagation.
ws_resolved="${HERMES_KANBAN_WORKSPACE:-}"
if [ -z "$ws_resolved" ] && [ -n "${HERMES_KANBAN_TASK:-}" ]; then
  ws_resolved="$(git -C "$repo" worktree list 2>/dev/null | awk -v t="$HERMES_KANBAN_TASK" '$0 ~ t {print $1; exit}')"
fi

# ── tests-first freeze state, computed ONCE and honoured by BOTH branches. ──
# Marker commit `tests: <card-id>` on THIS branch (base..HEAD, so an old marker on
# main cannot lock a fresh branch out of writing tests). The Bash branch was blind to
# this until 2026-07-10 (B6-2): `sed -i test_x.py` rewrote a frozen test freely.
tests_frozen=0
# Resolve the branch point against the INTEGRATION ref, not the local branch
# name. In a shared checkout the pipeline advances origin/main by merging PRs on
# GitHub while local `main` sits where it was last pulled; measuring base..HEAD
# from a stale local main sweeps in every commit that arrived from origin --
# including OTHER cards' `tests: <card-id>` markers -- and froze tests on
# branches that never had a tests-first commit at all (mum-crm
# fix/property-type-enum, 2026-07-24: local main was 22 commits behind).
# Take the LATEST branch point across the candidates, so a local main that is
# AHEAD of origin/main is handled too. Deliberately NOT @{upstream}: once a card
# branch is pushed its upstream is ITSELF, the range collapses to empty, and the
# freeze silently disarms -- the one failure mode this guard must never have.
# Scoped to the repo containing $1, NOT to the session cwd. Echoes 0 or 1.
#
# 2026-08-02 (tradebot): this was computed once from `repo="${cwd:-$PWD}"` and
# never from the path being written, which broke in BOTH directions.
#   * FALSE POSITIVE -- a repo's main checkout sat on an old card branch
#     carrying a `tests:` commit, so every call in a session cwd'd there was
#     frozen for every test file in every worktree; a brand-new zero-commit
#     branch could not be edited and a card stalled.
#   * FALSE NEGATIVE -- when the session cwd is not a git repo at all
#     (/home/agent, where a main session's shell cwd resets to), `_base` stayed
#     empty, the marker search never ran, and the freeze silently DISARMED
#     everywhere. That is the exact failure this guard "must never have",
#     named a few lines above and reintroduced by the cwd coupling.
# Pinned by tests/test_protect_paths_freeze_scope.py in assistant-ops.
_freeze_for() {
  _ff_p="$1"; _ff_base=""; _ff_top=""
  [ -n "$_ff_p" ] || { echo 0; return; }
  _ff_d="$_ff_p"
  [ -d "$_ff_d" ] || _ff_d="$(dirname -- "$_ff_d")"
  [ -d "$_ff_d" ] || { echo 0; return; }
  _ff_top="$(git -C "$_ff_d" rev-parse --show-toplevel 2>/dev/null || true)"
  [ -n "$_ff_top" ] || { echo 0; return; }
  # Card repos only. The freeze encodes a card convention that exists only in
  # this instance's own repos — a vendored fork's own `test:` commits vs its
  # own upstream would otherwise get frozen too. Disarm ONLY when the origin
  # parses as a github repo owned by someone else; a missing or unparseable
  # origin keeps the freeze (a silent disarm is the one failure this function
  # must never have).
  # Origin check DEFERRED to the marker-found path: as an unconditional
  # preamble it forked git+sed on every Bash/Edit in every session for a
  # verdict only consulted when a tests: marker exists.
  _ff_card_repo() {
    _ffo="$(git -C "$_ff_top" remote get-url origin 2>/dev/null || true)"
    _ffw="$(printf '%s\n' "$_ffo" | sed -nE 's#^(git@github\.com:|ssh://git@github\.com/|https?://github\.com/)([^/]+)/.*#\2#p' | tr '[:upper:]' '[:lower:]')"
    if [ -n "$_ffw" ] && [ "$_ffw" != "rsbassi9" ]; then return 1; fi
    return 0   # fail CLOSED: absent/unparseable origin keeps the freeze
  }
  for _ref in origin/main origin/master main master; do
    git -C "$_ff_top" rev-parse --verify --quiet "$_ref" >/dev/null 2>&1 || continue
    _b="$(git -C "$_ff_top" merge-base HEAD "$_ref" 2>/dev/null || true)"
    [ -n "$_b" ] || continue
    if [ -z "$_ff_base" ] || git -C "$_ff_top" merge-base --is-ancestor "$_ff_base" "$_b" 2>/dev/null; then
      _ff_base="$_b"
    fi
  done
  [ -n "$_ff_base" ] || { echo 0; return; }
  # Tolerant on purpose (2026-08-03). This used to be `grep -q '^tests: '` --
  # case-sensitive and anchored. Measured on shado-engine, three of twelve
  # cards wrote `Tests:` or `Test:` and the freeze silently never armed, so
  # their test files stayed editable for the whole card with nothing reporting
  # it. A guard whose arming depends on an agent's capitalisation is a guard
  # that fails open, and a freeze that fails open is indistinguishable from a
  # freeze that is holding.
  #
  # Deliberately NOT requiring the card id: that would be stricter but would
  # turn every mistyped id back into a silent no-freeze. The id belongs in the
  # report below, not in a condition that fails open.
  _ff_marker="$(git -C "$_ff_top" log --format=%s "${_ff_base}..HEAD" 2>/dev/null \
                | grep -iE '^[[:space:]]*tests?:' | tail -1)"
  # A freeze the branch no longer REACHES still counts (2026-08-04). The check
  # above is reachability, and `git reset` past the marker makes the file
  # writable again: shado-engine card P4-8a reset past its own `tests:` commit
  # twice, rewrote frozen assertions it judged unsatisfiable, and re-committed,
  # with the guard seeing an unfrozen branch at every edit. The reflog
  # remembers what reachability forgot.
  #
  # Matched on the reflog ACTION (`commit:`, `commit (amend):`) so only a
  # marker COMMITTED in this worktree arms it — a checkout, a merge or a pull
  # that merely mentions one does not. Same resolved toplevel as above, so a
  # per-card worktree sees only its own history.
  # Scoped to the CARD (2026-08-04, same day, correcting the line below it).
  # Grepping the whole reflog for any `tests:` commit froze every test file in
  # any long-lived checkout that had ever reset one away — assistant-ops had a
  # single such entry from an unrelated card and locked the repo out entirely.
  # The abuse this catches is a WORKER resetting past ITS OWN freeze, so it
  # requires that worker's card id and matches nothing else. An interactive
  # session has no HERMES_KANBAN_TASK and is unaffected here; the base..HEAD
  # check above still governs it, unchanged.
  if [ -z "$_ff_marker" ] && [ -n "${HERMES_KANBAN_TASK:-}" ]; then
    _ff_reflog="$(git -C "$_ff_top" reflog --format='%gs' 2>/dev/null \
                  | grep -iE "^commit[^:]*:[[:space:]]*tests?:[[:space:]]*${HERMES_KANBAN_TASK}" \
                  | sed 's/^[^:]*:[[:space:]]*//' | tail -1)"
    if [ -n "$_ff_reflog" ]; then
      _ff_marker="$_ff_reflog (reset away — held by the reflog)"
    fi
  fi
  if [ -n "$_ff_marker" ] && ! _ff_card_repo; then
    _ff_marker=""   # non-card repo (parseable non-rsbassi9 origin): no freeze
  fi
  if [ -n "$_ff_marker" ]; then
    printf 'protect-paths: tests frozen by %s\n' "$_ff_marker" >&2
    echo 1
  else
    echo 0
  fi
}

# Default for the Bash branch, which has no authoritative target path. The
# Edit/Write branch RE-RESOLVES against the file it is actually writing.
tests_frozen="$(_freeze_for "$repo")"

if [ "$tool" = "Bash" ]; then
  raw_cmd="$(printf '%s' "$payload" | python3 -c "
import json,sys
try: print((json.load(sys.stdin).get('tool_input') or {}).get('command','') or '')
except Exception: print('')")"
  # The verb must END the subcommand word. A hyphen is a word boundary, so `merge\b`
  # matched `git merge-base` — a read-only query — and blocked it on every protected
  # branch in a non-allowlisted repo (2026-07-27). Same for cherry/cherry-pick and
  # commit/commit-tree. [^-[:alnum:]_] requires the next character to be neither a hyphen
  # nor a word character; the end-of-string alternative covers a bare `git commit`.
  # Repo identity for a git command is its -C TARGET, not the shell's cwd
  # (2026-07-28). `repo` above comes from the payload cwd, so `git -C /other/repo
  # commit` was judged by whatever branch this shell happened to be standing in:
  # measured refusing a commit to a worktree on ci/gate-workflow purely because the
  # shell sat in ~/repos/mum-crm on main. Mirrors guard-git.py's DASH_C, which has
  # resolved -C this way since 2026-07-09; the two hooks must agree about which repo
  # a command touches. Quoted literals are stripped first so a path named inside a
  # commit message cannot redirect the branch check.
  git_repo="$repo"
  _dashc="$(printf '%s' "$raw_cmd" | python3 -c "
import re,sys
cmd = sys.stdin.read()
q = chr(34)
cmd = re.sub(r'[\x27][^\x27]*[\x27]', ' ', cmd)
cmd = re.sub(q + '[^' + q + ']*' + q, ' ', cmd)
m = re.search(r'\bgit\s+(?:-\S+\s+\S+\s+)*?-C\s+(\S+)', cmd)
print(m.group(1) if m else '')")"
  if [ -n "$_dashc" ]; then
    case "$_dashc" in "~"*) _dashc="$HOME${_dashc#\~}" ;; esac
    case "$_dashc" in /*) : ;; *) _dashc="$repo/$_dashc" ;; esac
    # Only trust it when it really is a git repo; otherwise keep cwd, which fails
    # toward the stricter check rather than toward "no branch found".
    if git -C "$_dashc" rev-parse --git-dir >/dev/null 2>&1; then
      git_repo="$_dashc"
      branch="$(git -C "$git_repo" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
    fi
  fi

  if printf '%s' "$raw_cmd" | grep -qE '(^|[;&|]\s*)git\s+(-C\s+\S+\s+)?(commit|merge|cherry-pick|rebase|revert|am)([^-[:alnum:]_]|$)'; then
    # --abort / --quit / --skip create nothing; blocking them strands someone mid-conflict.
    # --continue DOES create the commit and must NOT be exempted.
    # Strip quoted literals BEFORE matching, and require the flag to belong to the git
    # command itself. Without this, any command whose TEXT contains the word is waived:
    #     git commit -m "docs: --abort stays allowed"
    # committed to a protected branch on 2026-07-27 (mum-crm dae2c19) without consuming
    # the one-time token. guard-git.py already encodes this lesson for --no-verify.
    bare_abort="$(printf '%s' "$raw_cmd" | sed "s/'[^']*'/ /g; s/\"[^\"]*\"/ /g")"
    if printf '%s' "$bare_abort" | grep -qE '\bgit\b[^|;&]*\s--(abort|quit|skip)\b'; then
      :   # allowed — aborting or unwinding, not creating a commit
    elif [ -n "$branch" ] && protected_branch "$branch"; then
      # This instance starts with NO standing main-push exceptions (unlike the
      # reference system, which trusts a handful of its own infrastructure
      # repos to skip the token). Every repo goes through the same door: a
      # ONE-TIME token file `.claude/allow-main-push-<card-id>` that only
      # Rajvir can create (agents cannot write .claude/ — see below). The
      # hook honours it once and deletes it. A Telegram "yes" is not enough:
      # the token file is the only thing a hook can verify. If a repo ever
      # earns a standing exception, add it explicitly here — a deliberate,
      # per-repo call, not an assumption carried over from the reference
      # system's own trust decisions about ITS repos.
      # Identify the repo by its GIT DIR, not the checkout's directory name. A worktree
      # has a different basename than its repo, so a name-based exemption silently
      # disappears inside one. --git-common-dir points at
      # the MAIN repo's .git from any worktree; its parent is the canonical checkout.
      # Falls back to the old basename if git cannot answer — that fails toward blocking.
      _common_dir="$(git -C "$git_repo" rev-parse --git-common-dir 2>/dev/null || true)"
      if [ -n "$_common_dir" ]; then
        # One resolution covers both forms. --git-common-dir returns ".git" in an
        # ordinary checkout and an ABSOLUTE path to the main repo's .git inside a
        # worktree; cd-ing to its dirname from $repo lands on the canonical checkout
        # either way, because an absolute cd discards the first one.
        # A bare repo in a shared git dir ('<shared>/<name>.git') carries its own
        # identity; only a literal '<checkout>/.git' delegates it to the parent.
        _cd_base="$(basename "$_common_dir")"
        if [ "$_cd_base" != ".git" ] && [ "$_cd_base" != "${_cd_base%.git}" ]; then
          repo_name="${_cd_base%.git}"
        else
          repo_name="$(basename "$(cd "$git_repo" && cd "$(dirname "$_common_dir")" && pwd)")"
        fi
      else
        repo_name="$(basename "$(git -C "$git_repo" rev-parse --show-toplevel 2>/dev/null || echo "$git_repo")")"
      fi
      token="$git_repo/.claude/allow-main-push-${HERMES_KANBAN_TASK:-none}"
      if [ -f "$token" ]; then
        # Do NOT consume the token yet: a later guard may still block this command,
        # and a blocked command must not spend the token (a compound
        # command blocked after the token was already deleted wastes it).
        # Record the intent and consume only on the allow path, after every guard passes.
        token_to_consume="$token"
      else
        block "git commit on protected branch '$branch'. Create a feature branch first: git switch -c feat/<card-id>. (No standing exceptions on this instance — a one-time .claude/allow-main-push-<card-id> token, or .claude/allow-main-push-none for interactive sessions, that only Rajvir can create.)"
      fi
    fi
  fi

  # ── Push to a protected branch (2026-07-27) ──────────────────────────
  # `git push` was never gated — only commit/merge/cherry-pick/rebase/revert/am.
  # A push from a feature branch with an explicit refspec (e.g. `git push origin
  # master`) pushes the REFSPEC's target, not the current branch, so HEAD alone is
  # not sufficient. Judge the push by its refspec destination.
  if printf '%s' "$raw_cmd" | grep -qE '(^|[;&|]\s*)git\s+(-C\s+\S+\s+)?push\b'; then
    # Default: the current branch is what's being pushed.
    push_branch="$branch"
    # Parse an explicit refspec, if one is given.
    _parsed="$(printf '%s' "$raw_cmd" | python3 -c "
import re, sys
cmd = sys.stdin.read().strip()
cmd = re.sub(r'-C\s+\S+', '', cmd, count=1)
m = re.search(r'git\s+push\b(.*)', cmd)
if not m:
    print(''); sys.exit(0)
tail = m.group(1).strip()
# Break into tokens, stripping flags (and their values when applicable).
tokens = []
parts = tail.split()
i = 0
NO_VAL_FLAGS = {'--all','--tags','--mirror','--force','--delete','--dry-run',
                '--porcelain','--prune','--no-verify','--follow-tags','--atomic',
                '--thin','--no-thin','--recurse-submodules','--force-with-lease',
                '--set-upstream','-f','-u','-n','-q','-v'}
while i < len(parts):
    t = parts[i]; i += 1
    if t.startswith('-') and t not in ('-', '--'):
        if '=' not in t and t not in NO_VAL_FLAGS:
            if i < len(parts) and not parts[i].startswith('-'):
                i += 1  # consume the value
        continue
    tokens.append(t)
# tokens[0] is the remote. A refspec exists when there is a second non-flag token.
if len(tokens) < 2:
    # No explicit refspec — the push target is the current branch.
    # --tags pushes tags only, not the current branch.
    if re.search(r'\b--tags\b', tail):
        print(''); sys.exit(0)
    print(''); sys.exit(0)
rs = tokens[1]
# Normalise the destination branch from the refspec.
dst = ''
if rs.startswith(':'):
    dst = rs[1:]                         # delete remote branch
elif ':' in rs:
    dst = rs.split(':', 1)[1]            # src:dst
elif rs.startswith('refs/heads/'):
    dst = rs[11:]                        # refs/heads/<branch>
elif rs.startswith('refs/tags/'):
    dst = ''                             # tag push — fine
elif rs.startswith('refs/'):
    dst = ''                             # non-branch ref — fine
else:
    dst = rs                             # bare branch name or tag
# Strip any remaining refs/ prefix
if dst.startswith('refs/heads/'):
    dst = dst[11:]
elif dst.startswith('refs/tags/') or dst.startswith('refs/'):
    dst = ''
print(dst)
")"
    if [ -n "$_parsed" ]; then
      push_branch="$_parsed"
    fi

    if protected_branch "$push_branch"; then
      # Identify the repo by its GIT DIR (same identity fix as the commit block above).
      _common_dir="$(git -C "$git_repo" rev-parse --git-common-dir 2>/dev/null || true)"
      if [ -n "$_common_dir" ]; then
        # A bare repo in a shared git dir ('<shared>/<name>.git') carries its own
        # identity; only a literal '<checkout>/.git' delegates it to the parent
        # (2026-08-18: assistant-ops resolved to 'git-common' and lost its own
        # exemption, blocking every commit to the only checkout that has master).
        _cd_base="$(basename "$_common_dir")"
        if [ "$_cd_base" != ".git" ] && [ "$_cd_base" != "${_cd_base%.git}" ]; then
          repo_name="${_cd_base%.git}"
        else
          repo_name="$(basename "$(cd "$git_repo" && cd "$(dirname "$_common_dir")" && pwd)")"
        fi
      else
        repo_name="$(basename "$(git -C "$git_repo" rev-parse --show-toplevel 2>/dev/null || echo "$git_repo")")"
      fi
      token="$git_repo/.claude/allow-main-push-${HERMES_KANBAN_TASK:-none}"
      # No standing exceptions on this instance — see the commit block above.
      if [ -f "$token" ]; then
        token_to_consume="$token"
      else
        block "git push to protected branch '$push_branch'. Pushing to a protected branch requires a one-time .claude/allow-main-push-<card-id> token that only Rajvir can create."
      fi
    fi
  fi
fi

if [ -n "${HERMES_KANBAN_TASK:-}" ]; then
  if [ -n "$branch" ] && protected_branch "$branch"; then
    block "this card is working on protected branch '$branch'. Run: git switch -c feat/${HERMES_KANBAN_TASK}"
  fi
  ws="$ws_resolved"
  if [ -n "$ws" ] && [ -d "$ws" ]; then
    ws_real="$(cd "$ws" 2>/dev/null && pwd -P || echo "$ws")"
    cwd_real="$(cd "$repo" 2>/dev/null && pwd -P || echo "$repo")"
    # A workspace DIRECTORY is not a workspace. The dispatcher creates the dir at
    # claim time; the git worktree inside it is created separately and can be
    # missing. `-d` alone treated an empty dir as usable, so the mismatch message
    # below sent the agent to a path containing no repo — unactionable, and
    # unfixable from inside the run (a worker cannot create its own worktree).
    # mum-crm t_d48fa434, 2026-07-27: three engine runs died retrying this, and
    # the failure was misread as the model tier being unavailable.
    ws_top="$(git -C "$ws_real" rev-parse --show-toplevel 2>/dev/null || echo "")"
    [ -n "$ws_top" ] && ws_top="$(cd "$ws_top" 2>/dev/null && pwd -P || echo "$ws_top")"
    if [ "$ws_top" != "$ws_real" ]; then
      block "card ${HERMES_KANBAN_TASK} is assigned workspace '$ws_real', but that path is not provisioned — it contains no git worktree, so it cannot be worked in. Do NOT retry and do NOT switch directories; nothing inside this run can create the worktree. Stop and call kanban_block(kind=\"needs_input\", reason=\"workspace not provisioned: no git worktree at $ws_real\")."
    fi
    case "$cwd_real/" in
      "$ws_real"/*) ;;
      *) block "card ${HERMES_KANBAN_TASK} is assigned worktree '$ws_real', but this tool is running in '$cwd_real'. Work in your assigned workspace." ;;
    esac
  fi
fi

# ── Bash: the actual belt. ───────────────────────────────────────────────
# Without this the hook is theatre: `Edit` is blocked, and the worker simply runs
# `sed -i s/80/0/ .claude/gate.conf`. Verified: before this branch existed, that
# exact command sailed through. Reading a protected file stays allowed — a worker
# SHOULD read the gate to understand why it failed.
if [ "$tool" = "Bash" ]; then
  cmd="$(printf '%s' "$payload" | python3 -c "
import json,sys
try: print((json.load(sys.stdin).get('tool_input') or {}).get('command','') or '')
except Exception: print('')")"
  [ -n "$cmd" ] || exit 0

  # ── Pre-push gate integrity (2026-07-11). The main-push exception repos rely on a
  # pinned pre-push hook (.githooks/pre-push) to gate freehand pushes to main. A hook is
  # advisory: `--no-verify` skips it and re-pointing core.hooksPath disables it. Neither
  # is legitimate for a worker — the honest path when the gate is wrong is kanban_block.
  # Strip single-quoted literals so `echo 'git push --no-verify'` (words, not a command)
  # is not mistaken for a real bypass.
  bare_cmd="$(printf '%s' "$cmd" | sed "s/'[^']*'/ /g")"
  if printf '%s' "$bare_cmd" | grep -qE '(^|[;&|[:space:]])git\b'; then
    if printf '%s' "$bare_cmd" | grep -qE '\-\-no-verify\b' && printf '%s' "$bare_cmd" | grep -qE '\b(push|commit)\b'; then
      block "git push/commit with --no-verify skips the pinned pre-push gate (.githooks/pre-push). If the gate is genuinely wrong, kanban_block and ask — do not bypass it."
    fi
    if printf '%s' "$bare_cmd" | grep -qE '\bconfig\b' && printf '%s' "$bare_cmd" | grep -qiE 'hookspath'; then
      block "changing git core.hooksPath would disable the pinned pre-push gate (.githooks). Not a worker-editable setting."
    fi
  fi

  # ── Service protection (2026-07-11). A worker must NOT kill or restart the platform ──
  # it runs under. On T1 an implementer whose DoD said "restart hermes dashboard" ran
  # `pkill -f hermes.*dashboard` + `kill <pid>` and killed its own gateway → crashed twice.
  # Sanctioned: `systemctl --user restart hermes-dashboard.service` always, and
  # `systemctl --user restart hermes-gateway.service` ONLY from an interactive session
  # with no card in flight (2026-07-27 — gateway hooks register once at startup, so a
  # hook change is dead until a bounce, and the blanket ban cost a human round-trip
  # every time. The ban's real hazard is narrower than the ban: that the process asking
  # is usually running UNDER the unit it wants to restart).
  svc_rc=0
  svc_out="$(CMD="$cmd" TASK="${HERMES_KANBAN_TASK:-}" python3 - <<'PY'
import glob, os, re, sqlite3, sys
# Quote handling, split by SHAPE (2026-08-18, round-5 — measured hole).
# The old single rule DELETED every single-quoted literal, so
# `systemctl --user restart 'hermes-gateway.service'` left no hermes- token:
# SYSTEMCTL_HERMES found nothing, the allowances fullmatch-failed, and a quoted
# gateway bounce PASSED. But a quoted PHRASE really is data (`echo 'p<kill>
# hermes'` must stay allowed), so the two shapes are judged differently — the
# same split guard-services.py::unquote() uses, kept in step deliberately:
#   quoted WORD (no whitespace)   -> unquote: it is an argument wearing quotes
#   single-quoted PHRASE (spaces) -> drop:    it is data, not a command
bare = re.sub(r"""(['"])([^'"\s]*)\1""", r"\2", os.environ["CMD"])
bare = re.sub(r"'[^']*'", " ", bare)
# TWO RULES, because two different kinds of text are being read (2026-07-31).
# PLAT stays a SUBSTRING: `pkill -f X` kills anything whose cmdline contains X,
# so "could this pattern reach the platform?" is the right question. Narrowing
# it releases the T1 kill itself — `pkill -f <venv>/bin/python` names no
# platform identifier and matches the gateway's own cmdline.
# PLAT_IDENT is for the one place the text is a process IDENTITY: the
# /proc/<pid>/cmdline read for `kill <pid>`. A substring there made the
# `claude` inside /tmp/claude-1000/... — every Claude Code scratchpad path —
# refuse an ordinary kill. A name counts only where it names a
# process/unit/module: not a continuation of a longer word (`~/.claude/hooks`),
# not an interior path component (`hermes-agent/venv`), and `claude|qmd` take
# no dashed tail (`claude-1000`).
# guard-services.py carries the full rationale; the two must stay in step.
PLAT = r"hermes|gateway|dashboard|litellm|tirith|qmd|claude"
PLAT_IDENT = (r"(?<![\w.-])(?:(?:hermes|gateway|dashboard|litellm|tirith)(?:[-_.][\w.-]*)?"
              r"|(?:claude|qmd)(?:\.[A-Za-z]\w*)*(?![\w-]))(?![\w.-]*/)")

DASHBOARD = r"\bsystemctl\b(?:\s+--user)?\s+restart\s+hermes-dashboard(?:\.service)?(?=\s*(?:$|&&|\|\||;|\||[>&#)\n]|2>))"
# The clause-end lookahead (2026-08-18): without it the sanctioned-strip ate
# the systemctl anchor out of a MULTI-UNIT restart, so `restart
# hermes-events-receiver hermes-gateway` left a bare " hermes-gateway" that no
# danger rule matched — a gateway bounce smuggled through the sanction.
# Sanctioned like the dashboard (design decision): nothing runs under the
# events receiver and a dropped delivery is fire-and-forget by design.
RECEIVER = r"\bsystemctl\b(?:\s+--user)?\s+restart\s+hermes-events-receiver(?:\.service)?(?=\s*(?:$|&&|\|\||;|\||[>&#)\n]|2>))"
# Deliberately a WHOLE-command match, unlike the dashboard rule above: a mere search
# would let `systemctl --user restart hermes-gateway.service && pkill -f hermes` buy its
# way past every check below on the strength of its first clause. Anything chained,
# redirected or otherwise decorated falls through to the danger checks instead.
# The hermes CLI is a SECOND DOOR onto the same act (2026-07-31):
# `hermes gateway stop|restart`, `<venv>/bin/hermes gateway ...` and
# `python -m hermes_cli.main gateway ...` do what the systemctl verbs do, and
# every rule here keyed on the literal string `systemctl`. Same policy, not a
# new one: a RESTART is judged by gateway_restart_ok() below; stop/uninstall
# are refused outright. `run` is the foreground gateway itself and
# start/status/list/setup are read-only or additive — all stay unguarded,
# exactly as `systemctl start` is.
# python(?:3(?:\.\d+)?)? — a bare `python3?` missed `python3.11 -m ...`.
CLI = (r"(?<![\w./-])(?:\S*/)?"
       r"(?:hermes\b|python(?:3(?:\.\d+)?)?\s+-m\s+hermes_cli(?:\.main)?\b)")
CLI_FLAGS = r"(?:\s+-\S+(?:\s+\S+)?)*"
GATEWAY = (r"\s*(?:systemctl\s+--user\s+restart\s+hermes-gateway(?:\.service)?"
           r"|" + CLI + CLI_FLAGS + r"\s+gateway\s+restart)\s*")
CLI_GATEWAY_VERB = CLI + CLI_FLAGS + r"\s+gateway\s+(?:stop|restart|uninstall)\b"


def gateway_restart_ok():
    """Is bouncing the gateway safe RIGHT NOW? -> (ok, why_not)."""
    # A dispatched worker IS what dies — it runs under the unit. No board state makes
    # that safe, so it is checked first and on its own.
    task = os.environ.get("TASK", "")
    if task:
        return False, ("a dispatched worker (card %s) runs UNDER hermes-gateway.service "
                       "— restarting it kills this very process mid-card (T1, "
                       "2026-07-11). Ask Rajvir rather than bouncing the service you "
                       "run under." % task)
    live = []
    for db in glob.glob(os.path.expanduser("~/.hermes/kanban/boards/*/kanban.db")):
        try:
            con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
            live += ["%s:%s" % (db.split("/")[-2], r[0]) for r in con.execute(
                "select id from tasks where status in ('running','in_progress')")]
            con.close()
        except Exception as e:
            # Fail closed: a board we cannot read cannot prove the box is idle.
            return False, ("could not read %s to prove no card is in flight (%s); "
                           "refusing rather than guessing." % (db, type(e).__name__))
    if live:
        return False, ("cards are in flight and their workers run under this service: "
                       "%s. Wait for them to finish, or ask Rajvir."
                       % ", ".join(sorted(live)[:5]))
    return True, ""


# A sanctioned dashboard restart is REMOVED from the text rather than exiting early,
# and whatever remains is still judged. The old form exited 0 on a mere search, so
# `<dashboard restart> && pkill -f hermes` bought passage for its second clause on the
# strength of its first. Stripping keeps the restart legitimately chainable (`&& curl
# :9119` is fine) while leaving every other clause exposed to the checks below. The
# gateway allowance above stays a whole-command fullmatch instead: it tears down the
# unit workers run under, so "bare command only" is the right bar there.
bare = re.sub(DASHBOARD, " ", bare)
bare = re.sub(RECEIVER, " ", bare)
if re.fullmatch(GATEWAY, bare):
    ok, why = gateway_restart_ok()
    if ok:
        sys.exit(0)
    print("restarting hermes-gateway.service is not safe here: %s" % why, end="")
    sys.exit(1)

danger = False
if re.search(r"\b(?:hermes|hermes_cli(?:\.main)?)\b(?:\s+-\S+(?:\s+\S+)?)*\s+dashboard\b", bare): danger = True  # spawning a duplicate dashboard
if re.search(r"\bsystemctl\b[^\n;|&]*\b(stop|restart|kill|disable|mask)\b[^\n;|&]*\bhermes-\S+", bare): danger = True
if re.search(CLI_GATEWAY_VERB, bare): danger = True  # the same act, spelled through the hermes CLI
if re.search(r"\b(pkill|killall)\b", bare) and re.search(PLAT, bare, re.I): danger = True
if re.search(r"\bpgrep\b", bare) and re.search(PLAT, bare, re.I) and re.search(r"\b(xargs|kill)\b", bare): danger = True
m = re.search(r"\bkill\b(?:\s+-\w+)?\s+(\d{2,7})\b", bare)
if m:
    try:
        c = open(f"/proc/{m.group(1)}/cmdline","rb").read().replace(b"\0",b" ").decode("utf-8","replace")
        if re.search(PLAT_IDENT, c, re.I): danger = True  # identity, not a pattern
    except Exception: pass
sys.exit(1 if danger else 0)
PY
)" || svc_rc=$?
  if [ "$svc_rc" -ne 0 ]; then
    block "${svc_out:-this command kills or restarts a Hermes platform service (gateway/dashboard/…). A worker runs UNDER hermes-gateway.service — bouncing it crashes you (this is what killed T1, 2026-07-11).} Sanctioned: systemctl --user restart hermes-dashboard.service (always), systemctl --user restart hermes-events-receiver.service (always — nothing runs under it), and systemctl --user restart hermes-gateway.service from an interactive session with no card in flight. The hermes-CLI spelling 'hermes gateway restart' is the same act and gets the same treatment; there is no sanctioned 'stop'."
  fi

  verdict="$(REPO="$repo" CMD="$cmd" WS="$ws_resolved" TASK="${HERMES_KANBAN_TASK:-}" FROZEN="$tests_frozen" python3 - <<'PY'
import os, re, sys
cmd  = os.environ["CMD"]
repo = os.environ.get("REPO", "")
ws   = os.environ.get("WS", "")
task = os.environ.get("TASK", "")
frozen = os.environ.get("FROZEN") == "1"

# Split on EVERY command separator: newline, ; && || and a SINGLE pipe. A splitter
# that only breaks on &&|;|| (the B6-3 sibling bug) lets `cat f | tee protected` and a
# newline-separated write hide inside one "segment". Over-splitting is safe for a
# guard — it can only create MORE chances to spot a protected write, never fewer.
SEGS = [s.strip() for s in re.split(r"&&|\|\||[;\n|]", cmd) if s.strip()]

# ── Bash writes OUTSIDE the assigned worktree (Stage 2.2 follow-up (a)). ──
# `sed -i /home/agent/repos/other/x.py` runs with cwd inside the worktree and writes
# anywhere it likes; the Edit path is covered by the workspace check above.
WRITE_VERB = re.compile(
    r"(^|[;&|]\s*)\s*(sed\s+-i|tee|cp|mv|rm|install|truncate|dd|patch|chmod|chown"
    r"|git\s+-C\s+\S+\s+(commit|checkout|restore|apply)"
    r"|python3?\s+-c|tee\s+-a|touch|mkdir)\b")
REDIR = re.compile(r"(?<![0-9&])>>?\s*(?P<p>[^\s;&|>]+)")

def outside(p: str) -> bool:
    try:
        full = os.path.realpath(os.path.expanduser(p if os.path.isabs(p) or p.startswith("~")
                                                  else os.path.join(repo, p)))
        return not (full == ws_real or full.startswith(ws_real + os.sep))
    except Exception:
        return False

if task and ws and os.path.isdir(ws):
    ws_real = os.path.realpath(ws)
    for seg in SEGS:
        writes = bool(WRITE_VERB.search(seg))
        redirs = [m.group("p") for m in REDIR.finditer(seg)]
        if not writes and not redirs:
            continue
        cands = list(redirs)
        for tok in seg.split():
            if tok.startswith("-"):
                continue
            if tok.startswith("/") or tok.startswith("~") or "../" in tok:
                cands.append(tok)
        for p in cands:
            if p in ("/dev/null", "/dev/stdout", "/dev/stderr"):
                continue
            if p.startswith("/tmp/") or p.startswith("/var/tmp/"):
                continue      # scratch space is fine; the worktree is what matters
            if outside(p):
                print(f"BLOCK::a shell command writes to '{p}', outside card {task}'s "
                      f"worktree ({ws_real})")
                sys.exit(0)

# ── Path-independent, always dangerous. ──
for rx, why in [
    (r"git\s+commit\b[^\n]*--no-verify", "git commit --no-verify skips the gate"),
    (r"git\s+config\b[^\n]*core\.hooksPath", "rerouting core.hooksPath disables the git hooks"),
    (r"chmod\b[^\n]*[-+]x\b[^\n]*(gate\.sh|hooks/)", "chmod on the gate or hooks"),
]:
    if re.search(rx, cmd):
        print(f"BLOCK::{why}"); sys.exit(0)

# ── Protected scorer/gate/token targets. Matched on a distinctive BASENAME anywhere
#    in a segment, because `cd .claude && sed gate.conf`, `open('.cl'+'aude/gate.conf')`
#    and `awk 'print > "gate.conf"'` all evade a literal `.claude/gate.conf` regex
#    (B6-1). READING a protected file stays allowed — only a WRITE to one is refused,
#    classified by what the segment DOES, never by its first word. ──
PROT = re.compile(
    r"gate\.conf|gate\.sh|gate-[\w.-]+\.py|allow-main-push-[\w.-]*|conftest\.py|"
    r"pytest\.ini|tox\.ini|\.coveragerc|ruff\.toml|mypy\.ini|\.flake8|tsconfig\.json|"
    r"jest\.config\.|vitest\.config\.|\.eslintrc|eslint\.config\.|"
    r"\.claude/settings(\.local)?\.json|\.claude/hooks/|\.git/hooks/|(?:^|[^\w/])setup\.cfg\b")
    # No isolated client-data root on this instance (the reference system
    # protects a CRM data root here — /srv/mum-crm, unix-perm-walled — tied to
    # a client repo we don't have). If a future project needs the same
    # treatment (a data root outside any repo that agents must reach only via
    # a scoped API), add its path here explicitly, matching this pattern.
# Test files, for the after-tests freeze on the Bash branch (B6-2).
TESTF = re.compile(
    r"test_[\w.-]+\.py|[\w.-]+_test\.py|[\w.-]+\.test\.[jt]sx?|[\w.-]+\.spec\.[jt]sx?"
    r"|[\w.-]+_test\.go|(?:^|[^\w/])(?:tests|spec)/")

# Writer verbs, matched as WORDS ANYWHERE in a segment (not just as the leader): a
# leader-anchored match is defeated by an `env X=1 tee ...`, `xargs -I{} sed -i ...`,
# `nice cp ...`, `timeout 5 dd ...` prefix. Matching the verb as a word closes that.
# `bash`/`sh`/`python <file>` are NOT here — running a script executes it, it does not
# write the protected file; inline `-c/-e` programs are handled by INLINE_INTERP above.
WRITER_WORD = re.compile(r"\b(tee|dd|truncate|patch|install|cp|mv|ln|touch|chmod|chown|rm|sponge|shred)\b")
# An INLINE interpreter program (`python -c "..."`, `awk 'prog'`, `sh -c "..."`) is a
# quoted blob that may contain `;`, `>` and `os.chdir()` — it CANNOT be split into
# segments or parsed. So it is judged against the WHOLE command: if it references a
# protected basename anywhere, refuse. (Running a script FILE — `bash scripts/gate.sh`
# — is NOT inline and is allowed; that just executes the gate.)
INLINE_INTERP = re.compile(
    r"\b(?:python3?|perl|ruby|node|deno|php)\b[^\n]*?\s-(?:c|e|p)\b"
    r"|\bawk\b\s+(?:-[A-Za-z]+\s+)*['\"]"
    r"|\b(?:sh|bash|zsh|ksh)\b[^\n]*?\s-c\b", re.S)

def redir_tgts(seg):
    out = []
    for m in re.finditer(r"(?<![0-9&])>>?\s*([^\s;&|>]+)", seg):
        t = m.group(1)
        if t.startswith("&") or t in ("/dev/null", "/dev/stdout", "/dev/stderr"):
            continue
        out.append(t)
    return out

# Flags whose VALUE is human prose, not a path: a commit message or PR body may
# legitimately NAME a protected path while writing nothing. Without this, PROT and
# WRITER_WORD match in unrelated halves of one segment — `git commit -m "... pip
# install ... gate.conf ..."` was read as `install` writing `gate.conf` and refused
# (measured twice, 2026-07-28, on ordinary messages describing hook work).
# Scoped to git/gh/glab/hub segments ONLY, so a cp/install/tee invocation is never
# stripped and no real write target can hide behind a flag name.
VCS_LEADER = re.compile(r"(?:^|[;&|]\s*)\s*(?:sudo\s+|env\s+\S+=\S+\s+)*(?:git|gh|glab|hub)\b")
PROSE_FLAG = re.compile(
    r"(?:^|\s)(?:-m|--message|-b|--body|--title|--notes|--description|--body-file|-F|--file)"
    r"(?:=|\s+)(\"[^\"]*\"|'[^']*'|\S+)")


def strip_prose(seg: str) -> str:
    """Blank the VALUES of prose-carrying flags on a git/gh/glab/hub segment."""
    if not VCS_LEADER.search(seg):
        return seg
    return PROSE_FLAG.sub(" ", seg)


def writes_matching(seg, pat) -> bool:
    """True iff this segment WRITES a path matching `pat` (not merely reads it)."""
    if any(pat.search(t) for t in redir_tgts(seg)):
        return True                        # `> protected`, `>> protected`
    seg = strip_prose(seg)                 # a message that NAMES a path is not a write
    if not pat.search(seg):
        return False                       # the path is not named here at all
    if re.search(r"\bsed\b[^|;]*\s-\w*i\b", seg):
        return True                        # sed -i writes in place
    if WRITER_WORD.search(seg):
        return True                        # tee/dd/cp/mv/touch/ln/chmod/rm/... a protected path
    return False                           # pure read of a protected file, or write elsewhere

# No isolated-user data root outside any repo on this instance (the reference
# system refuses any docker/podman command referencing its CRM data root here,
# since a bind-mount would bypass its unix perms). Add the same pattern —
# an ISOLATED_ROOTS tuple + a RUNTIME regex check — if a future project needs
# it.

# Inline interpreters first — they cannot be segment-split (the -c/-e blob may hold
# `;`, `>`, chdir, string-concat), so within a stage they are judged against the
# whole stage. `py_compile` only reads, so it is exempt.
#
# But judge them against only the PIPE STAGES that actually contain an inline
# interpreter. A protected path in a NON-inline stage — `md5sum a/.claude/gate.conf
# | awk '{print}'`, `cat scripts/gate.sh | python3 -c "…"` — is that other tool's
# READ; the interpreter receives bytes on stdin, never the file, so blaming it is a
# false positive (hit repeatedly on routine `… | awk`, `… | python -c` inspection,
# 2026-07-24). Splitting on `|` cannot open an evasion: a `;`-separated in-quote
# write has no top-level pipe, so it stays whole inside its stage and is still
# caught; and to carry a write TARGET past a `|` you must put it in a different
# command, where the interpreter no longer runs it. `;`/`&&`/`||` are deliberately
# NOT split here — those could separate an inline interp from its own open(PROT,'w').
inline_scope = "|".join(s for s in cmd.split("|") if INLINE_INTERP.search(s))
if INLINE_INTERP.search(cmd) and not re.search(r"\bpython3?\s+-m\s+py_compile\b", cmd):
    if PROT.search(inline_scope):
        print("BLOCK::an inline interpreter program (python -c / awk / sh -c ...) "
              "references a protected path — refusing what cannot be safely parsed")
        sys.exit(0)
    if frozen and TESTF.search(inline_scope):
        print("BLOCK::an inline interpreter program references a frozen test file")
        sys.exit(0)

for seg in SEGS:
    if writes_matching(seg, PROT):
        print("BLOCK::a shell command writes to a protected path "
              "(the scorer, its config, a git hook, or the main-push token)")
        sys.exit(0)
    if frozen and writes_matching(seg, TESTF):
        print("BLOCK::a test file is frozen — the tests-first commit "
              "('tests: <card-id>') already landed on this branch")
        sys.exit(0)
print("ALLOW")
PY
)"
  case "$verdict" in
    BLOCK::*) block "${verdict#BLOCK::}" ;;
    *)
      # Consume a one-time token only after every guard has passed.
      # A block() above exits 2 and leaves the token untouched.
      if [ -n "${token_to_consume:-}" ] && [ -f "$token_to_consume" ]; then
        rm -f "$token_to_consume" || true
        [ -x "$HOME/bin/metric.sh" ] && "$HOME/bin/metric.sh" loop main_push_exception 1 "${repo_name:-unknown}:${HERMES_KANBAN_TASK:-none}" >/dev/null 2>&1 || true
        echo "protect-paths: one-time main-push exception consumed for ${HERMES_KANBAN_TASK:-none} (token deleted)" >&2
      fi
      exit 0
      ;;
  esac
fi

# Only Edit/Write-class tools carry a file_path. Everything else passes.
case "$tool" in
  Edit|Write|MultiEdit|NotebookEdit) ;;
  *) exit 0 ;;
esac
[ -n "$path" ] || exit 0

# No isolated client-data root on this instance (the reference system blocks
# writes to a CRM data root here — see the ISOLATED_ROOTS note above). Add a
# matching case block here if a future project needs it.

rel="${path#"$repo"/}"

# ── ALWAYS protected: the scorer and its configuration ───────────────────
case "$rel" in
  # Every pattern carries a `*/`-prefixed twin (same idiom as `*/conftest.py` below).
  # `rel` is relative to the REPO root, so a scorer file one level down did not match the
  # anchored form and was editable via Edit/Write — found 2026-07-27 on
  # `repo-template/.claude/hooks/protect-paths.sh`, the canonical copy provisioned into
  # every repo. Guarding the live hook but not the template that seeds it means the guard
  # survives exactly until the next repo is provisioned. The template also carries
  # settings.json, gate.sh and gate-*.py, so the whole block gets the twin, not just hooks.
  .claude/settings.json|.claude/settings.local.json|*/.claude/settings.json|*/.claude/settings.local.json) block "the permission + hook config ($rel)" ;;
  .claude/allow-main-push-*|*/.claude/allow-main-push-*) block "the one-time main-push token ($rel) — only Rajvir may create this; an agent that could mint its own token defeats the whole exception (B9-1)" ;;
  .claude/hooks/*|*/.claude/hooks/*)                 block "a hook script ($rel)" ;;
  .claude/gate.conf|*/.claude/gate.conf)             block "the gate configuration ($rel)" ;;
  scripts/gate.sh|scripts/gate-*.py|*/scripts/gate.sh|*/scripts/gate-*.py) block "the gate itself ($rel)" ;;
  .git/hooks/*|*/.git/hooks/*)                       block "a git hook ($rel)" ;;
  conftest.py|*/conftest.py)                         block "pytest's shared fixtures ($rel)" ;;
  pytest.ini|tox.ini|setup.cfg|.coveragerc)          block "test/coverage config ($rel)" ;;
  ruff.toml|.ruff.toml|mypy.ini|.flake8)             block "lint/typecheck config ($rel)" ;;
  .eslintrc*|eslint.config.*|jest.config.*|vitest.config.*) block "lint/test config ($rel)" ;;
  tsconfig.json)                                     block "typecheck config ($rel)" ;;
esac

# pyproject.toml only when it actually configures the graders.
if [ "$rel" = "pyproject.toml" ] && [ -f "$repo/pyproject.toml" ]; then
  if grep -qE '^\[tool\.(pytest|coverage|ruff|mypy)' "$repo/pyproject.toml" 2>/dev/null; then
    block "pyproject.toml configures the graders ([tool.pytest|coverage|ruff|mypy])"
  fi
fi

# ── AFTER-TESTS protected: test files, once tests have been committed ────
is_test=0
case "$rel" in
  test_*.py|*_test.py|tests/*|*/tests/*|*.test.ts|*.test.js|*.spec.ts|*.spec.js|*_test.go|spec/*)
    is_test=1 ;;
esac

# A pinned dependency list is not an assertion (2026-08-05). It cannot be
# weakened to make a failing test pass, and it is what CI installs from, so a
# card whose frozen test needs a package must be able to declare it. shado-engine
# P4-18a blocked holding a complete gate-green implementation because it could
# not add one pinned line to the file its own frozen test depended on.
#
# Exactly this filename, and nothing else. tests/fixtures/ stays frozen: it holds
# the recall-eval corpus, and recall-eval.md §6.4 forbids editing a query, a gold
# set or a corpus file to make a number pass.
case "$rel" in
  tests/requirements.txt|*/tests/requirements.txt) is_test=0 ;;
esac

# Resolve against the FILE BEING WRITTEN, not the session cwd -- the cwd may be
# another checkout entirely, or not a repo at all. See _freeze_for above.
if [ "$is_test" = "1" ] && [ "$(_freeze_for "$path")" = "1" ]; then
  # `tests_frozen` was computed once at the top (marker `tests: <card-id>` in base..HEAD),
  # and the Bash branch now honours the very same flag (B6-2).
  block "test file '$rel' is frozen — the tests-first commit ('tests: <card-id>') already landed on this branch"
fi

exit 0
