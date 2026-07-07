import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Boxes, FileText, Image, PanelsTopLeft, Plus, Send, Video } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader, Panel } from "@/components/ui/Panel";
import { api, type AssetOut, type AssetType, type CampaignOut } from "@/lib/api";
import { cn } from "@/lib/utils";

const generationTypes: Array<{ type: AssetType; label: string }> = [
  { type: "copy", label: "Copy" },
  { type: "image_concept", label: "Image Concept" },
  { type: "carousel", label: "Carousel" },
  { type: "video_script", label: "Video Script" },
];

function assetIcon(type: string) {
  if (type === "image_concept") return Image;
  if (type === "carousel") return PanelsTopLeft;
  if (type === "video_script") return Video;
  return FileText;
}

function formatType(type: string) {
  return type.replace("_", " ");
}

export function CampaignsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");

  const campaigns = useQuery({ queryKey: ["campaigns"], queryFn: api.campaigns });
  const selectedCampaign = useMemo(
    () => campaigns.data?.find((campaign) => campaign.id === selectedId) || campaigns.data?.[0] || null,
    [campaigns.data, selectedId],
  );

  const assets = useQuery({
    queryKey: ["campaigns", selectedCampaign?.id, "assets"],
    queryFn: () => api.campaignAssets(selectedCampaign!.id),
    enabled: Boolean(selectedCampaign?.id),
  });

  const createCampaign = useMutation({
    mutationFn: () => api.createCampaign({ name: name.trim(), goal: goal.trim(), status: "active" }),
    onSuccess: (campaign) => {
      queryClient.setQueryData<CampaignOut[]>(["campaigns"], (current = []) => [
        campaign,
        ...current.filter((item) => item.id !== campaign.id),
      ]);
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      setSelectedId(campaign.id);
      setName("");
      setGoal("");
    },
  });

  useEffect(() => {
    if (selectedId === null && campaigns.data?.length) {
      setSelectedId(campaigns.data[0].id);
    }
  }, [campaigns.data, selectedId]);

  const groupedAssets = useMemo(() => groupAssetsByType(assets.data || []), [assets.data]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      return;
    }
    createCampaign.mutate();
  }

  function generateInCampaign(type: AssetType) {
    if (!selectedCampaign) return;
    navigate("/playground", {
      state: {
        campaignId: selectedCampaign.id,
        campaignName: selectedCampaign.name,
        assetType: type,
        brief: selectedCampaign.goal ? `${selectedCampaign.name}\n\nCampaign goal: ${selectedCampaign.goal}` : selectedCampaign.name,
      },
    });
  }

  return (
    <div>
      <PageHeader eyebrow="Projects" title="Campaigns" actions={<Badge tone="ink">{campaigns.data?.length || 0} campaigns</Badge>} />

      <div className="grid gap-4 p-4 xl:grid-cols-[360px_1fr]">
        <div className="space-y-4">
          <Panel>
            <form className="space-y-4" onSubmit={submit}>
              <div>
                <label htmlFor="campaign-name" className="text-sm font-medium">
                  Campaign name
                </label>
                <input
                  id="campaign-name"
                  className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition focus:ring-2 focus:ring-ring"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Drop recovery, photoshoot push..."
                />
              </div>
              <div>
                <label htmlFor="campaign-goal" className="text-sm font-medium">
                  Goal
                </label>
                <textarea
                  id="campaign-goal"
                  className="mt-2 min-h-24 w-full rounded-md border border-input bg-background px-3 py-3 text-sm leading-6 outline-none transition focus:ring-2 focus:ring-ring"
                  value={goal}
                  onChange={(event) => setGoal(event.target.value)}
                  placeholder="What this campaign needs to accomplish"
                />
              </div>
              <Button type="submit" disabled={!name.trim() || createCampaign.isPending} className="w-full">
                <Plus className="h-4 w-4" />
                Create Campaign
              </Button>
              {createCampaign.error ? (
                <p role="alert" className="text-sm text-danger">
                  {createCampaign.error instanceof Error ? createCampaign.error.message : "Campaign could not be created."}
                </p>
              ) : null}
            </form>
          </Panel>

          <div className="space-y-2">
            {(campaigns.data || []).map((campaign) => (
              <CampaignButton
                key={campaign.id}
                campaign={campaign}
                selected={selectedCampaign?.id === campaign.id}
                onClick={() => setSelectedId(campaign.id)}
              />
            ))}
            {!campaigns.isLoading && !campaigns.data?.length ? (
              <Panel>
                <p className="text-sm text-muted-foreground">No campaigns yet.</p>
              </Panel>
            ) : null}
          </div>
        </div>

        <section className="min-w-0">
          {selectedCampaign ? (
            <div className="space-y-4">
              <Panel className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-display text-xl font-normal">{selectedCampaign.name}</h2>
                    <Badge>{selectedCampaign.status}</Badge>
                  </div>
                  <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
                    {selectedCampaign.goal || "No campaign goal set."}
                  </p>
                </div>
                <div className="grid shrink-0 grid-cols-2 gap-2 sm:grid-cols-4 md:grid-cols-2">
                  {generationTypes.map((item) => (
                    <Button
                      key={item.type}
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => generateInCampaign(item.type)}
                    >
                      <Send className="h-4 w-4" />
                      {item.label}
                    </Button>
                  ))}
                </div>
              </Panel>

              <div className="grid gap-4 lg:grid-cols-2">
                {Object.entries(groupedAssets).map(([type, list]) => (
                  <AssetGroup key={type} type={type} assets={list} />
                ))}
                {!assets.isLoading && !assets.data?.length ? (
                  <Panel className="lg:col-span-2">
                    <p className="text-sm font-medium">No assets in this campaign yet.</p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Use a generate shortcut to start a campaign-specific take in Playground.
                    </p>
                  </Panel>
                ) : null}
                {assets.isLoading ? (
                  <Panel className="h-44 animate-pulse bg-muted lg:col-span-2">
                    <span className="sr-only">Loading campaign assets</span>
                  </Panel>
                ) : null}
              </div>
            </div>
          ) : (
            <Panel>
              <div className="flex items-center gap-3">
                <Boxes className="h-5 w-5 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">Create or select a campaign.</p>
              </div>
            </Panel>
          )}
        </section>
      </div>
    </div>
  );
}

