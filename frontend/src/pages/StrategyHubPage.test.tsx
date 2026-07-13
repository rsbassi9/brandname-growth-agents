import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { StrategyHubPage } from "@/pages/StrategyHubPage";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <StrategyHubPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("StrategyHubPage", () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn(async () => undefined) },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input), "http://localhost");
        if (url.pathname === "/api/v1/strategy/context") {
          return response([
            { name: "brand_brief", content: "BRAND NAME is built around source-painting truth." },
            { name: "growth_strategy", content: "Use launches, proof, and manual publishing." },
          ]);
        }
        if (url.pathname === "/api/v1/strategy/brand-profile") {
          return response({
            current: {
              id: 2,
              version_no: 2,
              profile_md: "## Voice rules\n- Use source proof in the hook. (fb_1)\n## Banned phrases\nInsufficient evidence this period.\n## Visual codes\nInsufficient evidence this period.\n## Proven hooks\n- Open with canvas-to-garment proof. (pair_42)\n## Audience notes\nInsufficient evidence this period.",
              distilled_from_json: JSON.stringify({ evidence_ids: ["fb_1", "pair_42"] }),
              created_at: "2026-07-08T12:00:00",
            },
            versions: [
              {
                id: 2,
                version_no: 2,
                profile_md: "## Voice rules\n- Use source proof in the hook. (fb_1)\n## Banned phrases\nInsufficient evidence this period.\n## Visual codes\nInsufficient evidence this period.\n## Proven hooks\n- Open with canvas-to-garment proof. (pair_42)\n## Audience notes\nInsufficient evidence this period.",
                distilled_from_json: "{}",
                created_at: "2026-07-08T12:00:00",
              },
              {
                id: 1,
                version_no: 1,
                profile_md: "## Voice rules\nInsufficient evidence this period.\n## Banned phrases\nInsufficient evidence this period.\n## Visual codes\nInsufficient evidence this period.\n## Proven hooks\nInsufficient evidence this period.\n## Audience notes\nInsufficient evidence this period.",
                distilled_from_json: "{}",
                created_at: "2026-07-07T12:00:00",
              },
            ],
          });
        }
        if (url.pathname === "/api/v1/calendar") {
          return response([
            {
              id: "post-1",
              date: "2026-07-08",
              status: "draft",
              asset_id: 42,
              data: { title: "Launch teaser" },
            },
          ]);
        }
        if (url.pathname === "/api/v1/assets") {
          return response({
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
            total: 1,
            limit: 60,
            offset: 0,
          });
        }
        if (url.pathname === "/api/v1/assets/42") {
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
                content_text: "Caption draft: Same system, now worn.",
                file_path: null,
                model_used: "local-deterministic",
                created_at: "2026-07-07T12:00:01",
                is_selected: true,
              },
            ],
          });
        }
        if (url.pathname === "/api/v1/strategy/learn/summary") {
          return response({ summary: "Recent feedback prefers product-truth captions." });
        }
        if (url.pathname === "/api/v1/strategy/standup") {
          return response([
            {
              id: 7,
              week_start: "2026-07-06",
              report_md:
                "# Weekly Standup\n\n## What Published\n- [Source proof first](https://instagram.com/p/sourceproof)\n\n## Next Week Plan\n- Launch teaser",
              recommendations_json: JSON.stringify([
                {
                  title: "Turn the top proof hook into a fresh caption draft",
                  draft_type: "copy",
                  rationale: "Top performer: Source proof first.",
                  brief: "Create one unscheduled caption draft.",
                  evidence: { top_post_id: 5 },
                },
                {
                  title: "Patch the weakest post with clearer product truth",
                  draft_type: "copy",
                  rationale: "Bottom performer needs source proof.",
                  brief: "Create one unscheduled improvement draft.",
                  evidence: { bottom_post_id: 6 },
                },
                {
                  title: "Pre-build next week's anchor post",
                  draft_type: "copy",
                  rationale: "Next week has one planned item.",
                  brief: "Create one unscheduled anchor caption.",
                  evidence: { next_calendar_item_ids: ["post-1"] },
                },
              ]),
              created_at: "2026-07-13T09:00:00",
            },
          ]);
        }
        if (url.pathname === "/api/v1/strategy/standup/7/recommendations/0/draft" && init?.method === "POST") {
          return response({ asset_id: 42 });
        }
        if (url.pathname === "/api/v1/performance/posts") {
          return response({
            items: [
              {
                id: 5,
                calendar_item_id: null,
                asset_id: null,
                channel: "instagram",
                external_ref: "https://instagram.com/p/sourceproof",
                permalink: "https://instagram.com/p/sourceproof",
                title_or_caption: "Source proof first",
                post_type: "Reel",
                meta_json: "{}",
                published_at: "2026-07-01T10:00:00",
                created_at: "2026-07-09T10:00:00",
              },
            ],
            total: 1,
          });
        }
        if (url.pathname === "/api/v1/performance/dashboard") {
          return response({
            top_posts: [
              {
                post_id: 5,
                channel: "instagram",
                title_or_caption: "Source proof first",
                published_at: "2026-07-01T10:00:00",
                engagement_rate: 0.2125,
                calendar_item_id: null,
                asset_id: null,
              },
            ],
            weekly_trend: [{ week: "2026-W27", mean_engagement_rate: 0.2125, sample_size: 1 }],
            by_asset_type: [{ asset_type: "copy", mean_engagement_rate: 0.2125, sample_size: 1 }],
          });
        }
        if (url.pathname === "/api/v1/strategy/learn/feedback" && init?.method === "POST") {
          return response(
            {
              id: "fb-1",
              created_at: "2026-07-07T12:00:00",
              output_path: "asset:42",
              rating: 5,
              comment: "Sharper.",
              improvement_request: "More proof.",
              category: "strategy_hub",
            },
            201,
          );
        }
        if (url.pathname === "/api/v1/performance/import" && init?.method === "POST") {
          return response({
            status: "imported",
            detected_columns: ["Post date", "Permalink", "Views"],
            posts_upserted: 1,
            metrics_inserted: 1,
            warnings: [],
            posts: [],
          });
        }
        if (url.pathname === "/api/v1/performance/posts/5/link" && init?.method === "PATCH") {
          return response({
            id: 5,
            calendar_item_id: "post-1",
            asset_id: 42,
            channel: "instagram",
            external_ref: "https://instagram.com/p/sourceproof",
            permalink: "https://instagram.com/p/sourceproof",
            title_or_caption: "Source proof first",
            post_type: "Reel",
            meta_json: "{}",
            published_at: "2026-07-01T10:00:00",
            created_at: "2026-07-09T10:00:00",
          });
        }
        return response({}, 404);
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders strategy lanes and posts learning feedback", async () => {
    renderPage();

    expect(await screen.findByText(/source-painting truth/i)).toBeInTheDocument();
    expect(screen.getByText(/profile v2/i)).toBeInTheDocument();
    expect(screen.getByText(/use source proof in the hook/i)).toBeInTheDocument();
    expect(screen.getByText(/version history/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /plan/i }));
    expect(await screen.findByText("Launch teaser")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^build$/i }));
    expect(await screen.findByText("Drop caption")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /ship manually/i }));
    await userEvent.selectOptions(screen.getByLabelText(/^asset$/i), "42");
    expect(await screen.findByText(/caption draft/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^copy$/i }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("Caption draft: Same system, now worn.");

    await userEvent.click(screen.getByRole("button", { name: /^learn$/i }));
    expect(await screen.findByRole("heading", { name: /weekly standup/i })).toBeInTheDocument();
    expect(screen.getByText(/turn the top proof hook/i)).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: /add to calendar as draft/i })[0]);
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/strategy/standup/7/recommendations/0/draft",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: /^performance$/i }));
    expect(await screen.findByText(/product-truth captions/i)).toBeInTheDocument();
    expect(await screen.findAllByText(/source proof first/i)).not.toHaveLength(0);
    expect(screen.getByText(/weekly er/i)).toBeInTheDocument();
    expect(screen.getByText(/by asset type/i)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/paste table/i), "Post date,Permalink,Views\n2026-07-01,x,100");
    await userEvent.click(screen.getByRole("button", { name: /import csv/i }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/performance/import",
        expect.objectContaining({ method: "POST", body: expect.any(FormData) }),
      ),
    );
    expect(await screen.findByText(/post date, permalink, views/i)).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText(/published post/i), "5");
    await userEvent.type(screen.getByLabelText(/calendar item id/i), "post-1");
    await userEvent.click(screen.getByRole("button", { name: /^link$/i }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/performance/posts/5/link",
        expect.objectContaining({ method: "PATCH" }),
      ),
    );
    await userEvent.type(screen.getByLabelText(/output path/i), "asset:42");
    await userEvent.selectOptions(screen.getByLabelText(/rating/i), "5");
    await userEvent.type(screen.getByLabelText(/comment/i), "Sharper.");
    await userEvent.type(screen.getByLabelText(/improvement request/i), "More proof.");
    await userEvent.click(screen.getByRole("button", { name: /save feedback/i }));

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/strategy/learn/feedback",
        expect.objectContaining({ method: "POST" }),
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
