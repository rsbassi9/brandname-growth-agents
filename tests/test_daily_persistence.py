"""The paid workflow must produce inspectable versions, not a success string."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import select


@pytest.fixture
def daily(app_env, monkeypatch):
    from app.db import init_db
    from app.services import jobs

    init_db()
    monkeypatch.setattr(jobs, "_enqueue_brain_index", lambda **kwargs: None)
    root = app_env / "outputs"
    root.mkdir()
    return jobs, root


def counts():
    from app.db import session_scope
    from app.models import Asset, AssetVersion

    with session_scope() as session:
        return len(session.scalars(select(Asset)).all()), len(session.scalars(select(AssetVersion)).all())


def test_live_daily_handler_persists_the_same_shape_as_local(daily, monkeypatch):
    from src import orchestrator

    jobs, root = daily
    report = root / "report.md"
    report.write_text("Synthetic paid-path draft; no provider call.")

    async def synthetic_workflow():
        return {"report": str(report)}

    monkeypatch.setattr(jobs, "get_settings", lambda: SimpleNamespace(local_only_agent_runs=False))
    monkeypatch.setattr(orchestrator, "run_daily_workflow", synthetic_workflow)
    result = asyncio.run(jobs._handle_run_daily_workflow("fixture-job", {"source": "test"}))
    assert result["mode"] == "live"
    assert result["paths"] == {"report": str(report)}
    assert len(result["assets"]) == len(result["calendar_items"]) == 1
    assert result["calendar_items"][0]["status"] == "draft"
    assert counts() == (1, 1)


def test_visual_groups_are_real_binary_artifacts_not_empty_copy(daily):
    from app.db import session_scope
    from app.models import Asset, AssetVersion

    jobs, root = daily
    first, second = root / "slide-01.png", root / "slide-02.png"
    for path, color in [(first, "red"), (second, "blue")]:
        Image.new("RGB", (4, 4), color).save(path)
    rows = jobs._persist_daily_output_assets({"visual_slides": f"{first}, {second}"}, "live", "test")
    assert len(rows) == 2
    with session_scope() as session:
        assert {row.type for row in session.scalars(select(Asset))} == {"carousel"}
        versions = session.scalars(select(AssetVersion).order_by(AssetVersion.id)).all()
        for version, source in zip(versions, (first, second), strict=True):
            assert Path(version.file_path).read_bytes() == source.read_bytes()
            assert version.content_text is None
            assert len(json.loads(version.params_json)["artifact_sha256"]) == 64


@pytest.mark.parametrize("invalid", [
    "missing", "empty", "blank", "outside", "symlink", "broken-image", "bad-text",
    "empty-result", "blank-path", "unsupported", "text-image-group",
])
def test_invalid_outputs_fail_before_any_database_write(daily, invalid):
    jobs, root = daily
    good = root / "good.md"
    good.write_text("Valid synthetic draft")
    bad = root / "bad.md"
    if invalid == "empty":
        bad.touch()
    elif invalid == "blank":
        bad.write_text(" \n")
    elif invalid == "outside":
        bad = root.parent / "private.txt"
        bad.write_text("Synthetic unrelated file")
    elif invalid == "broken-image":
        bad = root / "broken.png"
        bad.write_bytes(b"not an image")
    elif invalid == "bad-text":
        bad.write_bytes(b"\xff\xfe")
    elif invalid == "symlink":
        target = root.parent / "private.txt"
        target.write_text("Synthetic unrelated file")
        bad.symlink_to(target)
    elif invalid == "unsupported":
        bad = root / "wrong.bin"
        bad.write_bytes(b"unsupported")
    elif invalid == "text-image-group":
        bad.write_text("Not a rendered image")
    paths = {} if invalid == "empty-result" else {"report": str(good), "drafts": str(bad)}
    if invalid == "blank-path":
        paths["drafts"] = ""
    elif invalid == "text-image-group":
        paths = {"visual_slides": str(bad)}
    with pytest.raises((ValueError, OSError)):
        jobs._persist_daily_output_assets(paths, "live", "test")
    assert counts() == (0, 0)


def test_changed_output_preserves_old_take_and_invalidates_selection(daily):
    from app.db import session_scope
    from app.models import Asset, AssetVersion, CalendarItem

    jobs, root = daily
    path = root / "draft.md"
    path.write_text("First caption")
    first = jobs._persist_daily_output_assets({"drafts": str(path)}, "live", "test")
    calendar = jobs._persist_daily_calendar_items(first, "job-one")
    with session_scope() as session:
        session.get(Asset, first[0]["asset_id"]).status = "selected"
        session.get(CalendarItem, calendar[0]["id"]).status = "approved"
    # An identical retry is not a new take and must preserve the review state.
    identical = jobs._persist_daily_output_assets({"drafts": str(path)}, "live", "test")
    assert jobs._persist_daily_calendar_items(identical, "retry")[0]["status"] == "approved"
    assert counts() == (1, 1)
    path.write_text("Second caption")
    changed = jobs._persist_daily_output_assets({"drafts": str(path)}, "live", "test")
    assert jobs._persist_daily_calendar_items(changed, "job-two")[0]["status"] == "draft"
    assert counts() == (1, 2)
    with session_scope() as session:
        assert session.get(Asset, first[0]["asset_id"]).status == "draft"
        versions = session.scalars(select(AssetVersion).order_by(AssetVersion.version_no)).all()
        assert [v.content_text for v in versions] == ["First caption", "Second caption"]
        assert [Path(v.file_path).read_text() for v in versions] == ["First caption", "Second caption"]
        assert not any(v.is_selected for v in versions)
        assert changed[0]["version_id"] == versions[-1].id


def test_new_daily_path_rebinds_calendar_to_current_draft(daily):
    from app.db import session_scope
    from app.models import CalendarItem

    jobs, root = daily
    first, second = root / "cycle-one.md", root / "cycle-two.md"
    first.write_text("First cycle")
    second.write_text("Second cycle")
    one = jobs._persist_daily_output_assets({"drafts": str(first)}, "local_only", "test")
    initial = jobs._persist_daily_calendar_items(one, "job-one")
    two = jobs._persist_daily_output_assets({"drafts": str(second)}, "local_only", "test")
    updated = jobs._persist_daily_calendar_items(two, "job-two")
    assert initial[0]["id"] == updated[0]["id"]
    assert updated[0]["asset_id"] == two[0]["asset_id"] != one[0]["asset_id"]
    with session_scope() as session:
        data = json.loads(session.get(CalendarItem, updated[0]["id"]).data_json)
        assert data["asset_version_id"] == two[0]["version_id"]
        assert data["workflow_job_id"] == "job-two"


@pytest.mark.parametrize("linked_post", [False, True])
def test_published_calendar_history_is_never_rewritten(daily, linked_post):
    from app.db import session_scope
    from app.models import CalendarItem, PublishedPost

    jobs, root = daily
    path = root / "published.md"
    path.write_text("Original published fixture")
    first = jobs._persist_daily_output_assets({"drafts": str(path)}, "live", "test")
    old = jobs._persist_daily_calendar_items(first, "job-one")[0]
    with session_scope() as session:
        row = session.get(CalendarItem, old["id"])
        if linked_post:
            session.add(PublishedPost(calendar_item_id=row.id, channel="instagram"))
        else:
            row.status = "published"
        old_data = row.data_json
    path.write_text("A new draft, not a revision of publication history")
    second = jobs._persist_daily_output_assets({"drafts": str(path)}, "live", "test")
    new = jobs._persist_daily_calendar_items(second, "job-two")[0]
    assert new["id"] != old["id"]
    assert new["status"] == "draft"
    assert jobs._persist_daily_calendar_items(second, "retry")[0]["id"] == new["id"]
    with session_scope() as session:
        assert session.get(CalendarItem, old["id"]).data_json == old_data


def test_snapshot_write_failure_rolls_back_database(daily, monkeypatch):
    jobs, root = daily
    path = root / "draft.md"
    path.write_text("Synthetic draft")

    def fail_replace(*args):
        raise OSError("Synthetic full disk")

    monkeypatch.setattr("app.services.daily_outputs.os.replace", fail_replace)
    with pytest.raises(OSError):
        jobs._persist_daily_output_assets({"drafts": str(path)}, "live", "test")
    assert counts() == (0, 0)
    assert not list((root / "daily_snapshots").iterdir())


def test_feed_advertises_only_servable_images(client, daily):
    jobs, root = daily
    text = root / "report.md"
    picture = root / "product.png"
    text.write_text("Synthetic text report")
    Image.new("RGB", (4, 4), "blue").save(picture)
    assets = jobs._persist_daily_output_assets({"report": str(text), "visual_slides": str(picture)}, "live", "test")
    calendar = jobs._persist_daily_calendar_items(assets, "fixture")
    feed = {row["id"]: row for row in client.get("/api/v1/feed").json()}
    assert feed[calendar[0]["id"]]["data"]["media_url"] is None
    url = feed[calendar[1]["id"]]["data"]["media_url"]
    assert url == f"/api/v1/assets/{assets[1]['asset_id']}/media"
    assert client.get(url).content == picture.read_bytes()
    Path(assets[1]["file_path"]).unlink()
    feed = {row["id"]: row for row in client.get("/api/v1/feed").json()}
    assert feed[calendar[1]["id"]]["data"]["media_url"] is None
