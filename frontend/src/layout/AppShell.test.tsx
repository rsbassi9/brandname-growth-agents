import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { AppShell } from "@/layout/AppShell";

function renderShell() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/playground"]}>
        <AppShell />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AppShell", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => ({
          local_only_agent_runs: true,
          brand_name: "BRAND NAME",
          image_model: "gpt-image-1",
          model_default: "local-model",
          model_premium: "",
          openai_base_url: "",
        }),
      })),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the fixed studio navigation", async () => {
    renderShell();

    expect(await screen.findAllByText("BRAND NAME")).toHaveLength(2);
    expect(screen.getByRole("link", { name: /playground/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /campaigns/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /library/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /calendar/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /feed grid/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /ads & seo/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /strategy hub/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /system/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/premium model/i)).toBeInTheDocument();
  });
});
