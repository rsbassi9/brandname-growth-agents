from __future__ import annotations

import json
from pathlib import Path


def _seed_legacy_data(root: Path) -> None:
    memory = root / "memory"
    memory.mkdir(parents=True, exist_ok=True)
    (memory / "content_calendar.json").write_text(
        json.dumps(
            [
                {"id": "post-1", "date": "2026-05-14", "status": "approved", "hook": "A"},
                {"id": "post-2", "date": "2026-05-15", "status": "draft", "hook": "B"},
            ]
        ),
        encoding="utf-8",
    )
    (memory / "feedback.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "fb-1",
                        "created_at": "2026-05-14T10:00:00",
                        "output_path": "outputs/content_drafts/a.md",
                        "rating": 4,
                        "comment": "good",
                        "improvement_request": "shorter",
                        "category": "copy",
                    }
                ),
                json.dumps({"rating": 2, "comment": "meh"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    outputs = root / "outputs"
    (outputs / "content_drafts").mkdir(parents=True, exist_ok=True)
    (outputs / "content_drafts" / "2026-05-14-content-drafts.md").write_text("# drafts", encoding="utf-8")
    (outputs / "visual_content" / "2026-05-14-demo").mkdir(parents=True, exist_ok=True)
    (outputs / "visual_content" / "2026-05-14-demo" / "slide-01.png").write_bytes(b"\x89PNG-fake")
    (outputs / "image_concepts" / "2026-05-14-demo").mkdir(parents=True, exist_ok=True)
    (outputs / "image_concepts" / "2026-05-14-demo" / "concept-01.png").write_bytes(b"\x89PNG-fake")
    (outputs / "content_plan").mkdir(parents=True, exist_ok=True)
    (outputs / "content_plan" / "2026-05-15-plan.json").write_text("{}", encoding="utf-8")


def test_migration_imports_all_sources(app_env: Path) -> None:
    from app.services.migrate_legacy import run_migration

    _seed_legacy_data(app_env)
    counts = run_migration()
    assert counts["calendar_items_new"] == 2
    assert counts["feedback_events_new"] == 2
    assert counts["assets_new"] == 4
    assert counts["asset_versions_total"] == 4


def test_migration_is_idempotent(app_env: Path) -> None:
    from app.services.migrate_legacy import run_migration

    _seed_legacy_data(app_env)
    first = run_migration()
    second = run_migration()
    assert second["calendar_items_new"] == 0
    assert second["feedback_events_new"] == 0
    assert second["assets_new"] == 0
    for key in ("calendar_items_total", "feedback_events_total", "assets_total", "asset_versions_total"):
        assert first[key] == second[key]


def test_migration_type_inference() -> None:
    from app.services.migrate_legacy import infer_asset_type

    assert infer_asset_type(Path("visual_content/demo/slide-01.png")) == "carousel"
    assert infer_asset_type(Path("image_concepts/demo/render.png")) == "image_concept"
    assert infer_asset_type(Path("content_drafts/drafts.md")) == "copy"
    assert infer_asset_type(Path("content_plan/plan.json")) == "copy"
    assert infer_asset_type(Path("misc/clip.mov")) == "video_script"


def test_migrated_version_marked_selected_and_text_captured(app_env: Path) -> None:
    from app.db import session_scope
    from app.models import Asset, AssetVersion
    from app.services.migrate_legacy import run_migration

    _seed_legacy_data(app_env)
    run_migration()
    with session_scope() as session:
        asset = (
            session.query(Asset)
            .filter(Asset.source_path == "outputs/content_drafts/2026-05-14-content-drafts.md")
            .one()
        )
        version = session.query(AssetVersion).filter(AssetVersion.asset_id == asset.id).one()
        assert version.is_selected is True
        assert version.version_no == 1
        assert version.content_text == "# drafts"
        assert version.model_used == "legacy-import"
