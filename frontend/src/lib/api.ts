export type AssetType = "copy" | "image_concept" | "carousel" | "video_script" | "voiceover" | "ad_brief" | "seo_fix";
export type AssetStatus = "draft" | "selected" | "archived";
export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export interface ModeOut {
  local_only_agent_runs: boolean;
  brand_name: string;
  image_model: string;
  model_default: string;
  model_premium: string;
  openai_base_url: string;
}

export interface HealthOut {
  status: string;
  brand: string;
}

export interface DailyWorkflowScheduleOut {
  enabled: boolean;
  time_local: string;
  last_enqueued_date: string;
}

export interface DailyWorkflowScheduleIn {
  enabled: boolean;
  time_local: string;
}

export interface DailyWorkflowRunOut {
  job_id: string;
}

export interface CalendarGuardrailsOut {
  max_items_per_day_channel: number;
}

export interface CalendarGuardrailsIn {
  max_items_per_day_channel: number;
}

export interface WorkflowRunStepOut {
  name: string;
  status: string;
  asset_id: number | null;
  source_path: string;
}

export interface WorkflowRunReportOut {
  id: string;
  status: JobStatus;
  progress_pct: number;
  message: string;
  mode: string;
  created_at: string;
  finished_at: string | null;
  steps: WorkflowRunStepOut[];
}

export interface GenerateRequest {
  type: AssetType;
  campaign_id?: number | null;
  brief: string;
  title?: string;
  params: Record<string, unknown>;
}

export interface GenerateResponse {
  job_id: string;
  asset_id: number;
}

export interface CritiqueOut {
  asset_id: number;
  version_no: number;
  critique: string;
}

export type SourceAssetOrigin = "drive" | "local" | "shopify";

export interface SourceAssetOut {
  id: number;
  origin: SourceAssetOrigin;
  path: string;
  tags_json: string;
  product_handle: string | null;
  created_at: string;
}

export interface SourceAssetListOut {
  items: SourceAssetOut[];
  total: number;
}

export interface SourceAssetIndexRequest {
  origin: SourceAssetOrigin;
  path?: string;
  tags?: string[];
  product_handle?: string | null;
  limit?: number;
}

export interface AdBriefRequest {
  objective: string;
  audience: string;
  placement: string;
  hook: string;
  brief?: string;
  campaign_id?: number | null;
  asset_id?: number | null;
  source_asset_id?: number | null;
  premium?: boolean;
}

