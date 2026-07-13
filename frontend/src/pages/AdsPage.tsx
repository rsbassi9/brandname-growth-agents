import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clipboard, Loader2, RectangleEllipsis, SearchCheck, Send } from "lucide-react";
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
  type SeoAuditOut,
  type SourceAssetOut,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type WorkspaceTab = "ads" | "seo";

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

interface SeoPlanPack {
  kind: "seo_plan";
  keyword_map: Array<{
    scope: "product" | "collection";
    handle: string;
    title: string;
    url: string;
    primary_keyword: string;
    secondary_keywords: string[];
  }>;
  blog_plan: Array<{
    title: string;
    target_keyword: string;
    outline: string[];
    internal_links: Array<{ label: string; url: string; handle: string }>;
  }>;
  manual_use: string;
}

const objectives = ["Sales", "Traffic", "Engagement", "Awareness"];
const placements = ["Instagram Feed + Reels", "Instagram Reels", "Facebook Feed", "Advantage+ placements"];

export function AdsPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<WorkspaceTab>("ads");
  const [objective, setObjective] = useState("Sales");
  const [audience, setAudience] = useState("Warm streetwear audience and recent site visitors");
  const [placement, setPlacement] = useState("Instagram Feed + Reels");
  const [hook, setHook] = useState("");
  const [brief, setBrief] = useState("");
  const [assetId, setAssetId] = useState("");
  const [sourceAssetId, setSourceAssetId] = useState("");
  const [activeAssetId, setActiveAssetId] = useState<number | null>(null);
  const [activeJob, setActiveJob] = useState<JobOut | null>(null);
  const [seoJob, setSeoJob] = useState<JobOut | null>(null);
  const [activeFixAssetId, setActiveFixAssetId] = useState<number | null>(null);
  const [activePlanAssetId, setActivePlanAssetId] = useState<number | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const assets = useQuery({ queryKey: ["assets", "ads-creative"], queryFn: () => api.assets({ limit: 100 }) });
  const sourceAssets = useQuery({ queryKey: ["source-assets", "ads"], queryFn: () => api.sourceAssets() });
  const activeAsset = useQuery({
    queryKey: ["assets", activeAssetId],
    queryFn: () => api.asset(activeAssetId!),
    enabled: activeAssetId !== null && activeJob?.status === "succeeded",
  });
  const audits = useQuery({ queryKey: ["seo", "audits"], queryFn: () => api.seoAudits({ limit: 100 }) });
  const planAssets = useQuery({ queryKey: ["assets", "seo-plan"], queryFn: () => api.assets({ type: "seo_plan", limit: 1 }) });
  const planAssetId = activePlanAssetId || planAssets.data?.items[0]?.id || null;
  const planAsset = useQuery({
    queryKey: ["assets", planAssetId],
    queryFn: () => api.asset(planAssetId!),
    enabled: planAssetId !== null,
  });
  const fixAsset = useQuery({
    queryKey: ["assets", activeFixAssetId],
    queryFn: () => api.asset(activeFixAssetId!),
    enabled: activeFixAssetId !== null && seoJob?.status === "succeeded",
  });

  const createBrief = useMutation({
    mutationFn: (payload: AdBriefRequest) => api.createAdBrief(payload),
    onSuccess: (response) => {
      setActiveAssetId(response.asset_id);
      setActiveJob(jobSnapshot(response.job_id, "generate_asset"));
    },
  });
  const runAudit = useMutation({
    mutationFn: api.runSeoAudit,
    onSuccess: (response) => setSeoJob(jobSnapshot(response.job_id, "seo_audit")),
  });
  const generateFix = useMutation({
    mutationFn: (auditId: number) => api.generateSeoFix(auditId),
    onSuccess: (response) => {
      setActiveFixAssetId(response.asset_id);
      setSeoJob(jobSnapshot(response.job_id, "seo_fix"));
    },
  });
  const generatePlan = useMutation({
    mutationFn: api.generateSeoPlan,
    onSuccess: (response) => {
      setActivePlanAssetId(response.asset_id);
      setSeoJob(jobSnapshot(response.job_id, "seo_plan"));
    },
  });

  useJobStream(activeJob, (snapshot) => {
    setActiveJob(snapshot);
    if (snapshot.status === "succeeded") {
      queryClient.invalidateQueries({ queryKey: ["assets", activeAssetId] });
      queryClient.invalidateQueries({ queryKey: ["assets"] });
    }
  });
  useJobStream(seoJob, (snapshot) => {
    setSeoJob(snapshot);
    if (snapshot.status === "succeeded") {
      queryClient.invalidateQueries({ queryKey: ["seo"] });
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      queryClient.invalidateQueries({ queryKey: ["assets", activeFixAssetId] });
      queryClient.invalidateQueries({ queryKey: ["assets", activePlanAssetId] });
    }
  });

  const pack = useMemo(() => parseAdBrief(activeAsset.data), [activeAsset.data]);
  const seoFix = useMemo(() => selectedVersionText(fixAsset.data), [fixAsset.data]);
  const seoPlan = useMemo(() => parseSeoPlan(planAsset.data), [planAsset.data]);
  const busy = createBrief.isPending || ["queued", "running"].includes(activeJob?.status || "");
  const seoBusy = runAudit.isPending || generateFix.isPending || generatePlan.isPending || ["queued", "running"].includes(seoJob?.status || "");

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

  async function copyBlock(key: string, text: string) {
    await navigator.clipboard?.writeText(text);
    setCopied(key);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Briefs"
        title="Ads & SEO"
        actions={
          tab === "ads" ? (
            <Button type="submit" form="ad-brief-form" disabled={busy || !hook.trim()}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Create Brief
            </Button>
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" disabled={seoBusy} onClick={() => runAudit.mutate()}>
                {runAudit.isPending || seoJob?.kind === "seo_audit" && seoBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <SearchCheck className="h-4 w-4" />}
                Run Audit
              </Button>
              <Button type="button" disabled={seoBusy} onClick={() => generatePlan.mutate()}>
                {generatePlan.isPending || seoJob?.kind === "seo_plan" && seoBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Generate Plan
              </Button>
            </div>
          )
        }
      />

      <div className="border-b border-border px-4 pt-4">
        <div className="flex w-full max-w-md rounded-md border border-border bg-surface p-1">
          <Button type="button" size="sm" variant={tab === "ads" ? "default" : "ghost"} aria-pressed={tab === "ads"} className="flex-1" onClick={() => setTab("ads")}>
            Ads
          </Button>
          <Button type="button" size="sm" variant={tab === "seo" ? "default" : "ghost"} aria-pressed={tab === "seo"} className="flex-1" onClick={() => setTab("seo")}>
            SEO
          </Button>
        </div>
      </div>

      {tab === "ads" ? (
        <AdsWorkspace
          objective={objective}
          audience={audience}
          placement={placement}
          hook={hook}
          brief={brief}
          assetId={assetId}
          sourceAssetId={sourceAssetId}
          assets={assets.data?.items || []}
          sourceAssets={sourceAssets.data?.items || []}
          activeJob={activeJob}
          busy={busy}
          pack={pack}
          copied={copied}
          error={createBrief.error}
          onSubmit={submit}
          onObjective={setObjective}
          onAudience={setAudience}
          onPlacement={setPlacement}
          onHook={setHook}
          onBrief={setBrief}
          onAsset={setAssetId}
          onSourceAsset={setSourceAssetId}
          onCopy={copyBlock}
        />
      ) : (
        <SeoWorkspace
          audits={audits.data || []}
          loadingAudits={audits.isLoading}
          seoJob={seoJob}
          seoBusy={seoBusy}
          generatingFix={generateFix.isPending}
          fixText={seoFix}
          plan={seoPlan}
          copied={copied}
          onGenerateFix={(auditId) => generateFix.mutate(auditId)}
          onCopy={copyBlock}
        />
      )}
    </div>
  );
}

