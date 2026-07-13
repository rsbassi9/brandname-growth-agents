from __future__ import annotations

import asyncio
import json
from pathlib import Path


def test_seo_audit_scores_required_checks_and_duplicates() -> None:
    from app.services.seo_audit import audit_products

    products = [
        {
            "title": "Short tee",
            "handle": "short-tee",
            "product_type": "T Shirt",
            "meta_description": "",
            "images": [{"alt": ""}],
        },
        {
            "title": "Short tee",
            "handle": "short-tee-two",
            "product_type": "T Shirt",
            "meta_description": "A concise product page for a quiet garment.",
            "images": [{"alt": "front product photo"}],
        },
    ]

    audits = audit_products(products)

    assert audits[0].score == 0
    assert "duplicate product title in catalog" in audits[0].issues
    assert "meta description is missing" in audits[0].issues
    assert "one or more product images are missing alt text" in audits[0].issues
    assert audits[1].product_handle == "short-tee-two"
    assert "duplicate product title in catalog" in audits[1].issues


def test_seo_audit_persists_and_lists_rows(client) -> None:
    from app.db import session_scope
    from app.services.seo_audit import SeoAuditResult, persist_audits

    with session_scope() as session:
        persist_audits(session, [SeoAuditResult(product_handle="canvas-tee", score=75, issues=["meta description should be 140-160 characters"])])

    response = client.get("/api/v1/seo/audits")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload[0]["product_handle"] == "canvas-tee"
    assert payload[0]["score"] == 75
    assert json.loads(payload[0]["issues_json"]) == ["meta description should be 140-160 characters"]


def test_seo_audit_endpoint_enqueues_read_only_job(client) -> None:
    from app.db import session_scope
    from app.models import Job

    response = client.post("/api/v1/seo/audit")

    assert response.status_code == 200, response.text
    with session_scope() as session:
        job = session.get(Job, response.json()["job_id"])
        assert job is not None
        assert job.kind == "seo_audit"


def test_generate_seo_fix_uses_memory_and_product_truth(app_env: Path) -> None:
    from app.db import init_db, session_scope
    from app.models import BrainDocument, BrainEmbedding, SeoAudit
    from app.services.brain import embed_texts, embedding_model_label, vector_to_blob
    from app.services.seo_fixes import generate_seo_fix

    init_db()
    memory = app_env / "memory"
    memory.mkdir(parents=True, exist_ok=True)
    (memory / "product_truth.json").write_text(
        json.dumps({"canvas-tee": "Canvas tee is a heavyweight cotton shirt with reconstructed source artwork."}),
        encoding="utf-8",
    )
    with session_scope() as session:
        audit = SeoAudit(
            product_handle="canvas-tee",
            score=35,
            issues_json=json.dumps(["title should be 50-60 characters", "meta description is missing"]),
        )
        session.add(audit)
        document = BrainDocument(
            kind="product",
            ref_id="canvas-tee",
            text="Canvas tee product truth: heavyweight cotton, source artwork, quiet reconstruction.",
            meta_json=json.dumps({"handle": "canvas-tee"}),
        )
        session.add(document)
        session.flush()
        vector = embed_texts([document.text])[0]
        session.add(
            BrainEmbedding(
                document_id=document.id,
                model=embedding_model_label(),
                dim=vector.size,
                vector=vector_to_blob(vector),
            )
        )
        audit_id = audit.id

    with session_scope() as session:
        generated = generate_seo_fix(session, audit_id)

    assert "BRAND MEMORY" in generated["prompt"]
    assert "Product truth excerpt:" in generated["prompt"]
    assert "heavyweight cotton shirt" in generated["prompt"]
    assert "Shopify writes remain disabled" in generated["content_text"]
    assert generated["params"]["memory_document_ids"]


def test_seo_fix_endpoint_enqueues_asset_job(client) -> None:
    from app.db import session_scope
    from app.models import Asset, Job, SeoAudit

    with session_scope() as session:
        audit = SeoAudit(product_handle="canvas-tee", score=40, issues_json=json.dumps(["meta description is missing"]))
        session.add(audit)
        session.flush()
        audit_id = audit.id

    response = client.post(f"/api/v1/seo/audits/{audit_id}/fix")

    assert response.status_code == 200, response.text
    payload = response.json()
    with session_scope() as session:
        asset = session.get(Asset, payload["asset_id"])
        job = session.get(Job, payload["job_id"])
        assert asset is not None
        assert asset.type == "seo_fix"
        assert asset.title == "SEO fix: canvas-tee"
        assert job is not None
        assert job.kind == "seo_fix"


def test_seo_fix_job_persists_version(app_env: Path) -> None:
    from app.db import init_db, session_scope
    from app.models import Asset, AssetVersion, SeoAudit
    from app.services.jobs import _handle_seo_fix

    init_db()
    memory = app_env / "memory"
    memory.mkdir(parents=True, exist_ok=True)
    (memory / "product_truth.json").write_text(
        json.dumps({"canvas-tee": "Canvas tee has source-grounded artwork and daily-wear cotton."}),
        encoding="utf-8",
    )
    with session_scope() as session:
        audit = SeoAudit(product_handle="canvas-tee", score=42, issues_json=json.dumps(["image alt text is missing"]))
        asset = Asset(type="seo_fix", title="SEO fix: canvas-tee", status="draft")
        session.add_all([audit, asset])
        session.flush()
        audit_id = audit.id
        asset_id = asset.id

    result = asyncio.run(_handle_seo_fix("missing-test-job", {"audit_id": audit_id, "asset_id": asset_id}))

    assert result == {"asset_id": asset_id, "version_no": 1}
    with session_scope() as session:
        version = session.query(AssetVersion).filter_by(asset_id=asset_id, version_no=1).one()
        assert version.content_text is not None
        assert "## New title" in version.content_text
        assert "Shopify writes remain disabled" in version.content_text
        params = json.loads(version.params_json)
        assert params["type"] == "seo_fix"
        assert params["seo_audit_id"] == audit_id