export interface JobOut {
  id: string;
  kind: string;
  status: JobStatus;
  progress_pct: number;
  message: string;
  payload_json: string;
  result_json: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface AssetVersionOut {
  id: number;
  asset_id: number;
  version_no: number;
  prompt_snapshot: string;
  params_json: string;
  content_text: string | null;
  file_path: string | null;
  model_used: string;
  created_at: string;
  is_selected: boolean;
}

export interface AssetOut {
  id: number;
  campaign_id: number | null;
  type: AssetType;
  title: string;
  status: AssetStatus;
  source_path: string | null;
  created_at: string;
}

export interface AssetDetailOut extends AssetOut {
  versions: AssetVersionOut[];
}

export interface AssetListOut {
  items: AssetOut[];
  total: number;
  limit: number;
  offset: number;
}

export interface CampaignOut {
  id: number;
  name: string;
  goal: string;
  status: string;
  created_at: string;
}

export interface CampaignIn {
  name: string;
  goal: string;
  status?: string;
}

export interface CalendarItemOut {
  id: string;
  date: string;
  status: string;
  asset_id: number | null;
  data: Record<string, unknown>;
}

export interface CalendarItemIn {
  id?: string | null;
  date: string;
  status?: string;
  asset_id?: number | null;
  data?: Record<string, unknown>;
}

export interface CalendarItemPatch {
  date?: string | null;
  slot?: string | null;
  status?: string | null;
  asset_id?: number | null;
  data?: Record<string, unknown> | null;
}

export interface StrategyDocOut {
  name: string;
  content: string;
}

export interface FeedbackIn {
  output_path?: string;
  rating?: number;
  comment?: string;
  improvement_request?: string;
  category?: string;
}

export interface FeedbackOut {
  id: string;
  created_at: string;
  output_path: string;
  rating: number | null;
  comment: string;
  improvement_request: string;
  category: string;
}

export interface BrandProfileVersionOut {
  id: number;
  version_no: number;
  profile_md: string;
  distilled_from_json: string;
  created_at: string;
}

export interface BrandProfileHistoryOut {
  current: BrandProfileVersionOut | null;
  versions: BrandProfileVersionOut[];
}

export type PerformanceChannel = "instagram" | "tiktok" | "facebook" | "other";

export interface PerformanceImportOut {
  status: string;
  detected_columns: string[];
  posts_upserted: number;
  metrics_inserted: number;
  warnings: string[];
  posts: PublishedPostOut[];
}

export interface PublishedPostOut {
  id: number;
  calendar_item_id: string | null;
  asset_id: number | null;
  channel: PerformanceChannel;
  external_ref: string | null;
  permalink: string | null;
  title_or_caption: string | null;
  post_type: string | null;
  meta_json: string;
  published_at: string | null;
  created_at: string;
}

export interface PublishedPostListOut {
  items: PublishedPostOut[];
  total: number;
}

export interface PerformanceTopPostOut {
  post_id: number;
  channel: PerformanceChannel;
  title_or_caption: string;
  published_at: string | null;
  engagement_rate: number;
  calendar_item_id: string | null;
  asset_id: number | null;
}

export interface PerformanceTrendOut {
  week: string;
  mean_engagement_rate: number;
  sample_size: number;
}

export interface PerformanceAssetTypeOut {
  asset_type: string;
  mean_engagement_rate: number;
  sample_size: number;
}

export interface PerformanceDashboardOut {
  top_posts: PerformanceTopPostOut[];
  weekly_trend: PerformanceTrendOut[];
  by_asset_type: PerformanceAssetTypeOut[];
}

export interface BestTimeSlotOut {
  channel: PerformanceChannel;
  weekday: number;
  hour: number;
  sample_size: number;
  mean_engagement_rate: number;
}

export interface LibrarySummaryOut {
  total: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
}

const API_BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail || detail;
    } catch {
      // Keep the HTTP status text when the server returns no JSON body.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function requestForm<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { method: "POST", body });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const parsed = (await response.json()) as { detail?: string | { message?: string } };
      detail = typeof parsed.detail === "string" ? parsed.detail : parsed.detail?.message || detail;
    } catch {
      // Keep the HTTP status text when no JSON body is returned.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

function toQuery(params: Record<string, string | number | null | undefined>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const value = query.toString();
  return value ? `?${value}` : "";
}

export const api = {
  mode: () => request<ModeOut>("/system/mode"),
  health: () => request<HealthOut>("/system/health"),
  dailyWorkflowSchedule: () => request<DailyWorkflowScheduleOut>("/system/daily-workflow"),
  updateDailyWorkflowSchedule: (payload: DailyWorkflowScheduleIn) =>
    request<DailyWorkflowScheduleOut>("/system/daily-workflow", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  runDailyWorkflow: () =>
    request<DailyWorkflowRunOut>("/system/daily-workflow/run", { method: "POST" }),
  calendarGuardrails: () => request<CalendarGuardrailsOut>("/system/calendar-guardrails"),
  updateCalendarGuardrails: (payload: CalendarGuardrailsIn) =>
    request<CalendarGuardrailsOut>("/system/calendar-guardrails", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  dailyWorkflowRuns: () => request<WorkflowRunReportOut[]>("/system/daily-workflow/runs"),
  createAssetVideoPromptPack: (assetId: number) =>
    request<GenerateResponse>(`/assets/${assetId}/video-prompt-pack`, { method: "POST" }),
  createCalendarVideoPromptPack: (itemId: string) =>
    request<GenerateResponse>(`/calendar/${encodeURIComponent(itemId)}/video-prompt-pack`, { method: "POST" }),
  generate: (payload: GenerateRequest) =>
    request<GenerateResponse>("/generate", { method: "POST", body: JSON.stringify(payload) }),
  createAdBrief: (payload: AdBriefRequest) =>
    request<GenerateResponse>("/ads/briefs", { method: "POST", body: JSON.stringify(payload) }),
  job: (jobId: string) => request<JobOut>(`/jobs/${jobId}`),
  assets: (params: {
    type?: string;
    campaign_id?: number | null;
    status?: string;
    q?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  } = {}) => request<AssetListOut>(`/assets${toQuery(params)}`),
  asset: (assetId: number) => request<AssetDetailOut>(`/assets/${assetId}`),
  sourceAssets: (params: { origin?: string; q?: string } = {}) =>
    request<SourceAssetListOut>(`/source-assets${toQuery(params)}`),
  indexSourceAssets: (payload: SourceAssetIndexRequest) =>
    request<SourceAssetListOut>("/source-assets/index", { method: "POST", body: JSON.stringify(payload) }),
  selectVersion: (assetId: number, versionNo: number) =>
    request<AssetDetailOut>(`/assets/${assetId}/versions/${versionNo}/select`, { method: "POST" }),
  critiqueVersion: (assetId: number, versionNo: number) =>
    request<CritiqueOut>(`/assets/${assetId}/versions/${versionNo}/critique`, { method: "POST" }),
  iterateVersion: (assetId: number, versionNo: number) =>
    request<GenerateResponse>(`/assets/${assetId}/versions/${versionNo}/iterate`, { method: "POST" }),
  regenerate: (assetId: number) =>
    request<GenerateResponse>(`/assets/${assetId}/regenerate`, { method: "POST" }),
  librarySummary: () => request<LibrarySummaryOut>("/library/summary"),
  campaigns: () => request<CampaignOut[]>("/campaigns"),
  createCampaign: (payload: CampaignIn) =>
    request<CampaignOut>("/campaigns", { method: "POST", body: JSON.stringify(payload) }),
  campaignAssets: (campaignId: number) => request<AssetOut[]>(`/campaigns/${campaignId}/assets`),
  calendar: (params: { month?: string; date?: string; status?: string } = {}) =>
    request<CalendarItemOut[]>(`/calendar${toQuery(params)}`),
  createCalendarItem: (payload: CalendarItemIn) =>
    request<CalendarItemOut>("/calendar", { method: "POST", body: JSON.stringify(payload) }),
  updateCalendarItem: (itemId: string, payload: CalendarItemPatch) =>
    request<CalendarItemOut>(`/calendar/${encodeURIComponent(itemId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteCalendarItem: (itemId: string) =>
    request<void>(`/calendar/${encodeURIComponent(itemId)}`, { method: "DELETE" }),
  feed: () => request<CalendarItemOut[]>("/feed"),
  setFeedOrder: (item_ids: string[]) =>
    request<{ ok: boolean; count: number }>("/feed/order", {
      method: "POST",
      body: JSON.stringify({ item_ids }),
    }),
  strategyDocs: () => request<StrategyDocOut[]>("/strategy/context"),
  brandProfile: () => request<BrandProfileHistoryOut>("/strategy/brand-profile"),
  importPerformance: (payload: { channel: PerformanceChannel; file?: File | null; csv_text?: string }) => {
    const body = new FormData();
    body.set("channel", payload.channel);
    if (payload.file) {
      body.set("file", payload.file);
    } else {
      body.set("file", new Blob([payload.csv_text || ""], { type: "text/csv" }), "pasted.csv");
    }
    return requestForm<PerformanceImportOut>("/performance/import", body);
  },
  performancePosts: (params: { channel?: string; limit?: number; offset?: number } = {}) =>
    request<PublishedPostListOut>(`/performance/posts${toQuery(params)}`),
  performanceDashboard: () => request<PerformanceDashboardOut>("/performance/dashboard"),
  performanceBestTimes: (params: { channel?: string } = {}) => request<BestTimeSlotOut[]>(`/performance/best-times${toQuery(params)}`),
  linkPerformancePost: (postId: number, payload: { calendar_item_id?: string | null; asset_id?: number | null }) =>
    request<PublishedPostOut>(`/performance/posts/${postId}/link`, { method: "PATCH", body: JSON.stringify(payload) }),
  unlinkPerformancePost: (postId: number) =>
    request<PublishedPostOut>(`/performance/posts/${postId}/link`, { method: "DELETE" }),
  learnSummary: () => request<{ summary: string }>("/strategy/learn/summary"),
  postFeedback: (payload: FeedbackIn) =>
    request<FeedbackOut>("/strategy/learn/feedback", { method: "POST", body: JSON.stringify(payload) }),
};

export function createJobEventSource(jobId: string) {
  return new EventSource(`${API_BASE}/jobs/${jobId}/events`);
}
