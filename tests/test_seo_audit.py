from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest


def valid_product(**overrides):
    product = {
        "title": "Gallery Streetwear Tee With Source Artwork And Heavy Cotton",
        "handle": "canvas-tee",
        "product_type": "T Shirt",
        "meta_description": "Gallery streetwear tee made from T Shirt source artwork, with heavy cotton construction and quiet reconstruction details for daily streetwear layering now.",
        "images": [{"alt": "canvas tee front product image"}],
    }
    product.update(overrides)
    return product


@pytest.mark.parametrize(
    ("product", "expected_score", "expected_issue"),
    [
        (valid_product(), 100, None),
        (valid_product(title="Short tee"), 75, "title length should be 50-60 characters"),
        (valid_product(meta_description=""), 75, "meta description is missing"),
        (
            valid_product(meta_description="Too short but still mentions T Shirt."),
            75,
            "meta description should be 140-160 characters",
        ),
        (valid_product(images=[{"alt": ""}]), 75, "one or more product images are missing alt text"),
        (
            valid_product(
                title="Canvas Product With Source Artwork And Heavy Cotton Garment",
                meta_description="A quiet product page with enough length for the checked rule while preserving copy clarity and source-led product details for daily streetwear today.",
            ),
            85,
            "target keyword 'gallery streetwear tee' is missing from title/description",
        ),
    ],
)
def test_seo_audit_rule_weights(product, expected_score, expected_issue) -> None:
    from app.services.seo_audit import audit_product

    result = audit_product(product, keyword_map={"canvas-tee": "gallery streetwear tee"})

    assert result.score == expected_score
    if expected_issue is None:
        assert result.issues == []
    else:
        assert expected_issue in result.issues


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


def test_seo_audit_uses_keyword_map_when_available() -> None:
    from app.services.seo_audit import audit_product

    product = {
        "title": "Canvas Tee With Quiet Reconstructed Source Artwork",
        "handle": "canvas-tee",
        "product_type": "T Shirt",
        "meta_description": "Canvas tee with quiet source artwork, heavyweight cotton, and daily-wear product proof.",
        "images": [{"alt": "canvas tee front"}],
    }

    result = audit_product(product, keyword_map={"canvas-tee": "gallery streetwear tee"})

    assert "target keyword 'gallery streetwear tee' is missing from title/description" in result.issues


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


def test_generate_seo_plan_builds_keyword_map_and_blog_links(app_env: Path) -> None:
    from app.db import init_db, session_scope
    from app.services.seo_plan import generate_seo_plan

    init_db()
    products = [
        {
            "title": "Canvas Tee",
            "handle": "canvas-tee",
            "product_type": "T Shirt",
            "tags": "canvas, reconstruction",
        },
        {
            "title": "Archive Hoodie",
            "handle": "archive-hoodie",
            "product_type": "Hoodie",
            "tags": "archive, heavyweight",
        },
    ]

    with session_scope() as session:
        generated = generate_seo_plan(session, products=products)

    payload = json.loads(generated["content_text"])
    product_rows = [row for row in payload["keyword_map"] if row["scope"] == "product"]
    assert payload["kind"] == "seo_plan"
    assert product_rows[0]["handle"] == "canvas-tee"
    assert product_rows[0]["primary_keyword"] == "t shirt streetwear"
    assert product_rows[0]["url"].endswith("/products/canvas-tee")
    assert payload["blog_plan"][0]["internal_links"][0]["url"].endswith("/products/canvas-tee")
    assert "Shopify writes remain disabled" in payload["manual_use"]
    assert generated["params"]["product_count"] == 2


def test_generate_seo_plan_records_memory_grounding(app_env: Path) -> None:
    from app.db import init_db, session_scope
    from app.models import BrainDocument, BrainEmbedding
    from app.services.brain import embed_texts, embedding_model_label, vector_to_blob
    from app.services.seo_plan import generate_seo_plan

    init_db()
    products = [valid_product()]
    with session_scope() as session:
        document = BrainDocument(
            kind="context_file",
            ref_id="seo-context.md",
            text="SEO memory: gallery source artwork and product truth should guide keywords.",
            meta_json=json.dumps({"path": "brand_context/seo-context.md"}),
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

    with session_scope() as session:
        generated = generate_seo_plan(session, products=products)

    assert "BRAND MEMORY" in generated["prompt"]
    assert generated["params"]["memory_document_ids"]


def test_seo_plan_endpoint_enqueues_asset_job(client) -> None:
    from app.db import session_scope
    from app.models import Asset, Job

    response = client.post("/api/v1/seo/plan")

    assert response.status_code == 200, response.text
    payload = response.json()
    with session_scope() as session:
        asset = session.get(Asset, payload["asset_id"])
        job = session.get(Job, payload["job_id"])
        assert asset is not None
        assert asset.type == "seo_plan"
        assert asset.title == "SEO keyword and content plan"
        assert job is not None
        assert job.kind == "seo_plan"


def test_seo_plan_job_persists_version_and_keyword_map(app_env: Path) -> None:
    from app.db import init_db, session_scope
    from app.models import Asset, AssetVersion
    from app.services.jobs import _handle_seo_plan
    from app.services.seo_plan import latest_keyword_map

    init_db()
    with session_scope() as session:
        asset = Asset(type="seo_plan", title="SEO keyword and content plan", status="draft")
        session.add(asset)
        session.flush()
        asset_id = asset.id

    result = asyncio.run(_handle_seo_plan("missing-test-job", {"asset_id": asset_id}))

    assert result == {"asset_id": asset_id, "version_no": 1}
    with session_scope() as session:
        version = session.query(AssetVersion).filter_by(asset_id=asset_id, version_no=1).one()
        params = json.loads(version.params_json)
        content = json.loads(version.content_text)
        assert params["type"] == "seo_plan"
        assert content["kind"] == "seo_plan"
        assert content["blog_plan"]
        assert latest_keyword_map(session) == {}


def test_latest_keyword_map_reads_selected_seo_plan(app_env: Path) -> None:
    from app.db import init_db, session_scope
    from app.models import Asset, AssetVersion
    from app.services.seo_plan import latest_keyword_map

    init_db()
    content = {
        "kind": "seo_plan",
        "keyword_map": [
            {
                "scope": "product",
                "handle": "canvas-tee",
                "primary_keyword": "gallery streetwear tee",
                "secondary_keywords": [],
            }
        ],
    }
    with session_scope() as session:
        asset = Asset(type="seo_plan", title="SEO keyword and content plan", status="draft")
        session.add(asset)
        session.flush()
        session.add(
            AssetVersion(
                asset_id=asset.id,
                version_no=1,
                prompt_snapshot="seo plan",
                params_json="{}",
                content_text=json.dumps(content),
                model_used="test",
                is_selected=True,
            )
        )

    with session_scope() as session:
        assert latest_keyword_map(session) == {"canvas-tee": "gallery streetwear tee"}


def test_seo_asset_types_are_registered_additively() -> None:
    from app.models import ASSET_TYPES
    from app.schemas import AssetType

    assert "seo_fix" in ASSET_TYPES
    assert "seo_plan" in ASSET_TYPES
    assert "copy" in ASSET_TYPES
    assert "seo_fix" in AssetType.__args__
    assert "seo_plan" in AssetType.__args__
