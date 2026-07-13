from __future__ import annotations

import asyncio
import json


def test_repurpose_shoot_endpoint_enqueues_job(client) -> None:
    from app.db import session_scope
    from app.models import Job, SourceAsset

    with session_scope() as session:
        source = SourceAsset(origin="local", path="shoot/front.jpg", tags_json=json.dumps(["front"]), product_handle="canvas-tee")
        session.add(source)
        session.flush()
        source_id = source.id

    response = client.post("/api/v1/repurpose/shoot", json={"source_asset_ids": [source_id], "campaign_name": "Drop shoot"})

    assert response.status_code == 200, response.text
    with session_scope() as session:
        job = session.get(Job, response.json()["job_id"])
        assert job is not None
        assert job.kind == "repurpose_shoot"


def test_repurpose_shoot_endpoint_rejects_missing_source(client) -> None:
    response = client.post("/api/v1/repurpose/shoot", json={"source_asset_ids": [999]})

    assert response.status_code == 404


def test_repurpose_shoot_job_creates_campaign_assets_and_versions(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import Asset, AssetVersion, Campaign, SourceAsset
    from app.services.jobs import _handle_repurpose_shoot

    init_db()
    with session_scope() as session:
        source = SourceAsset(
            origin="local",
            path="shoot/front.jpg",
            tags_json=json.dumps(["front", "studio"]),
            product_handle="canvas-tee",
        )
        session.add(source)
        session.flush()
        source_id = source.id

    result = asyncio.run(
        _handle_repurpose_shoot(
            "missing-test-job",
            {"source_asset_ids": [source_id], "campaign_name": "Drop shoot", "brief": "Use the cleanest garment proof."},
        )
    )

    assert result["campaign_id"]
    assert [step["status"] for step in result["steps"]] == ["succeeded", "succeeded", "succeeded", "succeeded", "succeeded"]
    assert {step["name"] for step in result["steps"]} == {
        "post_copy",
        "reel_video_script",
        "story_set",
        "ad_brief",
        "product_page_refresh",
    }
    with session_scope() as session:
        campaign = session.get(Campaign, result["campaign_id"])
        assert campaign is not None
        assets = session.query(Asset).filter_by(campaign_id=campaign.id).order_by(Asset.id).all()
        assert [asset.type for asset in assets] == ["copy", "video_script", "copy", "ad_brief", "seo_fix"]
        versions = session.query(AssetVersion).filter(AssetVersion.asset_id.in_([asset.id for asset in assets])).all()
        assert len(versions) == 5
        params = [json.loads(version.params_json) for version in versions]
        assert all(item["repurpose_campaign_id"] == campaign.id for item in params)
        assert any(item["repurpose_step"] == "product_page_refresh" and item["type"] == "seo_fix" for item in params)


def test_repurpose_shoot_without_product_skips_seo_refresh(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import SourceAsset
    from app.services.jobs import _handle_repurpose_shoot

    init_db()
    with session_scope() as session:
        source = SourceAsset(origin="local", path="shoot/detail.jpg", tags_json="[]", product_handle=None)
        session.add(source)
        session.flush()
        source_id = source.id

    result = asyncio.run(_handle_repurpose_shoot("missing-test-job", {"source_asset_ids": [source_id]}))

    assert {step["name"] for step in result["steps"]} == {"post_copy", "reel_video_script", "story_set", "ad_brief"}
