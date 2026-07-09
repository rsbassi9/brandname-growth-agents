import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  CheckCircle2,
  Clipboard,
  Download,
  FileText,
  GraduationCap,
  Layers3,
  Send,
  Sparkles,
  Upload,
} from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader, Panel } from "@/components/ui/Panel";
import {
  api,
  type AssetOut,
  type BrandProfileHistoryOut,
  type PerformanceChannel,
  type PerformanceDashboardOut,
  type PublishedPostOut,
} from "@/lib/api";
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
  const [performanceChannel, setPerformanceChannel] = useState<PerformanceChannel>("instagram");
  const [performanceFile, setPerformanceFile] = useState<File | null>(null);
  const [performancePaste, setPerformancePaste] = useState("");
  const [performancePostId, setPerformancePostId] = useState("");
  const [performanceCalendarId, setPerformanceCalendarId] = useState("");

  const docs = useQuery({ queryKey: ["strategy", "docs"], queryFn: api.strategyDocs });
  const brandProfile = useQuery({ queryKey: ["strategy", "brand-profile"], queryFn: api.brandProfile });
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
  const performancePosts = useQuery({
    queryKey: ["performance", "posts", performanceChannel],
    queryFn: () => api.performancePosts({ channel: performanceChannel, limit: 20 }),
  });
  const performanceDashboard = useQuery({ queryKey: ["performance", "dashboard"], queryFn: api.performanceDashboard });

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
  const performanceImport = useMutation({
    mutationFn: () =>
      api.importPerformance({
        channel: performanceChannel,
        file: performanceFile,
        csv_text: performancePaste,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["performance", "posts"] });
      queryClient.invalidateQueries({ queryKey: ["performance", "dashboard"] });
    },
  });
  const linkPerformance = useMutation({
    mutationFn: () => api.linkPerformancePost(Number(performancePostId), { calendar_item_id: performanceCalendarId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["performance", "posts"] }),
  });
  const unlinkPerformance = useMutation({
    mutationFn: () => api.unlinkPerformancePost(Number(performancePostId)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["performance", "posts"] }),
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

  function submitPerformanceImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    performanceImport.mutate();
  }

  function submitPerformanceLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    linkPerformance.mutate();
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

      {lane === "know" ? (
        <KnowLane
          docs={docs.data || []}
          profile={brandProfile.data}
          loading={docs.isLoading || brandProfile.isLoading}
        />
      ) : null}
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
          performanceChannel={performanceChannel}
          performanceFile={performanceFile}
          performancePaste={performancePaste}
          performancePending={performanceImport.isPending}
          performanceResult={performanceImport.data}
          performanceError={performanceImport.error}
          performanceDashboard={performanceDashboard.data}
          performancePosts={performancePosts.data?.items || []}
          performancePostId={performancePostId}
          performanceCalendarId={performanceCalendarId}
          performanceLinkPending={linkPerformance.isPending || unlinkPerformance.isPending}
          performanceLinkError={linkPerformance.error || unlinkPerformance.error}
          onTarget={setFeedbackTarget}
          onRating={setRating}
          onComment={setComment}
          onImprovement={setImprovement}
          onSubmit={submitFeedback}
          onPerformanceChannel={setPerformanceChannel}
          onPerformanceFile={setPerformanceFile}
          onPerformancePaste={setPerformancePaste}
          onPerformanceSubmit={submitPerformanceImport}
          onPerformancePostId={setPerformancePostId}
          onPerformanceCalendarId={setPerformanceCalendarId}
          onPerformanceLinkSubmit={submitPerformanceLink}
          onPerformanceUnlink={() => unlinkPerformance.mutate()}
        />
      ) : null}
    </div>
  );
}

