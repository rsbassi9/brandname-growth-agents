import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, CalendarRange, ExternalLink, GripVertical, Plus, Search, Trash2, Video } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader, Panel } from "@/components/ui/Panel";
import { api, type AssetOut, type AssetType, type CalendarItemOut, type CalendarItemPatch } from "@/lib/api";
import { cn } from "@/lib/utils";

const statuses = ["draft", "planned", "scheduled", "published", "selected", "archived"];
const weekdayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const assetTypes: Array<"" | AssetType> = ["", "copy", "image_concept", "carousel", "video_script", "voiceover", "ad_brief"];
type CalendarView = "month" | "week";

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

function startOfWeek(date: Date) {
  const next = new Date(date);
  const offset = (next.getDay() + 6) % 7;
  next.setDate(next.getDate() - offset);
  return next;
}

function weekStartKey(date: Date) {
  return dateKey(startOfWeek(date));
}

function shiftWeek(key: string, delta: number) {
  const [year, month, day] = key.split("-").map(Number);
  const next = new Date(year, month - 1, day);
  next.setDate(next.getDate() + delta * 7);
  return weekStartKey(next);
}

function weekDays(key: string) {
  const [year, month, day] = key.split("-").map(Number);
  const start = new Date(year, month - 1, day);
  return Array.from({ length: 7 }, (_, index) => {
    const next = new Date(start);
    next.setDate(start.getDate() + index);
    return { date: dateKey(next), label: weekdayLabels[index], day: next.getDate() };
  });
}

