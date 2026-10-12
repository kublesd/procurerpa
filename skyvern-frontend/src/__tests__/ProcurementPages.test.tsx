import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  render,
  screen,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  ProcurementTaskPage,
  ProcurementTasksPage,
} from "@/routes/enterprise/procurement/ProcurementTasksPage";
import { authFetch } from "@/util/authFetch";
vi.mock("@/util/authFetch", () => ({ authFetch: vi.fn() }));
vi.mock("@/store/AuthStore", () => ({
  useAuthStore: (fn: (s: { userId: string }) => unknown) =>
    fn({ userId: "buyer-demo" }),
}));
const user = {
  user_id: "buyer-demo",
  org_id: "org-demo",
  is_operator: true,
  is_approver: false,
  is_admin: false,
  department_roles: [],
};
const task = {
  task_id: "task-demo",
  title: "合成报价",
  status: "completed",
  department_id: "dept-demo",
  category_id: "cat-demo",
  risk_level: "low",
  risk_reason: "合成规则",
  created_by: "buyer-demo",
};
const clients: QueryClient[] = [];
function mount(path: string, route: string, element: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  clients.push(client);
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={route} element={element} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
const json = (body: unknown, status = 200) =>
  ({ ok: status < 400, status, json: async () => body }) as Response;
afterEach(() => {
  cleanup();
  clients.forEach((c) => c.clear());
  vi.clearAllMocks();
});
it("reloads a task and handles version conflict without repeating recovery", async () => {
  let mutations = 0;
  vi.mocked(authFetch).mockImplementation(async (input) => {
    const path = String(input);
    if (path.endsWith("/auth/me")) return json(user);
    if (path.includes("recover-quote")) {
      mutations++;
      expect(path).toContain("expected_version=7");
      return json({}, 409);
    }
    if (path.endsWith("/quote-state"))
      return json({
        state: { current_step: "running", version: 7, skills: [] },
      });
    if (path.includes("/quotes?")) return json({ quotes: [] });
    return json(task);
  });
  mount(
    "/enterprise/tasks/task-demo",
    "/enterprise/tasks/:taskId",
    <ProcurementTaskPage />,
  );
  fireEvent.click(await screen.findByText("恢复报价状态"));
  await screen.findByText(/状态已变化/);
  expect(mutations).toBe(1);
  expect(screen.getByText(/原生任务完成不等于报价入库成功/)).toBeTruthy();
});
it("restores comparison selection from URL and displays exact backend money", async () => {
  vi.mocked(authFetch).mockImplementation(async (input) => {
    const path = String(input);
    if (path.endsWith("/auth/me")) return json(user);
    if (path.includes("/quotes/compare?")) {
      expect(path).toContain("task_ids=task-demo");
      return json({
        recommended_quote_id: "quote-demo",
        recommendation_reason: "服务端确定性规则",
        quotes: [
          {
            quote_id: "quote-demo",
            task_id: "task-demo",
            artifact_id: "artifact-demo",
            supplier_id: "供应商演示",
            total_cny: "9007199254740993.01",
            landed_unit_price_cny: "0.123456",
            delivery_days: 3,
            eligible: true,
            rank: 1,
            reason: "规则结果",
          },
        ],
      });
    }
    return json({ tasks: [task], total: 1 });
  });
  mount(
    "/enterprise/tasks?task_ids=task-demo",
    "/enterprise/tasks",
    <ProcurementTasksPage />,
  );
  await screen.findByText("9007199254740993.01");
  expect(screen.getByText("0.123456")).toBeTruthy();
  await waitFor(() =>
    expect((screen.getByRole("checkbox") as HTMLInputElement).checked).toBe(
      true,
    ),
  );
});
it("does not display denied task data", async () => {
  vi.mocked(authFetch).mockImplementation(async (input) =>
    String(input).endsWith("/auth/me") ? json(user) : json({}, 403),
  );
  mount(
    "/enterprise/tasks/other-org",
    "/enterprise/tasks/:taskId",
    <ProcurementTaskPage />,
  );
  await screen.findByText(/无权限访问/);
  expect(screen.queryByText("合成报价")).toBeNull();
});

import { HumanReviewPage } from "@/routes/enterprise/procurement/HumanReviewsPage";
import { ApprovalDetailPage } from "@/routes/enterprise/approvals/ApprovalsPage";
const review = {
  review_id: "review-demo",
  task_id: "task-demo",
  status: "pending",
  reason_code: "invalid_quote",
  safe_error_summary: "合成抽取异常",
  artifact_id: "artifact-demo",
  created_at: "2026-10-02T00:00:00Z",
  resolution_action: null,
  resolution_note: null,
  resolved_by: null,
};
it("submits exact manual decimals and shows server validation rejection", async () => {
  let body: Record<string, unknown> | undefined;
  vi.mocked(authFetch).mockImplementation(async (input, init) => {
    const path = String(input);
    if (path.endsWith("/auth/me")) return json(user);
    if (path.endsWith("/resolve")) {
      body = JSON.parse(String(init?.body));
      return json({}, 422);
    }
    return json(review);
  });
  mount(
    "/enterprise/human-reviews/review-demo",
    "/enterprise/human-reviews/:reviewId",
    <HumanReviewPage />,
  );
  await screen.findByText("合成抽取异常");
  for (const [label, value] of [
    ["供应商 ID", "supplier-demo"],
    ["物料名称", "合成物料"],
    ["数量", "1"],
    ["单价（CNY）", "9007199254740993.01"],
    ["交期（天）", "3"],
  ])
    fireEvent.change(screen.getByLabelText(label!), { target: { value } });
  fireEvent.click(screen.getByRole("button", { name: "提交核验结果" }));
  await screen.findByText(/参数不符合要求/);
  expect(body).toMatchObject({
    action: "manual_complete",
    manual_result: {
      unit_price_cny: "9007199254740993.01",
      quantity: "1",
      artifact_id: "artifact-demo",
      delivery_days: 3,
      unit: "unit",
      currency: "CNY",
    },
  });
});
it("marks skipped review as no quote and refreshes after processing", async () => {
  let current: Omit<typeof review, "resolution_action"> & {
    resolution_action: string | null;
  } = { ...review };
  vi.mocked(authFetch).mockImplementation(async (input, init) => {
    const path = String(input);
    if (path.endsWith("/auth/me")) return json(user);
    if (path.endsWith("/resolve")) {
      expect(JSON.parse(String(init?.body))).toEqual({
        action: "skip_step",
        note: "",
      });
      current = {
        ...current,
        status: "resolved",
        resolution_action: "skip_step",
      };
      return json(current);
    }
    return json(current);
  });
  mount(
    "/enterprise/human-reviews/review-demo",
    "/enterprise/human-reviews/:reviewId",
    <HumanReviewPage />,
  );
  fireEvent.change(await screen.findByLabelText("处理方式"), {
    target: { value: "skip_step" },
  });
  fireEvent.click(screen.getByRole("button", { name: "提交核验结果" }));
  await screen.findByText("已跳过，未生成报价");
  expect(screen.queryByText(/已人工补录/)).toBeNull();
});
it("records approval once without automatically continuing procurement", async () => {
  let status = "pending";
  const writes: string[] = [];
  const a = {
    approval_id: "apr-demo",
    task_id: "task-demo",
    status,
    risk_level: "high",
    risk_reason: "合成高风险",
    operation_description: "合成申请",
    requester_user_id: "other-demo",
    department_id: "dept-demo",
    category_id: "cat-demo",
    approver_department_id: "dept-demo",
    requested_at: "2026-10-02",
    total_amount_cny: "100000",
    matched_threshold_cny: "100000",
    policy_version: "approval-cny-v1",
  };
  vi.mocked(authFetch).mockImplementation(async (input, init) => {
    const path = String(input);
    if (path.endsWith("/auth/me"))
      return json({ ...user, is_operator: false, is_approver: true });
    if (path.endsWith("/updates")) return new Promise<Response>(() => {});
    if (init?.method === "POST") {
      writes.push(path);
      status = "approved";
      return json({ ...a, status });
    }
    if (path.endsWith("/pending")) return json(status === "pending" ? [a] : []);
    return json({ ...a, status });
  });
  mount(
    "/enterprise/approvals/apr-demo",
    "/enterprise/approvals/:approvalId",
    <ApprovalDetailPage />,
  );
  fireEvent.click(await screen.findByRole("button", { name: "批准" }));
  await waitFor(() =>
    expect(screen.queryByRole("button", { name: "批准" })).toBeNull(),
  );
  expect(writes).toEqual(["/api/v1/enterprise/approvals/apr-demo/approve"]);
});

import { AuditLogsPage } from "@/routes/enterprise/audit/AuditLogsPage";
it("sends audit filters and pagination to the server", async () => {
  const requests: string[] = [];
  vi.mocked(authFetch).mockImplementation(async (input) => {
    const path = String(input);
    if (path.endsWith("/auth/me")) return json(user);
    requests.push(path);
    return json({
      items: [],
      total: 41,
      page: path.includes("page=2") ? 2 : 1,
      page_size: 20,
    });
  });
  mount(
    "/enterprise/audit?task_id=task-demo",
    "/enterprise/audit",
    <AuditLogsPage />,
  );
  fireEvent.click(await screen.findByRole("button", { name: "下一页" }));
  await waitFor(() =>
    expect(
      requests.some(
        (p) => p.includes("page=2") && p.includes("task_id=task-demo"),
      ),
    ).toBe(true),
  );
  fireEvent.change(screen.getByLabelText("动作类型"), {
    target: { value: "quote_state_changed" },
  });
  fireEvent.click(screen.getByRole("button", { name: "筛选" }));
  await waitFor(() =>
    expect(
      requests.some(
        (p) =>
          p.includes("action_type=quote_state_changed") && p.includes("page=1"),
      ),
    ).toBe(true),
  );
});
