from __future__ import annotations

import json

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError


def test_brain_tables_created(app_env) -> None:
    from app.db import get_engine, init_db

    init_db()
    tables = set(inspect(get_engine()).get_table_names())

    assert {"brain_documents", "brain_embeddings", "brand_profile_versions"}.issubset(tables)


def test_brain_document_kind_ref_unique_when_ref_present(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import BrainDocument

    init_db()
    with pytest.raises(IntegrityError):
        with session_scope() as session:
            session.add_all(
                [
                    BrainDocument(kind="asset_version", ref_id="42:1", text="Selected caption", meta_json="{}"),
                    BrainDocument(kind="asset_version", ref_id="42:1", text="Duplicate caption", meta_json="{}"),
                ]
            )


def test_brain_document_nullable_ref_allows_append_only_metric_notes(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import BrainDocument

    init_db()
    with session_scope() as session:
        session.add_all(
            [
                BrainDocument(kind="metric_insight", ref_id=None, text="Top quartile post", meta_json="{}"),
                BrainDocument(kind="metric_insight", ref_id=None, text="Another insight", meta_json="{}"),
            ]
        )

    with session_scope() as session:
        docs = session.query(BrainDocument).order_by(BrainDocument.id).all()
        assert [doc.text for doc in docs] == ["Top quartile post", "Another insight"]


def test_brain_embedding_is_one_per_document(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import BrainDocument, BrainEmbedding

    init_db()
    with pytest.raises(IntegrityError):
        with session_scope() as session:
            document = BrainDocument(kind="feedback", ref_id="fb_1", text="More proof in the hook.", meta_json="{}")
            session.add(document)
            session.flush()
            session.add_all(
                [
                    BrainEmbedding(document_id=document.id, model="local-hash", dim=2, vector=b"\x00\x00"),
                    BrainEmbedding(document_id=document.id, model="local-hash", dim=2, vector=b"\x01\x01"),
                ]
            )


def test_brand_profile_versions_are_unique_immutable_snapshots(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import BrandProfileVersion

    init_db()
    with session_scope() as session:
        session.add(
            BrandProfileVersion(
                version_no=1,
                profile_md="## Voice rules\n- Cite evidence. (fb_1)",
                distilled_from_json=json.dumps({"evidence_ids": ["fb_1"]}),
            )
        )

    with pytest.raises(IntegrityError):
        with session_scope() as session:
            session.add(
                BrandProfileVersion(
                    version_no=1,
                    profile_md="## Voice rules\n- Duplicate version. (fb_2)",
                    distilled_from_json=json.dumps({"evidence_ids": ["fb_2"]}),
                )
            )

    with session_scope() as session:
        profile = session.query(BrandProfileVersion).one()
        assert profile.version_no == 1
        assert json.loads(profile.distilled_from_json)["evidence_ids"] == ["fb_1"]
