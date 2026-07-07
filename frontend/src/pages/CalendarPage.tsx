import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/Badge";
import { PageHeader, Panel } from "@/components/ui/Panel";
import { api } from "@/lib/api";

export function CalendarPage() {
  const calendar = useQuery({ queryKey: ["calendar"], queryFn: () => api.calendar() });

  return (
    <div>
      <PageHeader eyebrow="Plan" title="Calendar" />
      <div className="space-y-3 p-4">
        {(calendar.data || []).slice(0, 30).map((item) => (
          <Panel key={item.id} className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-medium">{String(item.data.title || item.data.hook || item.id)}</p>
              <p className="text-sm text-muted-foreground">{item.date || "Unscheduled"}</p>
            </div>
            <Badge>{item.status}</Badge>
          </Panel>
        ))}
      </div>
    </div>
  );
}
