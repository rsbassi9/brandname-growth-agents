import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock3, Copy, Image, Loader2, PanelsTopLeft, RotateCcw, Video, Wand2 } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import type { ComponentType } from "react";
import { useLocation } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { VideoPromptPackView, parseVideoPromptPack } from "@/components/VideoPromptPackView";
import { PREMIUM_MODEL_EVENT, PREMIUM_MODEL_KEY } from "@/layout/AppShell";
import { PageHeader, Panel } from "@/components/ui/Panel";
import {
  api,
  createJobEventSource,
  type AssetDetailOut,
  type AssetType,
  type GenerateRequest,
  type GenerateResponse,
  type JobOut,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const DEFAULTS_KEY = "brandname.playground.defaults";
const HISTORY_KEY = "brandname.playground.history";

const assetTypes: Array<{ value: AssetType; label: string; icon: ComponentType<{ className?: string }> }> = [
  { value: "copy", label: "Copy", icon: Copy },
  { value: "image_concept", label: "Image Concept", icon: Image },
  { value: "carousel", label: "Carousel", icon: PanelsTopLeft },
  { value: "video_script", label: "Video Script", icon: Video },
];

interface PlaygroundDefaults {
  type: AssetType;
  model: string;
  tone: string;
  template: string;
  premium: boolean;
}

interface HistoryItem extends PlaygroundDefaults {
  id: string;
  brief: string;
  title: string;
  assetId?: number;
  versionNo?: number;
  createdAt: string;
}

interface PlaygroundRouteState {
  campaignId?: number;
  campaignName?: string;
  assetType?: AssetType;
  brief?: string;
}

const initialDefaults: PlaygroundDefaults = {
  type: "copy",
  model: "",
  tone: "quiet confidence",
  template: "default",
  premium: localStorage.getItem(PREMIUM_MODEL_KEY) === "true",
};

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? ({ ...fallback, ...JSON.parse(raw) } as T) : fallback;
  } catch {
    return fallback;
  }
}

function selectedVersion(asset?: AssetDetailOut | null) {
  return asset?.versions.find((version) => version.is_selected) || asset?.versions[asset.versions.length - 1] || null;
}

