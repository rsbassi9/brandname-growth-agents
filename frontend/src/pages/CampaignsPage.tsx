import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/Badge";
import { PageHeader, Panel } from "@/components/ui/Panel";
import { api } from "@/lib/api";

export function CampaignsPage() {
  const campaigns = useQuery({ queryKey: ["campaigns"], queryFn: api.campaigns });

  return (
    <div>
      <PageHeader eyebrow="Projects" title="Campaigns" />
      <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3">
        {(campaigns.data || []).map((campaign) => (
          <Panel key={campaign.id} className="space-y-3">
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-base font-semibold">{campaign.name}</h2>
              <Badge>{campaign.status}</Badge>
            </div>
            <p className="text-sm leading-6 text-muted-foreground">{campaign.goal || "No campaign goal set."}</p>
          </Panel>
        ))}
        {!campaigns.isLoading && !campaigns.data?.length ? (
          <Panel className="md:col-span-2 xl:col-span-3">
            <p className="text-sm text-muted-foreground">No campaigns yet.</p>
          </Panel>
        ) : null}
      </div>
    </div>
  );
}
