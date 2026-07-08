import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, CheckCircle2, Clipboard, Download, FileText, GraduationCap, Layers3, Send, Sparkles } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader, Panel } from "@/components/ui/Panel";
import { api, type AssetOut } from "@/lib/api";
import { cn } from "@/lib/utils";

const lanes = [
  { id: "know", label: "Know", icon: FileText },
  { id: "plan", label: "Plan", icon: CalendarDays },
  { id: "build", label: "Build", icon: Layers3 },
  { id: "ship", label: "Ship Manually", icon: CheckCircle2 },
  { id: "learn", label: "Learn", icon: GraduationCap },
] as const;

type LaneId = (typeof lanes)[number]["id"];

function formatName(name: string) {
  return name.split("_").join(" ");
}

function assetTypeLabel(type: string) {
  return type.replace("_", " ");
}

function itemTitle(data: Record<string, unknown>, fallback: string) {
  return String(data.title || data.hook || data.caption || fallback);
}

export function StrategyHubPage() {
  const queryClient = useQueryClient();
  const [lane, setLane] = useState<LaneId>("know");
  const [selectedAssetId, setSelectedAssetId] = useState<number | null>(null);
  const [feedbackTarget, setFeedbackTarget] = useState("");
  const [rating, setRating] = useState("4");
  const [comment, setComment] = useState("");
  const [improvement, setImprovement] = useState("");
  const [copied, setCopied] = useState(false);

  const docs = useQuery({ queryKey: ["strategy", "docs"], queryFn: api.strategyDocs });
  const calendar = useQuery({ queryKey: ["calendar", "strategy"], queryFn: () => api.calendar() });
  const draftAssets = useQuery({
    queryKey: ["assets", "strategy", "drafts"],
    queryFn: () => api.assets({ status: "draft", limit: 60, offset: 0 }),
  });
  const selectedAsset = useQuery({
    queryKey: ["assets", selectedAssetId],
    queryFn: () => api.asset(selectedAssetId!),
    enabled: selectedAssetId !== null,
  });
  const learning = useQuery({ queryKey: ["strategy", "learn"], queryFn: api.learnSummary });

  const feedback = useMutation({
    mutationFn: () =>
      api.postFeedback({
        output_path: feedbackTarget,
        rating: Number(rating),
        comment,
        improvement_request: improvement,
        category: "strategy_hub",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["strategy", "learn"] });
      setComment("");
      setImprovement("");
    },
  });

  const drafts = draftAssets.data?.items || [];
  const activeAsset = selectedAsset.data;
  const activeVersion = useMemo(() => {
    return activeAsset?.versions.find((version) => version.is_selected) || activeAsset?.versions[activeAsset.versions.length - 1] || null;
  }, [activeAsset]);
  const captionText = activeVersion?.content_text || "";

  function submitFeedback(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    feedback.mutate();
  }

  async function copyCaption() {
    if (!captionText) return;
    await navigator.clipboard?.writeText(captionText);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  return (
    <div>
      <PageHeader eyebrow="Know / Plan / Build / Ship / Learn" title="Strategy Hub" />
      <div className="border-b border-border bg-surface px-4 py-3">
        <div className="flex gap-2 overflow-x-auto">
          {lanes.map((item) => {
            const Icon = item.icon;
            const selected = lane === item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={cn(
                  "flex min-h-11 shrink-0 items-center gap-2 rounded-md border px-3 text-sm font-medium transition-colors duration-ui ease-ui",
                  selected ? "border-accent bg-accent-soft text-accent-soft-foreground" : "border-border bg-background hover:bg-muted",
                )}
                aria-pressed={selected}
                onClick={() => setLane(item.id)}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </button>
            );
          })}
        </div>
      </div>

      {lane === "know" ? <KnowLane docs={docs.data || []} loading={docs.isLoading} /> : null}
      {lane === "plan" ? <PlanLane items={calendar.data || []} loading={calendar.isLoading} /> : null}
      {lane === "build" ? <BuildLane assets={drafts} loading={draftAssets.isLoading} onSelect={setSelectedAssetId} /> : null}
      {lane === "ship" ? (
        <ShipLane
          assets={drafts}
          selectedAssetId={selectedAssetId}
          onSelect={setSelectedAssetId}
          captionText={captionText}
          filePath={activeVersion?.file_path || null}
          copied={copied}
          onCopy={copyCaption}
        />
      ) : null}
      {lane === "learn" ? (
        <LearnLane
          summary={learning.data?.summary || ""}
          feedbackTarget={feedbackTarget}
          rating={rating}
          comment={comment}
          improvement={improvement}
          pending={feedback.isPending}
          error={feedback.error}
          onTarget={setFeedbackTarget}
          onRating={setRating}
          onComment={setComment}
          onImprovement={setImprovement}
          onSubmit={submitFeedback}
        />
      ) : null}
    </div>
  );
}

