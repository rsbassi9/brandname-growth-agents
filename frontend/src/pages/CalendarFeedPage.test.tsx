import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
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
    data: { title: "Launch teaser" },
  },
];

const feedItems = [
  {
    id: "post-1",
    date: "2026-07-08",
    status: "draft",
    asset_id: 42,
    data: { title: "Launch teaser" },
  },
  {
    id: "post-2",
    date: "2026-07-09",
    status: "scheduled",
    asset_id: null,
    data: { title: "Studio grid" },
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
          return response(
            {
              id: "post-3",
              date: "2026-07-10",
              status: "planned",
              asset_id: null,
              data: { title: "New drop post" },
            },
            201,
          );
        }
        if (url.pathname === "/api/v1/calendar") {
          return response(calendarItems);
        }
        if (url.pathname === "/api/v1/calendar/post-1" && init?.method === "PATCH") {
          return response({ ...calendarItems[0], status: "scheduled" });
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
