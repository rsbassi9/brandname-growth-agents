import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { PlaygroundPage } from "@/pages/PlaygroundPage";

const videoPack = {
  kind: "video_prompt_pack",
  title: "Reconstructed reel",
  hook: "Open with the garment already in motion.",
  shot_list: [{ time: "0-2s", shot: "Campaign frame", motion: "Slow push-in" }],
  on_screen_text: ["SOURCE", "SYSTEM"],
  providers: {
    "muapi.ai": { role: "primary", prompt: "muapi prompt", settings: { aspect_ratio: "9:16" } },
    "fal.ai": { role: "secondary", prompt: "fal prompt", settings: { duration_seconds: 8 } },
    Runway: { role: "secondary", prompt: "runway prompt" },
    Kling: { role: "secondary", prompt: "kling prompt" },
  },
};

class MockEventSource {
  static instances: MockEventSource[] = [];
  listeners: Record<string, Array<(event: MessageEvent<string>) => void>> = {};
  url: string;

  constructor(url: string) {
    this.url = url;
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
        <PlaygroundPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PlaygroundPage", () => {
  beforeEach(() => {
    localStorage.clear();
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/v1/system/mode")) {
          return response({
            local_only_agent_runs: true,
            brand_name: "BRAND NAME",
            image_model: "gpt-image-1",
            model_default: "local-deterministic",
            model_premium: "",
            openai_base_url: "",
          });
        }
        if (url.endsWith("/api/v1/generate") && init?.method === "POST") {
          const body = JSON.parse(String(init.body || "{}")) as { type?: string };
          const assetId = body.type === "video_script" ? 77 : body.type === "voiceover" ? 78 : 42;
          return response({ job_id: "job-1", asset_id: assetId });
        }
        if (url.endsWith("/api/v1/assets/78")) {
          return response({
            id: 78,
            campaign_id: null,
            type: "voiceover",
            title: "Voiceover",
            status: "draft",
            source_path: null,
            created_at: "2026-07-07T12:00:00",
            versions: [
              {
                id: 8,
                asset_id: 78,
                version_no: 1,
                prompt_snapshot: "Prompt",
                params_json: "{}",
                content_text: "# Voiceover script draft\n\nTTS not configured (local-only mode): script-only version.",
                file_path: null,
                model_used: "local-deterministic",
                created_at: "2026-07-07T12:00:01",
                is_selected: true,
              },
            ],
          });
        }
        if (url.endsWith("/api/v1/assets/77")) {
          return response({
            id: 77,
            campaign_id: null,
            type: "video_script",
            title: "Reconstructed reel",
            status: "draft",
            source_path: null,
            created_at: "2026-07-07T12:00:00",
            versions: [
              {
                id: 7,
                asset_id: 77,
                version_no: 1,
                prompt_snapshot: "Prompt",
                params_json: "{}",
                content_text: JSON.stringify(videoPack),
                file_path: null,
                model_used: "local-deterministic",
                created_at: "2026-07-07T12:00:01",
                is_selected: true,
              },
            ],
          });
        }
        if (url.endsWith("/api/v1/assets/42")) {
          return response({
            id: 42,
            campaign_id: null,
            type: "copy",
            title: "Drop caption",
            status: "draft",
            source_path: null,
            created_at: "2026-07-07T12:00:00",
            versions: [
              {
                id: 1,
                asset_id: 42,
                version_no: 1,
                prompt_snapshot: "Prompt",
                params_json: "{}",
                content_text: "Hook: Archive fragment\n\nCaption draft: Same system, now worn.",
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

  it("submits a generate request and renders the completed version", async () => {
    renderPage();
    await userEvent.type(screen.getByLabelText(/brief/i), "Drop caption for the source-painting tee");
    await userEvent.click(screen.getByRole("button", { name: /generate/i }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    act(() => {
      MockEventSource.instances[0].emit("completion", {
        id: "job-1",
        kind: "generate_asset",
        status: "succeeded",
        progress_pct: 100,
        message: "done",
        payload_json: "{}",
        result_json: JSON.stringify({ asset_id: 42, version_no: 1 }),
        created_at: "2026-07-07T12:00:00",
        finished_at: "2026-07-07T12:00:02",
      });
    });

    expect(await screen.findByText(/caption draft/i)).toBeInTheDocument();
    expect(screen.getByText(/version 1/i)).toBeInTheDocument();
    expect(screen.getAllByText(/drop caption for the source-painting tee/i).length).toBeGreaterThanOrEqual(2);
  });

  it("renders video prompt packs with provider tabs", async () => {
    renderPage();
    await userEvent.click(screen.getByRole("button", { name: /video script/i }));
    await userEvent.type(screen.getByLabelText(/brief/i), "Build a reel from campaign frames");
    await userEvent.click(screen.getByRole("button", { name: /generate/i }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    act(() => {
      MockEventSource.instances[0].emit("completion", {
        id: "job-1",
        kind: "generate_asset",
        status: "succeeded",
        progress_pct: 100,
        message: "done",
        payload_json: "{}",
        result_json: JSON.stringify({ asset_id: 77, version_no: 1 }),
        created_at: "2026-07-07T12:00:00",
        finished_at: "2026-07-07T12:00:02",
      });
    });

    expect(await screen.findByText("Reconstructed reel")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /muapi.ai/i })).toHaveAttribute("aria-selected", "true");
    await userEvent.click(screen.getByRole("tab", { name: /runway/i }));
    expect(screen.getByText("runway prompt")).toBeInTheDocument();
  });

  it("creates a script-only voiceover from the UI", async () => {
    renderPage();
    await userEvent.click(screen.getByRole("button", { name: /voiceover/i }));
    await userEvent.type(screen.getByLabelText(/brief/i), "Narrate the source painting drop");
    await userEvent.click(screen.getByRole("button", { name: /generate/i }));

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    act(() => {
      MockEventSource.instances[0].emit("completion", {
        id: "job-1",
        kind: "generate_asset",
        status: "succeeded",
        progress_pct: 100,
        message: "done",
        payload_json: "{}",
        result_json: JSON.stringify({ asset_id: 78, version_no: 1 }),
        created_at: "2026-07-07T12:00:00",
        finished_at: "2026-07-07T12:00:02",
      });
    });

    expect(await screen.findByText(/tts not configured/i)).toBeInTheDocument();
    expect(screen.getByText(/version 1/i)).toBeInTheDocument();
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