function KnowLane({ docs, loading }: { docs: Array<{ name: string; content: string }>; loading: boolean }) {
  return (
    <div className="grid gap-4 p-4 xl:grid-cols-2">
      {docs.map((doc) => (
        <Panel key={doc.name}>
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-display text-xl font-normal capitalize">{formatName(doc.name)}</h2>
            <Badge tone="ink">Context</Badge>
          </div>
          <p className="mt-4 line-clamp-6 whitespace-pre-line text-sm leading-6 text-muted-foreground">{doc.content}</p>
        </Panel>
      ))}
      {loading
        ? Array.from({ length: 4 }, (_, index) => (
            <Panel key={index} className="h-52 animate-pulse bg-muted">
              <span className="sr-only">Loading strategy context</span>
            </Panel>
          ))
        : null}
    </div>
  );
}

function PlanLane({
  items,
  loading,
}: {
  items: Array<{ id: string; date: string; status: string; asset_id: number | null; data: Record<string, unknown> }>;
  loading: boolean;
}) {
  return (
    <div className="grid gap-4 p-4 xl:grid-cols-[1fr_360px]">
      <div className="space-y-3">
        {items.slice(0, 18).map((item) => (
          <Panel key={item.id} className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-semibold">{itemTitle(item.data, item.id)}</p>
              <p className="mt-1 text-xs text-muted-foreground">{item.date || "Unscheduled"}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {item.asset_id ? <Badge>Asset {item.asset_id}</Badge> : null}
              <Badge tone={item.status === "published" ? "success" : "neutral"}>{item.status}</Badge>
            </div>
          </Panel>
        ))}
        {loading ? (
          <Panel className="h-28 animate-pulse bg-muted">
            <span className="sr-only">Loading calendar plan</span>
          </Panel>
        ) : null}
      </div>
      <Panel>
        <h2 className="font-display text-xl font-normal">Calendar</h2>
        <Button asChild className="mt-4 w-full">
          <Link to="/calendar">
            <CalendarDays className="h-4 w-4" />
            Open Calendar
          </Link>
        </Button>
        <Button asChild variant="outline" className="mt-2 w-full">
          <Link to="/feed">
            <Layers3 className="h-4 w-4" />
            Open Feed Grid
          </Link>
        </Button>
      </Panel>
    </div>
  );
}

function BuildLane({ assets, loading, onSelect }: { assets: AssetOut[]; loading: boolean; onSelect: (assetId: number) => void }) {
  return (
    <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3">
      {assets.map((asset) => (
        <button
          key={asset.id}
          type="button"
          className="rounded-lg border border-border bg-surface p-3 text-left transition-colors duration-ui ease-ui hover:border-accent hover:bg-accent-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={() => onSelect(asset.id)}
        >
          <div className="flex aspect-[4/5] flex-col justify-between rounded-md border border-border bg-muted p-3">
            <Sparkles className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="line-clamp-3 text-sm font-semibold">{asset.title}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge tone="ink">{assetTypeLabel(asset.type)}</Badge>
                <Badge>{asset.status}</Badge>
              </div>
            </div>
          </div>
        </button>
      ))}
      {loading
        ? Array.from({ length: 6 }, (_, index) => (
            <Panel key={index} className="aspect-[4/5] animate-pulse bg-muted">
              <span className="sr-only">Loading build queue</span>
            </Panel>
          ))
        : null}
    </div>
  );
}

