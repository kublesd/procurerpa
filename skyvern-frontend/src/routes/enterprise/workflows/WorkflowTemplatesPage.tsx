import { FormEvent, useEffect, useRef, useState } from "react";
import { GlassCard } from "@/components/enterprise/GlassCard";
import { Link, useNavigate, useParams } from "react-router-dom";
import { authFetch } from "@/util/authFetch";

type Template = {
  template_id: string;
  name: string;
  description: string;
  execution_mode: string;
  data_mode?: string;
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
  const { instanceId } = useParams();
  const navigate = useNavigate();
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [instanceStale, setInstanceStale] = useState(false);
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
    setError("");
    setInstance(null);
    setDetail(null);
    if (instanceId) {
      setTemplates([]);
      setBusy(true);
      authFetch(
        "/api/v1/enterprise/workflows/instances/" +
          encodeURIComponent(instanceId),
      )
        .then(read<Instance>)
        .then((value) => {
          if (active) {
            setInstance(value);
            setInstanceStale(false);
          }
        })
        .catch(() => {
          if (active) setError("无法读取执行状态，请检查权限或重试");
        })
        .finally(() => {
          if (active) setBusy(false);
        });
      return () => {
        active = false;
      };
    }
    setBusy(true);
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
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [instanceId, loadAttempt]);

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
      navigate(
        "/enterprise/templates/instances/" +
          encodeURIComponent(result.instance_id),
      );
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
      setInstanceStale(false);
    } catch {
      setInstanceStale(true);
      setError("无法读取执行状态");
    } finally {
      setBusy(false);
    }
  }

  async function act(action: "recover" | "terminate") {
    if (!instance || busy || instanceStale) return;
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
      setInstanceStale(true);
      setError("状态或权限已变化，请刷新后重试");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-semibold">
        {instanceId ? "工作流实例" : "采购工作流模板"}
      </h1>
      {instanceId && (
        <Link className="text-blue-700 underline" to="/enterprise/templates">
          返回模板目录
        </Link>
      )}
      {busy && <p role="status">正在加载或提交…</p>}
      <p>
        选择模板后填写受控演示参数和组织内凭据引用。报价采集与比价请使用采购工作台。
      </p>
      {error && (
        <p role="alert" className="rounded-lg bg-red-50 p-3 text-red-700">
          {error}{" "}
          <button
            className="underline"
            onClick={() =>
              instance ? void refresh() : setLoadAttempt((n) => n + 1)
            }
          >
            重新读取
          </button>
        </p>
      )}
      {!busy && !error && !instanceId && templates.length === 0 && (
        <p role="status">暂无可用模板</p>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {templates.map((item) => (
          <GlassCard key={item.template_id}>
            <h2>{item.name}</h2>
            <p>{item.description}</p>
            <p>
              {item.execution_mode === "real"
                ? `原生工作流 · ${item.data_mode ?? "数据来源未标注"}`
                : `尚未接入执行（${item.execution_mode}）`}
            </p>
            <button
              className="glass-btn-secondary mt-3"
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
        <form
          onSubmit={(event) => void start(event)}
          className="space-y-4 rounded-xl border bg-white p-5"
        >
          <h2>{detail.name}</h2>
          <label>
            采购部门
            <select
              className="glass-input ml-3"
              disabled={busy}
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
              className="glass-input ml-3"
              disabled={busy}
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
                  className="glass-input mt-1 block w-full"
                  disabled={busy}
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
            className="glass-btn-primary"
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
        <section
          aria-label="执行状态"
          className="space-y-4 rounded-xl border bg-white p-5"
        >
          <h2>执行状态：{instance.status}</h2>
          <p>
            实例：{instance.instance_id} · 版本：{instance.version}
          </p>
          <button
            className="glass-btn-secondary"
            type="button"
            disabled={busy}
            onClick={() => void refresh()}
          >
            刷新状态
          </button>
          {instance.status === "ready" && (
            <button
              type="button"
              className="glass-btn-secondary mr-3"
              disabled={busy || instanceStale}
              onClick={() => void act("recover")}
            >
              启动未执行实例
            </button>
          )}
          {instance.status === "running" && (
            <button
              type="button"
              className="glass-btn-secondary mr-3"
              disabled={busy || instanceStale}
              onClick={() => void act("recover")}
            >
              转人工检查
            </button>
          )}
          {!["completed", "terminated"].includes(instance.status) && (
            <button
              type="button"
              className="glass-btn-secondary mr-3"
              disabled={busy || instanceStale}
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
              <li className="my-3 rounded-lg border p-3" key={step.label}>
                {step.label}：{step.status}{" "}
                {step.task_id && (
                  <Link
                    className="text-blue-700 underline"
                    to={
                      "/tasks/" +
                      encodeURIComponent(step.task_id) +
                      "/diagnostics"
                    }
                  >
                    Task: {step.task_id}
                  </Link>
                )}{" "}
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