function BarRows({ title, rows }: { title: string; rows: Array<{ label: string; value: number; meta: string }> }) {
  const maxValue = Math.max(...rows.map((row) => row.value), 0.01);
  return (
    <div>
      <h4 className="text-xs font-semibold uppercase text-muted-foreground">{title}</h4>
      <div className="mt-2 space-y-2">
        {rows.length ? (
          rows.map((row) => (
            <div key={row.label} className="space-y-1">
              <div className="flex items-center justify-between gap-3 text-xs">
                <span className="font-medium">{row.label}</span>
                <span className="text-muted-foreground">
                  {formatPercent(row.value)} - {row.meta}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(4, (row.value / maxValue) * 100)}%` }} />
              </div>
            </div>
          ))
        ) : (
          <p className="text-xs text-muted-foreground">No data yet.</p>
        )}
      </div>
    </div>
  );
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function KnowLane({
  docs,
  profile,
  loading,
}: {
  docs: Array<{ name: string; content: string }>;
  profile?: BrandProfileHistoryOut;
  loading: boolean;
}) {
  return (
    <div className="space-y-4 p-4">
      <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
        <Panel>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-display text-xl font-normal">Brand Profile</h2>
            {profile?.current ? <Badge tone="ink">Profile v{profile.current.version_no}</Badge> : <Badge>Not distilled</Badge>}
          </div>
          <article className="mt-4 max-h-[480px] overflow-auto rounded-md border border-border bg-background p-4">
            <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6 text-foreground">
              {profile?.current?.profile_md || "No distilled profile yet."}
            </pre>
          </article>
        </Panel>
        <Panel>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-display text-xl font-normal">Version History</h2>
            <Badge>{profile?.versions.length || 0} versions</Badge>
          </div>
          <div className="mt-4 space-y-2">
            {profile?.versions.map((version, index) => {
              const previous = profile.versions[index + 1];
              const diff = profileDiff(version.profile_md, previous?.profile_md || "");
              return (
                <div key={version.id} className="rounded-md border border-border bg-background p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-semibold">v{version.version_no}</span>
                    <div className="flex gap-2">
                      <Badge tone="success">+{diff.added}</Badge>
                      <Badge tone="danger">-{diff.removed}</Badge>
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{new Date(version.created_at).toLocaleString()}</p>
                </div>
              );
            })}
            {!profile?.versions.length ? (
              <div className="rounded-md border border-dashed border-border p-3 text-sm text-muted-foreground">
                Distilled profiles will appear here after the scheduled job runs.
              </div>
            ) : null}
          </div>
        </Panel>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
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
    </div>
  );
}

function profileDiff(current: string, previous: string) {
  const currentLines = new Set(current.split("\n").map((line) => line.trim()).filter(Boolean));
  const previousLines = new Set(previous.split("\n").map((line) => line.trim()).filter(Boolean));
  let added = 0;
  let removed = 0;
  currentLines.forEach((line) => {
    if (!previousLines.has(line)) {
      added += 1;
    }
  });
  previousLines.forEach((line) => {
    if (!currentLines.has(line)) {
      removed += 1;
    }
  });
  return { added, removed };
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
  performanceChannel,
  performanceFile,
  performancePaste,
  performancePending,
  performanceResult,
  performanceError,
  performanceDashboard,
  performancePosts,
  performancePostId,
  performanceCalendarId,
  performanceLinkPending,
  performanceLinkError,
  onTarget,
  onRating,
  onComment,
  onImprovement,
  onSubmit,
  onPerformanceChannel,
  onPerformanceFile,
  onPerformancePaste,
  onPerformanceSubmit,
  onPerformancePostId,
  onPerformanceCalendarId,
  onPerformanceLinkSubmit,
  onPerformanceUnlink,
}: {
  summary: string;
  feedbackTarget: string;
  rating: string;
  comment: string;
  improvement: string;
  pending: boolean;
  error: unknown;
  performanceChannel: PerformanceChannel;
  performanceFile: File | null;
  performancePaste: string;
  performancePending: boolean;
  performanceResult?: {
    detected_columns: string[];
    posts_upserted: number;
    metrics_inserted: number;
    warnings: string[];
  };
  performanceError: unknown;
  performanceDashboard?: PerformanceDashboardOut;
  performancePosts: PublishedPostOut[];
  performancePostId: string;
  performanceCalendarId: string;
  performanceLinkPending: boolean;
  performanceLinkError: unknown;
  onTarget: (value: string) => void;
  onRating: (value: string) => void;
  onComment: (value: string) => void;
  onImprovement: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onPerformanceChannel: (value: PerformanceChannel) => void;
  onPerformanceFile: (value: File | null) => void;
  onPerformancePaste: (value: string) => void;
  onPerformanceSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onPerformancePostId: (value: string) => void;
  onPerformanceCalendarId: (value: string) => void;
  onPerformanceLinkSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onPerformanceUnlink: () => void;
}) {
  return (
    <div className="grid gap-4 p-4 xl:grid-cols-[1fr_420px]">
      <Panel>
        <h2 className="font-display text-xl font-normal">Learning Loop</h2>
        <p className="mt-4 whitespace-pre-line text-sm leading-6 text-muted-foreground">{summary || "No learning summary yet."}</p>
        <form className="mt-5 space-y-4 border-t border-border pt-4" onSubmit={onPerformanceSubmit}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-sm font-semibold">Performance</h3>
            <Badge>{performanceResult ? `${performanceResult.metrics_inserted} metrics` : "CSV import"}</Badge>
          </div>
          <p className="text-xs leading-5 text-muted-foreground">
            CSV sources: Meta Business Suite Insights Content Export; TikTok Studio Analytics Content Download.
          </p>
          <label className="text-sm font-medium" htmlFor="performance-channel">
            Channel
            <select
              id="performance-channel"
              className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={performanceChannel}
              onChange={(event) => onPerformanceChannel(event.target.value as PerformanceChannel)}
            >
              <option value="instagram">Instagram</option>
              <option value="tiktok">TikTok</option>
              <option value="facebook">Facebook</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label className="block text-sm font-medium" htmlFor="performance-file">
            CSV file
            <input
              id="performance-file"
              type="file"
              accept=".csv,text/csv"
              className="mt-2 block w-full rounded-md border border-input bg-background px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-muted file:px-3 file:py-2 file:text-sm file:font-medium"
              onChange={(event) => onPerformanceFile(event.target.files?.[0] || null)}
            />
          </label>
          <label className="block text-sm font-medium" htmlFor="performance-paste">
            Paste table
            <textarea
              id="performance-paste"
              className="mt-2 min-h-28 w-full rounded-md border border-input bg-background px-3 py-3 font-mono text-xs leading-5 outline-none focus:ring-2 focus:ring-ring"
              value={performancePaste}
              onChange={(event) => onPerformancePaste(event.target.value)}
            />
          </label>
          <Button type="submit" variant="outline" disabled={performancePending || (!performanceFile && !performancePaste.trim())}>
            <Upload className="h-4 w-4" />
            Import CSV
          </Button>
          {performanceFile ? <p className="text-xs text-muted-foreground">{performanceFile.name}</p> : null}
          {performanceResult ? (
            <div className="rounded-md border border-border bg-background p-3 text-sm">
              <div className="flex flex-wrap gap-2">
                <Badge tone="success">{performanceResult.posts_upserted} posts</Badge>
                <Badge tone="success">{performanceResult.metrics_inserted} metrics</Badge>
              </div>
              <p className="mt-3 text-xs text-muted-foreground">Detected: {performanceResult.detected_columns.join(", ")}</p>
              {performanceResult.warnings.length ? (
                <p className="mt-2 text-xs text-warning">{performanceResult.warnings.join(" ")}</p>
              ) : null}
            </div>
          ) : null}
          {performanceError ? (
            <p role="alert" className="text-sm text-danger">
              {performanceError instanceof Error ? performanceError.message : "Performance import failed."}
            </p>
          ) : null}
        </form>
        <div className="mt-4 space-y-4 border-t border-border pt-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-sm font-semibold">Dashboard</h3>
            <Badge>{performanceDashboard?.top_posts.length || 0} top posts</Badge>
          </div>
          <div className="overflow-hidden rounded-md border border-border bg-background">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-border bg-muted text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Post</th>
                  <th className="px-3 py-2 font-medium">Channel</th>
                  <th className="px-3 py-2 text-right font-medium">ER</th>
                </tr>
              </thead>
              <tbody>
                {(performanceDashboard?.top_posts || []).slice(0, 5).map((post) => (
                  <tr key={post.post_id} className="border-b border-border last:border-0">
                    <td className="px-3 py-2">{post.title_or_caption}</td>
                    <td className="px-3 py-2 capitalize">{post.channel}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatPercent(post.engagement_rate)}</td>
                  </tr>
                ))}
                {!performanceDashboard?.top_posts.length ? (
                  <tr>
                    <td className="px-3 py-3 text-muted-foreground" colSpan={3}>
                      Import metrics to populate top posts.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
          <BarRows
            title="Weekly ER"
            rows={(performanceDashboard?.weekly_trend || []).map((item) => ({
              label: item.week,
              value: item.mean_engagement_rate,
              meta: `${item.sample_size} posts`,
            }))}
          />
          <BarRows
            title="By Asset Type"
            rows={(performanceDashboard?.by_asset_type || []).map((item) => ({
              label: assetTypeLabel(item.asset_type),
              value: item.mean_engagement_rate,
              meta: `${item.sample_size} posts`,
            }))}
          />
        </div>
        <form className="mt-4 space-y-3 border-t border-border pt-4" onSubmit={onPerformanceLinkSubmit}>
          <h3 className="text-sm font-semibold">Manual links</h3>
          <label className="text-sm font-medium" htmlFor="performance-post">
            Published post
            <select
              id="performance-post"
              className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={performancePostId}
              onChange={(event) => onPerformancePostId(event.target.value)}
            >
              <option value="">Select post</option>
              {performancePosts.map((post) => (
                <option key={post.id} value={post.id}>
                  {(post.title_or_caption || post.external_ref || `Post ${post.id}`).slice(0, 80)}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium" htmlFor="performance-calendar-id">
            Calendar item id
            <input
              id="performance-calendar-id"
              className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={performanceCalendarId}
              onChange={(event) => onPerformanceCalendarId(event.target.value)}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant="outline" disabled={performanceLinkPending || !performancePostId || !performanceCalendarId.trim()}>
              Link
            </Button>
            <Button type="button" variant="ghost" disabled={performanceLinkPending || !performancePostId} onClick={onPerformanceUnlink}>
              Unlink
            </Button>
          </div>
          <div className="space-y-2">
            {performancePosts.slice(0, 4).map((post) => (
              <div key={post.id} className="rounded-md border border-border bg-background p-2 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{post.title_or_caption || post.external_ref || `Post ${post.id}`}</span>
                  <Badge>{post.calendar_item_id || "unlinked"}</Badge>
                </div>
              </div>
            ))}
          </div>
          {performanceLinkError ? (
            <p role="alert" className="text-sm text-danger">
              {performanceLinkError instanceof Error ? performanceLinkError.message : "Performance link failed."}
            </p>
          ) : null}
        </form>
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
