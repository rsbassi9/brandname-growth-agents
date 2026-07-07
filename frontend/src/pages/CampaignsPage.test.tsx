import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { CampaignsPage } from "@/pages/CampaignsPage";

const navigateStateSpy = vi.fn();
let campaigns: Array<{
  id: number;
  name: string;
  goal: string;
  status: string;
  created_at: string;
}>;

function StateProbe() {
  const location = useLocation();
  navigateStateSpy(location.state);
  return <p>Playground target</p>;
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/campaigns"]}>
        <Routes>
          <Route path="/campaigns" element={<CampaignsPage />} />
          <Route path="/playground" element={<StateProbe />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CampaignsPage", () => {
  beforeEach(() => {
    navigateStateSpy.mockClear();
    campaigns = [
      {
        id: 7,
        name: "Drop Recovery",
        goal: "Rebuild trust around the source-painting tee.",
        status: "active",
        created_at: "2026-07-07T12:00:00",
      },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input), "http://localhost");
        if (url.pathname === "/api/v1/campaigns" && init?.method !== "POST") {
          return response(campaigns);
        }
        if (url.pathname === "/api/v1/campaigns" && init?.method === "POST") {
          const campaign = {
            id: 8,
            name: "Photoshoot Push",
            goal: "Turn raw photos into launch assets.",
            status: "active",
            created_at: "2026-07-07T12:30:00",
          };
          campaigns = [campaign, ...campaigns];
          return response(campaign, 201);
        }
        if (url.pathname === "/api/v1/campaigns/7/assets") {
          return response([
            {
              id: 42,
              campaign_id: 7,
              type: "copy",
              title: "Trust caption",
              status: "draft",
              source_path: null,
              created_at: "2026-07-07T12:05:00",
            },
            {
              id: 43,
              campaign_id: 7,
              type: "image_concept",
              title: "Source photo prompt",
              status: "selected",
              source_path: null,
              created_at: "2026-07-07T12:10:00",
            },
          ]);
        }
        if (url.pathname === "/api/v1/campaigns/8/assets") {
          return response([]);
        }
        return response({}, 404);
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates campaigns, groups assets, and shortcuts generation into Playground", async () => {
    renderPage();

    expect(await screen.findAllByText("Drop Recovery")).toHaveLength(2);
    expect(await screen.findByText("Trust caption")).toBeInTheDocument();
    expect(screen.getByText("Source photo prompt")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText(/campaign name/i), "Photoshoot Push");
    await userEvent.type(screen.getByLabelText(/^goal$/i), "Turn raw photos into launch assets.");
    await userEvent.click(screen.getByRole("button", { name: /create campaign/i }));

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/campaigns",
        expect.objectContaining({ method: "POST" }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: /copy/i }));
    expect(await screen.findByText("Playground target")).toBeInTheDocument();
    expect(navigateStateSpy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        campaignId: 8,
        campaignName: "Photoshoot Push",
        assetType: "copy",
      }),
    );
  });
});

function response(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 || status === 201 ? "OK" : "Not Found",
    json: async () => body,
  } as Response);
}
