import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { LibraryPage } from "@/pages/LibraryPage";

class MockEventSource {
  constructor(public url: string) {}
  addEventListener() {
    return undefined;
  }
  close() {
    return undefined;
  }
}

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

const sourcePhoto = {
  id: 9,
  origin: "local",
  path: "C:\\shoots\\drop-one\\front.jpg",
  tags_json: JSON.stringify(["drop-one", "front-design"]),
  product_handle: null,
  created_at: "2026-07-07T12:10:00",
};

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <LibraryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LibraryPage", () => {
  beforeEach(() => {
    vi.stubGlobal("EventSource", MockEventSource);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input), "http://localhost");
        if (url.pathname === "/api/v1/assets" && init?.method !== "POST") {
          const q = url.searchParams.get("q") || "";
          const items = q.toLowerCase().includes("source") ? [imageAsset] : [asset, imageAsset];
          return response({ items, total: items.length, limit: 24, offset: 0 });
        }
        if (url.pathname === "/api/v1/source-assets" && init?.method !== "POST") {
          return response({ items: [sourcePhoto], total: 1 });
        }
        if (url.pathname === "/api/v1/source-assets/index" && init?.method === "POST") {
          return response({ items: [sourcePhoto], total: 1 });
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
        if (url.pathname === "/api/v1/assets/42/versions/1/critique" && init?.method === "POST") {
          return response({ asset_id: 42, version_no: 1, critique: "QA critique: sharpen source proof." });
        }
        if (url.pathname === "/api/v1/assets/42/versions/1/iterate" && init?.method === "POST") {
          return response({ job_id: "job-iterate", asset_id: 42 });
        }
        if (url.pathname === "/api/v1/assets/42/video-prompt-pack" && init?.method === "POST") {
          return response({ job_id: "job-video", asset_id: 77 });
        }
        if (url.pathname === "/api/v1/assets/77" && init?.method !== "POST") {
          return response({
            ...asset,
            id: 77,
            type: "video_script",
            title: "Video prompt pack: Drop caption",
            versions: [],
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

    await userEvent.click(screen.getByRole("button", { name: /video pack/i }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/assets/42/video-prompt-pack",
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("critiques and iterates an asset version", async () => {
    renderPage();

    await userEvent.click(await screen.findByText("Drop caption"));
    const firstVersion = await screen.findByText("First caption take");
    const firstVersionPanel = firstVersion.closest("section");
    expect(firstVersionPanel).not.toBeNull();

    await userEvent.click(within(firstVersionPanel as HTMLElement).getByRole("button", { name: /^critique$/i }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/assets/42/versions/1/critique",
        expect.objectContaining({ method: "POST" }),
      ),
    );

    await userEvent.click(within(firstVersionPanel as HTMLElement).getByRole("button", { name: /^iterate$/i }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/assets/42/versions/1/iterate",
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("indexes and lists source photos", async () => {
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /source photos/i }));
    expect(await screen.findByText("front.jpg")).toBeInTheDocument();

    await userEvent.type(screen.getByPlaceholderText(/local photoshoot folder path/i), "C:\\shoots\\drop-one");
    await userEvent.type(screen.getByPlaceholderText(/tags, comma separated/i), "drop-one, front-design");
    await userEvent.click(screen.getByRole("button", { name: /index local/i }));

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/source-assets/index",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            origin: "local",
            path: "C:\\shoots\\drop-one",
            tags: ["drop-one", "front-design"],
          }),
        }),
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
