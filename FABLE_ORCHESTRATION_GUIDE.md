# FABLE_ORCHESTRATION_GUIDE.md
### How to make Sonnet / Opus / any capable model work the way Fable works
*Written by Claude Fable 5, 2026-07-06, for Bassi. Companion to the two SONNET_EXECUTION_PLAN.md files.*

---

## 1. What Fable actually does (the method, not the model)

Most of what looked like "Fable being smart" in our sessions was a repeatable operating loop:

1. **Clarify before building.** Ask 3–4 forced-choice questions up front (scope, depth, output location, verification level). Never start a multi-step task on an ambiguous brief.
2. **Audit before planning.** Never trust READMEs, roadmaps, or memory — read the code, install the deps, run the tests, boot the server, record exact errors. Plans built on verified reality don't collapse mid-execution.
3. **Plan as a binding artifact.** Write the plan into the repo as a file (SONNET_EXECUTION_PLAN.md) with: binding rules, verified current state, phased tasks with exact file paths and line numbers, and a Verification Gate after every phase. The plan is the contract; the chat is disposable.
4. **Delegate in parallel with self-contained briefs.** Spawn worker agents simultaneously on non-overlapping scopes. Each brief assumes the worker knows NOTHING about the conversation.
5. **Trust but verify.** A worker's report describes what it *intended*. After every wave, independently check git log, run the tests yourself, boot the thing. (Today this caught: a missing test fixture, a corrupted `.git/config`, a corrupted git index, and stale file-sync — none of which any worker reported.)
6. **Persist status into the artifact.** After each wave, write an EXECUTION STATUS block into the plan file with commit hashes and gate results. Any future session (or different model) can resume cold.

Any strong model following this loop gets 80–90% of Fable's output quality. The loop matters more than the model.

---

## 2. The hierarchy: roles, models, and who talks to whom

```
                    ┌─────────────────────────┐
                    │  ORCHESTRATOR (1)        │  Opus (best) or Sonnet
                    │  owns: plan, priorities, │  Long context, never writes
                    │  verification, status    │  production code itself
                    └───────┬─────────────────┘
              ┌─────────────┼──────────────┬───────────────┐
        ┌─────▼─────┐ ┌─────▼─────┐  ┌─────▼─────┐   ┌─────▼─────┐
        │ SCOUT     │ │ BUILDER A │  │ BUILDER B │   │ VERIFIER  │
        │ Haiku/    │ │ Sonnet    │  │ Sonnet    │   │ Sonnet    │
        │ Sonnet    │ │ writes    │  │ writes    │   │ fresh ctx │
        │ read-only │ │ code +    │  │ code +    │   │ re-runs   │
        │ research  │ │ tests     │  │ tests     │   │ gates     │
        └───────────┘ └───────────┘  └───────────┘   └───────────┘
```

