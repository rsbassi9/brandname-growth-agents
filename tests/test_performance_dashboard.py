from __future__ import annotations

from datetime import datetime


def test_performance_dashboard_summarizes_top_trend_and_asset_types(client) -> None:
    from app.db import session_scope
    from app.models import Asset, PostMetric, PublishedPost

    with session_scope() as session:
        copy_asset = Asset(type="copy", title="Caption", status="draft")
        video_asset = Asset(type="video_script", title="Reel", status="draft")
        session.add_all([copy_asset, video_asset])
        session.flush()
        rows = [
            ("instagram", "Source proof", copy_asset.id, datetime(2026, 7, 1, 10), 100, 30),
            ("instagram", "Quiet proof", copy_asset.id, datetime(2026, 7, 2, 10), 100, 20),
            ("tiktok", "Reel proof", video_asset.id, datetime(2026, 7, 8, 12), 200, 80),
        ]
        for channel, title, asset_id, published_at, reach, likes in rows:
            post = PublishedPost(channel=channel, title_or_caption=title, asset_id=asset_id, published_at=published_at)
            session.add(post)
            session.flush()
            session.add(PostMetric(published_post_id=post.id, captured_at=datetime(2026, 7, 9), reach=reach, likes=likes))

    response = client.get("/api/v1/performance/dashboard")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [post["title_or_caption"] for post in payload["top_posts"]] == ["Reel proof", "Source proof", "Quiet proof"]
    assert payload["weekly_trend"] == [
        {"week": "2026-W27", "mean_engagement_rate": 0.25, "sample_size": 2},
        {"week": "2026-W28", "mean_engagement_rate": 0.4, "sample_size": 1},
    ]
    assert payload["by_asset_type"] == [
        {"asset_type": "video_script", "mean_engagement_rate": 0.4, "sample_size": 1},
        {"asset_type": "copy", "mean_engagement_rate": 0.25, "sample_size": 2},
    ]
