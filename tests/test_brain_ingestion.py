from __future__ import annotations

import asyncio
import json


def test_brain_index_job_indexes_asset_version(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import Asset, AssetVersion, BrainDocument, BrainEmbedding
    from app.services.jobs import run_one_shot

    init_db()
    with session_scope() as session:
        asset = Asset(type="copy", title="Canvas tee caption", status="draft")
        session.add(asset)
        session.flush()
        version = AssetVersion(
            asset_id=asset.id,
            version_no=1,
            prompt_snapshot="Write about the canvas fragment tee.",
            params_json="{}",
            content_text="Canvas fragment tee launch caption.",
            model_used="local-deterministic",
            is_selected=True,
        )
        session.add(version)
        session.flush()
        version_id = version.id

    snapshot = asyncio.run(run_one_shot("brain_index", {"asset_version_id": version_id}))

    assert snapshot["status"] == "succeeded", snapshot["message"]
    with session_scope() as session:
        document = session.query(BrainDocument).filter_by(kind="asset_version", ref_id="1:1").one()
        assert "Canvas tee caption" in document.text
        assert json.loads(document.meta_json)["asset_version_id"] == version_id
        embedding = session.query(BrainEmbedding).filter_by(document_id=document.id).one()
        assert embedding.dim == 256


def test_feedback_endpoint_enqueues_brain_index(client, monkeypatch) -> None:
    from app.routers import strategy

    enqueued: list[tuple[str, dict]] = []

    def fake_enqueue(kind: str, payload: dict) -> str:
        enqueued.append((kind, payload))
        return "job-brain"

    monkeypatch.setattr(strategy.job_queue, "enqueue", fake_enqueue)

    response = client.post(
        "/api/v1/strategy/learn/feedback",
        json={"output_path": "asset:1", "rating": 5, "comment": "More proof.", "improvement_request": ""},
    )

    assert response.status_code == 201, response.text
    assert enqueued == [("brain_index", {"feedback_id": response.json()["id"]})]


def test_backfill_is_idempotent(app_env, monkeypatch) -> None:
    from app.db import init_db, session_scope
    from app.models import Asset, AssetVersion, BrainDocument, BrainEmbedding, FeedbackEvent
    from app.services import shopify
    from app.services.brain import run_backfill

    class FakeShopifyService:
        def product_preview(self, limit: int = 80) -> dict:
            return {
                "status": {"enabled": True},
                "products": [
                    {
                        "id": 101,
                        "title": "Fragment Tee",
                        "handle": "fragment-tee",
                        "product_type": "Tee",
                        "tags": "canvas, fragment",
                        "description_excerpt": "Source painting reconstructed as cotton.",
                    }
                ],
            }

    monkeypatch.setattr(shopify, "ShopifyService", FakeShopifyService)

    init_db()
    with session_scope() as session:
        asset = Asset(type="copy", title="Backfill caption", status="draft")
        session.add(asset)
        session.flush()
        session.add(
            AssetVersion(
                asset_id=asset.id,
                version_no=1,
                prompt_snapshot="Backfill prompt",
                params_json="{}",
                content_text="Backfill content",
                model_used="local-deterministic",
                is_selected=True,
            )
        )
        session.add(
            FeedbackEvent(
                id="fb_backfill",
                created_at="2026-07-08T00:00:00",
                output_path="asset:1",
                rating=4,
                comment="Keep the visual proof.",
                improvement_request="",
                category="qa",
            )
        )

    first = run_backfill()
    second = run_backfill()

    with session_scope() as session:
        documents = session.query(BrainDocument).all()
        embeddings = session.query(BrainEmbedding).all()
        keys = {(document.kind, document.ref_id) for document in documents}

    assert first["embeddings"] > 0
    assert second["embeddings"] == 0
    assert len(documents) == len(embeddings)
    assert ("asset_version", "1:1") in keys
    assert ("feedback", "fb_backfill") in keys
    assert ("product", "fragment-tee") in keys
    assert any(kind == "context_file" for kind, _ in keys)
