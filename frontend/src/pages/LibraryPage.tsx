import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/Badge";
import { PageHeader, Panel } from "@/components/ui/Panel";
import { api } from "@/lib/api";

export function LibraryPage() {
  const assets = useQuery({ queryKey: ["assets", "recent"], queryFn: () => api.assets({ limit: 24 }) });

  return (
    <div>
      <PageHeader eyebrow="Assets" title="Library" />
      <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3">
        {(assets.data?.items || []).map((asset) => (
          <Panel key={asset.id} className="space-y-3">
            <div className="flex items-start justify-between gap-3">
              <h2 className="line-clamp-2 text-base font-semibold">{asset.title}</h2>
              <Badge tone={asset.status === "selected" ? "success" : "neutral"}>{asset.status}</Badge>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge tone="ink">{asset.type.replace("_", " ")}</Badge>
              <Badge>{new Date(asset.created_at).toLocaleDateString()}</Badge>
            </div>
          </Panel>
        ))}
        {!assets.isLoading && !assets.data?.items.length ? (
          <Panel className="md:col-span-2 xl:col-span-3">
            <p className="text-sm text-muted-foreground">No assets found.</p>
          </Panel>
        ) : null}
      </div>
    </div>
  );
}
