import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/Badge";
import { PageHeader, Panel } from "@/components/ui/Panel";
import { api } from "@/lib/api";

export function FeedGridPage() {
  const feed = useQuery({ queryKey: ["feed"], queryFn: api.feed });

  return (
    <div>
      <PageHeader eyebrow="Preview" title="Feed Grid" />
      <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
        {(feed.data || []).slice(0, 18).map((item) => (
          <Panel key={item.id} className="aspect-square overflow-hidden p-3">
            <div className="flex h-full flex-col justify-between rounded-md bg-muted p-3">
              <Badge>{item.status}</Badge>
              <div>
                <p className="line-clamp-3 text-sm font-medium">
                  {String(item.data.title || item.data.hook || item.id)}
                </p>
                <p className="mt-2 text-xs text-muted-foreground">{item.date}</p>
              </div>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
