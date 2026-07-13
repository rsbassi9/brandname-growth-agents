"""ORM models (exact tables from the execution plan).

asset_versions rows are immutable snapshots: content columns are never
UPDATEd after insert (only the is_selected flag may be flipped).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

ASSET_TYPES = ("copy", "image_concept", "carousel", "video_script", "voiceover", "ad_brief", "seo_fix", "seo_plan")
ASSET_STATUSES = ("draft", "selected", "archived")
JOB_STATUSES = ("queued", "running", "succeeded", "failed")
SOURCE_ASSET_ORIGINS = ("drive", "local", "shopify")
BRAIN_DOCUMENT_KINDS = ("asset_version", "feedback", "product", "context_file", "metric_insight")
PUBLISHED_POST_CHANNELS = ("instagram", "tiktok", "facebook", "other")


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


class SourceAsset(Base):
    __tablename__ = "source_assets"
    __table_args__ = (UniqueConstraint("origin", "path", name="uq_source_asset_origin_path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    product_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class BrainDocument(Base):
    __tablename__ = "brain_documents"
    __table_args__ = (UniqueConstraint("kind", "ref_id", name="uq_brain_document_kind_ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    ref_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    meta_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    embedding: Mapped["BrainEmbedding | None"] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class BrainEmbedding(Base):
    __tablename__ = "brain_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("brain_documents.id"), unique=True, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    document: Mapped[BrainDocument] = relationship(back_populates="embedding")


class BrandProfileVersion(Base):
    __tablename__ = "brand_profile_versions"
    __table_args__ = (UniqueConstraint("version_no", name="uq_brand_profile_version_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_md: Mapped[str] = mapped_column(Text, nullable=False)
    distilled_from_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PublishedPost(Base):
    __tablename__ = "published_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calendar_item_id: Mapped[str | None] = mapped_column(ForeignKey("calendar_items.id"), nullable=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    permalink: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    title_or_caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    meta_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    metrics: Mapped[list["PostMetric"]] = relationship(
        back_populates="published_post", cascade="all, delete-orphan", order_by="PostMetric.captured_at"
    )


class PostMetric(Base):
    __tablename__ = "post_metrics"
    __table_args__ = (UniqueConstraint("published_post_id", "captured_at", name="uq_post_metric_capture"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    published_post_id: Mapped[int] = mapped_column(ForeignKey("published_posts.id"), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clicks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    follows_from_post: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    engagement_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    published_post: Mapped[PublishedPost] = relationship(back_populates="metrics")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.recompute_engagement_rate()

    def recompute_engagement_rate(self) -> None:
        if self.reach is None or self.reach == 0:
            self.engagement_rate = None
            return
        total = sum(value or 0 for value in (self.likes, self.comments, self.shares, self.saves))
        self.engagement_rate = total / self.reach


class SeoAudit(Base):
    __tablename__ = "seo_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_handle: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    issues_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    audited_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


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