export function PlaygroundPage() {
  const queryClient = useQueryClient();
  const location = useLocation();
  const routeState = (location.state || {}) as PlaygroundRouteState;
  const mode = useQuery({ queryKey: ["system", "mode"], queryFn: api.mode });
  const [defaults, setDefaults] = useState<PlaygroundDefaults>(() => readJson(DEFAULTS_KEY, initialDefaults));
  const [brief, setBrief] = useState("");
  const [title, setTitle] = useState("");
  const [campaignId, setCampaignId] = useState<number | null>(routeState.campaignId || null);
  const [campaignName, setCampaignName] = useState(routeState.campaignName || "");
  const [history, setHistory] = useState<HistoryItem[]>(() => readJson<HistoryItem[]>(HISTORY_KEY, []));
  const [activeAssetId, setActiveAssetId] = useState<number | null>(null);
  const [activeJob, setActiveJob] = useState<JobOut | null>(null);
  const [jobError, setJobError] = useState("");

  const activeAsset = useQuery({
    queryKey: ["assets", activeAssetId],
    queryFn: () => api.asset(activeAssetId!),
    enabled: activeAssetId !== null && activeJob?.status === "succeeded",
  });

  const generate = useMutation({
    mutationFn: (payload: GenerateRequest) => api.generate(payload),
    onSuccess: (response, payload) => {
      setActiveAssetId(response.asset_id);
      setActiveJob({
        id: response.job_id,
        kind: "generate_asset",
        status: "queued",
        progress_pct: 0,
        message: "queued",
        payload_json: JSON.stringify(payload),
        result_json: null,
        created_at: new Date().toISOString(),
        finished_at: null,
      });
      setJobError("");
      pushHistory(response, payload);
    },
  });

  useEffect(() => {
    localStorage.setItem(DEFAULTS_KEY, JSON.stringify(defaults));
    localStorage.setItem(PREMIUM_MODEL_KEY, String(defaults.premium));
  }, [defaults]);

  useEffect(() => {
    function syncPremium(event: Event) {
      const nextValue = event instanceof CustomEvent ? Boolean(event.detail) : localStorage.getItem(PREMIUM_MODEL_KEY) === "true";
      setDefaults((current) => ({ ...current, premium: nextValue }));
    }
    window.addEventListener(PREMIUM_MODEL_EVENT, syncPremium);
    window.addEventListener("storage", syncPremium);
    return () => {
      window.removeEventListener(PREMIUM_MODEL_EVENT, syncPremium);
      window.removeEventListener("storage", syncPremium);
    };
  }, []);

  useEffect(() => {
    if (routeState.campaignId) {
      setCampaignId(routeState.campaignId);
      setCampaignName(routeState.campaignName || "");
      setBrief((current) => current || routeState.brief || "");
      setTitle((current) => current || routeState.campaignName || "");
      if (routeState.assetType) {
        setDefaults((current) => ({ ...current, type: routeState.assetType! }));
      }
    }
  }, [routeState.assetType, routeState.brief, routeState.campaignId, routeState.campaignName]);

  useEffect(() => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 12)));
  }, [history]);

  useEffect(() => {
    if (!activeJob || ["succeeded", "failed"].includes(activeJob.status)) {
      return;
    }

    const source = createJobEventSource(activeJob.id);
    const update = (event: MessageEvent<string>) => {
      const snapshot = JSON.parse(event.data) as JobOut;
      setActiveJob(snapshot);
      if (snapshot.status === "succeeded") {
        queryClient.invalidateQueries({ queryKey: ["assets", activeAssetId] });
        queryClient.invalidateQueries({ queryKey: ["assets"] });
        queryClient.invalidateQueries({ queryKey: ["library"] });
      }
    };

    source.addEventListener("progress", update);
    source.addEventListener("completion", update);
    source.addEventListener("error", (event) => {
      if (event instanceof MessageEvent && event.data) {
        try {
          const payload = JSON.parse(event.data) as { detail?: string };
          setJobError(payload.detail || "Job stream error.");
        } catch {
          setJobError("Job stream error.");
        }
      }
    });

    return () => source.close();
  }, [activeAssetId, activeJob?.id, activeJob?.status, queryClient]);

  const currentVersion = selectedVersion(activeAsset.data);
  const isBusy = generate.isPending || ["queued", "running"].includes(activeJob?.status || "");
  const previewText = currentVersion?.content_text || "";
  const videoPack = parseVideoPromptPack(previewText);
  const activeType = assetTypes.find((item) => item.value === defaults.type) || assetTypes[0];
  const ActiveTypeIcon = activeType.icon;

  function updateDefaults(patch: Partial<PlaygroundDefaults>) {
    setDefaults((current) => ({ ...current, ...patch }));
  }

  function buildPayload(): GenerateRequest {
    const params: Record<string, unknown> = {
      tone: defaults.tone,
      template: defaults.template,
      premium: defaults.premium,
    };
    if (defaults.model.trim()) {
      params.model = defaults.model.trim();
    }
    return {
      type: defaults.type,
      campaign_id: campaignId,
      brief,
      title,
      params,
    };
  }

  function pushHistory(response: GenerateResponse, payload: GenerateRequest) {
    const item: HistoryItem = {
      ...defaults,
      id: response.job_id,
      brief: payload.brief,
      title: payload.title || payload.brief.split("\n")[0]?.slice(0, 80) || "Untitled",
      assetId: response.asset_id,
      createdAt: new Date().toISOString(),
    };
    setHistory((current) => [item, ...current.filter((existing) => existing.id !== item.id)].slice(0, 12));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!brief.trim()) {
      setJobError("Write a brief before generating.");
      return;
    }
    generate.mutate(buildPayload());
  }

  function restore(item: HistoryItem) {
    setDefaults({
      type: item.type,
      model: item.model,
      tone: item.tone,
      template: item.template,
      premium: item.premium,
    });
    setBrief(item.brief);
    setTitle(item.title);
    if (item.assetId) {
      setActiveAssetId(item.assetId);
      setActiveJob({
        id: item.id,
        kind: "generate_asset",
        status: "succeeded",
        progress_pct: 100,
        message: "restored from session history",
        payload_json: "{}",
        result_json: null,
        created_at: item.createdAt,
        finished_at: item.createdAt,
      });
    }
  }

  const progressLabel = useMemo(() => {
    if (generate.isPending) return "Submitting";
    if (activeJob) return activeJob.message || activeJob.status;
    return "Ready";
  }, [activeJob, generate.isPending]);

  return (
    <div>
      <PageHeader
        eyebrow="Generate"
        title="Playground"
        actions={
          <Button type="submit" form="playground-form" disabled={isBusy}>
            {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
            Generate
          </Button>
        }
      />

      <div className="grid gap-4 p-4 lg:grid-cols-[minmax(320px,440px)_1fr]">
        <Panel>
          <form id="playground-form" className="space-y-4" onSubmit={submit}>
            {campaignId ? (
              <div className="rounded-md border border-warning/30 bg-warning-soft p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase text-warning">Campaign</p>
                    <p className="mt-1 text-sm font-medium text-foreground">{campaignName || `Campaign ${campaignId}`}</p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-foreground hover:bg-warning-soft"
                    onClick={() => {
                      setCampaignId(null);
                      setCampaignName("");
                    }}
                  >
                    Clear
                  </Button>
                </div>
              </div>
            ) : null}

            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">Asset type</legend>
              <div className="grid grid-cols-2 gap-2">
                {assetTypes.map((item) => {
                  const Icon = item.icon;
                  const selected = defaults.type === item.value;
                  return (
                    <button
                      key={item.value}
                      type="button"
                      className={cn(
                        "flex min-h-11 items-center gap-2 rounded-md border px-3 text-left text-sm font-medium transition-colors duration-ui ease-ui",
                        selected
                          ? "border-accent bg-accent-soft text-accent-soft-foreground"
                          : "border-border bg-background hover:bg-muted",
                      )}
                      aria-pressed={selected}
                      onClick={() => updateDefaults({ type: item.value })}
                    >
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </button>
                  );
                })}
              </div>
            </fieldset>

            <div>
              <label className="text-sm font-medium" htmlFor="brief">
                Brief
              </label>
              <textarea
                id="brief"
                className="mt-2 min-h-44 w-full rounded-md border border-input bg-background px-3 py-3 text-sm leading-6 outline-none transition focus:ring-2 focus:ring-ring"
                placeholder="Describe the asset, campaign context, source photo direction, or product angle..."
                value={brief}
                onChange={(event) => setBrief(event.target.value)}
              />
            </div>

            <div>
              <label className="text-sm font-medium" htmlFor="title">
                Title
              </label>
              <input
                id="title"
                className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition focus:ring-2 focus:ring-ring"
                placeholder="Optional asset title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm font-medium" htmlFor="tone">
                Tone
                <select
                  id="tone"
                  className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={defaults.tone}
                  onChange={(event) => updateDefaults({ tone: event.target.value })}
                >
                  <option value="quiet confidence">Quiet confidence</option>
                  <option value="launch urgency">Launch urgency</option>
                  <option value="process proof">Process proof</option>
                  <option value="premium minimal">Premium minimal</option>
                </select>
              </label>
              <label className="text-sm font-medium" htmlFor="template">
                Template
                <select
                  id="template"
                  className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={defaults.template}
                  onChange={(event) => updateDefaults({ template: event.target.value })}
                >
                  <option value="default">Default</option>
                  <option value="drop teaser">Drop teaser</option>
                  <option value="process breakdown">Process breakdown</option>
                  <option value="product clarity">Product clarity</option>
                </select>
              </label>
            </div>

            <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
              <label className="text-sm font-medium" htmlFor="model">
                Model
                <input
                  id="model"
                  className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 font-mono text-sm outline-none transition focus:ring-2 focus:ring-ring"
                  placeholder={mode.data?.model_default || "default"}
                  value={defaults.model}
                  onChange={(event) => updateDefaults({ model: event.target.value })}
                />
              </label>
              <label className="flex min-h-11 items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm font-medium">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-accent"
                  checked={defaults.premium}
                  onChange={(event) => updateDefaults({ premium: event.target.checked })}
                />
                Premium
              </label>
            </div>

            <div className="grid grid-cols-4 gap-2" aria-label="Reference photos">
              {Array.from({ length: 4 }, (_, index) => (
                <div
                  key={index}
                  className="aspect-[4/5] rounded-md border border-dashed border-border bg-muted/40"
                  aria-label={`Reference slot ${index + 1}`}
                />
              ))}
            </div>
          </form>
        </Panel>

        <Panel className="min-h-[520px]">
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
              <div className="flex items-center gap-3">
                <span className="flex h-11 w-11 items-center justify-center rounded-md bg-primary text-primary-foreground">
                  <ActiveTypeIcon className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-sm font-semibold">{activeType.label}</p>
                  <p className="text-sm text-muted-foreground">{progressLabel}</p>
                </div>
              </div>
              <Badge tone={activeJob?.status === "succeeded" ? "success" : isBusy ? "warning" : "neutral"}>
                {activeJob?.status || "idle"}
              </Badge>
            </div>

            {generate.error || jobError ? (
              <div role="alert" className="rounded-md border border-danger/30 bg-danger-soft p-3 text-sm text-danger">
                {generate.error instanceof Error ? generate.error.message : jobError}
              </div>
            ) : null}

            {isBusy ? (
              <div className="rounded-md border border-border bg-muted p-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{activeJob?.message || "Working"}</span>
                  <span className="font-mono">{activeJob?.progress_pct ?? 0}%</span>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-background">
                  <div
                    className="h-full rounded-full bg-accent transition-all"
                    style={{ width: `${activeJob?.progress_pct ?? 8}%` }}
                  />
                </div>
              </div>
            ) : null}

            {currentVersion ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="success">
                    <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
                    Version {currentVersion.version_no}
                  </Badge>
                  <Badge>{currentVersion.model_used}</Badge>
                  {currentVersion.file_path ? <Badge tone="neutral">File attached</Badge> : null}
                </div>
                <article className="max-h-[560px] overflow-auto rounded-md border border-border bg-background p-4">
                  {videoPack ? (
                    <VideoPromptPackView content={previewText} />
                  ) : (
                    <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6 text-foreground">
                      {previewText || currentVersion.file_path || "Version persisted without text content."}
                    </pre>
                  )}
                </article>
              </div>
            ) : !isBusy ? (
              <div className="flex min-h-[360px] items-center justify-center rounded-md border border-dashed border-border bg-muted/40 p-8 text-center">
                <div>
                  <Clock3 className="mx-auto h-8 w-8 text-muted-foreground" />
                  <p className="mt-3 text-sm font-medium">Ready for a take</p>
                  <p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">
                    Generate a copy draft, image prompt pack, carousel plan, or video script in local-only mode.
                  </p>
                </div>
              </div>
            ) : null}
          </div>
        </Panel>
      </div>

      <section className="border-t border-border px-4 py-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">Session History</h2>
          <Badge>{history.length} saved</Badge>
        </div>
        <div className="flex gap-3 overflow-x-auto pb-2">
          {history.map((item) => (
            <button
              key={item.id}
              type="button"
              className={cn(
                "min-h-24 w-72 shrink-0 rounded-lg border bg-surface p-3 text-left transition-colors duration-ui ease-ui hover:bg-muted",
                item.assetId === activeAssetId ? "border-accent bg-accent-soft" : "border-border",
              )}
              onClick={() => restore(item)}
            >
              <div className="flex items-center justify-between gap-2">
                <Badge tone="ink">{item.type.replace("_", " ")}</Badge>
                <RotateCcw className="h-4 w-4 text-muted-foreground" />
              </div>
              <p className="mt-3 line-clamp-2 text-sm font-medium">{item.title}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {new Date(item.createdAt).toLocaleString()}
              </p>
            </button>
          ))}
          {!history.length ? (
            <div className="rounded-lg border border-dashed border-border px-4 py-5 text-sm text-muted-foreground">
              Generated takes will appear here for quick restore.
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
