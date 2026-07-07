import { useQuery } from "@tanstack/react-query";

import { PageHeader, Panel } from "@/components/ui/Panel";
import { api } from "@/lib/api";

export function StrategyHubPage() {
  const docs = useQuery({ queryKey: ["strategy", "docs"], queryFn: api.strategyDocs });
  const learning = useQuery({ queryKey: ["strategy", "learn"], queryFn: api.learnSummary });

  return (
    <div>
      <PageHeader eyebrow="Know / Plan / Build / Ship / Learn" title="Strategy Hub" />
      <div className="grid gap-4 p-4 xl:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          {(docs.data || []).slice(0, 4).map((doc) => (
            <Panel key={doc.name}>
              <h2 className="text-base font-semibold capitalize">{doc.name.split("_").join(" ")}</h2>
              <p className="mt-3 line-clamp-6 whitespace-pre-line text-sm leading-6 text-muted-foreground">
                {doc.content}
              </p>
            </Panel>
          ))}
        </div>
        <Panel>
          <h2 className="text-base font-semibold">Learning Loop</h2>
          <p className="mt-3 whitespace-pre-line text-sm leading-6 text-muted-foreground">
            {learning.data?.summary || "No learning summary yet."}
          </p>
        </Panel>
      </div>
    </div>
  );
}