function CampaignButton({
  campaign,
  selected,
  onClick,
}: {
  campaign: CampaignOut;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={cn(
        "w-full rounded-lg border bg-surface p-3 text-left transition-colors duration-ui ease-ui hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected ? "border-accent bg-accent-soft" : "border-border",
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="line-clamp-2 font-display text-base font-normal">{campaign.name}</p>
        <Badge>{campaign.status}</Badge>
      </div>
      <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">{campaign.goal || "No goal set."}</p>
    </button>
  );
}

function AssetGroup({ type, assets }: { type: string; assets: AssetOut[] }) {
  const Icon = assetIcon(type);
  return (
    <Panel>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-md bg-accent-soft text-accent-soft-foreground">
            <Icon className="h-4 w-4" />
          </span>
          <h3 className="text-sm font-semibold capitalize">{formatType(type)}</h3>
        </div>
        <Badge>{assets.length}</Badge>
      </div>
      <div className="space-y-2">
        {assets.map((asset) => (
          <div key={asset.id} className="rounded-md border border-border bg-background p-3">
            <div className="flex items-start justify-between gap-3">
              <p className="line-clamp-2 text-sm font-medium">{asset.title}</p>
              <Badge tone={asset.status === "selected" ? "success" : "neutral"}>{asset.status}</Badge>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">{new Date(asset.created_at).toLocaleString()}</p>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function groupAssetsByType(assets: AssetOut[]) {
  return assets.reduce<Record<string, AssetOut[]>>((groups, asset) => {
    groups[asset.type] = [...(groups[asset.type] || []), asset];
    return groups;
  }, {});
}
