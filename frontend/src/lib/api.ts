export type AssetType = "copy" | "image_concept" | "carousel" | "video_script" | "voiceover";
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
  dailyWorkflowRuns: () => request<WorkflowRunReportOut[]>("/system/daily-workflow/runs"),
  createAssetVideoPromptPack: (assetId: number) =>
    request<GenerateResponse>(`/assets/${assetId}/video-prompt-pack`, { method: "POST" }),
  createCalendarVideoPromptPack: (itemId: string) =>
    request<GenerateResponse>(`/calendar/${encodeURIComponent(itemId)}/video-prompt-pack`, { method: "POST" }),
  generate: (payload: GenerateRequest) =>
    request<GenerateResponse>("/generate", { method: "POST", body: JSON.stringify(payload) }),
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
  selectVersion: (assetId: number, versionNo: number) =>
    request<AssetDetailOut>(`/assets/${assetId}/versions/${versionNo}/select`, { method: "POST" }),
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
  learnSummary: () => request<{ summary: string }>("/strategy/learn/summary"),
  postFeedback: (payload: FeedbackIn) =>
    request<FeedbackOut>("/strategy/learn/feedback", { method: "POST", body: JSON.stringify(payload) }),
};

export function createJobEventSource(jobId: string) {
  return new EventSource(`${API_BASE}/jobs/${jobId}/events`);
}
