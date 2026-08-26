#!/usr/bin/env python3
"""gate-coverage.py — coverage on CHANGED LINES only. Stage 2.2.

Whole-repo coverage is nearly useless as a gate: a 5-line change to a 95%-covered
repo passes an 80% floor while being entirely untested. What we care about is
whether the lines this card ADDED are exercised.

Reads `coverage.json` and the diff against BASE. Exits 0 if changed-line coverage
>= --min, else 1 with a terse reason listing the uncovered lines — the implementer
needs to know WHICH lines, not just a number.

Coverage is the floor, not the signal. A line can be executed by a test that
asserts nothing. The mutation gate (nightly) is what checks whether the tests
actually bite.

TWO coverage.json SHAPES, because COVERAGE_CMD varies per repo family
-----------------------------------------------------------------------
1. Python `coverage json` (coverage.py): {"files": {"<repo-relative path>":
   {"executed_lines": [...], "missing_lines": [...], ...}}}. Paths are already
   repo-relative.
2. JS/TS Istanbul / c8 (`vitest --coverage`, `c8`, etc): {"files": {"<ABSOLUTE
   path>": {"path": "<same abs path>", "statementMap": {"<id>": {"start":
   {"line": N, ...}, "end": {"line": M, ...}}, ...}, "s": {"<id>": <hit count>,
   ...}, ...}}}. Paths are ABSOLUTE and there is no executed_lines/missing_lines
   — coverage is statement hit-counts keyed by statementMap.

Found live 2026-08-01 in mission-control: this script silently matched neither
shape correctly for Istanbul output — `cov.get(path)` against a repo-relative
diff path never hits an absolute-path key, every changed file's `entry` comes
back None, and the loop falls through to "no measurable changed lines" — a PASS
that checked nothing. COVERAGE_MIN=80 enforced nothing on any JS/TS repo using
this template, possibly since inception.

The fix: detect BOTH shapes, normalize absolute Istanbul paths to repo-relative
so they line up with `git diff` paths, and — this is the part that actually
closes the hole — FAIL LOUDLY when coverage.json exists, is non-empty, and
matches NEITHER shape. "No measurable changed lines" must only ever mean what
it says (the diff has no coverable lines), never "I couldn't read the file."

stdlib only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def changed_lines(base: str) -> dict[str, set[int]]:
    """{path: {line numbers ADDED or MODIFIED}} from `git diff -U0`."""
    try:
        merge_base = subprocess.run(["git", "merge-base", "HEAD", base],
                                    capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        merge_base = ""
    ref = merge_base or base
    out = subprocess.run(["git", "diff", "-U0", f"{ref}...HEAD"],
                         capture_output=True, text=True, timeout=60).stdout
    result: dict[str, set[int]] = {}
    path = None
    for line in out.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("@@") and path:
            # @@ -old,+new @@   -> we want the NEW side
            try:
                new = line.split("+", 1)[1].split(" ", 1)[0]
                start, _, count = new.partition(",")
                start_i, count_i = int(start), int(count or 1)
            except Exception:
                continue
            if count_i:
                result.setdefault(path, set()).update(range(start_i, start_i + count_i))
    return result


def _is_coveragepy_entry(entry: dict) -> bool:
    return isinstance(entry, dict) and (
        "executed_lines" in entry or "missing_lines" in entry
    )


def _is_istanbul_entry(entry: dict) -> bool:
    return isinstance(entry, dict) and "statementMap" in entry and "s" in entry


def _coveragepy_line_sets(entry: dict) -> tuple[set[int], set[int]]:
    executed = set(entry.get("executed_lines") or [])
    missing = set(entry.get("missing_lines") or [])
    return executed, missing


def _istanbul_line_sets(entry: dict) -> tuple[set[int], set[int]]:
    """Statement hit counts -> (executed lines, missing lines).

    Istanbul/c8 track coverage per STATEMENT, not per line, and a statement's
    start/end can span multiple lines. A line is "executed" if ANY statement
    covering it has a hit count > 0; "missing" only if every statement
    covering it has a hit count of 0 (executed wins on overlap — a line
    that's part of both a hit and a not-hit statement was, in fact, reached).
    """
    stmt_map = entry.get("statementMap") or {}
    hits = entry.get("s") or {}
    executed: set[int] = set()
    missing: set[int] = set()
    for stmt_id, loc in stmt_map.items():
        if not isinstance(loc, dict):
            continue
        start = (loc.get("start") or {}).get("line")
        end = (loc.get("end") or {}).get("line") or start
        if start is None:
            continue
        count = hits.get(stmt_id, 0) or 0
        lines = range(int(start), int(end) + 1)
        (executed if count > 0 else missing).update(lines)
    missing -= executed
    return executed, missing


def _abs_to_repo_relative(path: str, repo_root: Path) -> str:
    """Best-effort: an absolute path under repo_root becomes repo-relative.

    Anything else (already relative, or absolute but outside repo_root — e.g.
    a monorepo tool that ran from a different cwd) is returned unchanged; the
    caller simply won't find a matching diff entry for it, same as today.
    """
    p = Path(path)
    if not p.is_absolute():
        return path
    try:
        return str(p.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return path


def extract_files_map(data) -> dict:
    """Return the {path: entry} map regardless of the top-level wrapper.

    coverage.py and the mission-control `npm run coverage` wrapper both nest
    it under "files". Raw Istanbul `coverage-final.json` (no wrapper — some
    COVERAGE_CMDs move it straight to coverage.json) has the path->entry map
    AT THE TOP LEVEL. Try the wrapper first; fall back to treating the whole
    document as the map so that case still normalizes correctly instead of
    tripping the unknown-shape failure.
    """
    if isinstance(data, dict) and isinstance(data.get("files"), dict):
        return data["files"]
    if isinstance(data, dict):
        return data
    return {}


def normalize_coverage(
    data, repo_root: Path,
) -> tuple[dict[str, tuple[set[int], set[int]]], int, int]:
    """-> ({repo-relative path: (executed, missing)}, n_recognized, n_unrecognized).

    n_recognized / n_unrecognized count FILE ENTRIES, not lines — that's what
    the caller uses to decide "unknown shape" vs "legitimately no files".
    """
    files = extract_files_map(data)
    normalized: dict[str, tuple[set[int], set[int]]] = {}
    n_ok = n_bad = 0
    for raw_path, entry in files.items():
        if _is_coveragepy_entry(entry):
            rel = _abs_to_repo_relative(raw_path, repo_root)
            normalized[rel] = _coveragepy_line_sets(entry)
            n_ok += 1
        elif _is_istanbul_entry(entry):
            src_path = entry.get("path") or raw_path
            rel = _abs_to_repo_relative(src_path, repo_root)
            normalized[rel] = _istanbul_line_sets(entry)
            n_ok += 1
        else:
            n_bad += 1
    return normalized, n_ok, n_bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="main")
    ap.add_argument("--min", type=float, default=80.0)
    ap.add_argument("--coverage-json", default="coverage.json")
    ap.add_argument("--repo-root", default=".",
                     help="Base for normalizing absolute (Istanbul/c8) paths "
                          "to repo-relative. Defaults to cwd, which is where "
                          "gate.sh invokes this script from.")
    a = ap.parse_args()

    cov_path = Path(a.coverage_json)
    if not cov_path.exists():
        print(f"{cov_path} not found — COVERAGE_CMD must produce it "
              f"(e.g. `coverage json -o {cov_path}`)")
        return 1

    try:
        raw = json.loads(cov_path.read_text())
    except Exception as e:
        print(f"unreadable {cov_path}: {e}")
        return 1

    repo_root = Path(a.repo_root)
    cov, n_ok, n_bad = normalize_coverage(raw, repo_root)

    # The bug this fix closes: coverage.json existed, had real per-file data,
    # but NONE of it matched a shape we understand (e.g. a future coverage
    # tool with a third JSON shape, or a COVERAGE_CMD that wrote something
    # else entirely to that path). That must be a loud, non-zero failure —
    # never a silent "no measurable changed lines", which is what made this
    # bug invisible on every JS/TS repo for as long as it existed.
    if n_ok == 0 and n_bad > 0:
        sample_keys = list(extract_files_map(raw).keys())[:3]
        print(f"unrecognized coverage.json shape: {n_bad} file entr"
              f"{'y' if n_bad == 1 else 'ies'} in {cov_path} matched neither "
              "the coverage.py shape (executed_lines/missing_lines) nor the "
              "Istanbul/c8 shape (statementMap + s). Refusing to report a "
              "coverage number computed from data we can't read.\n"
              f"  sample keys: {sample_keys}\n"
              "  Fix COVERAGE_CMD, or extend gate-coverage.py's shape "
              "detection if this is a legitimate new coverage format.")
        return 3

    changed = changed_lines(a.base)
    if not changed:
        print("no changed lines vs base — nothing to cover")
        return 0

    total = covered = 0
    misses: list[str] = []
    for path, lines in sorted(changed.items()):
        # Only source we actually measure. Test files and untracked-by-coverage
        # files are not the subject of a coverage floor.
        entry = cov.get(path)
        if not entry:
            continue
        executed, missing = entry
        relevant = lines & (executed | missing)
        if not relevant:
            continue
        total += len(relevant)
        hit = relevant & executed
        covered += len(hit)
        gap = sorted(relevant - executed)
        if gap:
            misses.append(f"{path}: uncovered changed lines {gap[:15]}"
                          + (" …" if len(gap) > 15 else ""))

    if total == 0:
        print("no measurable changed lines (only tests/config changed?)")
        return 0

    pct = 100.0 * covered / total
    if pct + 1e-9 >= a.min:
        print(f"{pct:.1f}% of {total} changed lines (min {a.min:.0f}%)")
        return 0

    print(f"{pct:.1f}% of {total} changed lines covered — below {a.min:.0f}%")
    for m in misses[:8]:
        print(f"  {m}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
