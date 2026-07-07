"""ORM models (exact tables from the execution plan).

asset_versions rows are immutable snapshots: content columns are never
UPDATEd after insert (only the is_selected flag may be flipped).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

ASSET_TYPES = ("copy", "image_concept", "carousel", "video_script", "voiceover")
ASSET_STATUSES = ("draft", "selected", "archived")
JOB_STATUSES = ("queued", "running", "succeeded", "failed")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    assets: Mapped[list[Asset]] = relationship(back_populates="campaign")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    # Natural key for the legacy outputs/ import (P1-1 idempotency); NULL for
    # assets created through the API.
    source_path: Mapped[str | None] = mapped_column(String(1000), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    campaign: Mapped[Campaign | None] = relationship(back_populates="assets")
    versions: Mapped[list[AssetVersion]] = relationship(
        back_populates="asset", order_by="AssetVersion.version_no"
    )


class AssetVersion(Base):
    __tablename__ = "asset_versions"
    __table_args__ = (UniqueConstraint("asset_id", "version_no", name="uq_asset_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_snapshot: Mapped[str] = mapped_column(Text, default="", nullable=False)
    params_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    model_used: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    asset: Mapped[Asset] = relationship(back_populates="versions")


class CalendarItem(Base):
    __tablename__ = "calendar_items"

    # Legacy calendar items already carry string ids; reusing them is the
    # migration natural key.
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    date: Mapped[str] = mapped_column(String(32), default="", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    data_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"

    # Legacy feedback.jsonl rows carry uuid ids; a content hash is used when absent.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    output_path: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    improvement_request: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(120), default="general", nullable=False)
    data_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SettingsKV(Base):
    __tablename__ = "settings_kv"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
