import { useEffect, useMemo, useState } from "react";

import { createJobEventSource, type JobOut } from "@/lib/api";

export interface TrackedJob {
  id: string;
  assetId?: number;
  snapshot?: Partial<JobOut>;
}

export function useJobEvents(initialJobs: TrackedJob[]) {
  const [jobs, setJobs] = useState<TrackedJob[]>(initialJobs);

  useEffect(() => {
    setJobs(initialJobs);
  }, [initialJobs]);

  useEffect(() => {
    const active = jobs.filter((job) => !["succeeded", "failed"].includes(job.snapshot?.status || ""));
    const sources = active.map((job) => {
      const source = createJobEventSource(job.id);
      const update = (event: MessageEvent<string>) => {
        const snapshot = JSON.parse(event.data) as JobOut;
        setJobs((current) =>
          current.map((item) => (item.id === job.id ? { ...item, snapshot } : item)),
        );
      };
      source.addEventListener("progress", update);
      source.addEventListener("completion", update);
      source.addEventListener("error", () => {
        setJobs((current) =>
          current.map((item) =>
            item.id === job.id
              ? {
                  ...item,
                  snapshot: {
                    ...item.snapshot,
                    id: item.id,
                    status: "failed",
                    message: "Job event stream closed.",
                  },
                }
              : item,
          ),
        );
      });
      return source;
    });

    return () => sources.forEach((source) => source.close());
  }, [jobs.map((job) => `${job.id}:${job.snapshot?.status || "new"}`).join("|")]);

  const runningCount = useMemo(
    () => jobs.filter((job) => ["queued", "running"].includes(job.snapshot?.status || "queued")).length,
    [jobs],
  );

  return { jobs, setJobs, runningCount };
}
