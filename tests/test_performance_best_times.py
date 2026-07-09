from __future__ import annotations

from datetime import datetime


def test_best_times_threshold_ranking_and_latest_metric(client) -> None:
    from app.db import session_scope
    from app.models import PostMetric, PublishedPost

    with session_scope() as session:
        for index, rate_seed in enumerate([20, 24, 28], start=1):
            post = PublishedPost(
                channel="instagram",
                external_ref=f"ig-good-{index}",
                published_at=datetime(2026, 7, 6, 10, index),
            )
            session.add(post)
            session.flush()
            session.add(
                PostMetric(
                    published_post_id=post.id,
                    captured_at=datetime(2026, 7, 7, 9, 0),
                    reach=100,
                    likes=1,
                )
            )
            session.add(
                PostMetric(
                    published_post_id=post.id,
                    captured_at=datetime(2026, 7, 8, 9, 0),
                    reach=100,
                    likes=rate_seed,
                )
            )
        for index in range(2):
            post = PublishedPost(
                channel="instagram",
                external_ref=f"ig-small-{index}",
                published_at=datetime(2026, 7, 6, 12, index),
            )
            session.add(post)
            session.flush()
            session.add(PostMetric(published_post_id=post.id, captured_at=datetime(2026, 7, 8), reach=100, likes=90))
        for index in range(3):
            post = PublishedPost(
                channel="tiktok",
                external_ref=f"tt-{index}",
                published_at=datetime(2026, 7, 7, 10, index),
            )
            session.add(post)
            session.flush()
            session.add(PostMetric(published_post_id=post.id, captured_at=datetime(2026, 7, 8), reach=100, likes=10))

    response = client.get("/api/v1/performance/best-times?channel=instagram")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload == [
        {
            "channel": "instagram",
            "weekday": 0,
            "hour": 10,
            "sample_size": 3,
            "mean_engagement_rate": 0.24,
        }
    ]


def test_best_times_all_channels_are_deterministic(client) -> None:
    from app.db import session_scope
    from app.models import PostMetric, PublishedPost

    with session_scope() as session:
        for channel, hour, likes in [("instagram", 9, 30), ("tiktok", 11, 20)]:
            for index in range(3):
                post = PublishedPost(
                    channel=channel,
                    external_ref=f"{channel}-{index}",
                    published_at=datetime(2026, 7, 6, hour, index),
                )
                session.add(post)
                session.flush()
                session.add(PostMetric(published_post_id=post.id, captured_at=datetime(2026, 7, 8), reach=100, likes=likes))

    first = client.get("/api/v1/performance/best-times").json()
    second = client.get("/api/v1/performance/best-times").json()

    assert first == second
    assert [slot["channel"] for slot in first] == ["instagram", "tiktok"]
