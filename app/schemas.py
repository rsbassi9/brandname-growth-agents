"""Pydantic v2 request/response contracts for /api/v1."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AssetType = Literal["copy", "image_concept", "carousel", "video_script", "voiceover"]
AssetStatus = Literal["draft", "selected", "archived"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]


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
