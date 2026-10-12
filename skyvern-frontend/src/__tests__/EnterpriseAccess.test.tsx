import { authFetch } from "@/util/authFetch";
vi.mock("@/api/AxiosClient", () => ({
  setAuthorizationHeader: vi.fn(),
  removeAuthorizationHeader: vi.fn(),
}));
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import axios from "axios";
import { LoginPage } from "@/routes/auth/LoginPage";
import {
  canAccess,
  homeFor,
  type EnterpriseUser,
} from "@/routes/enterprise/shared";
import { queryClient } from "@/api/QueryClient";
import { useAuthStore } from "@/store/AuthStore";
vi.mock("@/util/env", () => ({
  apiBaseUrl: "/api/v1",
  environment: "local",
  wssBaseUrl: "ws://localhost",
  newWssBaseUrl: "ws://localhost",
}));
vi.mock("axios", async (importOriginal) => {
  const original = await importOriginal<typeof import("axios")>();
  return {
    ...original,
    default: { ...original.default, get: vi.fn(), post: vi.fn() },
  };
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  queryClient.clear();
});
describe("enterprise entry", () => {
  it("routes roles without granting procurement or audit rights to approvers", () => {
    const user: EnterpriseUser = {
      user_id: "demo-user",
      org_id: "demo-org",
      is_operator: false,
      is_approver: true,
      is_admin: false,
      has_cross_org_read: false,
      department_roles: [
        { role: "approver", department_id: "demo", department_name: "演示" },
      ],
    };
    expect(homeFor(user)).toBe("/enterprise/approvals");
    expect(canAccess(user, "operator")).toBe(false);
    expect(canAccess(user, "audit")).toBe(false);
    expect(homeFor({ ...user, is_operator: true })).toBe(
      "/enterprise/dashboard",
    );
    expect(homeFor({ ...user, is_approver: false })).toBe("/enterprise/tasks");
  });
  it("does not invent an organization after failure and can retry", async () => {
    vi.mocked(axios.get)
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({
        data: [{ organization_id: "demo-org", organization_name: "合成组织" }],
      });
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    await screen.findByText(/无法加载组织/);
    expect(screen.queryByText(/锐智/)).toBeNull();
    expect(
      (screen.getByRole("button", { name: /登.*录/ }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    await screen.findByText("合成组织");
    await waitFor(() =>
      expect(
        (screen.getByRole("button", { name: /登.*录/ }) as HTMLButtonElement)
          .disabled,
      ).toBe(false),
    );
  });
  it("clears cached procurement facts on logout", () => {
    vi.stubGlobal("localStorage", {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    });
    queryClient.setQueryData(["enterprise", "demo-org", "demo-user", "tasks"], {
      secret: "synthetic",
    });
    useAuthStore.getState().logout();
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
  });
});

it("expires only the matching session and ignores a late 401 from an older login", async () => {
  const values = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  });
  useAuthStore.getState().login("synthetic-old", "user-old", "合成用户");
  let finish: (response: Response) => void = () => {};
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          finish = resolve;
        }),
    ),
  );
  const request = authFetch("/api/v1/enterprise/auth/me");
  useAuthStore.getState().login("synthetic-new", "user-new", "合成用户");
  finish({ status: 401 } as Response);
  await request;
  expect(useAuthStore.getState().isAuthenticated).toBe(true);
  const current = authFetch("/api/v1/enterprise/auth/me");
  finish({ status: 401 } as Response);
  await current;
  expect(useAuthStore.getState().isAuthenticated).toBe(false);
  vi.unstubAllGlobals();
});