**Rules of the hierarchy:**
- **One orchestrator, ever.** It holds the goal, the plan, and the status ledger. It decomposes, briefs, verifies, and updates status. It does NOT implement (implementing burns its context and judgment).
- **Builders never talk to each other.** All coordination flows through the orchestrator via the plan file. Two builders must never touch the same files in the same wave — partition by repo, by directory, or by phase.
- **The verifier is always a FRESH agent** with no memory of the build. It gets only: the plan file path, the phase to verify, and the gate commands. Fresh context = no motivated reasoning, no "it should work because I wrote it."
- **Scouts are cheap and disposable.** Use the smallest model that can read code/web for lookups ("what's the payload shape of endpoint X?", "what does this library's API look like today?").
- **Model assignment:** Opus → orchestration + plan-writing + judgment calls. Sonnet → building, verifying, focused research (it is excellent at bounded, well-specified work — that's exactly what the plan files create). Haiku → lookups, file inventories, summarization.

---

## 3. Context building (the part most people get wrong)

Agents don't share memory. Every context is built, not inherited.

**3a. The briefing contract.** Every brief to a sub-agent must contain, in this order:
1. **Mission + why** — one paragraph: what the owner is trying to achieve, so the agent can make judgment calls.
2. **Source of truth** — the exact file to read first (the plan), and the instruction that it overrides everything else.
3. **Verified current state** — commit hashes, what exists, what's broken, where the last worker stopped. Never let an agent discover state you already know; never assert state you haven't verified.
4. **Environment quirks** — path mappings, timeouts, permission-denied dirs, "each bash call is independent," file-sync lag. (Today's biggest time-losses were all environment quirks the briefs pre-warned about.)
5. **Hard boundaries** — never echo .env, never make paid API calls, never touch directories X/Y, mock all providers in tests.
6. **Stop conditions** — "if a gate fails and you can't fix it, STOP and report exactly where" — prevents an agent from burying a failure under later work.
7. **Report format** — "under 500 words: commits, gate numbers, where you stopped." Precise reports keep the orchestrator's context small.

**3b. Context lives in files, not chat.** The plan file + EXECUTION STATUS block + git history ARE the memory. Design so that a brand-new session can resume from `git log` + the plan file alone. This is what made today's two usage-limit interruptions cheap to recover from.

**3c. Deviation-proofing (how to make Sonnet not freelance):**
- Number every task (P1-3), fix the tech stack explicitly ("do not substitute"), give exact file paths, table schemas, endpoint signatures.
- Give the escape valve: *"If ambiguous, implement the literal instruction and tag `TODO(fable-review):` — never design an alternative."* Without an escape valve, models improvise; with one, they flag.
- One commit per task with a fixed message format (`P1-3: <summary>`) — makes verification against git log mechanical.
- Gates are commands, not vibes: `pytest -q` green, `curl /health` → 200, "run migration twice, counts must match."

---

## 4. What Sonnet/Opus lack vs Fable — and the compensation for each

| Gap | Symptom | Compensation |
|---|---|---|
| Long-horizon judgment | Optimizes the current task, drifts from the goal | Orchestrator/worker split; the plan carries the goal so no worker needs to hold it |
| Scope discipline | "While I was in there I also refactored…" | Binding rules section + fixed stack + TODO(fable-review) escape valve + per-task commits (drift becomes visible in git log) |
| Honest self-assessment | Reports "done ✅" for partial work | Fresh-context verifier re-runs every gate; orchestrator checks git log against the task list |
| Recovery from interruption | Loses the thread when cut off | Status-in-file + commit-per-task; resume brief = "here's HEAD, here's what remains" |
| Knowing when to stop | Grinds on a broken approach | Explicit stop conditions + gate structure (a failed gate halts the phase) |
| Skepticism about docs | Believes the README | Bake audit findings into the plan ("trust this over the README") so workers inherit verified reality, not folklore |
| Environment intuition | Wastes calls rediscovering quirks | Quirks list in every brief (see 3a.4) |

**The single most important line to give any executor:**
> "This document is your ONLY source of truth. If reality disagrees with this document, STOP and report — do not improvise."

---

## 5. The reasoning protocol (how to "think like Fable")

Give this verbatim to an orchestrator model as its operating instructions:

1. Before any plan: verify the current state yourself (read, run, boot). Write down exact errors, versions, line numbers.
2. Ask the owner forced-choice questions for every genuinely open decision. Everything else: decide, and record the decision in the plan.
3. Decompose into phases where each phase is independently shippable and independently verifiable. Order by (risk removed) × (value unlocked): security first, then the single highest-value structural gap, then features, then polish.
4. Write the plan into the repo. Include: binding rules, verified state, numbered tasks with exact paths, appended-scope section for late-arriving owner directives, verification gates.
5. Brief workers per the briefing contract (3a). Parallelize only non-overlapping scopes.
6. When a worker reports: verify independently before believing. git log, run gates, spot-check diffs.
7. After each wave: update EXECUTION STATUS in the plan (commits, gate numbers, next phase), commit it.
8. When new owner requirements arrive mid-execution: edit the PLAN (not just the chat), mark the directives as binding, and re-brief.
9. Never let a worker handle secrets, payments, or irreversible actions. Never mark anything complete that has a failing gate.

---

## 6. Practical setup in Claude Code (agents in tandem)

- **Terminal-per-repo:** run one Claude Code session per project — they're already partitioned, zero collision risk. This is the simplest "tandem" and what I recommend for these two repos.
- **Within a session:** Claude Code's Task/subagent tool can spawn parallel workers. Ask for it explicitly: *"Spawn parallel subagents for P2-2 and P2-3 — they touch disjoint files — then verify both."*
- **Model mixing:** run the session on Opus when writing/revising plans; switch to Sonnet for grinding through phases (`/model`). Sonnet + a Fable-grade plan ≈ Fable-grade output at a fraction of the cost — consistent with your cheap-first policy.
- **Session hygiene:** start each session with the resume prompt (§7), end each session by having the model update EXECUTION STATUS + commit. Never rely on conversation memory between sessions.
- **CLAUDE.md:** both repos have governance docs (AGENTS.md in TradingAgents). Add a one-line CLAUDE.md pointing at SONNET_EXECUTION_PLAN.md so every future session auto-discovers the contract.

---

## 7. The two resume prompts for Claude Code

### TradingAgents — paste this:

```
Read SONNET_EXECUTION_PLAN.md in the repo root, in full, before doing anything else.
It is your ONLY source of truth and overrides IMPLEMENTATION_ROADMAP.md and README.md.
Check the EXECUTION STATUS section at the top, confirm it against `git log --oneline -10`,
then continue from the next incomplete phase (as of 2026-07-06 that is Phase P1: the
automation scheduler executor, plus appended tasks P1-7 nightly DB backup and P1-8
NVIDIA NIM provider docs).

Operating rules (binding):
- Execute tasks in order, one git commit per task, message format "P<phase>-<task>: <summary>".
- Run every Verification Gate for real before advancing a phase. If a gate fails and you
  cannot fix it, STOP and report exactly where.
- Never echo or commit .env (it contains live keys). Never make live LLM or market-data
  API calls; all tests mock providers using the existing patterns in tests/.
- If anything is ambiguous, implement the literal instruction and tag it
  "TODO(fable-review):" — do not design an alternative.
- When you finish a phase (or must stop), update the EXECUTION STATUS section of
  SONNET_EXECUTION_PLAN.md with commit hashes and gate results, and commit it.
```

### brandname-growth-agents — paste this:

```
Read SONNET_EXECUTION_PLAN.md in the repo root, in full, before doing anything else.
It is your ONLY source of truth. Pay special attention to the "Owner directives
(2026-07-06, binding)" block: brand = "BRAND NAME", Shopify https://www.brandnamedesign.co/,
cheap-first two-tier model policy (local/NIM default, premium optional), muapi.ai for
video prompt packs, Higgsfield excluded.
Check the EXECUTION STATUS section, confirm it against `git log --oneline -10`, then
continue from the next incomplete phase (as of 2026-07-06 that is Phase P2: the React
studio frontend — P0 and P1 are complete and gate-verified; the new backend lives in app/).

Operating rules (binding):
- Execute tasks in order, one git commit per task, message format "P<phase>-<task>: <summary>".
- Run every Verification Gate for real before advancing. Backend must stay green:
  `pytest -q` (47 tests as of P1) before and after your changes.
- Never echo or commit .env, oauth_client.json, or token.json (live credentials).
  Never make live OpenAI/Shopify/Google calls; all tests mock external clients.
  LOCAL_ONLY_AGENT_RUNS=true is the default for all manual testing.
- If anything is ambiguous, implement the literal instruction and tag it
  "TODO(fable-review):" — do not design an alternative.
- When you finish a phase (or must stop), update the EXECUTION STATUS section of
  SONNET_EXECUTION_PLAN.md with commit hashes and gate results, and commit it.
```

---

## 8. Current state ledger (as of this handoff)

| | TradingAgents | brandname-growth-agents |
|---|---|---|
| Branch | codex/platform-foundation | feat/openai-growth-agents |
| HEAD | a923aae | a72bea9 |
| Done | P0 complete (hygiene, live-test gating, clutter removal) | P0 + P1 complete: full new `app/` backend, 47/47 tests, GATE P1 verified (boot + idempotent migration 17/43/271/271) |
| Next | P1 scheduler executor (+P1-7 backup, +P1-8 NIM docs) | P2 React studio frontend |
| Unpushed | 5 commits ahead of origin | 7 commits ahead of origin |
| Owner TODO | Rotate OpenAI/Anthropic/Alpha Vantage keys; `git push` | Rotate OpenAI key + Google OAuth; `git push`; get NVIDIA NIM key (free) |
