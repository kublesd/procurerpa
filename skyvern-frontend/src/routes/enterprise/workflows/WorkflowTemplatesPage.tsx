import { FormEvent, useEffect, useRef, useState } from "react";
import { GlassCard } from "@/components/enterprise/GlassCard";
import { authFetch } from "@/util/authFetch";

type Template = {
  template_id: string;
  name: string;
  description: string;
  execution_mode: string;
};
type Parameter = {
  name: string;
  label: string;
  param_type: string;
  required: boolean;
  default: string | null;
};
type Detail = Template & { parameters: Parameter[] };
type Context = {
  departments: { department_id: string; name: string }[];
  categories: { category_id: string; name: string }[];
};
type Instance = {
  instance_id: string;
  status: string;
  version: number;
  steps: {
    label: string;
    status: string;
    task_id: string | null;
    artifact_ids: string[];
  }[];
};

async function read<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`请求失败 (${response.status})`);
  return response.json() as Promise<T>;
}

export function WorkflowTemplatesPage() {
  const attemptKey = useRef<string | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [context, setContext] = useState<Context>({
    departments: [],
    categories: [],
  });
  const [department, setDepartment] = useState("");
  const [category, setCategory] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [instance, setInstance] = useState<Instance | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    Promise.all([
      authFetch("/api/v1/enterprise/workflows/templates").then(
        read<Template[]>,
      ),
      authFetch("/api/v1/enterprise/procurement/context-options").then(
        read<Context>,
      ),
    ])
      .then(([items, options]) => {
        if (!active) return;
        setTemplates(items);
        setContext(options);
        setDepartment(options.departments[0]?.department_id ?? "");
        setCategory(options.categories[0]?.category_id ?? "");
      })
      .catch(() => {
        if (active) setError("无法加载模板目录");
      });
    return () => {
      active = false;
    };
  }, []);

  function resetAttempt() {
    attemptKey.current = null;
    setInstance(null);
  }

  async function select(template: Template) {
    setBusy(true);
    setError("");
    setDetail(null);
    setInstance(null);
    attemptKey.current = null;
    try {
      const item = await authFetch(
        `/api/v1/enterprise/workflows/templates/${template.template_id}`,
      ).then(read<Detail>);
      setDetail(item);
      setValues(
        Object.fromEntries(
          item.parameters
            .filter((p) => !["password", "username"].includes(p.name))
            .map((p) => [p.name, p.default ?? ""]),
        ),
      );
    } catch {
      setError("无法加载模板参数");
    } finally {
      setBusy(false);
    }
  }

  async function start(event: FormEvent) {
    event.preventDefault();
    if (!detail || busy || detail.execution_mode !== "real") return;
    setBusy(true);
    setError("");
    try {
      const result = await authFetch(
        `/api/v1/enterprise/workflows/instantiate/${detail.template_id}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": (attemptKey.current ??= crypto.randomUUID()),
          },
          body: JSON.stringify({
            department_id: department,
            category_id: category,
            parameters: values,
          }),
        },
      ).then(read<Instance>);
      setInstance(result);
    } catch {
      setError("启动失败，请检查权限、参数及凭据引用");
    } finally {
      setBusy(false);
    }
  }

  async function refresh() {
    if (!instance || busy) return;
    setBusy(true);
    setError("");
    try {
      setInstance(
        await authFetch(
          `/api/v1/enterprise/workflows/instances/${instance.instance_id}`,
        ).then(read<Instance>),
      );
    } catch {
      setError("无法读取执行状态");
    } finally {
      setBusy(false);
    }
  }

  async function act(action: "recover" | "terminate") {
    if (!instance || busy) return;
    setBusy(true);
    setError("");
    try {
      setInstance(
        await authFetch(
          `/api/v1/enterprise/workflows/instances/${instance.instance_id}/${action}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ expected_version: instance.version }),
          },
        ).then(read<Instance>),
      );
    } catch {
      setError("状态或权限已变化，请刷新后重试");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-semibold">采购工作流模板</h1>
      <p>
        选择模板后填写受控演示参数和组织内凭据引用。报价采集与比价请使用采购工作台。
      </p>
      {error && <p role="alert">{error}</p>}
      <div className="grid gap-4 md:grid-cols-2">
        {templates.map((item) => (
          <GlassCard key={item.template_id}>
            <h2>{item.name}</h2>
            <p>{item.description}</p>
            <p>
              {item.execution_mode === "real"
                ? "原生工作流 · 受控演示数据"
                : "尚未接入执行"}
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={() => void select(item)}
            >
              选择 {item.name}
            </button>
          </GlassCard>
        ))}
      </div>
      {detail && (
        <form onSubmit={(event) => void start(event)} className="space-y-4">
          <h2>{detail.name}</h2>
          <label>
            采购部门
            <select
              required
              value={department}
              onChange={(event) => {
                setDepartment(event.target.value);
                resetAttempt();
              }}
            >
              {context.departments.map((item) => (
                <option key={item.department_id} value={item.department_id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            采购品类
            <select
              required
              value={category}
              onChange={(event) => {
                setCategory(event.target.value);
                resetAttempt();
              }}
            >
              {context.categories.map((item) => (
                <option key={item.category_id} value={item.category_id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          {detail.parameters
            .filter((p) => !["password", "username"].includes(p.name))
            .map((p) => (
              <label key={p.name} className="block">
                {p.label}
                <input
                  required={p.required}
                  type={
                    p.param_type === "date"
                      ? "date"
                      : p.param_type === "integer"
                        ? "number"
                        : p.param_type === "url"
                          ? "url"
                          : "text"
                  }
                  value={values[p.name] ?? ""}
                  onChange={(event) => {
                    setValues((previous) => ({
                      ...previous,
                      [p.name]: event.target.value,
                    }));
                    resetAttempt();
                  }}
                />
              </label>
            ))}
          <button
            type="submit"
            disabled={
              busy || instance !== null || detail.execution_mode !== "real"
            }
          >
            启动模板
          </button>
        </form>
      )}
      {instance && (
        <section aria-label="执行状态">
          <h2>执行状态：{instance.status}</h2>
          <p>
            实例：{instance.instance_id} · 版本：{instance.version}
          </p>
          <button type="button" disabled={busy} onClick={() => void refresh()}>
            刷新状态
          </button>
          {instance.status === "ready" && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void act("recover")}
            >
              启动未执行实例
            </button>
          )}
          {instance.status === "running" && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void act("recover")}
            >
              转人工检查
            </button>
          )}
          {!["completed", "terminated"].includes(instance.status) && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void act("terminate")}
            >
              终止实例
            </button>
          )}
          {instance.status === "needs_human" && (
            <p>执行或证据不完整，需要人工检查；不会自动重放页面动作。</p>
          )}
          <ol>
            {instance.steps.map((step) => (
              <li key={step.label}>
                {step.label}：{step.status}{" "}
                {step.task_id && <span>Task: {step.task_id}</span>}{" "}
                {step.artifact_ids.map((id) => (
                  <span key={id}>Artifact: {id} </span>
                ))}
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
