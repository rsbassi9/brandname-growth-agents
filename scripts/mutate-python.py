#!/usr/bin/env python3
"""mutate-python.py — diff-scoped mutation testing, stdlib only. Stage 2.2.

Coverage is the floor; mutation score is the signal. LLM-written tests average
~53% mutation score while passing coverage: they execute the line and assert
nothing about it. This finds those.

Diff-scoped on purpose. Mutating the whole repo takes hours and indicts code this
card never touched. We mutate only the lines the branch ADDED, and only in source
(never tests). If those mutants survive, the new tests do not bite.

Each mutant: rewrite one changed line, confirm the file still parses (a mutant
that cannot compile teaches nothing), run TEST_CMD, and see whether the suite
notices. A mutant the suite fails to kill is printed with its line and its
mutation, because "score: 41%" is not actionable and "line 22: `>` -> `>=`
survived" is.

    mutate-python.py --base main --test-cmd "python3 -m unittest discover" [--min 60]

Exit 0 if score >= --min (or nothing mutable). Exit 1 otherwise.
"""
from __future__ import annotations

import argparse
import ast
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# (pattern, replacement, label). Applied to one changed line at a time.
MUTATIONS = [
    (r"(?<![<>!=])==(?!=)", "!=", "== -> !="),
    (r"!=", "==", "!= -> =="),
    (r"(?<![<>=!])>=", "<", ">= -> <"),
    (r"(?<![<>=!])<=", ">", "<= -> >"),
    (r"(?<![<>=!-])>(?![=>])", "<", "> -> <"),
    (r"(?<![<>=!-])<(?![=<])", ">", "< -> >"),
    (r"\bTrue\b", "False", "True -> False"),
    (r"\bFalse\b", "True", "False -> True"),
    (r"\band\b", "or", "and -> or"),
    (r"\bor\b", "and", "or -> and"),
    (r"(?<![+\-*/=])\+(?![+=])", "-", "+ -> -"),
    (r"(?<![+\-*/=])-(?![-=>])", "+", "- -> +"),
    (r"\bnot\s+", "", "drop `not`"),
    (r"\breturn\s+True\b", "return False", "return True -> False"),
]

SKIP_LINE = re.compile(r"^\s*(#|import |from |@)|^\s*$")


def is_gate_machinery(path: str) -> bool:
    """Never mutate the scorer. Mutating gate-tripwires.py tells us nothing about
    the card's tests and drags the score to the floor — observed on the first run."""
    return (path.startswith(".claude/") or path.startswith("scripts/gate")
            or path.startswith("scripts/mutate"))


def docstring_lines(tree) -> set:
    """Lines occupied by docstrings and bare string expressions.

    Without this, `and`/`-`/`or` inside a module docstring get "mutated", every
    mutant survives (prose does not break tests) and the score is nonsense.
    Observed: gate-tripwires.py's own docstring produced four phantom survivors.
    """
    out = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            lo = node.lineno
            hi = getattr(node, "end_lineno", lo) or lo
            out.update(range(lo, hi + 1))
    return out


def git(*a, timeout=60) -> str:
    r = subprocess.run(["git", *a], capture_output=True, timeout=timeout)
    return r.stdout.decode("utf-8", errors="replace")


def is_test(p: str) -> bool:
    n = Path(p).name.lower()
    return (n.startswith("test_") or n.endswith("_test.py") or "/tests/" in p
            or p.startswith("tests/"))


def changed_python_lines(base: str) -> dict[str, set[int]]:
    mb = git("merge-base", "HEAD", base).strip() or base
    out = git("diff", "-U0", f"{mb}...HEAD")
    res: dict[str, set[int]] = {}
    path = None
    for line in out.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif (line.startswith("@@") and path and path.endswith(".py")
              and not is_test(path) and not is_gate_machinery(path)):
            try:
                new = line.split("+", 1)[1].split(" ", 1)[0]
                start, _, cnt = new.partition(",")
                s, c = int(start), int(cnt or 1)
            except Exception:
                continue
            if c:
                res.setdefault(path, set()).update(range(s, s + c))
    return res


def run_tests(cmd: str, cwd: Path, timeout: int) -> bool:
    """True if the suite PASSES (i.e. the mutant survived)."""
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, timeout=timeout)
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False   # a mutant that hangs the suite counts as killed
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="main")
    ap.add_argument("--test-cmd", required=True)
    ap.add_argument("--min", type=float, default=60.0)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--max-mutants", type=int, default=60)
    a = ap.parse_args()

    repo = Path(git("rev-parse", "--show-toplevel").strip() or ".")
    targets = changed_python_lines(a.base)
    if not targets:
        print("no changed Python source lines — nothing to mutate")
        return 0

    # Sanity: the suite must pass BEFORE we mutate, or every mutant looks killed
    # and the score is a meaningless 100%.
    if not run_tests(a.test_cmd, repo, a.timeout):
        print("baseline test suite FAILS — mutation score is meaningless until it is green")
        return 1

    killed = survived = invalid = 0
    survivors: list[str] = []

    for path, lines in sorted(targets.items()):
        f = repo / path
        if not f.exists():
            continue
        original = f.read_text()
        src_lines = original.splitlines(keepends=True)
        try:
            skip = docstring_lines(ast.parse(original))
        except SyntaxError:
            continue
        for lineno in sorted(lines):
            if lineno > len(src_lines) or lineno in skip:
                continue
            line = src_lines[lineno - 1]
            if SKIP_LINE.match(line):
                continue
            for rx, repl, label in MUTATIONS:
                if killed + survived >= a.max_mutants:
                    break
                if not re.search(rx, line):
                    continue
                mutated = re.sub(rx, repl, line, count=1)
                if mutated == line:
                    continue
                candidate = list(src_lines)
                candidate[lineno - 1] = mutated
                text = "".join(candidate)
                try:
                    ast.parse(text)
                except SyntaxError:
                    invalid += 1
                    continue
                backup = tempfile.NamedTemporaryFile(delete=False).name
                shutil.copyfile(f, backup)
                try:
                    f.write_text(text)
                    if run_tests(a.test_cmd, repo, a.timeout):
                        survived += 1
                        survivors.append(f"{path}:{lineno}: {label}  ({line.strip()[:60]})")
                    else:
                        killed += 1
                finally:
                    shutil.copyfile(backup, f)
                    Path(backup).unlink(missing_ok=True)

    total = killed + survived
    if total == 0:
        print(f"no viable mutants on the changed lines ({invalid} did not compile)")
        return 0

    score = 100.0 * killed / total
    print(f"mutation score {score:.0f}% "
          f"({killed} killed / {total} mutants; {invalid} uncompilable)")
    if survivors:
        print("surviving mutants — tests pass but do not bite:")
        for s in survivors[:12]:
            print(f"  {s}")
    return 0 if score + 1e-9 >= a.min else 1


if __name__ == "__main__":
    sys.exit(main())
