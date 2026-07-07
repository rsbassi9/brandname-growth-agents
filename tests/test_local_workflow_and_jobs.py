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
