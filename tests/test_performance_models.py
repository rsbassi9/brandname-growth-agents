from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError


def test_performance_tables_created(app_env) -> None:
    from app.db import get_engine, init_db

    init_db()
    tables = set(inspect(get_engine()).get_table_names())

    assert {"published_posts", "post_metrics"}.issubset(tables)


def test_published_post_allows_nullable_links(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import PublishedPost

    init_db()
    with session_scope() as session:
        session.add(
            PublishedPost(
                calendar_item_id=None,
                asset_id=None,
                channel="instagram",
                external_ref="ig_1",
                permalink="https://example.test/post/ig_1",
                published_at=datetime(2026, 7, 8, 12, 0),
            )
        )

    with session_scope() as session:
        post = session.query(PublishedPost).one()
        assert post.calendar_item_id is None
        assert post.asset_id is None
        assert post.channel == "instagram"


def test_post_metric_dedupe_key_is_post_and_capture_time(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import PostMetric, PublishedPost

    init_db()
    captured_at = datetime(2026, 7, 9, 9, 0)
    with pytest.raises(IntegrityError):
        with session_scope() as session:
            post = PublishedPost(channel="tiktok", external_ref="tt_1")
            session.add(post)
            session.flush()
            session.add_all(
                [
                    PostMetric(published_post_id=post.id, captured_at=captured_at, reach=100, likes=10),
                    PostMetric(published_post_id=post.id, captured_at=captured_at, reach=100, likes=11),
                ]
            )


def test_engagement_rate_computed_from_nullable_metrics(app_env) -> None:
    from app.db import init_db, session_scope
    from app.models import PostMetric, PublishedPost

    init_db()
    with session_scope() as session:
        post = PublishedPost(channel="facebook", permalink="https://example.test/fb")
        session.add(post)
        session.flush()
        metric = PostMetric(
            published_post_id=post.id,
            captured_at=datetime(2026, 7, 9, 10, 0),
            impressions=None,
            reach=200,
            likes=20,
            comments=4,
            shares=None,
            saves=6,
            clicks=3,
        )
        session.add(metric)

    with session_scope() as session:
        metric = session.query(PostMetric).one()
        assert metric.engagement_rate == pytest.approx(0.15)
        assert metric.impressions is None
        assert metric.clicks == 3


@pytest.mark.parametrize("reach", [None, 0])
def test_engagement_rate_null_when_reach_missing_or_zero(app_env, reach) -> None:
    from app.db import init_db, session_scope
    from app.models import PostMetric, PublishedPost

    init_db()
    with session_scope() as session:
        post = PublishedPost(channel="other", external_ref=f"post-{reach}")
        session.add(post)
        session.flush()
        session.add(
            PostMetric(
                published_post_id=post.id,
                captured_at=datetime(2026, 7, 9, 11, 0),
                reach=reach,
                likes=20,
                comments=4,
                shares=2,
                saves=1,
            )
        )

    with session_scope() as session:
        assert session.query(PostMetric).one().engagement_rate is None
