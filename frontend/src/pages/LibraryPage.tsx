import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  ChevronRight,
  FileText,
  Image,
  Loader2,
  PanelsTopLeft,
  RefreshCw,
  Search,
  Video,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader, Panel } from "@/components/ui/Panel";
import {
  api,
  createJobEventSource,
  type AssetDetailOut,
  type AssetOut,
  type AssetStatus,
  type AssetType,
  type AssetVersionOut,
  type JobOut,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 24;

const assetTypes: Array<{ value: "" | AssetType; label: string }> = [
  { value: "", label: "All types" },
  { value: "copy", label: "Copy" },
  { value: "image_concept", label: "Image Concept" },
  { value: "carousel", label: "Carousel" },
  { value: "video_script", label: "Video Script" },
  { value: "voiceover", label: "Voiceover" },
];

const statuses: Array<{ value: "" | AssetStatus; label: string }> = [
  { value: "", label: "All status" },
  { value: "draft", label: "Draft" },
  { value: "selected", label: "Selected" },
  { value: "archived", label: "Archived" },
];

function assetIcon(type: string) {
  if (type === "image_concept") return Image;
  if (type === "carousel") return PanelsTopLeft;
  if (type === "video_script") return Video;
  return FileText;
}

function formatType(type: string) {
  return type.replace("_", " ");
}

function assetAspect(type: string) {
  if (type === "video_script") return "aspect-[9/16]";
  if (type === "image_concept" || type === "carousel") return "aspect-[4/5]";
  return "aspect-[4/5]";
}

function selectedVersion(asset?: AssetDetailOut | null) {
  return asset?.versions.find((version) => version.is_selected) || asset?.versions[asset.versions.length - 1] || null;
}

export function LibraryPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [type, setType] = useState<"" | AssetType>("");
  const [status, setStatus] = useState<"" | AssetStatus>("");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [selectedAssetId, setSelectedAssetId] = useState<number | null>(null);
  const [regenJob, setRegenJob] = useState<JobOut | null>(null);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  const filters = useMemo(
    () => ({
      type,
      status,
      q: search.trim(),
      date_from: dateFrom,
      date_to: dateTo,
    }),
    [dateFrom, dateTo, search, status, type],
  );

  const assets = useInfiniteQuery({
    queryKey: ["assets", "library", filters],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      api.assets({
        type: filters.type,
        status: filters.status,
        q: filters.q,
        date_from: filters.date_from,
        date_to: filters.date_to,
        limit: PAGE_SIZE,
        offset: pageParam,
      }),
    getNextPageParam: (lastPage) => {
      const nextOffset = lastPage.offset + lastPage.items.length;
      return nextOffset < lastPage.total ? nextOffset : undefined;
    },
  });

  const items = assets.data?.pages.flatMap((page) => page.items) || [];
  const total = assets.data?.pages[0]?.total ?? 0;

  useEffect(() => {
    const assetId = Number(searchParams.get("asset"));
    if (Number.isInteger(assetId) && assetId > 0) {
      setSelectedAssetId(assetId);
    }
  }, [searchParams]);

  const detail = useQuery({
    queryKey: ["assets", selectedAssetId],
    queryFn: () => api.asset(selectedAssetId!),
    enabled: selectedAssetId !== null,
  });

  const selectVersion = useMutation({
    mutationFn: ({ assetId, versionNo }: { assetId: number; versionNo: number }) =>
      api.selectVersion(assetId, versionNo),
    onSuccess: (asset) => {
      queryClient.setQueryData(["assets", asset.id], asset);
      queryClient.invalidateQueries({ queryKey: ["assets", "library"] });
      queryClient.invalidateQueries({ queryKey: ["library"] });
    },
  });

  const regenerate = useMutation({
    mutationFn: (assetId: number) => api.regenerate(assetId),
    onSuccess: (response) => {
      setRegenJob({
        id: response.job_id,
        kind: "generate_asset",
        status: "queued",
        progress_pct: 0,
        message: "queued",
        payload_json: "{}",
        result_json: null,
        created_at: new Date().toISOString(),
        finished_at: null,
      });
    },
  });

  useEffect(() => {
    if (!regenJob || ["succeeded", "failed"].includes(regenJob.status)) {
      return;
    }
    const source = createJobEventSource(regenJob.id);
    const update = (event: MessageEvent<string>) => {
      const snapshot = JSON.parse(event.data) as JobOut;
      setRegenJob(snapshot);
      if (snapshot.status === "succeeded") {
        queryClient.invalidateQueries({ queryKey: ["assets", selectedAssetId] });
        queryClient.invalidateQueries({ queryKey: ["assets", "library"] });
      }
    };
    source.addEventListener("progress", update);
    source.addEventListener("completion", update);
    return () => source.close();
  }, [queryClient, regenJob?.id, regenJob?.status, selectedAssetId]);

  useEffect(() => {
    const node = loadMoreRef.current;
    if (!node || !assets.hasNextPage || assets.isFetchingNextPage) {
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting) {
        assets.fetchNextPage();
      }
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [assets]);

  function resetFilters() {
    setType("");
    setStatus("");
    setSearch("");
    setDateFrom("");
    setDateTo("");
  }

  return (
    <div>
      <PageHeader
        eyebrow="Assets"
        title="Library"
        actions={<Badge tone="ink">{total} assets</Badge>}
      />

      <section className="border-b border-border bg-surface px-4 py-4">
        <div className="grid gap-3 lg:grid-cols-[minmax(220px,1fr)_160px_160px_150px_150px_auto]">
          <label className="relative text-sm font-medium" htmlFor="library-search">
            <span className="sr-only">Search library</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              id="library-search"
              className="h-11 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm outline-none transition focus:ring-2 focus:ring-ring"
              placeholder="Search assets"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <label className="text-sm font-medium" htmlFor="library-type">
            <span className="sr-only">Type</span>
            <select
              id="library-type"
              className="h-11 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={type}
              onChange={(event) => setType(event.target.value as "" | AssetType)}
            >
              {assetTypes.map((item) => (
                <option key={item.value || "all"} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium" htmlFor="library-status">
            <span className="sr-only">Status</span>
            <select
              id="library-status"
              className="h-11 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={status}
              onChange={(event) => setStatus(event.target.value as "" | AssetStatus)}
            >
              {statuses.map((item) => (
                <option key={item.value || "all"} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium" htmlFor="date-from">
            <span className="sr-only">Date from</span>
            <input
              id="date-from"
              type="date"
              className="h-11 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
            />
          </label>
          <label className="text-sm font-medium" htmlFor="date-to">
            <span className="sr-only">Date to</span>
            <input
              id="date-to"
              type="date"
              className="h-11 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
            />
          </label>
          <Button type="button" variant="outline" onClick={resetFilters}>
            Reset
          </Button>
        </div>
      </section>

      <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {items.map((asset) => (
          <AssetCard
            key={asset.id}
            asset={asset}
            selected={selectedAssetId === asset.id}
            onOpen={() => {
              setSelectedAssetId(asset.id);
              setRegenJob(null);
            }}
          />
        ))}
        {assets.isLoading ? (
          Array.from({ length: 8 }, (_, index) => (
            <Panel key={index} className="h-44 animate-pulse bg-muted">
              <span className="sr-only">Loading asset</span>
            </Panel>
          ))
        ) : null}
        {!assets.isLoading && !items.length ? (
          <Panel className="md:col-span-2 xl:col-span-3 2xl:col-span-4">
            <p className="text-sm font-medium">No assets found.</p>
            <p className="mt-2 text-sm text-muted-foreground">Adjust filters or generate a new take in Playground.</p>
          </Panel>
        ) : null}
      </div>

      {assets.hasNextPage ? (
        <div className="flex justify-center px-4 pb-6">
          <div ref={loadMoreRef} className="h-1 w-1" aria-hidden="true" />
          <Button
            type="button"
            variant="outline"
            disabled={assets.isFetchingNextPage}
            onClick={() => assets.fetchNextPage()}
          >
            {assets.isFetchingNextPage ? <Loader2 className="h-4 w-4 animate-spin" /> : <ChevronRight className="h-4 w-4" />}
            Load more
          </Button>
        </div>
      ) : null}

      <AssetDrawer
        asset={detail.data || null}
        loading={detail.isLoading}
        open={selectedAssetId !== null}
        onClose={() => setSelectedAssetId(null)}
        onSelect={(assetId, versionNo) => selectVersion.mutate({ assetId, versionNo })}
        selectingVersion={selectVersion.variables?.versionNo}
        onRegenerate={(assetId) => regenerate.mutate(assetId)}
        regenerating={regenerate.isPending || ["queued", "running"].includes(regenJob?.status || "")}
        regenJob={regenJob}
      />
    </div>
  );
}

function AssetCard({
  asset,
  selected,
  onOpen,
}: {
  asset: AssetOut;
  selected: boolean;
  onOpen: () => void;
}) {
  const Icon = assetIcon(asset.type);
  return (
    <button
      type="button"
      className={cn(
        "rounded-lg border bg-surface p-3 text-left transition-colors duration-ui ease-ui hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected ? "border-accent bg-accent-soft" : "border-border",
      )}
      onClick={onOpen}
    >
      <div className={cn("flex flex-col justify-between rounded-md border border-border bg-muted p-3", assetAspect(asset.type))}>
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Icon className="h-5 w-5" />
        </span>
        <div>
          <h2 className="line-clamp-3 text-base font-semibold">{asset.title}</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge tone="ink">{formatType(asset.type)}</Badge>
            <Badge tone={asset.status === "selected" ? "success" : "neutral"}>{asset.status}</Badge>
          </div>
        </div>
      </div>
      <p className="mt-3 text-xs text-muted-foreground">{new Date(asset.created_at).toLocaleDateString()}</p>
    </button>
  );
}

function AssetDrawer({
  asset,
  loading,
  open,
  onClose,
  onSelect,
  selectingVersion,
  onRegenerate,
  regenerating,
  regenJob,
}: {
  asset: AssetDetailOut | null;
  loading: boolean;
  open: boolean;
  onClose: () => void;
  onSelect: (assetId: number, versionNo: number) => void;
  selectingVersion?: number;
  onRegenerate: (assetId: number) => void;
  regenerating: boolean;
  regenJob: JobOut | null;
}) {
  const chosen = selectedVersion(asset);
  return (
    <div className={cn("fixed inset-0 z-50", open ? "pointer-events-auto" : "pointer-events-none")}>
      <button
        type="button"
        aria-label="Close asset detail"
        className={cn("absolute inset-0 bg-ink/50 transition-opacity duration-ui ease-ui", open ? "opacity-100" : "opacity-0")}
        onClick={onClose}
      />
      <aside
        className={cn(
          "absolute right-0 top-0 flex h-full w-full max-w-4xl flex-col border-l border-border bg-background transition-transform duration-ui ease-ui",
          open ? "translate-x-0" : "translate-x-full",
        )}
        aria-label="Asset detail"
      >
        <div className="flex min-h-16 items-center justify-between gap-3 border-b border-border px-4">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Asset detail</p>
            <h2 className="truncate text-lg font-semibold">{asset?.title || "Loading asset"}</h2>
          </div>
          <Button type="button" variant="ghost" size="icon" aria-label="Close asset detail" onClick={onClose}>
            <X className="h-5 w-5" />
          </Button>
        </div>

        <div className="flex-1 overflow-auto p-4">
          {loading ? (
            <Panel className="h-64 animate-pulse bg-muted">
              <span className="sr-only">Loading asset detail</span>
            </Panel>
          ) : asset ? (
            <div className="space-y-4">
              <Panel className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div className="flex flex-wrap gap-2">
                  <Badge tone="ink">{formatType(asset.type)}</Badge>
                  <Badge tone={asset.status === "selected" ? "success" : "neutral"}>{asset.status}</Badge>
                  {chosen ? <Badge>Selected v{chosen.version_no}</Badge> : null}
                </div>
                <Button type="button" variant="outline" disabled={regenerating} onClick={() => onRegenerate(asset.id)}>
                  {regenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  Regenerate
                </Button>
              </Panel>

              {regenJob ? (
                <Panel>
                  <div className="flex items-center justify-between gap-4 text-sm">
                    <span className="font-medium">{regenJob.message || regenJob.status}</span>
                    <span className="font-mono">{regenJob.progress_pct}%</span>
                  </div>
                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full bg-accent" style={{ width: `${regenJob.progress_pct}%` }} />
                  </div>
                </Panel>
              ) : null}

              <div className="grid gap-4 xl:grid-cols-2">
                {asset.versions.map((version) => (
                  <VersionPanel
                    key={version.id}
                    version={version}
                    selected={version.is_selected}
                    selecting={selectingVersion === version.version_no}
                    onSelect={() => onSelect(asset.id, version.version_no)}
                  />
                ))}
              </div>
            </div>
          ) : (
            <Panel>
              <p className="text-sm text-muted-foreground">Select an asset to inspect versions.</p>
            </Panel>
          )}
        </div>
      </aside>
    </div>
  );
}

function VersionPanel({
  version,
  selected,
  selecting,
  onSelect,
}: {
  version: AssetVersionOut;
  selected: boolean;
  selecting: boolean;
  onSelect: () => void;
}) {
  return (
    <Panel className={cn("space-y-3", selected && "border-accent bg-accent-soft")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">Version {version.version_no}</h3>
            {selected ? (
              <Badge tone="success">
                <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
                Selected
              </Badge>
            ) : null}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {new Date(version.created_at).toLocaleString()} · {version.model_used || "unknown model"}
          </p>
        </div>
        <Button type="button" size="sm" variant={selected ? "subtle" : "outline"} disabled={selected || selecting} onClick={onSelect}>
          {selecting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          {selected ? "Selected" : "Select this take"}
        </Button>
      </div>
      <div className="max-h-80 overflow-auto rounded-md border border-border bg-background p-3">
        <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6">
          {version.content_text || version.file_path || "No text content for this version."}
        </pre>
      </div>
    </Panel>
  );
}