function ShipLane({
  assets,
  selectedAssetId,
  onSelect,
  captionText,
  filePath,
  copied,
  onCopy,
}: {
  assets: AssetOut[];
  selectedAssetId: number | null;
  onSelect: (assetId: number) => void;
  captionText: string;
  filePath: string | null;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <div className="grid gap-4 p-4 xl:grid-cols-[360px_1fr]">
      <Panel>
        <label htmlFor="ship-asset" className="text-sm font-medium">
          Asset
        </label>
        <select
          id="ship-asset"
          className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
          value={selectedAssetId || ""}
          onChange={(event) => {
            if (event.target.value) {
              onSelect(Number(event.target.value));
            }
          }}
        >
          <option value="">Select asset</option>
          {assets.map((asset) => (
            <option key={asset.id} value={asset.id}>
              {asset.title}
            </option>
          ))}
        </select>
        <div className="mt-4 space-y-2">
          {["Caption reviewed", "Creative downloaded", "Manual post scheduled", "Feedback loop ready"].map((item) => (
            <label key={item} className="flex min-h-11 items-center gap-2 rounded-md border border-border px-3 text-sm">
              <input type="checkbox" className="h-4 w-4 accent-accent" />
              {item}
            </label>
          ))}
        </div>
      </Panel>
      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-xl font-normal">Caption Card</h2>
          <div className="flex gap-2">
            <Button type="button" variant="outline" disabled={!captionText} onClick={onCopy}>
              <Clipboard className="h-4 w-4" />
              {copied ? "Copied" : "Copy"}
            </Button>
            {filePath ? (
              <Button asChild variant="outline">
                <a href={filePath} download>
                  <Download className="h-4 w-4" />
                  Download
                </a>
              </Button>
            ) : null}
          </div>
        </div>
        <article className="mt-4 max-h-[520px] overflow-auto rounded-md border border-border bg-background p-4">
          <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6">
            {captionText || "Select a draft asset with a text version."}
          </pre>
        </article>
      </Panel>
    </div>
  );
}

function LearnLane({
  summary,
  feedbackTarget,
  rating,
  comment,
  improvement,
  pending,
  error,
  onTarget,
  onRating,
  onComment,
  onImprovement,
  onSubmit,
}: {
  summary: string;
  feedbackTarget: string;
  rating: string;
  comment: string;
  improvement: string;
  pending: boolean;
  error: unknown;
  onTarget: (value: string) => void;
  onRating: (value: string) => void;
  onComment: (value: string) => void;
  onImprovement: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <div className="grid gap-4 p-4 xl:grid-cols-[1fr_420px]">
      <Panel>
        <h2 className="font-display text-xl font-normal">Learning Loop</h2>
        <p className="mt-4 whitespace-pre-line text-sm leading-6 text-muted-foreground">{summary || "No learning summary yet."}</p>
      </Panel>
      <Panel>
        <form className="space-y-4" onSubmit={onSubmit}>
          <div>
            <label htmlFor="feedback-target" className="text-sm font-medium">
              Output path
            </label>
            <input
              id="feedback-target"
              className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={feedbackTarget}
              onChange={(event) => onTarget(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="feedback-rating" className="text-sm font-medium">
              Rating
            </label>
            <select
              id="feedback-rating"
              className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={rating}
              onChange={(event) => onRating(event.target.value)}
            >
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="feedback-comment" className="text-sm font-medium">
              Comment
            </label>
            <textarea
              id="feedback-comment"
              className="mt-2 min-h-24 w-full rounded-md border border-input bg-background px-3 py-3 text-sm leading-6 outline-none focus:ring-2 focus:ring-ring"
              value={comment}
              onChange={(event) => onComment(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="feedback-improvement" className="text-sm font-medium">
              Improvement request
            </label>
            <textarea
              id="feedback-improvement"
              className="mt-2 min-h-24 w-full rounded-md border border-input bg-background px-3 py-3 text-sm leading-6 outline-none focus:ring-2 focus:ring-ring"
              value={improvement}
              onChange={(event) => onImprovement(event.target.value)}
            />
          </div>
          <Button type="submit" className="w-full" disabled={pending || (!comment.trim() && !improvement.trim())}>
            <Send className="h-4 w-4" />
            Save Feedback
          </Button>
          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error instanceof Error ? error.message : "Feedback could not be saved."}
            </p>
          ) : null}
        </form>
      </Panel>
    </div>
  );
}
