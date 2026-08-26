#!/usr/bin/env python3
"""gate-tripwires.py — the three cheap checks that catch AI-code rot. Stage 2.2.

Measured on real AI-authored code (GitClear): duplication +81%, error-masking
+47%. Neither shows up in tests, lint, or coverage. Both show up here.

  (a) bare except / swallowed error   — NEW ones only, in the diff
  (b) copy-paste duplication delta    — NEW duplicated blocks, in the diff
  (c) diff size ceiling               — >600 changed lines means "decompose it"

All three judge the DIFF, never the repo. Pre-existing sins are not this card's
problem, and failing a card for them teaches the worker to fear unrelated files.

stdlib only, so it runs anywhere without provisioning a toolchain.

KNOWN BLIND SPOT, stated rather than hidden: the duplication check matches exact
normalized lines. It catches literal copy-paste (Type-1 clones) — verified — and
it MISSES a block whose identifiers were renamed (Type-2). Detecting those needs
jscpd or PMD-CPD, neither of which is installed. A crude check that runs beats a
good one that isn't, but do not read a clean duplication result as "no clones".

Exit 0 = clean. Exit 1 = tripwire hit, with reasons on stdout.
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

METRIC = Path.home() / "bin" / "metric.sh"

# Swallowed-error constructs, per language. Each must match an ADDED line.
SWALLOW = [
    (re.compile(r"^\s*except\s*:"), "bare `except:`"),
    (re.compile(r"^\s*except\s+.*:\s*pass\s*$"), "`except ...: pass`"),
    (re.compile(r"^\s*except\s+.*:\s*(?:#.*)?$"), None),   # needs next-line check
    (re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}"), "empty `catch {}`"),
    (re.compile(r"^\s*}\s*catch\s*\([^)]*\)\s*\{\s*\}"), "empty `catch {}`"),
    (re.compile(r"\.catch\(\s*\(\s*\)\s*=>\s*\{\s*\}\s*\)"), "empty `.catch(() => {})`"),
    (re.compile(r"^\s*_\s*=\s*(?:err|error)\s*$"), "discarded error (`_ = err`)"),
    (re.compile(r"if\s+err\s*!=\s*nil\s*\{\s*\}"), "empty Go error branch"),
]

SHINGLE = 6      # consecutive normalized lines that constitute a "block"
MIN_BLOCK_CHARS = 80


def metric(*args) -> None:
    if METRIC.exists():
        try:
            subprocess.run([str(METRIC), *[str(a) for a in args]], timeout=15,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass


def git(*args, timeout=60) -> str:
    """Never let a binary blob crash the gate. A repo has images and .pyc files;
    `git show` on one raises UnicodeDecodeError with text=True."""
    try:
        r = subprocess.run(["git", *args], capture_output=True, timeout=timeout)
    except Exception:
        return ""
    return r.stdout.decode("utf-8", errors="replace")


def looks_binary(text: str) -> bool:
    return "\x00" in text[:2000] or text.count("�") > 20


def base_ref(base: str) -> str:
    mb = git("merge-base", "HEAD", base).strip()
    return mb or base


def removed_lines(ref: str) -> dict[str, set[int]]:
    """{path: {base_lineno, ...}} for lines the diff REMOVES (base-side numbering).

    Feeds the moved-code exemption in check_duplication: an added block that
    matches a base-corpus block whose source lines are REMOVED by this same
    diff is a MOVE (extract-to-shared-module), not a clone. Without this,
    every legitimate dedup extraction self-flags against the copies it
    deletes (observed on use-load-in.js, 2026-07-12)."""
    out = git("diff", "-U0", f"{ref}...HEAD")
    files: dict[str, set[int]] = defaultdict(set)
    path, lineno = None, 0
    for line in out.splitlines():
        if line.startswith("--- a/"):
            path = line[6:]
        elif line.startswith("@@"):
            try:
                old = line.split("-", 1)[1].split(" ", 1)[0]
                start, _, _c = old.partition(",")
                lineno = int(start)
            except Exception:
                lineno = 0
        elif line.startswith("-") and not line.startswith("---") and path:
            files[path].add(lineno)
            lineno += 1
    return files


def added_lines(ref: str) -> dict[str, list[tuple[int, str]]]:
    """{path: [(lineno, text), ...]} for lines the diff ADDS."""
    out = git("diff", "-U0", f"{ref}...HEAD")
    files: dict[str, list[tuple[int, str]]] = defaultdict(list)
    path, lineno = None, 0
    for line in out.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("@@"):
            try:
                new = line.split("+", 1)[1].split(" ", 1)[0]
                start, _, _c = new.partition(",")
                lineno = int(start)
            except Exception:
                lineno = 0
        elif line.startswith("+") and not line.startswith("+++") and path:
            files[path].append((lineno, line[1:]))
            lineno += 1
    return files


def is_test(path: str) -> bool:
    p = path.lower()
    return (("test" in Path(p).name) or p.startswith("tests/") or "/tests/" in p
            or p.startswith("spec/"))


def check_swallowed(files) -> list[str]:
    hits = []
    for path, lines in files.items():
        if is_test(path) or is_gate_machinery(path) or is_generated(path):
            continue
        by_no = dict(lines)
        for no, text in lines:
            for rx, label in SWALLOW:
                if not rx.search(text):
                    continue
                if label is None:
                    # `except X:` whose next ADDED line is bare `pass`
                    nxt = by_no.get(no + 1, "")
                    if re.match(r"^\s*pass\s*$", nxt):
                        hits.append(f"{path}:{no}: `except ...:` followed by bare `pass`")
                    break
                hits.append(f"{path}:{no}: {label}")
                break
    return hits


def normalize(line: str) -> str:
    """Strip trailing comments — carefully.

    Naively removing `//...` collapses every URL to the same token, so
    "https://example.com/a" and ".../b" register as a clone. Caught by Claude Code
    reading this file during the Stage 2.2 temptation test. Only treat `//` as a
    comment when it is NOT preceded by a colon.
    """
    s = line.strip()
    s = re.sub(r"(?<!:)//.*$", "", s)
    s = re.sub(r"(?<!['\"])#(?!['\"]).*$", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def doc_line_numbers(text: str) -> set[int]:
    """Line numbers inside doc blocks: Python triple-quoted strings that OPEN at a
    line start (module/def docstrings) and /* ... */ comment blocks.

    Why (2026-07-11): two sibling query functions had legitimately similar
    docstrings and the shingle detector flagged the PROSE as a clone (Fix-T4a
    wedged a full stuck-block cycle on it). Documentation similarity is not code
    duplication. Mid-line/inline triple quotes are deliberately not chased — the
    delimiter-at-line-start case is the false-positive class we actually hit,
    and over-stripping would blind the detector to real string-heavy clones.
    """
    doc: set[int] = set()
    state: str | None = None
    for no, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if state is None:
            if s.startswith('"""') or s.startswith("'''"):
                q = s[:3]
                doc.add(no)
                if q not in s[3:]:          # doesn't close on the same line
                    state = q
            elif s.startswith("/*"):
                doc.add(no)
                if "*/" not in s:
                    state = "*/"
        else:
            doc.add(no)
            if state in s:
                state = None
    return doc


