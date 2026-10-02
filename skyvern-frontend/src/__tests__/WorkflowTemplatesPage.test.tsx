import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { WorkflowTemplatesPage } from "@/routes/enterprise/workflows/WorkflowTemplatesPage";
import { authFetch } from "@/util/authFetch";
vi.mock("@/util/authFetch", () => ({ authFetch: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
it("shows disconnected templates and never renders legacy password inputs", async () => {
  vi.mocked(authFetch).mockImplementation(async (input) => {
    const path = String(input);
    const template = {
      template_id: "tpl_quote",
      name: "报价台账",
      description: "受控演示",
      execution_mode: "not_connected",
    };
    const body = path.endsWith("context-options")
      ? { departments: [], categories: [] }
      : path.endsWith("templates")
        ? [template]
        : {
            ...template,
            parameters: [
              {
                name: "password",
                label: "门户密码",
                required: true,
                param_type: "password",
                default: null,
              },
              {
                name: "credential_id",
                label: "凭据引用",
                required: true,
                param_type: "string",
                default: null,
              },
            ],
          };
    return { ok: true, json: async () => body } as Response;
  });
  render(<WorkflowTemplatesPage />);
  fireEvent.click(await screen.findByText("选择 报价台账"));
  expect(await screen.findByLabelText("凭据引用")).toBeTruthy();
  expect(screen.queryByLabelText("门户密码")).toBeNull();
  expect((screen.getByText("启动模板") as HTMLButtonElement).disabled).toBe(
    true,
  );
  expect(
    vi
      .mocked(authFetch)
      .mock.calls.every(([, init]) => init?.method !== "POST"),
  ).toBe(true);
});

it("retries a lost start response with the same idempotency key and displays safe evidence", async () => {
  const keys: string[] = [];
  vi.mocked(authFetch).mockImplementation(async (input, init) => {
    const path = String(input);
    const template = {
      template_id: "tpl_quote",
      name: "报价台账",
      description: "受控演示",
      execution_mode: "real",
    };
    if (init?.method === "POST") {
      keys.push(new Headers(init.headers).get("Idempotency-Key") ?? "");
      if (keys.length === 1) throw new Error("lost response");
      return {
        ok: true,
        json: async () => ({
          instance_id: "instance-demo",
          status: "completed",
          version: 2,
          steps: [
            {
              label: "table_extract_1",
              status: "completed",
              task_id: "task-demo",
              artifact_ids: ["artifact-demo"],
            },
          ],
        }),
      } as Response;
    }
    const body = path.endsWith("context-options")
      ? {
          departments: [{ department_id: "dept-demo", name: "演示部门" }],
          categories: [{ category_id: "category-demo", name: "演示品类" }],
        }
      : path.endsWith("templates")
        ? [template]
        : { ...template, parameters: [] };
    return { ok: true, json: async () => body } as Response;
  });
  render(<WorkflowTemplatesPage />);
  fireEvent.click(await screen.findByText("选择 报价台账"));
  fireEvent.click(await screen.findByText("启动模板"));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByText("启动模板"));
  expect(await screen.findByText("Artifact: artifact-demo")).toBeTruthy();
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[1]).toBe(keys[0]);
});

it("recovers and terminates using the latest instance version", async () => {
  const actions: { path: string; version: number }[] = [];
  vi.mocked(authFetch).mockImplementation(async (input, init) => {
    const path = String(input);
    const template = {
      template_id: "tpl_quote",
      name: "报价台账",
      description: "受控演示",
      execution_mode: "real",
    };
    if (init?.method === "POST") {
      let status = "running";
      let version = 3;
      if (path.endsWith("recover") || path.endsWith("terminate")) {
        actions.push({
          path,
          version: JSON.parse(String(init.body)).expected_version,
        });
        status = path.endsWith("recover") ? "needs_human" : "terminated";
        version = path.endsWith("recover") ? 4 : 5;
      }
      return {
        ok: true,
        json: async () => ({
          instance_id: "instance-demo",
          status,
          version,
          steps: [],
        }),
      } as Response;
    }
    const body = path.endsWith("context-options")
      ? {
          departments: [{ department_id: "dept-demo", name: "演示部门" }],
          categories: [{ category_id: "category-demo", name: "演示品类" }],
        }
      : path.endsWith("templates")
        ? [template]
        : { ...template, parameters: [] };
    return { ok: true, json: async () => body } as Response;
  });
  render(<WorkflowTemplatesPage />);
  fireEvent.click(await screen.findByText("选择 报价台账"));
  fireEvent.click(await screen.findByText("启动模板"));
  fireEvent.click(await screen.findByText("转人工检查"));
  await screen.findByText("执行状态：needs_human");
  fireEvent.click(screen.getByText("终止实例"));
  await screen.findByText("执行状态：terminated");
  expect(actions.map(({ version }) => version)).toEqual([3, 4]);
  expect(actions[0]?.path).toMatch(/recover$/);
  expect(actions[1]?.path).toMatch(/terminate$/);
  expect(screen.queryByText("终止实例")).toBeNull();
});
