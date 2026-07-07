"""SQLAlchemy engine/session management. SQLite at data/app.db by default."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import get_settings


class Base(DeclarativeBase):
    pass


_lock = threading.Lock()
_engine: Engine | None = None
_engine_url: str | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _engine_url, _session_factory
    url = get_settings().resolved_database_url()
    with _lock:
        if _engine is None or _engine_url != url:
            if url.startswith("sqlite"):
                db_path = url.replace("sqlite:///", "", 1)
                if db_path and db_path != ":memory:":
                    from pathlib import Path

                    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
                engine = create_engine(url, connect_args={"check_same_thread": False})
            else:
                engine = create_engine(url)
            _engine = engine
            _engine_url = url
            _session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        assert _engine is not None
        return _engine


def reset_engine() -> None:
    """Test helper: drop the cached engine so the next call re-reads settings."""
    global _engine, _engine_url, _session_factory
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _engine_url = None
        _session_factory = None


def init_db() -> None:
    from . import models  # noqa: F401  (register mappings)

    Base.metadata.create_all(get_engine())


def _factory() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    session = _factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    session = _factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
