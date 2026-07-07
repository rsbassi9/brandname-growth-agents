import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/Badge";
import { PageHeader, Panel } from "@/components/ui/Panel";
import { api } from "@/lib/api";

export function SystemPage() {
  const mode = useQuery({ queryKey: ["system", "mode"], queryFn: api.mode });
  const health = useQuery({ queryKey: ["system", "health"], queryFn: api.health });

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
      </div>
    </div>
  );
}
