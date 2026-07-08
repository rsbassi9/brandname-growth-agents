import { Clock3, ExternalLink, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader, Panel } from "@/components/ui/Panel";
import { api } from "@/lib/api";

export function SystemPage() {
  const queryClient = useQueryClient();
  const mode = useQuery({ queryKey: ["system", "mode"], queryFn: api.mode });
  const health = useQuery({ queryKey: ["system", "health"], queryFn: api.health });
  const schedule = useQuery({ queryKey: ["system", "daily-workflow"], queryFn: api.dailyWorkflowSchedule });
  const runs = useQuery({
    queryKey: ["system", "daily-workflow", "runs"],
    queryFn: api.dailyWorkflowRuns,
    refetchInterval: (query) =>
      query.state.data?.some((run) => run.status === "queued" || run.status === "running") ? 1500 : false,
  });
  const [enabled, setEnabled] = useState(false);
  const [timeLocal, setTimeLocal] = useState("09:00");
  const [lastJobId, setLastJobId] = useState("");

  useEffect(() => {
    if (schedule.data) {
      setEnabled(schedule.data.enabled);
      setTimeLocal(schedule.data.time_local);
    }
  }, [schedule.data]);

  const updateSchedule = useMutation({
    mutationFn: api.updateDailyWorkflowSchedule,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["system", "daily-workflow"] }),
  });

  const runWorkflow = useMutation({
    mutationFn: api.runDailyWorkflow,
    onSuccess: (result) => {
      setLastJobId(result.job_id);
      queryClient.invalidateQueries({ queryKey: ["system", "daily-workflow"] });
      queryClient.invalidateQueries({ queryKey: ["system", "daily-workflow", "runs"] });
    },
  });

  const scheduleDirty = Boolean(schedule.data && (enabled !== schedule.data.enabled || timeLocal !== schedule.data.time_local));

  return (
    <div>
      <PageHeader eyebrow="Runtime" title="System" />
      <div className="grid gap-4 p-4 lg:grid-cols-2">
        <Panel>
          <h2 className="text-base font-semibold">Health</h2>
          <div className="mt-4 flex items-center gap-2">
            <Badge tone={health.data?.status === "ok" ? "success" : "warning"}>{health.data?.status || "unknown"}</Badge>
            <span className="text-sm text-muted-foreground">{health.data?.brand}</span>
          </div>
        </Panel>
        <Panel>
          <h2 className="text-base font-semibold">Model Policy</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Default</dt>
              <dd className="font-mono">{mode.data?.model_default || "-"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Premium</dt>
              <dd className="font-mono">{mode.data?.model_premium || "Not set"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Image</dt>
              <dd className="font-mono">{mode.data?.image_model || "-"}</dd>
            </div>
          </dl>
        </Panel>
        <Panel className="lg:col-span-2">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Clock3 className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
                <h2 className="text-base font-semibold">Daily Workflow</h2>
              </div>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                Runs the in-app growth workflow through the job queue. Scheduled runs are off until enabled; manual runs create
                draft Library assets from the generated workflow outputs.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge tone={schedule.data?.enabled ? "success" : "neutral"}>
                  {schedule.data?.enabled ? "Scheduled" : "Off"}
                </Badge>
                <Badge tone="neutral">Last run {schedule.data?.last_enqueued_date || "Never"}</Badge>
              </div>
            </div>
            <Button
              type="button"
              variant="outline"
              disabled={runWorkflow.isPending}
              onClick={() => runWorkflow.mutate()}
            >
              <Play className="h-4 w-4" aria-hidden="true" />
              {runWorkflow.isPending ? "Starting" : "Run now"}
            </Button>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
            <label className="flex min-h-11 items-center gap-3 rounded-md border border-border bg-background px-3 text-sm font-medium">
              <input
                type="checkbox"
                className="h-4 w-4 accent-accent"
                checked={enabled}
                onChange={(event) => setEnabled(event.target.checked)}
              />
              Enable daily schedule
            </label>
            <label className="grid gap-2 text-sm font-medium">
              Local time
              <input
                type="time"
                value={timeLocal}
                onChange={(event) => setTimeLocal(event.target.value)}
                className="h-11 rounded-md border border-border bg-background px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </label>
            <div className="md:col-span-2 flex flex-wrap items-center gap-3">
              <Button
                type="button"
                disabled={!scheduleDirty || updateSchedule.isPending}
                onClick={() => updateSchedule.mutate({ enabled, time_local: timeLocal })}
              >
                {updateSchedule.isPending ? "Saving" : "Save schedule"}
              </Button>
              {lastJobId ? <p className="text-sm text-muted-foreground">Started job {lastJobId}</p> : null}
              {updateSchedule.isError ? <p className="text-sm text-danger">Schedule could not be saved.</p> : null}
              {runWorkflow.isError ? <p className="text-sm text-danger">Workflow could not be started.</p> : null}
            </div>
          </div>
        </Panel>
        <Panel className="lg:col-span-2">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-base font-semibold">Workflow Runs</h2>
              <p className="mt-1 text-sm text-muted-foreground">Recent daily workflow jobs and their created Library assets.</p>
            </div>
            <Badge tone="neutral">{runs.data?.length || 0} runs</Badge>
          </div>

          <div className="mt-4 space-y-3">
            {runs.isLoading ? (
              Array.from({ length: 3 }, (_, index) => (
                <div key={index} className="h-24 animate-pulse rounded-md border border-border bg-muted">
                  <span className="sr-only">Loading workflow run</span>
                </div>
              ))
            ) : runs.data?.length ? (
              runs.data.map((run) => <WorkflowRunRow key={run.id} run={run} />)
            ) : (
              <div className="rounded-md border border-border bg-background p-4">
                <p className="text-sm font-medium">No workflow runs yet.</p>
                <p className="mt-1 text-sm text-muted-foreground">Use Run now or enable the daily schedule to create the first report.</p>
              </div>
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function WorkflowRunRow({ run }: { run: Awaited<ReturnType<typeof api.dailyWorkflowRuns>>[number] }) {
  const statusTone = run.status === "succeeded" ? "success" : run.status === "failed" ? "danger" : "warning";
  return (
    <article className="rounded-md border border-border bg-background p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={statusTone}>{run.status}</Badge>
            {run.mode ? <Badge tone="neutral">{run.mode}</Badge> : null}
            <span className="font-mono text-xs text-muted-foreground">{run.id.slice(0, 10)}</span>
          </div>
          <p className="mt-2 text-sm font-medium">{run.message || "No status message"}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {new Date(run.created_at).toLocaleString()}
            {run.finished_at ? ` · finished ${new Date(run.finished_at).toLocaleString()}` : ""}
          </p>
        </div>
        <span className="font-mono text-sm text-muted-foreground">{run.progress_pct}%</span>
      </div>

      {run.steps.length ? (
        <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {run.steps.map((step) => (
            <div key={`${run.id}-${step.name}`} className="rounded-md border border-border bg-surface p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{formatStepName(step.name)}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{step.status.replace("_", " ")}</p>
                </div>
                {step.asset_id ? (
                  <a
                    className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    href={`/library?asset=${step.asset_id}`}
                    aria-label={`Open ${formatStepName(step.name)} asset in Library`}
                  >
                    <ExternalLink className="h-4 w-4" aria-hidden="true" />
                  </a>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function formatStepName(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
