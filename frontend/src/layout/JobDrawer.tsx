import { Activity, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Panel } from "@/components/ui/Panel";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function JobDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const summary = useQuery({
    queryKey: ["library", "summary"],
    queryFn: api.librarySummary,
    enabled: open,
  });

  return (
    <div className={cn("fixed inset-0 z-50", open ? "pointer-events-auto" : "pointer-events-none")}>
      <button
        aria-label="Close job drawer"
        className={cn(
          "absolute inset-0 bg-zinc-950/50 transition-opacity",
          open ? "opacity-100" : "opacity-0",
        )}
        onClick={onClose}
      />
      <aside
        className={cn(
          "absolute right-0 top-0 h-full w-full max-w-md border-l border-border bg-background shadow-xl transition-transform duration-200",
          open ? "translate-x-0" : "translate-x-full",
        )}
        aria-label="Job drawer"
      >
        <div className="flex min-h-16 items-center justify-between border-b border-border px-4">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            <h2 className="text-lg font-semibold">Job Monitor</h2>
          </div>
          <Button type="button" variant="ghost" size="icon" aria-label="Close job drawer" onClick={onClose}>
            <X className="h-5 w-5" />
          </Button>
        </div>
        <div className="space-y-4 p-4">
          <Panel>
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium">Library assets</p>
                <p className="text-sm text-muted-foreground">Latest persisted output count</p>
              </div>
              <span className="font-mono text-2xl font-semibold">{summary.data?.total ?? "-"}</span>
            </div>
          </Panel>
          <Panel>
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Status</p>
              <Badge tone="neutral">Live per generation</Badge>
            </div>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              Generation pages subscribe to each job stream as it starts. This drawer will become the global
              running-job ledger as P2 adds generation flows across the studio.
            </p>
          </Panel>
        </div>
      </aside>
    </div>
  );
}
