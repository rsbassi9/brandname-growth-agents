import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SystemPage } from "@/pages/SystemPage";

function renderSystemPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <SystemPage />
    </QueryClientProvider>,
  );
}

describe("P3-1 System daily workflow controls", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input), "http://localhost");
        if (url.pathname === "/api/v1/system/health") {
          return response({ status: "ok", brand: "BRAND NAME" });
        }
        if (url.pathname === "/api/v1/system/mode") {
          return response({
            local_only_agent_runs: true,
            brand_name: "BRAND NAME",
            image_model: "gpt-image-1",
            model_default: "gpt-5.4-mini",
            model_premium: "",
            openai_base_url: "",
          });
        }
        if (url.pathname === "/api/v1/system/daily-workflow" && init?.method === "PUT") {
          return response({ enabled: true, time_local: "08:15", last_enqueued_date: "" });
        }
        if (url.pathname === "/api/v1/system/daily-workflow/run" && init?.method === "POST") {
          return response({ job_id: "job-123" });
        }
        if (url.pathname === "/api/v1/system/daily-workflow/runs") {
          return response([
            {
              id: "job-abc-123",
              status: "succeeded",
              progress_pct: 100,
              message: "done",
              mode: "local_only",
              created_at: "2026-07-08T12:00:00",
              finished_at: "2026-07-08T12:01:00",
              steps: [
                {
                  name: "content_candidates",
                  status: "asset_created",
                  asset_id: 42,
                  source_path: "outputs/content_candidates/demo.md",
                },
              ],
            },
          ]);
        }
        if (url.pathname === "/api/v1/system/daily-workflow") {
          return response({ enabled: false, time_local: "09:00", last_enqueued_date: "" });
        }
        return response({}, 404);
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("updates schedule settings and starts a manual workflow run", async () => {
    renderSystemPage();

    expect(await screen.findByText("Daily Workflow")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText(/enable daily schedule/i));
    await userEvent.clear(screen.getByLabelText(/local time/i));
    await userEvent.type(screen.getByLabelText(/local time/i), "08:15");
    await userEvent.click(screen.getByRole("button", { name: /save schedule/i }));

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/system/daily-workflow",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ enabled: true, time_local: "08:15" }),
        }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: /run now/i }));
    expect(await screen.findByText(/started job job-123/i)).toBeInTheDocument();
    expect(await screen.findByText(/workflow runs/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open content candidates asset in library/i })).toHaveAttribute(
      "href",
      "/library?asset=42",
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
