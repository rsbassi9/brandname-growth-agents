import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clipboard, Loader2, RectangleEllipsis, Send } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader, Panel } from "@/components/ui/Panel";
import {
  api,
  createJobEventSource,
  type AdBriefRequest,
  type AssetDetailOut,
  type AssetOut,
  type JobOut,
  type SourceAssetOut,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface AdBriefPack {
  kind: "ad_brief";
  objective: string;
  audience: string;
  placement: string;
  hook: string;
  primary_text: string[];
  headlines: string[];
  cta: string;
  recommended_creative: string;
  manual_export_blocks: string[];
}

const objectives = ["Sales", "Traffic", "Engagement", "Awareness"];
const placements = ["Instagram Feed + Reels", "Instagram Reels", "Facebook Feed", "Advantage+ placements"];

export function AdsPage() {
  const queryClient = useQueryClient();
  const [objective, setObjective] = useState("Sales");
  const [audience, setAudience] = useState("Warm streetwear audience and recent site visitors");
  const [placement, setPlacement] = useState("Instagram Feed + Reels");
  const [hook, setHook] = useState("");
  const [brief, setBrief] = useState("");
  const [assetId, setAssetId] = useState("");
  const [sourceAssetId, setSourceAssetId] = useState("");
  const [activeAssetId, setActiveAssetId] = useState<number | null>(null);
  const [activeJob, setActiveJob] = useState<JobOut | null>(null);
  const [copied, setCopied] = useState<number | null>(null);

  const assets = useQuery({ queryKey: ["assets", "ads-creative"], queryFn: () => api.assets({ limit: 100 }) });
  const sourceAssets = useQuery({ queryKey: ["source-assets", "ads"], queryFn: () => api.sourceAssets() });
  const activeAsset = useQuery({
    queryKey: ["assets", activeAssetId],
    queryFn: () => api.asset(activeAssetId!),
    enabled: activeAssetId !== null && activeJob?.status === "succeeded",
  });

  const createBrief = useMutation({
    mutationFn: (payload: AdBriefRequest) => api.createAdBrief(payload),
    onSuccess: (response) => {
      setActiveAssetId(response.asset_id);
      setActiveJob({
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
      }
    };
    source.addEventListener("progress", update);
    source.addEventListener("completion", update);
    return () => source.close();
  }, [activeAssetId, activeJob?.id, activeJob?.status, queryClient]);

  const pack = useMemo(() => parseAdBrief(activeAsset.data), [activeAsset.data]);
  const busy = createBrief.isPending || ["queued", "running"].includes(activeJob?.status || "");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createBrief.mutate({
      objective,
      audience,
      placement,
      hook,
      brief,
      asset_id: assetId ? Number(assetId) : null,
      source_asset_id: sourceAssetId ? Number(sourceAssetId) : null,
    });
  }

  async function copyBlock(index: number, text: string) {
    await navigator.clipboard?.writeText(text);
    setCopied(index);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Briefs"
        title="Ads"
        actions={
          <Button type="submit" form="ad-brief-form" disabled={busy || !hook.trim()}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            Create Brief
          </Button>
        }
      />

      <div className="grid gap-4 p-4 xl:grid-cols-[420px_1fr]">
        <Panel>
          <form id="ad-brief-form" className="space-y-4" onSubmit={submit}>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm font-medium" htmlFor="ad-objective">
                Objective
                <select
                  id="ad-objective"
                  className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={objective}
                  onChange={(event) => setObjective(event.target.value)}
                >
                  {objectives.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-medium" htmlFor="ad-placement">
                Placement
                <select
                  id="ad-placement"
                  className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={placement}
                  onChange={(event) => setPlacement(event.target.value)}
                >
                  {placements.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div>
              <label className="text-sm font-medium" htmlFor="ad-audience">
                Audience
              </label>
              <input
                id="ad-audience"
                className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition focus:ring-2 focus:ring-ring"
                value={audience}
                onChange={(event) => setAudience(event.target.value)}
              />
            </div>

            <div>
              <label className="text-sm font-medium" htmlFor="ad-hook">
                Hook
              </label>
              <input
                id="ad-hook"
                className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition focus:ring-2 focus:ring-ring"
                placeholder="Lead angle for this Meta test"
                value={hook}
                onChange={(event) => setHook(event.target.value)}
              />
            </div>

            <div>
              <label className="text-sm font-medium" htmlFor="ad-brief">
                Brief
              </label>
              <textarea
                id="ad-brief"
                className="mt-2 min-h-28 w-full rounded-md border border-input bg-background px-3 py-3 text-sm leading-6 outline-none transition focus:ring-2 focus:ring-ring"
                placeholder="Offer, product truth, proof points, constraints"
                value={brief}
                onChange={(event) => setBrief(event.target.value)}
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <CreativeSelect
                id="linked-asset"
                label="Library asset"
                value={assetId}
                assets={assets.data?.items || []}
                onChange={setAssetId}
              />
              <SourceSelect
                id="linked-source"
                label="Source photo"
                value={sourceAssetId}
                sources={sourceAssets.data?.items || []}
                onChange={setSourceAssetId}
              />
            </div>

            {createBrief.error ? (
              <p role="alert" className="text-sm text-danger">
                {createBrief.error instanceof Error ? createBrief.error.message : "Ad brief could not be created."}
              </p>
            ) : null}
          </form>
        </Panel>

        <section className="min-w-0 space-y-4">
          {activeJob && activeJob.status !== "succeeded" ? (
            <Panel>
              <div className="flex items-center justify-between gap-4 text-sm">
                <span className="font-medium">{activeJob.message || activeJob.status}</span>
                <span className="font-mono">{activeJob.progress_pct}%</span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-accent" style={{ width: `${activeJob.progress_pct}%` }} />
              </div>
            </Panel>
          ) : null}

          {pack ? (
            <AdBriefView pack={pack} copied={copied} onCopy={copyBlock} />
          ) : (
            <Panel className="min-h-96">
              <div className="flex min-h-80 items-center justify-center rounded-md border border-dashed border-border bg-muted/40">
                <div className="text-center">
                  <RectangleEllipsis className="mx-auto h-8 w-8 text-muted-foreground" aria-hidden="true" />
                  <p className="mt-3 text-sm font-medium">Ready for a Meta brief</p>
                  <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
                    Create structured copy blocks for manual entry into Meta Ads Manager.
                  </p>
                </div>
              </div>
            </Panel>
          )}
        </section>
      </div>
    </div>
  );
}

function CreativeSelect({
  id,
  label,
  value,
  assets,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  assets: AssetOut[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-sm font-medium" htmlFor={id}>
      {label}
      <select
        id={id}
        className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">None</option>
        {assets.map((asset) => (
          <option key={asset.id} value={asset.id}>
            {asset.title}
          </option>
        ))}
      </select>
    </label>
  );
}

function SourceSelect({
  id,
  label,
  value,
  sources,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  sources: SourceAssetOut[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-sm font-medium" htmlFor={id}>
      {label}
      <select
        id={id}
        className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">None</option>
        {sources.map((source) => (
          <option key={source.id} value={source.id}>
            {sourceName(source)}
          </option>
        ))}
      </select>
    </label>
  );
}

function AdBriefView({
  pack,
  copied,
  onCopy,
}: {
  pack: AdBriefPack;
  copied: number | null;
  onCopy: (index: number, text: string) => void;
}) {
  return (
    <div className="space-y-4">
      <Panel>
        <div className="flex flex-wrap gap-2">
          <Badge tone="ink">{pack.objective}</Badge>
          <Badge>{pack.placement}</Badge>
          <Badge>{pack.cta}</Badge>
        </div>
        <h2 className="mt-4 font-display text-xl font-normal">{pack.hook}</h2>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">{pack.audience}</p>
        <p className="mt-3 rounded-md border border-border bg-muted p-3 text-sm leading-6">
          {pack.recommended_creative}
        </p>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-3">
        {pack.manual_export_blocks.map((block, index) => (
          <Panel key={index} className={cn("flex min-h-72 flex-col gap-3", copied === index && "border-accent bg-accent-soft")}>
            <div className="flex items-center justify-between gap-3">
              <Badge>Variant {index + 1}</Badge>
              <Button type="button" size="sm" variant="outline" onClick={() => onCopy(index, block)}>
                {copied === index ? <CheckCircle2 className="h-4 w-4" /> : <Clipboard className="h-4 w-4" />}
                Copy
              </Button>
            </div>
            <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6">{block}</pre>
          </Panel>
        ))}
      </div>
    </div>
  );
}

function parseAdBrief(asset?: AssetDetailOut | null): AdBriefPack | null {
  const version = asset?.versions.find((item) => item.is_selected) || asset?.versions[asset.versions.length - 1];
  if (!version?.content_text) {
    return null;
  }
  try {
    const parsed = JSON.parse(version.content_text) as AdBriefPack;
    return parsed.kind === "ad_brief" ? parsed : null;
  } catch {
    return null;
  }
}

function sourceName(source: SourceAssetOut) {
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(source.path)) {
    try {
      const url = new URL(source.path);
      return url.pathname.split("/").filter(Boolean).pop() || source.path;
    } catch {
      return source.path;
    }
  }
  return source.path.split(/[\\/]/).filter(Boolean).pop() || source.path;
}