function weekLabel(key: string) {
  const days = weekDays(key);
  const [firstYear, firstMonth, firstDay] = days[0].date.split("-").map(Number);
  const [lastYear, lastMonth, lastDay] = days[6].date.split("-").map(Number);
  const first = new Date(firstYear, firstMonth - 1, firstDay);
  const last = new Date(lastYear, lastMonth - 1, lastDay);
  return `${first.toLocaleDateString(undefined, { month: "short", day: "numeric" })} - ${last.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  })}`;
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

function itemChannel(item: CalendarItemOut) {
  return String(item.data.channel || item.data.platform || "Manual");
}

function itemSlot(item: CalendarItemOut) {
  return String(item.data.slot || "day");
}

function assetTypeLabel(type: string) {
  return type.replace("_", " ");
}

function statusTone(status: string) {
  if (status === "published" || status === "selected") return "success";
  if (status === "scheduled" || status === "planned") return "warning";
  if (status === "archived") return "danger";
  return "neutral";
}

function groupByDate(items: CalendarItemOut[]) {
  return items.reduce<Record<string, CalendarItemOut[]>>((groups, item) => {
    const key = item.date || "unscheduled";
    groups[key] = [...(groups[key] || []), item];
    return groups;
  }, {});
}

export function CalendarPage() {
  const queryClient = useQueryClient();
  const [view, setView] = useState<CalendarView>("month");
  const [month, setMonth] = useState(() => monthKey(new Date()));
  const [weekStart, setWeekStart] = useState(() => weekStartKey(new Date()));
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(() => dateKey(new Date()));
  const [status, setStatus] = useState("draft");
  const [assetId, setAssetId] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [moveError, setMoveError] = useState("");
  const [traySearch, setTraySearch] = useState("");
  const [trayType, setTrayType] = useState<"" | AssetType>("");

  const calendarQueryKey = ["calendar", view, view === "month" ? month : weekStart] as const;
  const calendar = useQuery({
    queryKey: calendarQueryKey,
    queryFn: () => (view === "month" ? api.calendar({ month }) : api.calendar()),
  });
  const draftAssets = useQuery({
    queryKey: ["assets", "calendar-tray", traySearch, trayType],
    queryFn: () => api.assets({ status: "draft", q: traySearch, type: trayType || undefined, limit: 60, offset: 0 }),
  });
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const createItem = useMutation({
    mutationFn: () =>
      api.createCalendarItem({
        date,
        status,
        asset_id: assetId ? Number(assetId) : null,
        data: { title, slot: "day" },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar"] });
      queryClient.invalidateQueries({ queryKey: ["feed"] });
      setTitle("");
      setAssetId("");
    },
  });

  const scheduleAsset = useMutation({
    mutationFn: ({ asset, nextDate }: { asset: AssetOut; nextDate: string }) =>
      api.createCalendarItem({
        date: nextDate,
        status: "draft",
        asset_id: asset.id,
        data: {
          title: asset.title,
          asset_type: asset.type,
          slot: "day",
        },
      }),
    onMutate: async ({ asset, nextDate }) => {
      setMoveError("");
      await queryClient.cancelQueries({ queryKey: ["calendar"] });
      const previousItems = queryClient.getQueryData<CalendarItemOut[]>(calendarQueryKey);
      if (previousItems) {
        const optimistic: CalendarItemOut = {
          id: `draft-${asset.id}`,
          date: nextDate,
          status: "draft",
          asset_id: asset.id,
          data: { title: asset.title, asset_type: asset.type, slot: "day" },
        };
        queryClient.setQueryData<CalendarItemOut[]>(calendarQueryKey, [...previousItems, optimistic]);
      }
      return { previousItems };
    },
    onError: (error, _variables, context) => {
      if (context?.previousItems) {
        queryClient.setQueryData(calendarQueryKey, context.previousItems);
      }
      setMoveError(error instanceof Error ? error.message : "Draft asset could not be scheduled.");
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar"] });
      queryClient.invalidateQueries({ queryKey: ["feed"] });
      queryClient.invalidateQueries({ queryKey: ["assets", "calendar-tray"] });
    },
  });

  const updateItem = useMutation({
    mutationFn: ({ itemId, patch }: { itemId: string; patch: CalendarItemPatch }) => api.updateCalendarItem(itemId, patch),
    onMutate: async ({ itemId, patch }) => {
      setMoveError("");
      await queryClient.cancelQueries({ queryKey: ["calendar"] });
      const previousItems = queryClient.getQueryData<CalendarItemOut[]>(calendarQueryKey);
      if (previousItems && (patch.date || patch.slot)) {
        queryClient.setQueryData<CalendarItemOut[]>(
          calendarQueryKey,
          previousItems.map((item) =>
            item.id === itemId
              ? {
                  ...item,
                  date: patch.date || item.date,
                  data: patch.slot ? { ...item.data, slot: patch.slot } : item.data,
                }
              : item,
          ),
        );
      }
      return { previousItems };
    },
    onError: (error, _variables, context) => {
      if (context?.previousItems) {
        queryClient.setQueryData(calendarQueryKey, context.previousItems);
      }
      setMoveError(error instanceof Error ? error.message : "Calendar item could not be moved.");
    },
    onSettled: () => {
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

  const createVideoPack = useMutation({
    mutationFn: (itemId: string) => api.createCalendarVideoPromptPack(itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      queryClient.invalidateQueries({ queryKey: ["library"] });
    },
  });

  const byDate = useMemo(() => groupByDate(calendar.data || []), [calendar.data]);
  const linkedAssetIds = useMemo(() => new Set((calendar.data || []).map((item) => item.asset_id).filter((id): id is number => id !== null)), [calendar.data]);
  const unscheduledAssets = useMemo(
    () => (draftAssets.data?.items || []).filter((asset) => !linkedAssetIds.has(asset.id)),
    [draftAssets.data?.items, linkedAssetIds],
  );

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim() || !date) return;
    createItem.mutate();
  }

  function moveItemToDate(itemId: string, nextDate: string) {
    const item = (calendar.data || []).find((candidate) => candidate.id === itemId);
    if (!item || item.date === nextDate) return;
    updateItem.mutate({ itemId, patch: { date: nextDate, slot: "day" } });
  }

  function onDragStart(event: DragStartEvent) {
    setActiveId(String(event.active.id));
    setMoveError("");
  }

  function onDragEnd(event: DragEndEvent) {
    const overId = event.over?.id ? String(event.over.id) : "";
    const draggableId = String(event.active.id);
    setActiveId(null);
    if (!overId.startsWith("day:")) return;
    const nextDate = overId.replace("day:", "");
    if (draggableId.startsWith("asset:")) {
      const assetId = Number(draggableId.replace("asset:", ""));
      const asset = unscheduledAssets.find((candidate) => candidate.id === assetId);
      if (asset) scheduleAsset.mutate({ asset, nextDate });
      return;
    }
    moveItemToDate(draggableId, nextDate);
  }

  const activeItem = (calendar.data || []).find((item) => item.id === activeId);

  return (
    <div>
      <PageHeader
        eyebrow="Plan"
        title="Calendar"
        actions={
          <>
            <div className="flex rounded-md border border-border bg-background p-1">
              <Button
                type="button"
                variant={view === "month" ? "default" : "ghost"}
                size="sm"
                aria-pressed={view === "month"}
                onClick={() => setView("month")}
              >
                Month
              </Button>
              <Button
                type="button"
                variant={view === "week" ? "default" : "ghost"}
                size="sm"
                aria-pressed={view === "week"}
                onClick={() => setView("week")}
              >
                <CalendarRange className="h-4 w-4" />
                Week
              </Button>
            </div>
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label={view === "month" ? "Previous month" : "Previous week"}
              onClick={() => (view === "month" ? setMonth(shiftMonth(month, -1)) : setWeekStart(shiftWeek(weekStart, -1)))}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <Badge tone="ink">{view === "month" ? monthLabel(month) : weekLabel(weekStart)}</Badge>
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label={view === "month" ? "Next month" : "Next week"}
              onClick={() => (view === "month" ? setMonth(shiftMonth(month, 1)) : setWeekStart(shiftWeek(weekStart, 1)))}
            >
              <ArrowRight className="h-4 w-4" />
            </Button>
          </>
        }
      />

      <div className={cn("grid gap-4 p-4", view === "week" ? "xl:grid-cols-[320px_1fr_280px]" : "xl:grid-cols-[360px_1fr]")}>
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
            {moveError ? (
              <p role="alert" className="text-sm text-danger">
                {moveError}
              </p>
            ) : null}
          </form>
        </Panel>

        {view === "month" ? (
          <section className="min-w-0">
            <MonthCalendar
              days={calendarDays(month)}
              byDate={byDate}
              updating={updateItem.isPending || deleteItem.isPending}
              creatingVideoPack={createVideoPack.isPending}
              onStatus={(itemId, nextStatus) => updateItem.mutate({ itemId, patch: { status: nextStatus } })}
              onDelete={(itemId) => deleteItem.mutate(itemId)}
              onVideoPack={(itemId) => createVideoPack.mutate(itemId)}
            />
            {calendar.isLoading ? (
              <Panel className="mt-4 h-24 animate-pulse bg-muted">
                <span className="sr-only">Loading calendar</span>
              </Panel>
            ) : null}
          </section>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setActiveId(null)}>
            <section className="min-w-0">
              <WeekCalendar
                days={weekDays(weekStart)}
                byDate={byDate}
                activeId={activeId}
                updating={updateItem.isPending || deleteItem.isPending}
                creatingVideoPack={createVideoPack.isPending}
                onMove={moveItemToDate}
                onStatus={(itemId, nextStatus) => updateItem.mutate({ itemId, patch: { status: nextStatus } })}
                onDelete={(itemId) => deleteItem.mutate(itemId)}
                onVideoPack={(itemId) => createVideoPack.mutate(itemId)}
              />
              {activeItem ? <span className="sr-only">Moving {activeItem.asset_id ? itemTitle(activeItem) : "draft asset"}</span> : null}
              {calendar.isLoading ? (
                <Panel className="mt-4 h-24 animate-pulse bg-muted">
                  <span className="sr-only">Loading calendar</span>
                </Panel>
              ) : null}
            </section>
            <UnscheduledTray
              assets={unscheduledAssets}
              loading={draftAssets.isLoading}
              search={traySearch}
              type={trayType}
              scheduling={scheduleAsset.isPending}
              onSearch={setTraySearch}
              onType={setTrayType}
              onSchedule={(asset, nextDate) => scheduleAsset.mutate({ asset, nextDate })}
            />
          </DndContext>
        )}
      </div>
    </div>
  );
}

function MonthCalendar({
  days,
  byDate,
  updating,
  creatingVideoPack,
  onStatus,
  onDelete,
  onVideoPack,
}: {
  days: { date: string; inMonth: boolean }[];
  byDate: Record<string, CalendarItemOut[]>;
  updating: boolean;
  creatingVideoPack: boolean;
  onStatus: (itemId: string, status: string) => void;
  onDelete: (itemId: string) => void;
  onVideoPack: (itemId: string) => void;
}) {
  return (
    <>
      <div className="grid grid-cols-7 border-b border-l border-border bg-surface text-center text-xs font-semibold uppercase text-muted-foreground">
        {weekdayLabels.map((day) => (
          <div key={day} className="border-r border-border px-2 py-2">
            {day}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 border-l border-border bg-surface sm:grid-cols-7">
        {days.map((day) => (
          <div
            key={day.date}
            className={cn("min-h-36 border-b border-r border-border p-2", day.inMonth ? "bg-surface" : "bg-muted/45 text-muted-foreground")}
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
                  draggableCard={false}
                  updating={updating}
                  creatingVideoPack={creatingVideoPack}
                  onStatus={(nextStatus) => onStatus(item.id, nextStatus)}
                  onDelete={() => onDelete(item.id)}
                  onVideoPack={() => onVideoPack(item.id)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function WeekCalendar({
  days,
  byDate,
  activeId,
  updating,
  creatingVideoPack,
  onMove,
  onStatus,
  onDelete,
  onVideoPack,
}: {
  days: { date: string; label: string; day: number }[];
  byDate: Record<string, CalendarItemOut[]>;
  activeId: string | null;
  updating: boolean;
  creatingVideoPack: boolean;
  onMove: (itemId: string, date: string) => void;
  onStatus: (itemId: string, status: string) => void;
  onDelete: (itemId: string) => void;
  onVideoPack: (itemId: string) => void;
}) {
  return (
    <div className="grid gap-3 lg:grid-cols-7">
      {days.map((day) => (
        <WeekDayColumn key={day.date} day={day} itemCount={byDate[day.date]?.length || 0}>
          {(byDate[day.date] || []).map((item) => (
            <CalendarItemCard
              key={item.id}
              item={item}
              draggableCard
              active={activeId === item.id}
              updating={updating}
              creatingVideoPack={creatingVideoPack}
              onMove={(nextDate) => onMove(item.id, nextDate)}
              onStatus={(nextStatus) => onStatus(item.id, nextStatus)}
              onDelete={() => onDelete(item.id)}
              onVideoPack={() => onVideoPack(item.id)}
            />
          ))}
        </WeekDayColumn>
      ))}
    </div>
  );
}

function WeekDayColumn({
  day,
  itemCount,
  children,
}: {
  day: { date: string; label: string; day: number };
  itemCount: number;
  children: React.ReactNode;
}) {
  const { isOver, setNodeRef } = useDroppable({ id: `day:${day.date}` });
  return (
    <section
      ref={setNodeRef}
      className={cn(
        "min-h-[20rem] rounded-lg border border-border bg-surface p-2 transition-colors duration-ui ease-ui",
        isOver ? "border-accent bg-accent-soft" : "",
      )}
      aria-label={`${day.label} ${day.day}`}
    >
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">
          {day.label} {day.day}
        </h2>
        <Badge>{itemCount}</Badge>
      </div>
      {isOver ? <div className="mb-2 h-11 rounded-md border-2 border-dashed border-accent bg-background" /> : null}
      <div className="space-y-2">{children}</div>
      {!itemCount ? <p className="rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">Open slot</p> : null}
    </section>
  );
}

function UnscheduledTray({
  assets,
  loading,
  search,
  type,
  scheduling,
  onSearch,
  onType,
  onSchedule,
}: {
  assets: AssetOut[];
  loading: boolean;
  search: string;
  type: "" | AssetType;
  scheduling: boolean;
  onSearch: (value: string) => void;
  onType: (value: "" | AssetType) => void;
  onSchedule: (asset: AssetOut, date: string) => void;
}) {
  return (
    <aside className="rounded-lg border border-border bg-surface p-3">
      <div className="mb-3">
        <h2 className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">Unscheduled drafts</h2>
        <p className="mt-1 text-xs text-muted-foreground">{loading ? "Loading drafts" : `${assets.length} available`}</p>
      </div>
      <div className="space-y-2">
        <label className="sr-only" htmlFor="calendar-tray-search">
          Search drafts
        </label>
        <div className="flex min-h-11 items-center gap-2 rounded-md border border-input bg-background px-3">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            id="calendar-tray-search"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none"
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            placeholder="Search drafts"
          />
        </div>
        <label className="sr-only" htmlFor="calendar-tray-type">
          Draft type
        </label>
        <select
          id="calendar-tray-type"
          className="h-11 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
          value={type}
          onChange={(event) => onType(event.target.value as "" | AssetType)}
        >
          {assetTypes.map((value) => (
            <option key={value || "all"} value={value}>
              {value ? assetTypeLabel(value) : "All draft types"}
            </option>
          ))}
        </select>
      </div>
      <div className="mt-3 space-y-2">
        {loading ? (
          <Panel className="h-24 animate-pulse bg-muted">
            <span className="sr-only">Loading draft assets</span>
          </Panel>
        ) : null}
        {!loading && !assets.length ? <p className="rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">No unscheduled drafts match.</p> : null}
        {assets.map((asset) => (
          <TrayAssetCard key={asset.id} asset={asset} scheduling={scheduling} onSchedule={onSchedule} />
        ))}
      </div>
    </aside>
  );
}

function TrayAssetCard({
  asset,
  scheduling,
  onSchedule,
}: {
  asset: AssetOut;
  scheduling: boolean;
  onSchedule: (asset: AssetOut, date: string) => void;
}) {
  const [scheduleDate, setScheduleDate] = useState(() => dateKey(new Date()));
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `asset:${asset.id}`,
    disabled: scheduling,
  });
  const style = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
      }
    : undefined;

  return (
    <article
      ref={setNodeRef}
      style={style}
      className={cn(
        "rounded-md border border-border bg-background p-2 transition-colors duration-ui ease-ui",
        isDragging ? "border-accent bg-accent-soft" : "",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="line-clamp-2 text-sm font-medium">{asset.title}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge tone="ink">{assetTypeLabel(asset.type)}</Badge>
            <Badge>{asset.status}</Badge>
          </div>
        </div>
        <button
          type="button"
          className="inline-flex h-11 w-11 items-center justify-center rounded-md text-muted-foreground transition-colors duration-ui ease-ui hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-45"
          aria-label={`Drag ${asset.title}`}
          disabled={scheduling}
          {...listeners}
          {...attributes}
        >
          <GripVertical className="h-4 w-4" />
        </button>
      </div>
      <div className="mt-2 grid grid-cols-[1fr_auto] gap-2">
        <label className="sr-only" htmlFor={`schedule-asset-${asset.id}`}>
          Schedule {asset.title}
        </label>
        <input
          id={`schedule-asset-${asset.id}`}
          type="date"
          className="h-9 rounded-md border border-input bg-surface px-2 text-xs outline-none focus:ring-2 focus:ring-ring"
          value={scheduleDate}
          disabled={scheduling}
          onChange={(event) => setScheduleDate(event.target.value)}
        />
        <Button type="button" size="sm" variant="outline" disabled={scheduling || !scheduleDate} onClick={() => onSchedule(asset, scheduleDate)}>
          Add
        </Button>
      </div>
    </article>
  );
}

function CalendarItemCard({
  item,
  updating,
  creatingVideoPack,
  draggableCard,
  active = false,
  onMove,
  onStatus,
  onDelete,
  onVideoPack,
}: {
  item: CalendarItemOut;
  updating: boolean;
  creatingVideoPack: boolean;
  draggableCard: boolean;
  active?: boolean;
  onMove?: (date: string) => void;
  onStatus: (status: string) => void;
  onDelete: () => void;
  onVideoPack: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: item.id,
    disabled: !draggableCard || updating,
  });
  const style = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
      }
    : undefined;
  const title = itemTitle(item);

  return (
    <div
      ref={draggableCard ? setNodeRef : undefined}
      style={style}
      className={cn(
        "rounded-md border border-border bg-background p-2 transition-colors duration-ui ease-ui",
        active || isDragging ? "border-accent bg-accent-soft" : "",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="line-clamp-2 text-sm font-medium">{title}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge>{itemChannel(item)}</Badge>
            <Badge tone={statusTone(item.status)}>{item.status}</Badge>
            {draggableCard ? <span className="text-xs text-muted-foreground">{itemSlot(item)}</span> : null}
          </div>
        </div>
        <div className="flex shrink-0 gap-1">
          {draggableCard ? (
            <button
              type="button"
              className="inline-flex h-11 w-11 items-center justify-center rounded-md text-muted-foreground transition-colors duration-ui ease-ui hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-45"
              aria-label={`Drag ${title}`}
              disabled={updating}
              {...listeners}
              {...attributes}
            >
              <GripVertical className="h-4 w-4" />
            </button>
          ) : null}
          {item.asset_id ? (
            <Button asChild variant="ghost" size="icon" aria-label={`Open asset ${item.asset_id}`}>
              <Link to={`/library?asset=${item.asset_id}`}>
                <ExternalLink className="h-4 w-4" />
              </Link>
            </Button>
          ) : null}
        </div>
      </div>
      {draggableCard && onMove ? (
        <div className="mt-2 grid grid-cols-2 gap-2">
          <label className="text-xs font-medium text-muted-foreground" htmlFor={`move-${item.id}`}>
            Move date
          </label>
          <input
            id={`move-${item.id}`}
            type="date"
            className="h-9 rounded-md border border-input bg-surface px-2 text-xs outline-none focus:ring-2 focus:ring-ring"
            value={item.date}
            disabled={updating}
            onChange={(event) => onMove(event.target.value)}
          />
        </div>
      ) : null}
      <div className="mt-2 flex items-center gap-2">
        {!draggableCard ? <Badge tone={statusTone(item.status)}>{item.status}</Badge> : null}
        <select
          aria-label={`Status for ${title}`}
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
        <Button type="button" variant="ghost" size="icon" aria-label={`Delete ${title}`} disabled={updating} onClick={onDelete}>
          <Trash2 className="h-4 w-4" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={`Create video pack for ${title}`}
          disabled={creatingVideoPack}
          onClick={onVideoPack}
        >
          <Video className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
