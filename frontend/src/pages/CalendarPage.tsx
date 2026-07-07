import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, ExternalLink, Plus, Trash2 } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader, Panel } from "@/components/ui/Panel";
import { api, type CalendarItemOut } from "@/lib/api";
import { cn } from "@/lib/utils";

const statuses = ["draft", "planned", "scheduled", "published", "selected", "archived"];
const weekdayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function monthKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function dateKey(date: Date) {
  return `${monthKey(date)}-${String(date.getDate()).padStart(2, "0")}`;
}

function monthLabel(key: string) {
  const [year, month] = key.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

function shiftMonth(key: string, delta: number) {
  const [year, month] = key.split("-").map(Number);
  return monthKey(new Date(year, month - 1 + delta, 1));
}

function calendarDays(key: string) {
  const [year, month] = key.split("-").map(Number);
  const first = new Date(year, month - 1, 1);
  const startOffset = (first.getDay() + 6) % 7;
  const start = new Date(year, month - 1, 1 - startOffset);
  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return { date: dateKey(day), inMonth: day.getMonth() === month - 1 };
  });
}

function itemTitle(item: CalendarItemOut) {
  return String(item.data.title || item.data.hook || item.data.caption || item.id);
}

function statusTone(status: string) {
  if (status === "published" || status === "selected") return "success";
  if (status === "scheduled" || status === "planned") return "warning";
  if (status === "archived") return "danger";
  return "neutral";
}

