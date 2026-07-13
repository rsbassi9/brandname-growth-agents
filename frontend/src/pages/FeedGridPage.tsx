import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, GripVertical, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader, Panel } from "@/components/ui/Panel";
import { api, type CalendarItemOut } from "@/lib/api";
import { cn } from "@/lib/utils";

function titleFor(item: CalendarItemOut) {
  return String(item.data.title || item.data.hook || item.data.caption || item.id);
}

function mediaUrlFor(item: CalendarItemOut) {
  return item.asset_id ? `/api/v1/assets/${item.asset_id}/media` : "";
}

function tileTone(status: string) {
  if (status === "published" || status === "selected") return "success";
  if (status === "scheduled" || status === "planned") return "warning";
  if (status === "archived") return "danger";
  return "neutral";
}

function moveItem(items: CalendarItemOut[], from: number, to: number) {
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

export function FeedGridPage() {
  const queryClient = useQueryClient();
  const feed = useQuery({ queryKey: ["feed"], queryFn: api.feed });
  const [items, setItems] = useState<CalendarItemOut[]>([]);
  const [draggedId, setDraggedId] = useState<string | null>(null);

  useEffect(() => {
    setItems(feed.data || []);
  }, [feed.data]);

  const dirty = useMemo(() => {
    const current = items.map((item) => item.id).join("|");
    const original = (feed.data || []).map((item) => item.id).join("|");
    return current !== original;
  }, [feed.data, items]);

  const saveOrder = useMutation({
    mutationFn: () => api.setFeedOrder(items.map((item) => item.id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["feed"] });
    },
  });

  function reorder(activeId: string, targetId: string) {
    if (activeId === targetId) return;
    const from = items.findIndex((item) => item.id === activeId);
    const to = items.findIndex((item) => item.id === targetId);
    if (from < 0 || to < 0) return;
    setItems(moveItem(items, from, to));
  }

  function moveBy(index: number, delta: number) {
    const nextIndex = index + delta;
    if (nextIndex < 0 || nextIndex >= items.length) return;
    setItems(moveItem(items, index, nextIndex));
  }

  return (
    <div>
      <PageHeader
        eyebrow="Preview"
        title="Feed Grid"
        actions={
          <>
            <Badge tone={dirty ? "warning" : "neutral"}>{dirty ? "Unsaved order" : `${items.length} items`}</Badge>
            <Button type="button" onClick={() => saveOrder.mutate()} disabled={!dirty || saveOrder.isPending}>
              <Save className="h-4 w-4" />
              Save Order
            </Button>
          </>
        }
      />
      <div className="p-4">
        {feed.isLoading ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }, (_, index) => (
              <Panel key={index} className="aspect-square animate-pulse bg-muted">
                <span className="sr-only">Loading feed item</span>
              </Panel>
            ))}
          </div>
        ) : null}

        {!feed.isLoading && !items.length ? (
          <Panel>
            <p className="text-sm text-muted-foreground">No feed items yet.</p>
          </Panel>
        ) : null}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item, index) => (
            <article
              key={item.id}
              draggable
              onDragStart={() => setDraggedId(item.id)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => {
                if (draggedId) reorder(draggedId, item.id);
                setDraggedId(null);
              }}
              onDragEnd={() => setDraggedId(null)}
              className={cn(
                "aspect-square rounded-lg border border-border bg-surface p-3 transition-colors duration-ui ease-ui",
                draggedId === item.id ? "border-accent bg-accent-soft" : "hover:border-accent/60",
              )}
            >
              <div className="relative flex h-full flex-col justify-between overflow-hidden rounded-md bg-muted">
                {mediaUrlFor(item) ? (
                  <img
                    src={mediaUrlFor(item)}
                    alt=""
                    loading="lazy"
                    className="absolute inset-0 h-full w-full object-cover"
                    onError={(event) => {
                      event.currentTarget.hidden = true;
                    }}
                  />
                ) : null}
                <div className="absolute inset-0 bg-ink/45" aria-hidden="true" />
                <div className="flex items-start justify-between gap-2">
                  <Badge tone={tileTone(item.status)} className="relative z-10 m-3">
                    {item.status}
                  </Badge>
                  <div className="relative z-10 m-3 flex gap-1 rounded-md bg-background/80">
                    <Button type="button" variant="ghost" size="icon" aria-label={`Move ${titleFor(item)} earlier`} onClick={() => moveBy(index, -1)}>
                      <ArrowUp className="h-4 w-4" />
                    </Button>
                    <Button type="button" variant="ghost" size="icon" aria-label={`Move ${titleFor(item)} later`} onClick={() => moveBy(index, 1)}>
                      <ArrowDown className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="relative z-10 m-3 rounded-md bg-background/85 p-3">
                  <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
                    <GripVertical className="h-4 w-4" />
                    Slot {index + 1}
                  </div>
                  <p className="line-clamp-3 text-sm font-medium">{titleFor(item)}</p>
                  <p className="mt-2 text-xs text-muted-foreground">{item.date || "Unscheduled"}</p>
                </div>
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
