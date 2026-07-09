import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { CalendarPage } from "@/pages/CalendarPage";
import { FeedGridPage } from "@/pages/FeedGridPage";

const calendarItems = [
  {
    id: "post-1",
    date: "2026-07-08",
    status: "draft",
    asset_id: 42,
    data: { title: "Launch teaser", channel: "Instagram" },
  },
];

const feedItems = [
  {
    id: "post-1",
    date: "2026-07-08",
    status: "draft",
    asset_id: 42,
    data: { title: "Launch teaser", channel: "Instagram" },
  },
  {
    id: "post-2",
    date: "2026-07-09",
    status: "scheduled",
    asset_id: null,
    data: { title: "Studio grid" },
  },
];

const draftAssets = [
  {
    id: 42,
    campaign_id: null,
    type: "copy",
    title: "Already scheduled draft",
    status: "draft",
    source_path: null,
    created_at: "2026-07-08T10:00:00",
  },
  {
    id: 77,
    campaign_id: null,
    type: "image_concept",
    title: "Fabric macro",
    status: "draft",
    source_path: null,
    created_at: "2026-07-08T11:00:00",
  },
];

function renderRoute(route: "/calendar" | "/feed") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/feed" element={<FeedGridPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("P2-5 Calendar and Feed Grid", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input), "http://localhost");
        if (url.pathname === "/api/v1/calendar" && init?.method === "POST") {
          const body = JSON.parse(String(init.body || "{}"));
          return response(
            {
              id: body.asset_id ? "post-asset-77" : "post-3",
              date: body.date,
              status: body.status,
              asset_id: body.asset_id ?? null,
              data: body.data,
            },
            201,
          );
        }
        if (url.pathname === "/api/v1/assets") {
          return response({ items: draftAssets, total: draftAssets.length, limit: 60, offset: 0 });
        }
        if (url.pathname === "/api/v1/performance/best-times") {
          return response([{ channel: "instagram", weekday: 2, hour: 18, sample_size: 3, mean_engagement_rate: 0.2 }]);
        }
        if (url.pathname === "/api/v1/calendar") {
          return response(calendarItems);
        }
        if (url.pathname === "/api/v1/calendar/post-1" && init?.method === "PATCH") {
          const patch = JSON.parse(String(init.body || "{}"));
          return response({
            ...calendarItems[0],
            ...("date" in patch ? { date: patch.date } : {}),
            ...("status" in patch ? { status: patch.status } : {}),
            data: { ...calendarItems[0].data, ...("slot" in patch ? { slot: patch.slot } : {}) },
          });
        }
        if (url.pathname === "/api/v1/calendar/post-1" && init?.method === "DELETE") {
          return response(null, 204);
        }
        if (url.pathname === "/api/v1/calendar/post-1/video-prompt-pack" && init?.method === "POST") {
          return response({ job_id: "job-video", asset_id: 88 });
        }
        if (url.pathname === "/api/v1/feed/order" && init?.method === "POST") {
          return response({ ok: true, count: 2 });
        }
        if (url.pathname === "/api/v1/feed") {
          return response(feedItems);
        }
        return response({}, 404);
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates and edits calendar items", async () => {
    renderRoute("/calendar");

    expect(await screen.findByText("Launch teaser")).toBeInTheDocument();
    expect(screen.getByText("Instagram")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/item title/i), "New drop post");
    await userEvent.clear(screen.getByLabelText(/^date$/i));
    await userEvent.type(screen.getByLabelText(/^date$/i), "2026-07-10");
    await userEvent.selectOptions(screen.getByLabelText(/^status$/i), "planned");
    await userEvent.click(screen.getByRole("button", { name: /add item/i }));

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/calendar",
        expect.objectContaining({ method: "POST" }),
      ),
    );

    await userEvent.selectOptions(screen.getByLabelText(/status for launch teaser/i), "scheduled");
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/calendar/post-1",
        expect.objectContaining({ method: "PATCH" }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: /^week$/i }));
    expect(await screen.findByText(/suggested - 18:00/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /suggested - 18:00/i }));
    await waitFor(() => {
      const patchCalls = vi.mocked(fetch).mock.calls.filter(([input, init]) => String(input) === "/api/v1/calendar/post-1" && init?.method === "PATCH");
      expect(patchCalls.some(([, init]) => init?.body === JSON.stringify({ date: "2026-07-08", slot: "18:00" }))).toBe(true);
    });
    fireEvent.change(screen.getByLabelText(/move date/i), { target: { value: "2026-07-09" } });
    await waitFor(() => {
      const patchCalls = vi.mocked(fetch).mock.calls.filter(([input, init]) => String(input) === "/api/v1/calendar/post-1" && init?.method === "PATCH");
      expect(patchCalls.some(([, init]) => init?.body === JSON.stringify({ date: "2026-07-09", slot: "day" }))).toBe(true);
    });
    expect(await screen.findByText("Fabric macro")).toBeInTheDocument();
    expect(screen.queryByText("Already scheduled draft")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/schedule fabric macro/i), { target: { value: "2026-07-11" } });
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));
    await waitFor(() => {
      const createCalls = vi.mocked(fetch).mock.calls.filter(([input, init]) => String(input) === "/api/v1/calendar" && init?.method === "POST");
      expect(
        createCalls.some(([, init]) => {
          const body = JSON.parse(String(init?.body || "{}"));
          return body.asset_id === 77 && body.date === "2026-07-11" && body.data.title === "Fabric macro";
        }),
      ).toBe(true);
    });

    await userEvent.click(screen.getByRole("button", { name: /delete launch teaser/i }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/calendar/post-1",
        expect.objectContaining({ method: "DELETE" }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: /create video pack for launch teaser/i }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/calendar/post-1/video-prompt-pack",
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("persists feed grid order changes", async () => {
    renderRoute("/feed");

    expect(await screen.findByText("Launch teaser")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /move launch teaser later/i }));
    await userEvent.click(screen.getByRole("button", { name: /save order/i }));

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/feed/order",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ item_ids: ["post-2", "post-1"] }),
        }),
      ),
    );
  });
});

function response(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 404 ? "Not Found" : "OK",
    json: async () => body,
  } as Response);
}