# The gate must not grade its own machinery, nor the config it reads.
def is_gate_machinery(path: str) -> bool:
    return path.startswith(".claude/") or path.startswith("scripts/gate")


def is_generated(path: str) -> bool:
    """Build artifacts are outputs, not authored code — grading them punishes
    every rebuild (2026-07-12: relocating dist/ read as a 16k-line diff and
    meta.json 'duplication'). Source stays fully gated."""
    p = path.lower()
    return (p.startswith("dist/") or "/dist/" in p
            or p.endswith(".map") or p == "coverage.json" or p.startswith("coverage/")
            or p.endswith("package-lock.json")
            or p.endswith("pubspec.lock")
            or p.endswith("firestore.indexes.json")
            or p.endswith(".rules")) 

def is_doc(path: str) -> bool:
    """Markdown is prose — including the code it quotes normatively."""
    return path.lower().endswith((".md", ".markdown"))


def check_duplication(files, ref: str) -> list[str]:
    """New blocks that duplicate code ALREADY PRESENT AT `ref`, or each other.

    The corpus is the BASE revision, never the working tree. Building it from the
    working tree means every added block matches itself and the gate fires on
    every card — observed on the first run, and a gate that always fires is a
    gate everyone learns to bypass.
    """
    corpus: dict[tuple[str, ...], str] = {}
    for f in git("ls-tree", "-r", "--name-only", ref).splitlines():
        if not f or is_test(f) or is_gate_machinery(f) or is_generated(f):
            continue
        blob = git("show", f"{ref}:{f}")
        if not blob or len(blob) > 400_000 or looks_binary(blob):
            continue
        doc = doc_line_numbers(blob)
        numbered = [(i, normalize(x)) for i, x in enumerate(blob.splitlines(), 1)]
        numbered = [(i, t) for i, t in numbered if t and i not in doc]
        for i in range(len(numbered) - SHINGLE + 1):
            window = numbered[i:i + SHINGLE]
            key = tuple(t for _, t in window)
            if sum(len(x) for x in key) >= MIN_BLOCK_CHARS:
                corpus.setdefault(key, f"{f}:{window[0][0]}")

    hits, seen = [], set()
    removed = removed_lines(ref)
    added_blocks: dict[tuple[str, ...], str] = {}
    for path, lines in sorted(files.items()):
        if is_test(path) or is_gate_machinery(path) or is_generated(path):
            continue
        # Exact doc-line filtering needs full-file context (a docstring can open
        # above the diff hunk) — read the working tree; on any failure, filter nothing.
        try:
            doc = doc_line_numbers(Path(path).read_text(encoding="utf-8", errors="replace"))
        except Exception:
            doc = set()
        norm = [(no, normalize(t)) for no, t in lines if no not in doc]
        norm = [(no, t) for no, t in norm if t]
        for i in range(len(norm) - SHINGLE + 1):
            window = norm[i:i + SHINGLE]
            key = tuple(t for _, t in window)
            if sum(len(x) for x in key) < MIN_BLOCK_CHARS or key in seen:
                continue
            here = f"{path}:{window[0][0]}"
            src = corpus.get(key) or added_blocks.get(key)
            if src and src in corpus.values() and key in corpus:
                # moved-code exemption: if the base block this matches is being
                # REMOVED by the same diff, it is a move, not a clone.
                sf, _, sl = corpus[key].rpartition(":")
                try:
                    span = set(range(int(sl), int(sl) + SHINGLE))
                except ValueError:
                    span = set()
                if span and span & removed.get(sf, set()):
                    continue
            if src:
                # Cross-type match: prose against code. A spec that states
                # normative SQL/config and the artifact implementing it
                # verbatim are one fact in two required forms, not a clone —
                # the same principle doc_line_numbers() applies within a
                # file. 2026-08-04: P4-1a (brain schema migration) was
                # unpassable by construction; all 120 hits were
                # migrations/0001_init.sql against docs/brain-ddl.md, and the
                # card required that DDL verbatim. code-vs-code and
                # doc-vs-doc detection are untouched.
                if is_doc(src.rpartition(":")[0]) != is_doc(path):
                    continue
                seen.add(key)
                hits.append(f"{here}: {SHINGLE} lines duplicate {src}")
            else:
                added_blocks[key] = here
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="main")
    ap.add_argument("--diff-max", type=int, default=600)
    # Optional: a repo can exclude doc-heavy paths from the diff-size ceiling --
    # cards legitimately land 1000+ lines of markdown; the 600-line ceiling is
    # about AUTHORED CODE scope. Globs listed here are excluded from the
    # --diff-max count ONLY — swallowed-error and duplication checks are
    # untouched, and --diff-total-max is an absolute backstop over everything
    # (docs included) so "it's only docs" can never smuggle an unbounded diff.
    ap.add_argument("--diff-exclude", default="",
                    help="space/comma-separated globs excluded from the --diff-max count")
    ap.add_argument("--diff-total-max", type=int, default=0,
                    help="absolute ceiling on ALL changed lines incl. excluded globs (0 = off)")
    a = ap.parse_args()

    exclude_globs = [g for g in re.split(r"[,\s]+", a.diff_exclude) if g]

    def is_size_excluded(path: str) -> bool:
        return any(fnmatch.fnmatch(path, g) for g in exclude_globs)

    ref = base_ref(a.base)
    files = added_lines(ref)

    problems: list[str] = []

    # (c) diff size — checked first: an oversized diff makes the others noisy.
    # numstat per file so generated artifacts (dist/, coverage) don't count:
    # the ceiling is about AUTHORED scope, and artifacts rebuild wholesale.
    # Tests are counted but NOT gated against diff_max (2026-08-03). The
    # ceiling's message is "decompose this card", which is about PRODUCT scope,
    # and the other two tripwires already exempt tests via is_test(). Counting
    # them here made the gate unreachable by construction on a tests-first card:
    # P3-3 wrote a 346-line matcher plus a 500-line frozen test file, so 846 >
    # 600 left ~100 lines for the matcher, and no decomposition could help
    # because every split still diffs against the base and re-counts the same
    # frozen tests. They remain in `total`, because DIFF_TOTAL_MAX is a
    # deliberate backstop over everything, and they are REPORTED below - a
    # silent exemption is how a ceiling quietly becomes a lie.
    changed = 0
    total = 0
    test_changed = 0
    for line in git("diff", "--numstat", f"{ref}...HEAD").splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or is_generated(parts[2]):
            continue
        n_lines = sum(int(n) for n in parts[:2] if n.isdigit())
        total += n_lines
        if is_test(parts[2]):
            test_changed += n_lines
            continue
        if not is_size_excluded(parts[2]):
            changed += n_lines
    if test_changed:
        print(f"  diff: {changed} product lines (+{test_changed} test lines, not gated)")
    if changed > a.diff_max:
        problems.append(f"diff is {changed} changed lines (> {a.diff_max}) — decompose this card")
        metric("loop", "gate_failure", 1, "diff_size")
    if a.diff_total_max and total > a.diff_total_max:
        problems.append(
            f"TOTAL diff incl. docs/excluded globs is {total} changed lines "
            f"(> {a.diff_total_max} backstop) — decompose this card"
        )
        metric("loop", "gate_failure", 1, "diff_size")

    swallowed = check_swallowed(files)
    if swallowed:
        problems.append("new swallowed-error constructs:")
        problems += [f"    {h}" for h in swallowed[:10]]
        metric("loop", "gate_failure", len(swallowed), "bare_except")

    dups = check_duplication(files, ref)
    if dups:
        problems.append("new duplicated blocks (token-shingle detector; crude but running):")
        problems += [f"    {h}" for h in dups[:8]]
        metric("loop", "gate_failure", len(dups), "duplication")

    if not problems:
        return 0
    print("\n".join(problems))
    return 1


if __name__ == "__main__":
    sys.exit(main())