function AdsWorkspace({
  objective,
  audience,
  placement,
  hook,
  brief,
  assetId,
  sourceAssetId,
  assets,
  sourceAssets,
  activeJob,
  busy,
  pack,
  copied,
  error,
  onSubmit,
  onObjective,
  onAudience,
  onPlacement,
  onHook,
  onBrief,
  onAsset,
  onSourceAsset,
  onCopy,
}: {
  objective: string;
  audience: string;
  placement: string;
  hook: string;
  brief: string;
  assetId: string;
  sourceAssetId: string;
  assets: AssetOut[];
  sourceAssets: SourceAssetOut[];
  activeJob: JobOut | null;
  busy: boolean;
  pack: AdBriefPack | null;
  copied: string | null;
  error: unknown;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onObjective: (value: string) => void;
  onAudience: (value: string) => void;
  onPlacement: (value: string) => void;
  onHook: (value: string) => void;
  onBrief: (value: string) => void;
  onAsset: (value: string) => void;
  onSourceAsset: (value: string) => void;
  onCopy: (key: string, text: string) => void;
}) {
  return (
    <div className="grid gap-4 p-4 xl:grid-cols-[420px_1fr]">
      <Panel>
        <form id="ad-brief-form" className="space-y-4" onSubmit={onSubmit}>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-medium" htmlFor="ad-objective">
              Objective
              <select id="ad-objective" className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm" value={objective} onChange={(event) => onObjective(event.target.value)}>
                {objectives.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-medium" htmlFor="ad-placement">
              Placement
              <select id="ad-placement" className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm" value={placement} onChange={(event) => onPlacement(event.target.value)}>
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
            <input id="ad-audience" className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition focus:ring-2 focus:ring-ring" value={audience} onChange={(event) => onAudience(event.target.value)} />
          </div>

          <div>
            <label className="text-sm font-medium" htmlFor="ad-hook">
              Hook
            </label>
            <input id="ad-hook" className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition focus:ring-2 focus:ring-ring" placeholder="Lead angle for this Meta test" value={hook} onChange={(event) => onHook(event.target.value)} />
          </div>

          <div>
            <label className="text-sm font-medium" htmlFor="ad-brief">
              Brief
            </label>
            <textarea id="ad-brief" className="mt-2 min-h-28 w-full rounded-md border border-input bg-background px-3 py-3 text-sm leading-6 outline-none transition focus:ring-2 focus:ring-ring" placeholder="Offer, product truth, proof points, constraints" value={brief} onChange={(event) => onBrief(event.target.value)} />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <CreativeSelect id="linked-asset" label="Library asset" value={assetId} assets={assets} onChange={onAsset} />
            <SourceSelect id="linked-source" label="Source photo" value={sourceAssetId} sources={sourceAssets} onChange={onSourceAsset} />
          </div>

          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error instanceof Error ? error.message : "Ad brief could not be created."}
            </p>
          ) : null}
        </form>
      </Panel>

      <section className="min-w-0 space-y-4">
        {activeJob && activeJob.status !== "succeeded" ? <JobProgress job={activeJob} /> : null}

        {pack ? (
          <AdBriefView pack={pack} copied={copied} onCopy={onCopy} />
        ) : (
          <Panel className="min-h-96">
            <div className="flex min-h-80 items-center justify-center rounded-md border border-dashed border-border bg-muted/40">
              <div className="text-center">
                <RectangleEllipsis className="mx-auto h-8 w-8 text-muted-foreground" aria-hidden="true" />
                <p className="mt-3 text-sm font-medium">Ready for a Meta brief</p>
                <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">Create structured copy blocks for manual entry into Meta Ads Manager.</p>
              </div>
            </div>
          </Panel>
        )}
      </section>
    </div>
  );
}

