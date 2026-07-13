from __future__ import annotations

import asyncio
import json
from datetime import datetime


def test_recycle_top_posts_creates_idempotent_unscheduled_remixes(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import Asset, AssetVersion, PostMetric, PublishedPost
    from app.services.jobs import _handle_recycle_top_posts

    init_db()
    with session_scope() as session:
        for index, likes in enumerate([40, 30, 20, 10], start=1):
            post = PublishedPost(
                channel="instagram",
                title_or_caption=f"Post {index}",
                published_at=datetime(2026, 5, index),
            )
            session.add(post)
            session.flush()
            session.add(PostMetric(published_post_id=post.id, captured_at=datetime(2026, 7, 1), reach=100, likes=likes))
        recent = PublishedPost(channel="instagram", title_or_caption="Recent top", published_at=datetime(2026, 7, 1))
        session.add(recent)
        session.flush()
        session.add(PostMetric(published_post_id=recent.id, captured_at=datetime(2026, 7, 1), reach=100, likes=99))

    result = asyncio.run(_handle_recycle_top_posts("missing-test-job", {"cutoff_days": 45}))
    second = asyncio.run(_handle_recycle_top_posts("missing-test-job", {"cutoff_days": 45}))

    assert result["candidates"] == 1
    assert len(result["created"]) == 1
    assert second["created"] == []
    with session_scope() as session:
        asset = session.query(Asset).filter(Asset.source_path.like("remix:%")).one()
        assert asset.status == "draft"
        assert asset.source_path == "remix:1"
        version = session.query(AssetVersion).filter_by(asset_id=asset.id).one()
        params = json.loads(version.params_json)
        assert params["remix_of"] == 1
        assert "No auto-scheduling was performed" in version.content_text


def test_recycle_top_posts_keeps_top_quartile_for_larger_sample(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import PostMetric, PublishedPost
    from app.services.jobs import _handle_recycle_top_posts

    init_db()
    with session_scope() as session:
        for index, likes in enumerate([80, 70, 60, 50, 40, 30, 20, 10], start=1):
            post = PublishedPost(channel="tiktok", title_or_caption=f"Post {index}", published_at=datetime(2026, 4, index))
            session.add(post)
            session.flush()
            session.add(PostMetric(published_post_id=post.id, captured_at=datetime(2026, 7, 1), reach=100, likes=likes))

    result = asyncio.run(_handle_recycle_top_posts("missing-test-job", {"cutoff_days": 45}))

    assert result["candidates"] == 2
    assert [item["post_id"] for item in result["created"]] == [1, 2]


def test_recycling_schedule_is_off_by_default_and_enqueues_monthly(client) -> None:
    from app.db import session_scope
    from app.models import Job
    from app.services.scheduler import enqueue_due_recycling, set_recycling_schedule

    assert client.get("/api/v1/system/recycling").json()["enabled"] is False
    assert enqueue_due_recycling(datetime(2026, 7, 1, 10, 0)) is None

    updated = client.put("/api/v1/system/recycling", json={"enabled": True, "day": 1, "time_local": "09:00"})
    assert updated.status_code == 200
    job_id = enqueue_due_recycling(datetime(2026, 7, 1, 10, 0))
    assert job_id is not None
    assert enqueue_due_recycling(datetime(2026, 7, 1, 11, 0)) is None
    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.kind == "recycle_top_posts"

    schedule = set_recycling_schedule(False, 1, "09:00")
    assert schedule.enabled is False


def test_recycling_run_endpoint_enqueues_job(client) -> None:
    from app.db import session_scope
    from app.models import Job

    response = client.post("/api/v1/system/recycling/run")

    assert response.status_code == 200, response.text
    with session_scope() as session:
        job = session.get(Job, response.json()["job_id"])
        assert job is not None
        assert job.kind == "recycle_top_posts"
