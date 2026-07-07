import { RectangleEllipsis } from "lucide-react";

import { PageHeader, Panel } from "@/components/ui/Panel";

export function AdsPage() {
  return (
    <div>
      <PageHeader eyebrow="Briefs" title="Ads" />
      <div className="p-4">
        <Panel className="min-h-72">
          <div className="flex h-full min-h-56 items-center justify-center rounded-md border border-dashed border-border bg-muted/40">
            <RectangleEllipsis className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
          </div>
        </Panel>
      </div>
    </div>
  );
}
