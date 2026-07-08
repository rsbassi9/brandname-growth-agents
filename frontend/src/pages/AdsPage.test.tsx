import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { AdsPage } from "@/pages/AdsPage";

const adBrief = {
  kind: "ad_brief",
  objective: "Sales",
  audience: "Warm drop audience",
  placement: "Instagram Feed + Reels",
  hook: "Source work, now worn",
  primary_text: ["Primary one", "Primary two", "Primary three"],
  headlines: ["Headline one", "Headline two", "Headline three"],
  cta: "Shop now",
  recommended_creative: "Library asset 42 + Source photo 9",
  manual_export_blocks: [
    "Primary text 1:\nPrimary one\n\nHeadline 1:\nHeadline one\n\nCTA:\nShop now",
    "Primary text 2:\nPrimary two\n\nHeadline 2:\nHeadline two\n\nCTA:\nShop now",
    "Primary text 3:\nPrimary three\n\nHeadline 3:\nHeadline three\n\nCTA:\nShop now",
  ],
};

class MockEventSource {
  static instances: MockEventSource[] = [];
  listeners: Record<string, Array<(event: MessageEvent<string>) => void>> = {};

  constructor(public url: string) {
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    this.listeners[type] = [...(this.listeners[type] || []), listener];
  }

  close() {
    return undefined;
  }

  emit(type: string, payload: unknown) {
    const event = new MessageEvent(type, { data: JSON.stringify(payload) });
    (this.listeners[type] || []).forEach((listener) => listener(event));
  }
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AdsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AdsPage", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    Object.assign(navigator, { clipboard: { writeText: vi.fn() } });
    vi.stubGlobal("EventSource", MockEventSource);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input), "http://localhost");
        if (url.pathname === "/api/v1/assets" && init?.method !== "POST") {
          return response({
            total: 1,
            limit: 100,
            offset: 0,
            items: [
              {
                id: 42,
                campaign_id: null,
                type: "copy",
                title: "Drop caption",
                status: "draft",
                source_path: null,
                created_at: "2026-07-07T12:00:00",
              },
            ],
          });
        }
        if (url.pathname === "/api/v1/source-assets") {
          return response({
            total: 1,
            items: [
              {
                id: 9,
                origin: "local",
                path: "C:\\shoots\\front.jpg",
                tags_json: "[]",
                product_handle: null,
                created_at: "2026-07-07T12:00:00",
              },
            ],
          });
        }
        if (url.pathname === "/api/v1/ads/briefs" && init?.method === "POST") {
          return response({ job_id: "job-ad", asset_id: 88 });
        }
        if (url.pathname === "/api/v1/assets/88") {
          return response({
            id: 88,
            campaign_id: null,
            type: "ad_brief",
            title: "Meta ad brief",
            status: "draft",
            source_path: null,
            created_at: "2026-07-07T12:00:00",
            versions: [
              {
                id: 8,
                asset_id: 88,
                version_no: 1,
                prompt_snapshot: "Prompt",
                params_json: "{}",
                content_text: JSON.stringify(adBrief),
                file_path: null,
                model_used: "local-deterministic",
                created_at: "2026-07-07T12:00:01",
                is_selected: true,
              },
            ],
          });
        }
        return response({}, 404);
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates a Meta ad brief and copies export blocks", async () => {
    renderPage();

    await userEvent.type(screen.getByLabelText(/hook/i), "Source work, now worn");
    await userEvent.selectOptions(await screen.findByLabelText(/library asset/i), "42");
    await userEvent.selectOptions(await screen.findByLabelText(/source photo/i), "9");
    await userEvent.click(screen.getByRole("button", { name: /create brief/i }));

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/ads/briefs",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"asset_id":42'),
        }),
      ),
    );

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    act(() => {
      MockEventSource.instances[0].emit("completion", {
        id: "job-ad",
        kind: "generate_asset",
        status: "succeeded",
        progress_pct: 100,
        message: "done",
        payload_json: "{}",
        result_json: JSON.stringify({ asset_id: 88, version_no: 1 }),
        created_at: "2026-07-07T12:00:00",
        finished_at: "2026-07-07T12:00:02",
      });
    });

    expect(await screen.findByText("Library asset 42 + Source photo 9")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: /copy/i })[0]);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining("Primary text 1"));
  });
});

function response(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Not Found",
    json: async () => body,
  } as Response);
}
