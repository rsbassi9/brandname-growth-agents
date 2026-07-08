"""Deterministic local workflow port + daily-workflow job flag check (P1-4)."""

from __future__ import annotations

from pathlib import Path

from tests._helpers import wait_for_job


def test_local_daily_workflow_writes_outputs(app_env: Path) -> None:
    from app.services.local_workflow import run_local_daily_workflow

    paths = run_local_daily_workflow()
    expected = {"asset_inventory", "ideas", "content_candidates", "drafts", "seo", "analytics", "ad_concepts", "report"}
    assert expected == set(paths)
    for path in paths.values():
        assert Path(path).exists(), path
    report = Path(paths["report"]).read_text(encoding="utf-8")
    assert "Local only" in report


def test_local_workflow_uses_brand_setting(app_env, monkeypatch) -> None:
    from app.services.local_workflow import _candidate_specs
    from app.settings import reset_settings_cache

    monkeypatch.setenv("BRAND_NAME", "TEST LABEL")
    reset_settings_cache()
    specs = _candidate_specs({}, 1)
    joined = " ".join(spec["why"] for spec in specs)
    assert "TEST LABEL" in joined


def test_daily_workflow_job_local_only_uses_fallback(client) -> None:
    """LOCAL_ONLY_AGENT_RUNS=true: the job runs the deterministic port, no OpenAI."""
    import json

    from app.services.jobs import job_queue

    job_id = job_queue.enqueue("run_daily_workflow", {})
    job = wait_for_job(client, job_id, timeout=30)
    assert job["status"] == "succeeded", job["message"]
    result = json.loads(job["result_json"])
    assert result["mode"] == "local_only"
    assert Path(result["paths"]["report"]).exists()
    assert len(result["assets"]) == 8
    assert client.get(f"/api/v1/assets/{result['assets'][0]['asset_id']}").status_code == 200


def test_daily_workflow_schedule_defaults_off(client) -> None:
    payload = client.get("/api/v1/system/daily-workflow").json()
    assert payload == {"enabled": False, "time_local": "09:00", "last_enqueued_date": ""}


def test_daily_workflow_schedule_can_be_updated(client) -> None:
    response = client.put("/api/v1/system/daily-workflow", json={"enabled": True, "time_local": "07:30"})
    assert response.status_code == 200, response.text
    assert response.json()["enabled"] is True
    assert response.json()["time_local"] == "07:30"

    fetched = client.get("/api/v1/system/daily-workflow").json()
    assert fetched["enabled"] is True
    assert fetched["time_local"] == "07:30"


def test_due_scheduler_enqueues_once_per_day(client) -> None:
    from datetime import datetime

    from app.services.scheduler import enqueue_due_daily_workflow

    client.put("/api/v1/system/daily-workflow", json={"enabled": True, "time_local": "07:30"})
    first = enqueue_due_daily_workflow(datetime(2026, 7, 8, 7, 31))
    second = enqueue_due_daily_workflow(datetime(2026, 7, 8, 12, 0))
    assert first
    assert second is None


def test_manual_daily_workflow_endpoint_enqueues_job(client) -> None:
    response = client.post("/api/v1/system/daily-workflow/run")
    assert response.status_code == 200, response.text
    assert response.json()["job_id"]


def test_unknown_job_kind_rejected(client) -> None:
    import pytest

    from app.services.jobs import job_queue

    with pytest.raises(ValueError):
        job_queue.enqueue("mine_bitcoin", {})


def test_job_404(client) -> None:
    assert client.get("/api/v1/jobs/does-not-exist").status_code == 404


def test_render_carousel_job(client) -> None:
    import json

    from app.services.jobs import job_queue

    job_id = job_queue.enqueue(
        "render_carousel",
        {"title": "demo", "slides": [{"headline": "Fragment", "body": "Canvas to file.", "palette": "dark"}]},
    )
    job = wait_for_job(client, job_id, timeout=30)
    assert job["status"] == "succeeded", job["message"]
    result = json.loads(job["result_json"])
    assert result["paths"] and result["paths"][0].endswith(".png")
    assert Path(result["paths"][0]).exists()
