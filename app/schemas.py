"""Pydantic v2 request/response contracts for /api/v1."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AssetType = Literal["copy", "image_concept", "carousel", "video_script", "voiceover", "ad_brief", "seo_fix", "seo_plan"]
AssetStatus = Literal["draft", "selected", "archived"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]
SourceAssetOrigin = Literal["drive", "local", "shopify"]
BrainDocumentKind = Literal["asset_version", "feedback", "product", "context_file", "metric_insight"]
PublishedPostChannel = Literal["instagram", "tiktok", "facebook", "other"]


class GenerateRequest(BaseModel):
    type: AssetType
    campaign_id: int | None = None
    brief: str = Field(min_length=1)
    title: str = ""
    params: dict[str, Any] = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    job_id: str
    asset_id: int


class CritiqueOut(BaseModel):
    asset_id: int
    version_no: int
    critique: str


class SourceAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    origin: SourceAssetOrigin
    path: str
    tags_json: str
    product_handle: str | None
    created_at: datetime


class SourceAssetListOut(BaseModel):
    items: list[SourceAssetOut]
    total: int


class BrainDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: BrainDocumentKind
    ref_id: str | None
    text: str
    meta_json: str
    created_at: datetime


class BrainEmbeddingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    model: str
    dim: int
    created_at: datetime


class BrandProfileVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_no: int
    profile_md: str
    distilled_from_json: str
    created_at: datetime


class PublishedPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    calendar_item_id: str | None
    asset_id: int | None
    channel: PublishedPostChannel
    external_ref: str | None
    permalink: str | None
    title_or_caption: str | None
    post_type: str | None
    meta_json: str
    published_at: datetime | None
    created_at: datetime


class PostMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    published_post_id: int
    captured_at: datetime
    impressions: int | None
    reach: int | None
    likes: int | None
    comments: int | None
    shares: int | None
    saves: int | None
    clicks: int | None
    follows_from_post: int | None
    meta_json: str
    engagement_rate: float | None


class PerformanceImportOut(BaseModel):
    status: str = "imported"
    detected_columns: list[str] = Field(default_factory=list)
    posts_upserted: int = 0
    metrics_inserted: int = 0
    warnings: list[str] = Field(default_factory=list)
    posts: list[PublishedPostOut] = Field(default_factory=list)
    metrics: list[PostMetricOut] = Field(default_factory=list)


class PublishedPostListOut(BaseModel):
    items: list[PublishedPostOut]
    total: int


class PublishedPostLinkIn(BaseModel):
    calendar_item_id: str | None = None
    asset_id: int | None = None


class BestTimeSlotOut(BaseModel):
    channel: PublishedPostChannel
    weekday: int
    hour: int
    sample_size: int
    mean_engagement_rate: float


class PerformanceTopPostOut(BaseModel):
    post_id: int
    channel: PublishedPostChannel
    title_or_caption: str
    published_at: datetime | None
    engagement_rate: float
    calendar_item_id: str | None = None
    asset_id: int | None = None


class PerformanceTrendOut(BaseModel):
    week: str
    mean_engagement_rate: float
    sample_size: int


class PerformanceAssetTypeOut(BaseModel):
    asset_type: str
    mean_engagement_rate: float
    sample_size: int


class PerformanceDashboardOut(BaseModel):
    top_posts: list[PerformanceTopPostOut] = Field(default_factory=list)
    weekly_trend: list[PerformanceTrendOut] = Field(default_factory=list)
    by_asset_type: list[PerformanceAssetTypeOut] = Field(default_factory=list)


class SeoAuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_handle: str
    score: int
    issues_json: str
    audited_at: datetime


class SeoAuditRunOut(BaseModel):
    job_id: str


class RepurposeShootRequest(BaseModel):
    source_asset_ids: list[int] = Field(min_length=1, max_length=10)
    campaign_name: str = ""
    brief: str = ""


class RepurposeShootRunOut(BaseModel):
    job_id: str


class SourceAssetIndexRequest(BaseModel):
    origin: SourceAssetOrigin = "local"
    path: str = ""
    tags: list[str] = Field(default_factory=list)
    product_handle: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class AdBriefRequest(BaseModel):
    objective: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    placement: str = "Instagram Feed + Reels"
    hook: str = Field(min_length=1)
    brief: str = ""
    campaign_id: int | None = None
    asset_id: int | None = None
    source_asset_id: int | None = None
    premium: bool = False


class AdBriefContent(BaseModel):
    objective: str
    audience: str
    placement: str
    hook: str
    primary_text: list[str] = Field(min_length=3, max_length=3)
    headlines: list[str] = Field(min_length=3, max_length=3)
    cta: str
    recommended_creative: str
    manual_export_blocks: list[str]


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    status: JobStatus
    progress_pct: int
    message: str
    payload_json: str
    result_json: str | None
    created_at: datetime
    finished_at: datetime | None


class AssetVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    version_no: int
    prompt_snapshot: str
    params_json: str
    content_text: str | None
    file_path: str | None
    model_used: str
    created_at: datetime
    is_selected: bool


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int | None
    type: str
    title: str
    status: str
    source_path: str | None
    created_at: datetime


class AssetDetailOut(AssetOut):
    versions: list[AssetVersionOut] = Field(default_factory=list)


class AssetListOut(BaseModel):
    items: list[AssetOut]
    total: int
    limit: int
    offset: int


class CampaignIn(BaseModel):
    name: str = Field(min_length=1)
    goal: str = ""
    status: str = "active"


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    goal: str
    status: str
    created_at: datetime


class CalendarItemIn(BaseModel):
    id: str | None = None
    date: str = ""
    status: str = "draft"
    asset_id: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class CalendarItemPatch(BaseModel):
    date: str | None = None
    slot: str | None = None
    status: str | None = None
    asset_id: int | None = None
    data: dict[str, Any] | None = None


class CalendarItemOut(BaseModel):
    id: str
    date: str
    status: str
    asset_id: int | None
    data: dict[str, Any]


class FeedbackIn(BaseModel):
    output_path: str = ""
    rating: int = 3
    comment: str = ""
    improvement_request: str = ""
    category: str = "general"


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: str
    output_path: str
    rating: int | None
    comment: str
    improvement_request: str
    category: str


class FeedOrderIn(BaseModel):
    item_ids: list[str]


class HealthOut(BaseModel):
    status: str = "ok"
    brand: str = ""


class ModeOut(BaseModel):
    local_only_agent_runs: bool
    brand_name: str
    image_model: str
    model_default: str
    model_premium: str = ""
    openai_base_url: str = ""


class DailyWorkflowScheduleIn(BaseModel):
    enabled: bool = False
    time_local: str = Field(default="09:00", pattern=r"^\d{2}:\d{2}$")


class DailyWorkflowScheduleOut(DailyWorkflowScheduleIn):
    last_enqueued_date: str = ""


class BrandProfileDistillationScheduleIn(BaseModel):
    enabled: bool = False
    time_local: str = Field(default="09:00", pattern=r"^\d{2}:\d{2}$")
    weekday: int = Field(default=0, ge=0, le=6)


class BrandProfileDistillationScheduleOut(BrandProfileDistillationScheduleIn):
    last_enqueued_date: str = ""


class RecyclingScheduleIn(BaseModel):
    enabled: bool = False
    day: int = Field(default=1, ge=1, le=28)
    time_local: str = Field(default="09:00", pattern=r"^\d{2}:\d{2}$")


class RecyclingScheduleOut(RecyclingScheduleIn):
    last_enqueued_month: str = ""


class WeeklyStandupScheduleIn(BaseModel):
    enabled: bool = False
    time_local: str = Field(default="09:00", pattern=r"^\d{2}:\d{2}$")
    weekday: int = Field(default=0, ge=0, le=6)


class WeeklyStandupScheduleOut(WeeklyStandupScheduleIn):
    last_enqueued_date: str = ""


class CalendarGuardrailsIn(BaseModel):
    max_items_per_day_channel: int = Field(default=3, ge=1, le=20)


class CalendarGuardrailsOut(CalendarGuardrailsIn):
    pass


class DailyWorkflowRunOut(BaseModel):
    job_id: str


class WorkflowRunStepOut(BaseModel):
    name: str
    status: str
    asset_id: int | None = None
    source_path: str = ""


class WorkflowRunReportOut(BaseModel):
    id: str
    status: JobStatus
    progress_pct: int
    message: str
    mode: str = ""
    created_at: datetime
    finished_at: datetime | None
    steps: list[WorkflowRunStepOut] = Field(default_factory=list)


class StrategyDocOut(BaseModel):
    name: str
    content: str


class BrandProfileHistoryOut(BaseModel):
    current: BrandProfileVersionOut | None = None
    versions: list[BrandProfileVersionOut] = Field(default_factory=list)


class StandupReportOut(BaseModel):
    id: int
    week_start: str
    report_md: str
    recommendations_json: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StandupDraftOut(BaseModel):
    asset_id: int
