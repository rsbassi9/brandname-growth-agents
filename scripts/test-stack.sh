#!/usr/bin/env bash
# Linux-only isolated API/browser cycle; see docs/testing.md.
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python3 scripts/functional_stack.py "$@"
