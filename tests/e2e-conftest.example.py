"""SCAFFOLD: copy to tests/e2e/conftest.py and fill the TODOs.

The two error recorders (TESTING.md, non-negotiable): every page fixture
tracks HTTP >= 500 and uncaught JS/console errors, and FAILS THE TEST on
either at teardown even when the test's own asserts passed. This is what
turns "found an internal server error by clicking around" into a red gate.

Requires: pip install playwright pytest-playwright
          python3 -m playwright install chromium
Driven by scripts/test-stack.sh e2e, which sources .test-stack.env.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import pytest

# Known-noise console lines that must not fail tests. Keep SHORT and explicit;
# every entry is a documented decision, not a convenience.
IGNORED_CONSOLE = [
    re.compile(r"favicon", re.I),
    re.compile(r"the server responded with a status of 4\d\d", re.I),
]


@dataclass
class AppPage:
    page: object
    base_url: str
    server_errors: list = field(default_factory=list)
    console_errors: list = field(default_factory=list)

    def goto(self, route: str = ""):
        self.page.goto(f"{self.base_url}/{route.lstrip('/')}")
        self.page.wait_for_load_state("networkidle")

    def assert_healthy(self, context: str = ""):
        where = f" on {context}" if context else ""
        assert not self.server_errors, \
            f"server errors (>=500){where}: {self.server_errors}"
        assert not self.console_errors, \
            f"console/page errors{where}: {self.console_errors}"


@pytest.fixture(scope="session")
def base_url():
    url = os.environ.get("APP_BASE_URL")  # TODO: your env var name (from .test-stack.env)
    if not url:
        pytest.skip("APP_BASE_URL not set (run via scripts/test-stack.sh e2e)")
    return url.rstrip("/")


def _track(app: AppPage):
    app.page.on("response", lambda r: r.status >= 500
                and app.server_errors.append(f"{r.status} {r.url}"))
    app.page.on("console", lambda m: m.type == "error"
                and not any(p.search(m.text) for p in IGNORED_CONSOLE)
                and app.console_errors.append(m.text))
    app.page.on("pageerror", lambda e: app.console_errors.append(f"pageerror: {e}"))


@pytest.fixture()
def anon(page, base_url) -> AppPage:
    """Un-authenticated tracked page (login-flow tests)."""
    app = AppPage(page=page, base_url=base_url)
    _track(app)
    yield app


@pytest.fixture()
def app(page, base_url) -> AppPage:
    """Logged-in tracked page; teardown sweep fails on any recorded error."""
    a = AppPage(page=page, base_url=base_url)
    _track(a)
    # TODO: perform login with seeded credentials, wait for a post-login anchor:
    #   page.goto(base_url); page.fill(...); page.click(...)
    #   page.wait_for_selector("<stable post-login selector>", timeout=30_000)
    yield a
    a.assert_healthy("teardown sweep")
