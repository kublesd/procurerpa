import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { DashboardPage } from "@/routes/enterprise/dashboard/DashboardPage";
import { authFetch } from "@/util/authFetch";

vi.mock("@/util/authFetch", () => ({ authFetch: vi.fn() }));
vi.mock("echarts-for-react", () => ({
  default: () => <div data-testid="chart" />,
}));
function translate(key: string) {
  return key;
}

vi.mock("@/i18n/useI18n", () => ({
  useI18n: () => ({ t: translate }),
}));

const mockedAuthFetch = vi.mocked(authFetch);

const emptyCost = {
  total_input_tokens: 0,
  total_output_tokens: 0,
  total_cached_tokens: 0,
  total_tokens: 0,
  total_cost_usd: 0,
  cost_status: "known",
  breakdown: [],
  action_cache: { status: "restricted" },
};

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe("DashboardPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows an empty state when PostgreSQL-backed APIs return no facts", async () => {
    mockedAuthFetch.mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/cost")) return jsonResponse(emptyCost);
      if (url.endsWith("/overview"))
        return jsonResponse({
          total_tasks: 0,
          completed_tasks: 0,
          active_tasks: 0,
          failed_tasks: 0,
          canceled_tasks: 0,
          pending_approvals: 0,
          total_quotes: 0,
          success_rate_30d: 0,
        });
      if (url.endsWith("/recent-tasks?limit=10"))
        return jsonResponse({ items: [] });
      return jsonResponse([]);
    });

    render(<DashboardPage />);

    await waitFor(() =>
      expect(screen.getAllByTestId("dashboard-empty").length).toBe(4),
    );
    expect(screen.queryByText("3,842")).toBeNull();
    expect(screen.queryByText(/Corporate Lending|LLM Cost/i)).toBeNull();
  });

  it("shows the API error without demo metrics", async () => {
    mockedAuthFetch.mockResolvedValue(
      jsonResponse({ detail: "dashboard unavailable" }, 500),
    );

    render(<DashboardPage />);

    await waitFor(() =>
      expect(screen.getAllByRole("alert")[0]?.textContent).toContain(
        "dashboard unavailable",
      ),
    );
    expect(screen.queryByText("3,842")).toBeNull();
    expect(screen.queryByText(/Corporate Lending|LLM Cost/i)).toBeNull();
  });
});

it("shows recorded tokens, unknown cost and Redis failure without inventing savings", async () => {
  mockedAuthFetch.mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/cost"))
      return jsonResponse({
        ...emptyCost,
        total_input_tokens: 300,
        total_output_tokens: 50,
        total_tokens: 350,
        total_cached_tokens: 100,
        total_cost_usd: null,
        cost_status: "unknown",
        breakdown: [
          {
            model_tier: "standard",
            total_steps: 2,
            total_tokens: 350,
            cost_usd: null,
            cost_status: "unknown",
          },
        ],
        action_cache: { status: "unavailable" },
      });
    if (url.endsWith("/overview"))
      return jsonResponse({
        total_tasks: 0,
        completed_tasks: 0,
        active_tasks: 0,
        failed_tasks: 0,
        canceled_tasks: 0,
        pending_approvals: 0,
        total_quotes: 0,
        success_rate_30d: 0,
      });
    if (url.includes("recent-tasks")) return jsonResponse({ items: [] });
    return jsonResponse([]);
  });
  render(<DashboardPage />);
  await screen.findByText("standard");
  expect(screen.getAllByText(/dashboard.costUnknown/)).toHaveLength(2);
  expect(screen.getByText("dashboard.cacheUnavailable")).toBeTruthy();
  expect(screen.queryByText("60%")).toBeNull();
  cleanup();
  vi.clearAllMocks();
});

it("keeps procurement overview readable if the cost API fails", async () => {
  mockedAuthFetch.mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/cost"))
      return jsonResponse({ detail: "cost unavailable" }, 503);
    if (url.endsWith("/overview"))
      return jsonResponse({
        total_tasks: 7,
        completed_tasks: 0,
        active_tasks: 0,
        failed_tasks: 0,
        canceled_tasks: 0,
        pending_approvals: 0,
        total_quotes: 0,
        success_rate_30d: 0,
      });
    if (url.includes("recent-tasks")) return jsonResponse({ items: [] });
    return jsonResponse([]);
  });
  render(<DashboardPage />);
  await screen.findByText("7");
  expect(screen.getByRole("alert").textContent).toContain("cost unavailable");
  cleanup();
  vi.clearAllMocks();
});
