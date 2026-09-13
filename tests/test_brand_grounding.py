from unittest.mock import Mock

import pytest

from app.services.source_policy import is_production_image


def asset(**overrides):
    return {"id": "synthetic-owned-photo", "name": "front.jpg", "mimeType": "image/jpeg",
            "folderPath": "root/Products/Test", "creativeBucket": "Store Products", **overrides}


@pytest.mark.parametrize("changes", [
    {"creativeBucket": "First Post Inspiration"}, {"creativeBucket": "Other"},
    {"name": "ASRV-shot.jpg"}, {"folderPath": "root/competitor"},
    {"folderPath": "root/moodboard"}, {"mimeType": "video/mp4"},
])
def test_reference_and_unknown_assets_are_not_production_inputs(changes):
    assert not is_production_image(asset(**changes))


def test_owned_product_image_is_eligible():
    assert is_production_image(asset())


def test_drive_index_excludes_research_before_applying_limit(app_env, monkeypatch):
    from app.db import init_db, session_scope
    from app.services.source_assets import index_drive_sources

    init_db()
    monkeypatch.setattr("app.services.drive.GoogleDriveService.list_raw_assets", Mock(return_value=[
        asset(id="synthetic-competitor-photo", name="ASRV-reference.jpg"), asset(),
    ]))
    with session_scope() as session:
        rows = index_drive_sources(session, limit=1)
        assert len(rows) == 1
        assert rows[0].path == "drive://synthetic-owned-photo"


@pytest.mark.parametrize("module_name", ["app.services.drive", "src.drive_service"])
def test_both_downloaders_exclude_research_before_requesting_bytes(app_env, monkeypatch, module_name):
    import importlib

    module = importlib.import_module(module_name)
    service = module.GoogleDriveService()
    service.enabled = True
    monkeypatch.setattr(service, "_missing_auth_message", lambda: "")
    api = Mock()
    monkeypatch.setattr(service, "_build_service", lambda: api)
    monkeypatch.setattr(service, "list_raw_assets", lambda: [asset(name="ASRV-reference.jpg"), asset()])
    downloader = Mock()
    downloader.next_chunk.return_value = (None, True)
    monkeypatch.setattr(service, "_media_downloader", lambda handle, request: downloader)
    paths = service.download_image_assets(app_env / "downloads", 1)
    assert len(paths) == 1
    api.files().get_media.assert_called_once_with(fileId="synthetic-owned-photo")


def test_prompt_loads_identity_even_without_learned_memory(app_env, monkeypatch):
    import app.services.brand_foundation as foundation
    from app.services.generation import build_prompt

    context = app_env / "context"
    context.mkdir()
    (context / "brand_brief.md").write_text("Synthetic brand: paintings become garments.")
    (context / "visual_system.md").write_text("Synthetic approved visual rule: sparse typography.")
    monkeypatch.setattr(foundation, "brand_context_dir", lambda: context)
    prompt = build_prompt("copy", "Make a post today", {})
    assert "paintings become garments" in prompt
    assert "sparse typography" in prompt
    assert "brand_brief.md sha256=" in prompt
    assert "not a product to advertise" in prompt
    assert "explicit approval" in prompt


def test_missing_identity_cannot_silently_become_generic_copy(app_env, monkeypatch):
    import app.services.brand_foundation as foundation

    monkeypatch.setattr(foundation, "brand_context_dir", lambda: app_env)
    with pytest.raises(FileNotFoundError):
        foundation.brand_foundation()