export function CalendarPage() {
  const queryClient = useQueryClient();
  const [month, setMonth] = useState(() => monthKey(new Date()));
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(() => dateKey(new Date()));
  const [status, setStatus] = useState("draft");
  const [assetId, setAssetId] = useState("");

  const calendar = useQuery({
    queryKey: ["calendar", month],
    queryFn: () => api.calendar({ month }),
  });

  const createItem = useMutation({
    mutationFn: () =>
      api.createCalendarItem({
        date,
        status,
        asset_id: assetId ? Number(assetId) : null,
        data: { title },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar"] });
      queryClient.invalidateQueries({ queryKey: ["feed"] });
      setTitle("");
      setAssetId("");
    },
  });

  const updateItem = useMutation({
    mutationFn: ({ itemId, nextStatus }: { itemId: string; nextStatus: string }) =>
      api.updateCalendarItem(itemId, { status: nextStatus }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar"] });
      queryClient.invalidateQueries({ queryKey: ["feed"] });
    },
  });

  const deleteItem = useMutation({
    mutationFn: (itemId: string) => api.deleteCalendarItem(itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar"] });
      queryClient.invalidateQueries({ queryKey: ["feed"] });
    },
  });

  const byDate = useMemo(() => {
    return (calendar.data || []).reduce<Record<string, CalendarItemOut[]>>((groups, item) => {
      const key = item.date || "unscheduled";
      groups[key] = [...(groups[key] || []), item];
      return groups;
    }, {});
  }, [calendar.data]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim() || !date) return;
    createItem.mutate();
  }

  return (
    <div>
      <PageHeader
        eyebrow="Plan"
        title="Calendar"
        actions={
          <>
            <Button type="button" variant="outline" size="icon" aria-label="Previous month" onClick={() => setMonth(shiftMonth(month, -1))}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <Badge tone="ink">{monthLabel(month)}</Badge>
            <Button type="button" variant="outline" size="icon" aria-label="Next month" onClick={() => setMonth(shiftMonth(month, 1))}>
              <ArrowRight className="h-4 w-4" />
            </Button>
          </>
        }
      />

      <div className="grid gap-4 p-4 xl:grid-cols-[360px_1fr]">
        <Panel>
          <form className="space-y-4" onSubmit={submit}>
            <div>
              <label htmlFor="calendar-title" className="text-sm font-medium">
                Item title
              </label>
              <input
                id="calendar-title"
                className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition focus:ring-2 focus:ring-ring"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Launch post, reel idea, ad angle..."
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="calendar-date" className="text-sm font-medium">
                  Date
                </label>
                <input
                  id="calendar-date"
                  type="date"
                  className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition focus:ring-2 focus:ring-ring"
                  value={date}
                  onChange={(event) => setDate(event.target.value)}
                />
              </div>
              <div>
                <label htmlFor="calendar-status" className="text-sm font-medium">
                  Status
                </label>
                <select
                  id="calendar-status"
                  className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition focus:ring-2 focus:ring-ring"
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                >
                  {statuses.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label htmlFor="calendar-asset" className="text-sm font-medium">
                Linked asset ID
              </label>
              <input
                id="calendar-asset"
                inputMode="numeric"
                className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition focus:ring-2 focus:ring-ring"
                value={assetId}
                onChange={(event) => setAssetId(event.target.value.replace(/\D/g, ""))}
                placeholder="Optional"
              />
            </div>
            <Button type="submit" className="w-full" disabled={!title.trim() || createItem.isPending}>
              <Plus className="h-4 w-4" />
              Add Item
            </Button>
            {createItem.error ? (
              <p role="alert" className="text-sm text-danger">
                {createItem.error instanceof Error ? createItem.error.message : "Calendar item could not be created."}
              </p>
            ) : null}
          </form>
        </Panel>

        <section className="min-w-0">
          <div className="grid grid-cols-7 border-b border-l border-border bg-surface text-center text-xs font-semibold uppercase text-muted-foreground">
            {weekdayLabels.map((day) => (
              <div key={day} className="border-r border-border px-2 py-2">
                {day}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-1 border-l border-border bg-surface sm:grid-cols-7">
            {calendarDays(month).map((day) => (
              <div
                key={day.date}
                className={cn(
                  "min-h-36 border-b border-r border-border p-2",
                  day.inMonth ? "bg-surface" : "bg-muted/45 text-muted-foreground",
                )}
              >
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-semibold">{day.date.slice(-2)}</span>
                  {byDate[day.date]?.length ? <Badge>{byDate[day.date].length}</Badge> : null}
                </div>
                <div className="space-y-2">
                  {(byDate[day.date] || []).map((item) => (
                    <CalendarItemCard
                      key={item.id}
                      item={item}
                      updating={updateItem.isPending || deleteItem.isPending}
                      onStatus={(nextStatus) => updateItem.mutate({ itemId: item.id, nextStatus })}
                      onDelete={() => deleteItem.mutate(item.id)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
          {calendar.isLoading ? (
            <Panel className="mt-4 h-24 animate-pulse bg-muted">
              <span className="sr-only">Loading calendar</span>
            </Panel>
          ) : null}
        </section>
      </div>
    </div>
  );
}

function CalendarItemCard({
  item,
  updating,
  onStatus,
  onDelete,
}: {
  item: CalendarItemOut;
  updating: boolean;
  onStatus: (status: string) => void;
  onDelete: () => void;
}) {
  return (
    <div className="rounded-md border border-border bg-background p-2">
      <div className="flex items-start justify-between gap-2">
        <p className="line-clamp-2 text-sm font-medium">{itemTitle(item)}</p>
        {item.asset_id ? (
          <Button asChild variant="ghost" size="icon" aria-label={`Open asset ${item.asset_id}`}>
            <Link to={`/library?asset=${item.asset_id}`}>
              <ExternalLink className="h-4 w-4" />
            </Link>
          </Button>
        ) : null}
      </div>
      <div className="mt-2 flex items-center gap-2">
        <Badge tone={statusTone(item.status)}>{item.status}</Badge>
        <select
          aria-label={`Status for ${itemTitle(item)}`}
          className="h-9 min-w-0 flex-1 rounded-md border border-input bg-surface px-2 text-xs outline-none focus:ring-2 focus:ring-ring"
          value={item.status}
          disabled={updating}
          onChange={(event) => onStatus(event.target.value)}
        >
          {statuses.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        <Button type="button" variant="ghost" size="icon" aria-label={`Delete ${itemTitle(item)}`} disabled={updating} onClick={onDelete}>
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
