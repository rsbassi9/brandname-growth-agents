from __future__ import annotations

import asyncio
import json
from datetime import datetime


def test_weekly_standup_job_creates_report_with_three_recommendations(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import CalendarItem, PostMetric, PublishedPost, StandupReport
    from app.services.jobs import _handle_weekly_standup

    init_db()
    with session_scope() as session:
        top = PublishedPost(
            channel="instagram",
            title_or_caption="Source proof first",
            permalink="https://instagram.com/p/sourceproof",
            published_at=datetime(2026, 7, 7, 10, 0),
        )
        bottom = PublishedPost(channel="instagram", title_or_caption="Vague styling post", published_at=datetime(2026, 7, 8, 10, 0))
        session.add_all([top, bottom])
        session.flush()
        top_id = top.id
        session.add(PostMetric(published_post_id=top.id, captured_at=datetime(2026, 7, 12), reach=100, likes=30, comments=5))
        session.add(PostMetric(published_post_id=bottom.id, captured_at=datetime(2026, 7, 12), reach=100, likes=2))
        session.add(
            CalendarItem(
                id="next-week-anchor",
                date="2026-07-15",
                status="draft",
                data_json=json.dumps({"title": "Launch teaser"}),
            )
        )

    result = asyncio.run(_handle_weekly_standup("missing-test-job", {"week_start": "2026-07-06"}))

    assert result["recommendations"] == 3
    with session_scope() as session:
        report = session.get(StandupReport, result["standup_report_id"])
        assert report is not None
        assert report.week_start == "2026-07-06"
        assert "Source proof first" in report.report_md
        assert "Launch teaser" in report.report_md
        recommendations = json.loads(report.recommendations_json)
        assert len(recommendations) == 3
        assert recommendations[0]["evidence"]["top_post_id"] == top_id


def test_standup_draft_endpoint_creates_idempotent_tray_asset(client) -> None:
    from app.db import session_scope
    from app.models import Asset, AssetVersion, StandupReport

    with session_scope() as session:
        report = StandupReport(
            week_start="2026-07-06",
            report_md="# Weekly Standup",
            recommendations_json=json.dumps(
                [
                    {
                        "title": "Turn the top proof hook into a fresh caption draft",
                        "draft_type": "copy",
                        "rationale": "Top performer keeps winning.",
                        "brief": "Draft the next caption.",
                        "evidence": {"top_post_id": 1},
                    }
                ]
            ),
        )
        session.add(report)
        session.flush()
        report_id = report.id

    first = client.post(f"/api/v1/strategy/standup/{report_id}/recommendations/0/draft")
    second = client.post(f"/api/v1/strategy/standup/{report_id}/recommendations/0/draft")

    assert first.status_code == 200, first.text
    assert second.json()["asset_id"] == first.json()["asset_id"]
    with session_scope() as session:
        asset = session.get(Asset, first.json()["asset_id"])
        assert asset is not None
        assert asset.status == "draft"
        assert asset.source_path == f"standup:{report_id}:0"
        version = session.query(AssetVersion).filter_by(asset_id=asset.id).one()
        params = json.loads(version.params_json)
        assert params["standup_report_id"] == report_id
        assert "No auto-scheduling was performed" in version.content_text


def test_weekly_standup_schedule_is_off_by_default_and_enqueues_weekly(client) -> None:
    from app.db import session_scope
    from app.models import Job
    from app.services.scheduler import enqueue_due_weekly_standup

    assert client.get("/api/v1/system/weekly-standup").json()["enabled"] is False
    assert enqueue_due_weekly_standup(datetime(2026, 7, 13, 10, 0)) is None

    updated = client.put("/api/v1/system/weekly-standup", json={"enabled": True, "weekday": 0, "time_local": "09:00"})
    assert updated.status_code == 200
    job_id = enqueue_due_weekly_standup(datetime(2026, 7, 13, 10, 0))
    assert job_id is not None
    assert enqueue_due_weekly_standup(datetime(2026, 7, 13, 11, 0)) is None
    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.kind == "weekly_standup"


def test_weekly_standup_run_endpoint_enqueues_job(client) -> None:
    from app.db import session_scope
    from app.models import Job

    response = client.post("/api/v1/system/weekly-standup/run")

    assert response.status_code == 200, response.text
    with session_scope() as session:
        job = session.get(Job, response.json()["job_id"])
        assert job is not None
        assert job.kind == "weekly_standup"
