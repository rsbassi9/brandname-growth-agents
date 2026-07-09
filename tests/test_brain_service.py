from __future__ import annotations

import numpy as np


def test_hashing_vectorizer_is_deterministic_and_normalized(app_env) -> None:
    from app.services.brain import LOCAL_EMBED_DIM, embed_texts

    first, second, different = embed_texts(["canvas fragment tee", "canvas fragment tee", "email launch copy"])

    assert first.shape == (LOCAL_EMBED_DIM,)
    assert np.array_equal(first, second)
    assert not np.array_equal(first, different)
    assert np.isclose(np.linalg.norm(first), 1.0)


def test_embedding_blob_round_trip(app_env) -> None:
    from app.services.brain import blob_to_vector, embed_texts, vector_to_blob

    vector = embed_texts(["oxide red source image"])[0]
    restored = blob_to_vector(vector_to_blob(vector), vector.size)

    assert restored.dtype == np.dtype("<f4")
    assert np.array_equal(vector, restored)


def test_search_ranks_matching_documents(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import BrainDocument, BrainEmbedding
    from app.services.brain import embedding_model_label, embed_texts, search, vector_to_blob

    init_db()
    docs = [
        ("asset_version", "asset:1", "canvas fragment tee launch caption"),
        ("feedback", "fb_1", "email subject line and newsletter proof"),
        ("context_file", "brand.md", "canvas fragment source painting visual codes"),
    ]
    with session_scope() as session:
        for kind, ref_id, text in docs:
            document = BrainDocument(kind=kind, ref_id=ref_id, text=text, meta_json="{}")
            session.add(document)
            session.flush()
            vector = embed_texts([text])[0]
            session.add(
                BrainEmbedding(
                    document_id=document.id,
                    model=embedding_model_label(),
                    dim=vector.size,
                    vector=vector_to_blob(vector),
                )
            )

    results = search("canvas tee fragment", k=2)

    assert [item.document.ref_id for item in results] == ["asset:1", "brand.md"]
    assert results[0].score >= results[1].score


def test_search_filters_by_kind(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import BrainDocument, BrainEmbedding
    from app.services.brain import embedding_model_label, embed_texts, search, vector_to_blob

    init_db()
    with session_scope() as session:
        for kind, ref_id in [("asset_version", "asset:1"), ("feedback", "fb_1")]:
            document = BrainDocument(kind=kind, ref_id=ref_id, text="canvas fragment", meta_json="{}")
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

    results = search("canvas", kinds=["feedback"])

    assert [item.document.kind for item in results] == ["feedback"]


def test_memory_context_boosts_selected_winners(app_env) -> None:
    import json

    from app.db import init_db, session_scope
    from app.models import BrainDocument, BrainEmbedding
    from app.services.brain import build_memory_context, embedding_model_label, embed_texts, vector_to_blob

    init_db()
    vector = embed_texts(["canvas fragment"])[0]
    with session_scope() as session:
        unselected = BrainDocument(
            kind="asset_version",
            ref_id="asset:1",
            text="canvas fragment but unselected",
            meta_json=json.dumps({"is_selected": False}),
        )
        selected = BrainDocument(
            kind="asset_version",
            ref_id="asset:2",
            text="canvas fragment selected winner",
            meta_json=json.dumps({"is_selected": True}),
        )
        session.add_all([unselected, selected])
        session.flush()
        for document in [unselected, selected]:
            session.add(
                BrainEmbedding(
                    document_id=document.id,
                    model=embedding_model_label(),
                    dim=vector.size,
                    vector=vector_to_blob(vector),
                )
            )

    memory = build_memory_context("canvas fragment", k=2)

    assert memory.document_ids == [2, 1]
    assert "doc#2" in memory.block.splitlines()[2]


def test_local_only_embeddings_make_zero_network_calls(app_env, monkeypatch) -> None:
    from app.services import brain

    def fail_client():
        raise AssertionError("network client should not be constructed in local-only mode")

    monkeypatch.setattr(brain, "get_openai_client", fail_client)

    assert brain.embed_texts(["local only"])[0].shape == (brain.LOCAL_EMBED_DIM,)
