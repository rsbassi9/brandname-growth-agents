from __future__ import annotations

import asyncio
import json
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures" / "perf_import"


def test_p11_gate_local_only_repurpose_metrics_brain_and_standup(client, app_env) -> None:
    from app.db import session_scope
    from app.models import BrainDocument, CalendarItem, SourceAsset, StandupReport
    from app.services.brain import run_backfill
    from app.services.jobs import _handle_repurpose_shoot, _handle_weekly_standup

    context_dir = app_env / "brand_context"
    context_dir.mkdir(parents=True, exist_ok=True)
    (context_dir / "p11_gate.md").write_text("Source proof and product truth should lead the weekly plan.", encoding="utf-8")

    backfill = run_backfill()
    assert backfill["documents"] >= 1
    assert backfill["context_files"] >= 1

    csv_text = (FIXTURES / "p8_gate_instagram_ranked.csv").read_text(encoding="utf-8")
    imported = client.post("/api/v1/performance/import", json={"channel": "instagram", "csv_text": csv_text})
    assert imported.status_code == 200, imported.text

    with session_scope() as session:
        source = SourceAsset(
            origin="local",
            path="shoot/p11-gate.jpg",
            tags_json=json.dumps(["gate", "source-proof"]),
            product_handle="canvas-tee",
        )
        session.add(source)
        session.add(
            CalendarItem(
                id="p11-next-week",
                date="2026-07-13",
                status="draft",
                data_json=json.dumps({"title": "Next week source proof anchor"}),
            )
        )
        session.flush()
        source_id = source.id

    repurpose = asyncio.run(
        _handle_repurpose_shoot("missing-test-job", {"source_asset_ids": [source_id], "campaign_name": "P11 gate shoot"})
    )
    assert all(step["status"] == "succeeded" for step in repurpose["steps"])

    standup = asyncio.run(_handle_weekly_standup("missing-test-job", {"week_start": "2026-07-06"}))
    assert standup["recommendations"] == 3

    visible = client.get("/api/v1/strategy/standup")
    assert visible.status_code == 200, visible.text
    assert visible.json()[0]["id"] == standup["standup_report_id"]
    assert "Proof-first atelier reel" in visible.json()[0]["report_md"]
    assert "Next week source proof anchor" in visible.json()[0]["report_md"]

    with session_scope() as session:
        assert session.query(BrainDocument).filter_by(kind="context_file").count() >= 1
        assert session.get(StandupReport, standup["standup_report_id"]) is not None
