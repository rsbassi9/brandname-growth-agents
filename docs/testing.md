# Functional cycle

Linux with `unshare`, `nsenter`, `ip` and root (passwordless sudo on CI).
The harness fails if isolation is unavailable. Install requirements-dev and
Chromium before entering the isolated network namespace:

```
PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/ms-playwright" .venv/bin/python3 -m playwright install chromium
bash scripts/test-stack.sh ci
```

On non-root CI, run the second command via sudo while preserving the toolchain
PATH. `ci --no-e2e` retains API integration. All TESTING.md verbs are supported;
`smoke` defaults to the current disposable instance. The read-only smoke function
can separately be invoked as `tests/functional/checks.py smoke <approved URL>`
after deployment; it performs no writes.

The stack exports committed app/src/agent instructions into a fresh owned temp
directory. No live .env, token, DB, outputs, personal memory or Drive images are
copied. Brand context is synthetic. Environment is allowlisted, local-only model
mode is mandatory, Drive/Shopify writes/backups are off. The API and browser share
an isolated loopback network; no outbound calls are possible. This is not a
filesystem security boundary against malicious root code.

`apply` uses the real `npm run build` and `uvicorn app.main:app`/`init_db` startup,
then API reads, enum-backed generation/jobs, calendar CRUD and eight browser
routes run. Browser tests fail on HTTP >=500, pageerror or console.error, and
exercise campaign creation and asset generation. `ci` always calls `down`;
teardown checks an ownership marker and PID start time before deleting/signaling.
The cycle instruments its controller/check subprocesses and combines coverage
with the unit run, so the unchanged changed-lines floor measures the new harness.

Parity gaps: external Drive/Shopify/paid models are intentionally disabled and
must be verified separately with approved read-only integration probes before
release. This FastAPI Studio currently has **no authentication layer** (unlike
the legacy dashboard); there is no login/ACL test to pretend passes. Do not expose
it publicly. Operator access must remain restricted by the existing host/network
boundary until authenticated service access is separately implemented. The
legacy dashboard's Windows launcher is not used by the Linux Studio.

Playwright is a pinned, dev-only dependency from Microsoft's PyPI package. No
browser server is exposed; Chromium is launched only inside the test namespace.