function SeoWorkspace({
  audits,
  loadingAudits,
  seoJob,
  seoBusy,
  generatingFix,
  fixText,
  plan,
  copied,
  onGenerateFix,
  onCopy,
}: {
  audits: SeoAuditOut[];
  loadingAudits: boolean;
  seoJob: JobOut | null;
  seoBusy: boolean;
  generatingFix: boolean;
  fixText: string | null;
  plan: SeoPlanPack | null;
  copied: string | null;
  onGenerateFix: (auditId: number) => void;
  onCopy: (key: string, text: string) => void;
}) {
  return (
    <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_420px]">
      <section className="min-w-0 space-y-4">
        {seoJob && seoJob.status !== "succeeded" ? <JobProgress job={seoJob} /> : null}
        <Panel>
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="font-display text-xl font-normal">Catalog Audit</h2>
              <p className="mt-1 text-sm text-muted-foreground">{loadingAudits ? "Loading audits" : `${audits.length} audited products`}</p>
            </div>
            <Badge tone="warning">Read only</Badge>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b border-border text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="py-2 pr-3 font-medium">Product</th>
                  <th className="py-2 pr-3 font-medium">Score</th>
                  <th className="py-2 pr-3 font-medium">Issues</th>
                  <th className="py-2 pr-0 text-right font-medium">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {audits.map((audit) => (
                  <tr key={audit.id}>
                    <td className="py-3 pr-3 font-medium">{audit.product_handle}</td>
                    <td className="py-3 pr-3">
                      <Badge tone={audit.score >= 80 ? "success" : audit.score >= 50 ? "warning" : "danger"}>{audit.score}</Badge>
                    </td>
                    <td className="py-3 pr-3">
                      <div className="flex flex-wrap gap-1.5">
                        {auditIssues(audit).map((issue) => (
                          <Badge key={issue}>{issue}</Badge>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 pr-0 text-right">
                      <Button type="button" size="sm" variant="outline" disabled={seoBusy} onClick={() => onGenerateFix(audit.id)}>
                        {generatingFix ? <Loader2 className="h-4 w-4 animate-spin" /> : <Clipboard className="h-4 w-4" />}
                        Generate Fix
                      </Button>
                    </td>
                  </tr>
                ))}
                {!loadingAudits && !audits.length ? (
                  <tr>
                    <td className="py-8 text-center text-muted-foreground" colSpan={4}>
                      Run an audit to populate product scores.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </Panel>

        <SeoPlanView plan={plan} copied={copied} onCopy={onCopy} />
      </section>

      <aside className="space-y-4">
        <Panel>
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-display text-xl font-normal">Fix Detail</h2>
            <Badge>Manual copy</Badge>
          </div>
          {fixText ? (
            <div className="mt-4 space-y-3">
              <Button type="button" size="sm" variant="outline" onClick={() => onCopy("seo-fix", fixText)}>
                {copied === "seo-fix" ? <CheckCircle2 className="h-4 w-4" /> : <Clipboard className="h-4 w-4" />}
                Copy Fix
              </Button>
              <pre className="max-h-[36rem] overflow-auto whitespace-pre-wrap break-words rounded-md border border-border bg-muted p-3 font-sans text-sm leading-6">{fixText}</pre>
            </div>
          ) : (
            <div className="mt-4 rounded-md border border-dashed border-border bg-muted/40 p-6 text-sm leading-6 text-muted-foreground">Generate a fix from an audit row to review copy-ready title, meta description, and alt text blocks here.</div>
          )}
        </Panel>
      </aside>
    </div>
  );
}

function SeoPlanView({ plan, copied, onCopy }: { plan: SeoPlanPack | null; copied: string | null; onCopy: (key: string, text: string) => void }) {
  if (!plan) {
    return (
      <Panel>
        <div className="rounded-md border border-dashed border-border bg-muted/40 p-6 text-sm leading-6 text-muted-foreground">Generate a keyword plan to see product keywords, collection targets, blog outlines, and internal links.</div>
      </Panel>
    );
  }
  const raw = JSON.stringify(plan, null, 2);
  return (
    <Panel>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-xl font-normal">Keyword & Content Plan</h2>
          <p className="mt-1 text-sm text-muted-foreground">{plan.keyword_map.length} keyword targets, {plan.blog_plan.length} blog briefs</p>
        </div>
        <Button type="button" size="sm" variant="outline" onClick={() => onCopy("seo-plan", raw)}>
          {copied === "seo-plan" ? <CheckCircle2 className="h-4 w-4" /> : <Clipboard className="h-4 w-4" />}
          Copy Plan
        </Button>
      </div>
      <div className="mt-4 grid gap-4 2xl:grid-cols-2">
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Keyword Map</h3>
          <div className="max-h-96 overflow-auto rounded-md border border-border">
            {plan.keyword_map.map((row) => (
              <div key={`${row.scope}-${row.handle}`} className="border-b border-border p-3 last:border-b-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={row.scope === "product" ? "ink" : "neutral"}>{row.scope}</Badge>
                  <span className="text-sm font-medium">{row.title}</span>
                </div>
                <p className="mt-2 text-sm">{row.primary_keyword}</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">{row.secondary_keywords.join(", ")}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Blog Plan</h3>
          <div className="space-y-3">
            {plan.blog_plan.map((post) => (
              <article key={post.title} className="rounded-md border border-border bg-background p-3">
                <Badge>{post.target_keyword}</Badge>
                <h4 className="mt-2 text-sm font-medium">{post.title}</h4>
                <ul className="mt-2 list-disc space-y-1 pl-4 text-sm leading-6 text-muted-foreground">
                  {post.outline.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                <div className="mt-2 flex flex-wrap gap-2">
                  {post.internal_links.map((link) => (
                    <Badge key={link.url}>{link.handle || link.label}</Badge>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </div>
      </div>
    </Panel>
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
      <select id={id} className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)}>
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
      <select id={id} className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)}>
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
  copied: string | null;
  onCopy: (key: string, text: string) => void;
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
        <p className="mt-3 rounded-md border border-border bg-muted p-3 text-sm leading-6">{pack.recommended_creative}</p>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-3">
        {pack.manual_export_blocks.map((block, index) => {
          const key = `ad-${index}`;
          return (
            <Panel key={key} className={cn("flex min-h-72 flex-col gap-3", copied === key && "border-accent bg-accent-soft")}>
              <div className="flex items-center justify-between gap-3">
                <Badge>Variant {index + 1}</Badge>
                <Button type="button" size="sm" variant="outline" onClick={() => onCopy(key, block)}>
                  {copied === key ? <CheckCircle2 className="h-4 w-4" /> : <Clipboard className="h-4 w-4" />}
                  Copy
                </Button>
              </div>
              <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6">{block}</pre>
            </Panel>
          );
        })}
      </div>
    </div>
  );
}

function JobProgress({ job }: { job: JobOut }) {
  return (
    <Panel>
      <div className="flex items-center justify-between gap-4 text-sm">
        <span className="font-medium">{job.message || job.status}</span>
        <span className="font-mono">{job.progress_pct}%</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-accent" style={{ width: `${job.progress_pct}%` }} />
      </div>
    </Panel>
  );
}

function useJobStream(job: JobOut | null, onUpdate: (snapshot: JobOut) => void) {
  useEffect(() => {
    if (!job || ["succeeded", "failed"].includes(job.status)) {
      return;
    }
    const source = createJobEventSource(job.id);
    const update = (event: MessageEvent<string>) => onUpdate(JSON.parse(event.data) as JobOut);
    source.addEventListener("progress", update);
    source.addEventListener("completion", update);
    return () => source.close();
  }, [job?.id, job?.status]);
}

function jobSnapshot(id: string, kind: string): JobOut {
  return {
    id,
    kind,
    status: "queued",
    progress_pct: 0,
    message: "queued",
    payload_json: "{}",
    result_json: null,
    created_at: new Date().toISOString(),
    finished_at: null,
  };
}

function parseAdBrief(asset?: AssetDetailOut | null): AdBriefPack | null {
  const version = selectedVersion(asset);
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

function parseSeoPlan(asset?: AssetDetailOut | null): SeoPlanPack | null {
  const version = selectedVersion(asset);
  if (!version?.content_text) {
    return null;
  }
  try {
    const parsed = JSON.parse(version.content_text) as SeoPlanPack;
    return parsed.kind === "seo_plan" ? parsed : null;
  } catch {
    return null;
  }
}

function selectedVersionText(asset?: AssetDetailOut | null) {
  return selectedVersion(asset)?.content_text || null;
}

function selectedVersion(asset?: AssetDetailOut | null) {
  return asset?.versions.find((item) => item.is_selected) || asset?.versions[asset.versions.length - 1];
}

function auditIssues(audit: SeoAuditOut) {
  try {
    const parsed = JSON.parse(audit.issues_json) as unknown;
    return Array.isArray(parsed) ? parsed.map((item) => String(item)) : [];
  } catch {
    return [];
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
