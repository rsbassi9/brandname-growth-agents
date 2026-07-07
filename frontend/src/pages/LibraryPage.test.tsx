import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { LibraryPage } from "@/pages/LibraryPage";

const asset = {
  id: 42,
  campaign_id: null,
  type: "copy",
  title: "Drop caption",
  status: "draft",
  source_path: null,
  created_at: "2026-07-07T12:00:00",
};

const imageAsset = {
  id: 43,
  campaign_id: null,
  type: "image_concept",
  title: "Source photo prompt",
  status: "selected",
  source_path: null,
  created_at: "2026-07-07T12:05:00",
};

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <LibraryPage />
    </QueryClientProvider>,
  );
}

describe("LibraryPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input), "http://localhost");
        if (url.pathname === "/api/v1/assets" && init?.method !== "POST") {
          const q = url.searchParams.get("q") || "";
          const items = q.toLowerCase().includes("source") ? [imageAsset] : [asset, imageAsset];
          return response({ items, total: items.length, limit: 24, offset: 0 });
        }
        if (url.pathname === "/api/v1/assets/42" && init?.method !== "POST") {
          return response({
            ...asset,
            versions: [
              {
                id: 1,
                asset_id: 42,
                version_no: 1,
                prompt_snapshot: "Prompt one",
                params_json: "{}",
                content_text: "First caption take",
                file_path: null,
                model_used: "local-deterministic",
                created_at: "2026-07-07T12:00:01",
                is_selected: true,
              },
              {
                id: 2,
                asset_id: 42,
                version_no: 2,
                prompt_snapshot: "Prompt two",
                params_json: "{}",
                content_text: "Second caption take",
                file_path: null,
                model_used: "local-deterministic",
                created_at: "2026-07-07T12:01:01",
                is_selected: false,
              },
            ],
          });
        }
        if (url.pathname === "/api/v1/assets/42/versions/2/select" && init?.method === "POST") {
          return response({
            ...asset,
            status: "selected",
            versions: [
              {
                id: 1,
                asset_id: 42,
                version_no: 1,
                prompt_snapshot: "Prompt one",
                params_json: "{}",
                content_text: "First caption take",
                file_path: null,
                model_used: "local-deterministic",
                created_at: "2026-07-07T12:00:01",
                is_selected: false,
              },
              {
                id: 2,
                asset_id: 42,
                version_no: 2,
                prompt_snapshot: "Prompt two",
                params_json: "{}",
                content_text: "Second caption take",
                file_path: null,
                model_used: "local-deterministic",
                created_at: "2026-07-07T12:01:01",
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

  it("filters assets and selects a library version", async () => {
    renderPage();

    expect(await screen.findByText("Drop caption")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/search library/i), "source");
    expect(await screen.findByText("Source photo prompt")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Drop caption")).not.toBeInTheDocument());

    await userEvent.clear(screen.getByLabelText(/search library/i));
    await userEvent.click(await screen.findByText("Drop caption"));

    expect(await screen.findByText("First caption take")).toBeInTheDocument();
    const secondVersion = screen.getByText("Second caption take").closest("section");
    expect(secondVersion).not.toBeNull();
    await userEvent.click(within(secondVersion as HTMLElement).getByRole("button", { name: /select this take/i }));

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/assets/42/versions/2/select",
        expect.objectContaining({ method: "POST" }),
      ),
    );
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
