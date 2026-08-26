#!/usr/bin/env python3
"""gate-newdeps.py — new-dependency tripwire. Stage 2.4, written natively.

Runs ONLY when the diff touches a dependency manifest. A card that adds a
dependency is the card that should answer for it; a card touching one Python file
should not wait on an npm audit.

WHY THIS IS NOT `supply-chain-guard`
A prior skill in this space was authorized "pinned ONLY if the read is clean". The code contained
no malice — but reading it (2026-07-09) found a defect worse than malice would have
been. Against its own `compromised-package-lock.json` fixture it printed:

    !!CRITICAL: axios — ['Malware in axios', ...]
    !!plain-crypto-js@4.2.1: ['MAL-2026-2306']
    [VERDICT] CLEAR            <- exit 0

Its `!!CRITICAL` lines are emitted from subshells (`npm audit | python3 -c ...`,
and a python heredoc for the OSV fallback), so they can never set the parent's
`_EXIT_CODE`. Only the `osv-scanner` branch sets it, and `osv-scanner` is not
installed here. Detection was display-only. A gate wired to that exit code would
have waved a lockfile pinning the 2026 axios RAT straight through.

So we implement the three things it wraps — `npm audit`, an OSV lookup, and the
Python equivalent — and we obey the rule the whole gate system is built on:

    A CHECK THAT CANNOT RUN MUST FAIL, NEVER PASS.

Exit 0 = clean. Exit 1 = findings, or the scan could not be performed.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

OSV = "https://api.osv.dev/v1/querybatch"
METRIC = Path.home() / "bin" / "metric.sh"

NPM_MANIFESTS = {"package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
PY_MANIFESTS = {"pyproject.toml", "uv.lock", "Pipfile", "Pipfile.lock"}


def metric(*a):
    if METRIC.exists():
        try:
            subprocess.run([str(METRIC), *[str(x) for x in a]], timeout=15,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass


def git(*a, cwd=None) -> str:
    try:
        r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, timeout=60)
        return r.stdout.decode("utf-8", errors="replace")
    except Exception:
        return ""


def changed_manifests(base: str, repo: Path) -> tuple[bool, bool]:
    mb = git("merge-base", "HEAD", base, cwd=repo).strip() or base
    files = [f for f in git("diff", "--name-only", f"{mb}...HEAD", cwd=repo).splitlines() if f]
    npm = any(Path(f).name in NPM_MANIFESTS for f in files)
    py = any(Path(f).name in PY_MANIFESTS or re.match(r"requirements.*\.txt$", Path(f).name)
             for f in files)
    return npm, py


def osv_query(pkgs: list[tuple[str, str, str]]) -> list[str]:
    """pkgs = [(name, version, ecosystem)]. Returns human-readable hits.

    Raises on transport failure — the caller turns that into a FAIL, never a pass.
    """
    if not pkgs:
        return []
    hits: list[str] = []
    for i in range(0, len(pkgs), 100):
        chunk = pkgs[i:i + 100]
        body = json.dumps({"queries": [
            {"package": {"name": n, "ecosystem": e}, "version": v} for n, v, e in chunk]}).encode()
        req = urllib.request.Request(OSV, data=body,
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "assistant-ops-newdeps/1.0"})
        with urllib.request.urlopen(req, timeout=45) as r:
            res = json.load(r)
        for (n, v, _e), entry in zip(chunk, res.get("results", []), strict=False):
            vulns = entry.get("vulns") or []
            if vulns:
                ids = [x.get("id", "?") for x in vulns[:4]]
                mal = " ← MALWARE" if any(str(x).startswith("MAL-") for x in ids) else ""
                hits.append(f"{n}@{v}: {', '.join(ids)}{mal}")
    return hits


def npm_lock_packages(repo: Path) -> list[tuple[str, str, str]]:
    lock = repo / "package-lock.json"
    if not lock.exists():
        return []
    d = json.loads(lock.read_text())
    out: list[tuple[str, str, str]] = []
    for path, meta in (d.get("packages") or {}).items():
        if not path or not isinstance(meta, dict):
            continue
        name = path.split("node_modules/")[-1]
        ver = meta.get("version")
        if name and ver:
            out.append((name, ver, "npm"))
    for name, meta in (d.get("dependencies") or {}).items():
        if isinstance(meta, dict) and meta.get("version"):
            out.append((name, meta["version"], "npm"))
    return out


def npm_audit(repo: Path) -> tuple[list[str], str | None]:
    """(findings, error). npm audit needs a lockfile; it does not need node_modules."""
    if not (repo / "package-lock.json").exists():
        return [], None
    try:
        r = subprocess.run(["npm", "audit", "--json"], cwd=repo,
                           capture_output=True, text=True, timeout=180)
    except FileNotFoundError:
        return [], "npm is not installed — cannot run `npm audit`"
    except Exception as e:
        return [], f"npm audit failed: {type(e).__name__}"
    try:
        d = json.loads(r.stdout or "{}")
    except Exception:
        return [], "npm audit produced unparseable JSON"
    findings = []
    for name, info in (d.get("vulnerabilities") or {}).items():
        sev = str(info.get("severity", "?")).upper()
        via = info.get("via") or []
        titles = sorted({v.get("title") for v in via if isinstance(v, dict) and v.get("title")})
        mal = any("malware" in (t or "").lower() for t in titles)
        if sev in ("CRITICAL", "HIGH") or mal:
            head = titles[0] if titles else "advisory"
            findings.append(f"{sev}: {name} — {head}" + ("  ← MALWARE" if mal else ""))
    return findings, None


def py_packages(repo: Path) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for req in list(repo.glob("requirements*.txt")):
        for line in req.read_text(errors="replace").splitlines():
            line = line.split("#", 1)[0].strip()
            m = re.match(r"^([A-Za-z0-9._-]+)\s*==\s*([0-9][\w.\-+]*)$", line)
            if m:
                out.append((m.group(1), m.group(2), "PyPI"))
    lock = repo / "uv.lock"
    if lock.exists():
        name = None
        for line in lock.read_text(errors="replace").splitlines():
            if m := re.match(r'^name = "(.+)"', line.strip()):
                name = m.group(1)
            elif (m := re.match(r'^version = "(.+)"', line.strip())) and name:
                out.append((name, m.group(1), "PyPI"))
                name = None
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="main")
    ap.add_argument("--repo", default=".")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()

    npm_changed, py_changed = changed_manifests(a.base, repo)
    if not npm_changed and not py_changed:
        return 0

    problems: list[str] = []
    blocked: list[str] = []

    if npm_changed:
        print("new-deps: npm manifest changed — scanning")
        findings, err = npm_audit(repo)
        if err:
            blocked.append(err)
        problems += [f"  npm audit: {f}" for f in findings]
        try:
            hits = osv_query(npm_lock_packages(repo))
            problems += [f"  osv: {h}" for h in hits]
        except Exception as e:
            blocked.append(f"OSV lookup failed for npm packages: {type(e).__name__}: {e}")

    if py_changed:
        print("new-deps: python manifest changed — scanning")
        try:
            hits = osv_query(py_packages(repo))
            problems += [f"  osv: {h}" for h in hits]
        except Exception as e:
            blocked.append(f"OSV lookup failed for python packages: {type(e).__name__}: {e}")

    if blocked:
        print("new-deps: CANNOT SCAN — refusing to pass a dependency change unscanned:")
        for b in blocked:
            print(f"  {b}")
        metric("loop", "gate_failure", 1, "new_deps_unscannable")
        return 1

    if problems:
        print(f"new-deps: {len(problems)} finding(s) on the dependencies this card adds:")
        for p in problems:
            print(p)
        print("")
        print("Pin it, replace it, or kanban_block and ask. Do not silence the scanner.")
        metric("loop", "gate_failure", len(problems), "new_deps")
        return 1

    print("new-deps: clean")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # Fail closed. A dependency scanner that errors open is worse than none.
        print(f"new-deps: scanner crashed ({type(e).__name__}: {e}) — failing closed")
        sys.exit(1)
