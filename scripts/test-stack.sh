#!/usr/bin/env bash
# Linux-only isolated API/browser cycle; see docs/testing.md.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "${1:-}" = ci ]; then
  for coverage_part in run checks server; do
    .venv/bin/python3 -m coverage erase --data-file=".coverage.functional-$coverage_part"
  done
  result=0
  .venv/bin/python3 -m coverage run --data-file=.coverage.functional-run scripts/functional_stack.py "$@" || result=$?
  .venv/bin/python3 -m coverage combine --append --keep .coverage.functional-* || result=$?
  exit "$result"
fi
exec .venv/bin/python3 scripts/functional_stack.py "$@"
