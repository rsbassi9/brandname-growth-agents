import { Clock3, Play } from "lucide-react";
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
      </div>
    </div>
  );
}
