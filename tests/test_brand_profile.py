from __future__ import annotations

import asyncio
import json
from datetime import datetime


PROFILE_RESPONSE = """## Voice rules
- Use source proof in the hook. (fb_1, pair_1_1_2)
## Banned phrases
Insufficient evidence this period.
## Visual codes
Insufficient evidence this period.
## Proven hooks
- Open with canvas-to-garment proof. (pair_1_1_2)
## Audience notes
Insufficient evidence this period."""


def test_distill_brand_profile_job_writes_immutable_version(app_env, monkeypatch) -> None:
    from app.db import init_db, session_scope
    from app.models import Asset, AssetVersion, BrandProfileVersion, FeedbackEvent
    from app.services.jobs import run_one_shot

    init_db()
    captured = {}

    async def fake_agent(prompt: str) -> str:
        captured["prompt"] = prompt
        return PROFILE_RESPONSE

    monkeypatch.setattr("app.services.brand_profile.run_distillation_agent", fake_agent)
    with session_scope() as session:
        asset = Asset(type="copy", title="Drop caption", status="draft")
        session.add(asset)
        session.flush()
        session.add_all(
            [
                AssetVersion(
                    asset_id=asset.id,
                    version_no=1,
                    prompt_snapshot="selected",
                    params_json="{}",
                    content_text="Hook: canvas proof, now worn.",
                    model_used="local",
                    is_selected=True,
                ),
                AssetVersion(
                    asset_id=asset.id,
                    version_no=2,
                    prompt_snapshot="unselected",
                    params_json="{}",
                    content_text="Generic hype caption.",
                    model_used="local",
                    is_selected=False,
                ),
                FeedbackEvent(
                    id="fb_1",
                    created_at="2026-07-08T12:00:00",
                    output_path="asset:1",
                    rating=5,
                    comment="Source proof works.",
                    improvement_request="Keep it concrete.",
                    category="test",
                    data_json="{}",
                ),
            ]
        )

    snapshot = asyncio.run(run_one_shot("distill_brand_profile", {"source": "test"}))
    assert snapshot["status"] == "succeeded", snapshot["message"]
    assert "CURRENT PROFILE (v0)" in captured["prompt"]
    assert "fb_1" in captured["prompt"]
    assert "pair_1_1_2" in captured["prompt"]

    with session_scope() as session:
        profile = session.query(BrandProfileVersion).one()
        assert profile.version_no == 1
        assert "## Voice rules" in profile.profile_md
        distilled_from = json.loads(profile.distilled_from_json)
        assert set(distilled_from["evidence_ids"]) == {"fb_1", "pair_1_1_2"}


def test_invalid_distillation_response_is_dropped(app_env, monkeypatch) -> None:
    from app.db import init_db, session_scope
    from app.models import BrandProfileVersion
    from app.services.brand_profile import distill_brand_profile

    init_db()

    async def fake_agent(prompt: str) -> str:
        return "## Voice rules\n- Missing most sections. (fb_1)"

    monkeypatch.setattr("app.services.brand_profile.run_distillation_agent", fake_agent)
    result = asyncio.run(distill_brand_profile())
    assert result["created"] is False
    assert "missing section" in result["reason"]
    with session_scope() as session:
        assert session.query(BrandProfileVersion).count() == 0


def test_brand_profile_distillation_schedule_is_off_and_deduped(app_env, monkeypatch) -> None:
    from app.db import init_db
    from app.services import scheduler

    init_db()
    assert scheduler.enqueue_due_brand_profile_distillation(datetime(2026, 7, 8, 12, 0)) is None

    enqueued = []
    monkeypatch.setattr(scheduler, "enqueue_brand_profile_distillation", lambda source: enqueued.append(source) or "job-1")
    scheduler.set_brand_profile_distillation_schedule(enabled=True, time_local="07:30", weekday=2)

    first = scheduler.enqueue_due_brand_profile_distillation(datetime(2026, 7, 8, 7, 31))
    second = scheduler.enqueue_due_brand_profile_distillation(datetime(2026, 7, 8, 12, 0))
    wrong_day = scheduler.enqueue_due_brand_profile_distillation(datetime(2026, 7, 9, 12, 0))

    assert first == "job-1"
    assert second is None
    assert wrong_day is None
    assert enqueued == ["scheduler"]


def test_strategy_brand_profile_endpoint_returns_history(client) -> None:
    from app.db import session_scope
    from app.models import BrandProfileVersion

    with session_scope() as session:
        session.add_all(
            [
                BrandProfileVersion(version_no=1, profile_md="## Voice rules\nOld", distilled_from_json="{}"),
                BrandProfileVersion(version_no=2, profile_md=PROFILE_RESPONSE, distilled_from_json='{"evidence_ids":["fb_1"]}'),
            ]
        )

    response = client.get("/api/v1/strategy/brand-profile")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["current"]["version_no"] == 2
    assert [item["version_no"] for item in payload["versions"]] == [2, 1]
