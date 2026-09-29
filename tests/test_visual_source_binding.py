from pathlib import Path

import pytest


def test_selects_named_product_not_first_in_list(tmp_path):
    from src.visual_renderer import select_asset

    first, requested = tmp_path / "coat.png", tmp_path / "shirt.png"
    first.touch()
    requested.touch()
    assert select_asset("shirt.png", [first, requested]) == requested


@pytest.mark.parametrize("hint", ["", "../shirt.png", "/shirt.png", "ASRV.png", "reference.png", "missing.png"])
def test_invalid_or_research_selection_fails(tmp_path, hint):
    from src.visual_renderer import select_asset

    with pytest.raises(ValueError):
        select_asset(hint, [])


def test_ambiguous_filename_fails(tmp_path):
    from src.visual_renderer import select_asset

    source = tmp_path / "shirt.png"
    source.touch()
    with pytest.raises(ValueError, match="ambiguous"):
        select_asset(source.name, [source, source])


def test_invalid_slide_fails_before_creating_output(app_env, monkeypatch):
    from src import visual_renderer as renderer

    output = app_env / "isolated-render-output"
    monkeypatch.setattr(renderer, "OUTPUTS_DIR", output)
    with pytest.raises(ValueError):
        renderer.render_carousel({"slides": [{"asset_hint": "missing.png"}]}, [])
    assert not output.exists()


def test_renderer_preserves_named_source_and_forces_draft(app_env, monkeypatch):
    import json

    from PIL import Image

    from src import visual_renderer as renderer

    source = app_env / "owned-shirt.png"
    Image.new("RGB", (8, 8), "red").save(source)
    output = app_env / "isolated-render-output"
    monkeypatch.setattr(renderer, "OUTPUTS_DIR", output)
    seen = []
    original = renderer._load_asset
    monkeypatch.setattr(renderer, "_load_asset", lambda path: (seen.append(path), original(path))[1])
    paths = renderer.render_carousel({"approval_status": "Approved", "slides": [
        {"asset_hint": source.name, "headline": "Fixture"},
    ]}, [source])
    assert seen == [source]
    assert Path(paths[0]).is_file()
    assert json.loads((paths[0].parent / "design-brief.json").read_text())["approval_status"] == "Draft"


def test_live_daily_context_reads_same_brand_memory(app_env, monkeypatch):
    from types import SimpleNamespace

    from src import orchestrator

    monkeypatch.setattr(orchestrator, "build_memory_context", lambda *a, **k: SimpleNamespace(block="OWNER FEEDBACK FIXTURE"))
    monkeypatch.setattr(orchestrator, "brand_foundation", lambda: "REQUIRED IDENTITY FIXTURE")
    monkeypatch.setattr(orchestrator.GoogleDriveService, "list_raw_assets", lambda self: [])
    monkeypatch.setattr(orchestrator, "fetch_website_summary", lambda *a: "")
    monkeypatch.setattr(orchestrator, "product_catalog_summary", lambda *a: "")
    context = orchestrator.build_shared_context("synthetic asset inventory")
    assert "OWNER FEEDBACK FIXTURE" in context
    assert "REQUIRED IDENTITY FIXTURE" in context


def test_all_concept_sources_validated_before_any_paid_call(app_env, monkeypatch):
    from src import image_concepts

    source = app_env / "owned.png"
    source.touch()
    monkeypatch.setattr(image_concepts, "AI_IMAGE_GENERATION_ENABLED", True)
    monkeypatch.setattr(image_concepts, "OUTPUTS_DIR", app_env / "concept-test")
    monkeypatch.setattr(image_concepts, "IMAGE_CONCEPT_COUNT", 3)
    calls = []
    monkeypatch.setattr(image_concepts, "_generate_image", lambda *a: calls.append(a))
    with pytest.raises(ValueError):
        image_concepts.generate_image_concepts({"image_concepts": [
            {"source_asset_hint": source.name}, {"source_asset_hint": "ASRV.png"},
        ]}, [source])
    assert not calls
