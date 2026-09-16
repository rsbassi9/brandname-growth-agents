"""Real HTTP + browser contracts, launched only inside the disposable namespace."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request


def request(base, path, data=None, method="GET", expected=200):
    req = urllib.request.Request(base + path, method=method,
                                 data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        response = urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        assert response.status == expected, (path, response.status, response.read()[:300])
        raw = response.read()
        return json.loads(raw) if raw and "application/json" in response.headers.get("Content-Type", "") else raw


def smoke(base):
    assert request(base, "/api/v1/system/health")["status"] == "ok"
    for path in ("/api/v1/system/mode", "/api/v1/assets", "/api/v1/campaigns", "/api/v1/calendar", "/api/v1/feed"):
        request(base, path)
    assert b'id="root"' in request(base, "/playground")


def seed(base):
    assert request(base, "/api/v1/system/mode")["local_only_agent_runs"] is True
    request(base, "/api/v1/campaigns", {"name": "Synthetic launch", "goal": "Fixture-only drafts"}, "POST", 201)


def integration(base):
    smoke(base)
    assert request(base, "/api/v1/system/mode")["local_only_agent_runs"] is True
    assert request(base, "/api/v1/system/daily-workflow")["enabled"] is False
    schema = request(base, "/openapi.json")["components"]["schemas"]
    kinds = schema["GenerateRequest"]["properties"]["type"]["enum"]
    assert set(kinds) == {"copy", "image_concept", "carousel", "video_script", "voiceover", "ad_brief", "seo_fix", "seo_plan"}
    for kind in kinds:
        item = request(base, "/api/v1/generate", {"type": kind, "brief": "Synthetic garment proof", "params": {}}, "POST")
        for _ in range(100):
            job = request(base, f"/api/v1/jobs/{item['job_id']}")
            if job["status"] in {"succeeded", "failed"}:
                break
            time.sleep(0.1)
        assert job["status"] == "succeeded", job
        asset = request(base, f"/api/v1/assets/{item['asset_id']}")
        assert asset["type"] == kind and asset["versions"], asset
        assert asset["versions"][0]["model_used"] == "local-deterministic"
    request(base, "/api/v1/generate", {"type": "invalid", "brief": "fixture"}, "POST", 422)
    request(base, "/api/v1/generate", {"type": "copy", "brief": "fixture", "params": {"source_asset_ids": [999999]}}, "POST", 404)
    item = request(base, "/api/v1/calendar", {"date": "2026-01-05", "status": "draft", "data": {"hook": "Synthetic"}}, "POST", 201)
    route = f"/api/v1/calendar/{item['id']}"
    assert request(base, route)["status"] == "draft"
    assert request(base, route, {"data": {"caption": "Synthetic revision"}}, "PATCH")["data"]["hook"] == "Synthetic"
    request(base, route, method="DELETE", expected=204)
    request(base, route, expected=404)
    request(base, "/api/v1/strategy/context/unknown-fixture.md", expected=404)


def e2e(base):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context()
        failures = []

        def track(page):
            page.on("response", lambda response: failures.append(f"HTTP {response.status} {response.url}") if response.status >= 500 else None)
            page.on("pageerror", lambda error: failures.append(str(error)))
            page.on("console", lambda message: failures.append(message.text) if message.type == "error" else None)

        context.on("page", track)
        try:
            page = context.new_page()
            for route in ("playground", "campaigns", "library", "calendar", "feed", "ads", "strategy", "system"):
                page.goto(f"{base}/{route}")
                expect(page.get_by_role("navigation", name="Primary")).to_be_visible()
                expect(page.locator("h1")).to_be_visible()
                page.wait_for_load_state("networkidle")
                assert not failures, failures
            page.goto(base + "/campaigns")
            page.get_by_label("Campaign name", exact=True).fill("Browser fixture campaign")
            page.get_by_label("Goal", exact=True).fill("Synthetic content only")
            page.get_by_role("button", name="Create Campaign", exact=True).click()
            expect(page.get_by_role("heading", name="Browser fixture campaign", exact=True)).to_be_visible()
            assert any(item["name"] == "Browser fixture campaign" for item in request(base, "/api/v1/campaigns"))
            page.goto(base + "/playground")
            page.get_by_label("Brief", exact=True).fill("Browser synthetic garment brief")
            page.get_by_role("button", name="Generate", exact=True).click()
            expect(page.get_by_text("Version 1", exact=True)).to_be_visible(timeout=20000)
            assets = request(base, "/api/v1/assets")["items"]
            generated = next(item for item in assets if item["title"] == "Browser synthetic garment brief")
            detail = request(base, f"/api/v1/assets/{generated['id']}")
            assert "Browser synthetic garment brief" in detail["versions"][0]["content_text"]
            assert not failures, failures
        finally:
            context.close()
            browser.close()
        assert not failures, failures


if __name__ == "__main__":
    verb, base = sys.argv[1:]
    if verb == "health":
        try:
            request(base, "/api/v1/system/health")
        except urllib.error.URLError:
            raise SystemExit(1) from None
    else:
        {"smoke": smoke, "seed": seed, "integration": integration, "e2e": e2e}[verb](base)
        print(f"functional {verb}: PASS")
