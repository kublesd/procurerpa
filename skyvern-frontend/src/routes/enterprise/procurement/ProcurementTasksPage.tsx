import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { GlassCard } from "@/components/enterprise/GlassCard";
import { StatusBadge } from "@/components/enterprise/StatusBadge";
import { RiskBadge } from "@/components/enterprise/RiskBadge";
import {
  enterpriseJson,
  useEnterpriseQuery,
  useEnterpriseUser,
} from "../shared";
import { Pagination, QueryFeedback } from "../EnterpriseAccess";

type Task = {
  task_id: string;
  title: string | null;
  status: string;
  department_id: string;
  category_id: string;
  risk_level: string;
  risk_reason: string;
  created_by: string;
  approval_id?: string | null;
  review_id?: string | null;
};
type Quote = {
  quote_id: string;
  task_id: string;
  supplier_id: string;
  material_name: string;
  quantity: string;
  unit_price_cny: string;
  freight_cny: string;
  artifact_id: string;
};
type Comparison = {
  recommended_quote_id: string | null;
  recommendation_reason: string;
  quotes: {
    quote_id: string;
    task_id: string;
    artifact_id: string;
    supplier_id: string;
    total_cny: string;
    landed_unit_price_cny: string;
    delivery_days: number;
    eligible: boolean;
    rank: number | null;
    reason: string;
  }[];
};
type QuoteState = {
  state: {
    current_step: string;
    version: number;
    skill_execution_mode: string;
    skills: { step_id: string; status: string }[];
  } | null;
};
export function QuoteComparison({ taskIds }: { taskIds: string[] }) {
  const params = new URLSearchParams();
  taskIds.forEach((id) => params.append("task_ids", id));
  const result = useEnterpriseQuery<Comparison>(
    "/procurement/quotes/compare?" + params,
    taskIds.length > 0,
  );
  if (!taskIds.length) return null;
  return (
    <GlassCard hoverable={false}>
      <h2 className="mb-4 font-semibold">报价比较 · CNY</h2>
      <QueryFeedback
        loading={result.isPending}
        error={result.error}
        retry={() => void result.refetch()}
      />
      {result.data && !result.error && (
        <>
          <p className="mb-4 text-sm">
            服务端推荐：{result.data.recommended_quote_id ?? "无符合条件的报价"}{" "}
            · {result.data.recommendation_reason}
          </p>
          <div className="overflow-x-auto">
            <table className="enterprise-table">
              <thead>
                <tr>
                  {[
                    "排名",
                    "供应商",
                    "到岸单价",
                    "总额",
                    "交期（天）",
                    "依据",
                    "追溯",
                  ].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.data.quotes.map((q) => (
                  <tr
                    key={q.quote_id}
                    className={
                      q.quote_id === result.data?.recommended_quote_id
                        ? "bg-blue-50"
                        : ""
                    }
                  >
                    <td>{q.eligible ? q.rank : "不符合条件"}</td>
                    <td>{q.supplier_id}</td>
                    <td>{q.landed_unit_price_cny}</td>
                    <td>{q.total_cny}</td>
                    <td>{q.delivery_days}</td>
                    <td>{q.reason}</td>
                    <td>
                      <Link
                        to={
                          "/enterprise/tasks/" + encodeURIComponent(q.task_id)
                        }
                      >
                        任务与证据
                      </Link>
                      <p className="text-xs">{q.artifact_id}</p>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </GlassCard>
  );
}
export function ProcurementTasksPage() {
  const tasks = useEnterpriseQuery<{ tasks: Task[]; total: number }>(
    "/procurement/tasks",
  );
  const [params, setParams] = useSearchParams();
  const selected = params.getAll("task_ids");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  // ponytail: filter the authorized response locally; add server pagination when task volume warrants it.
  const filtered = (tasks.data?.tasks ?? []).filter(
    (t) =>
      (!status || t.status === status) &&
      (t.title + " " + t.task_id + " " + t.department_id + " " + t.category_id)
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">采购任务</h1>
          <p className="mt-1 text-sm text-slate-500">
            跟踪采集、审批与核验；选择任务查看服务端比价。
          </p>
        </div>
        <button
          className="glass-btn-secondary"
          onClick={() => void tasks.refetch()}
        >
          刷新
        </button>
      </div>
      <GlassCard hoverable={false}>
        <div className="mb-4 flex flex-wrap gap-3">
          <input
            aria-label="搜索任务"
            className="glass-input"
            placeholder="任务、部门或品类"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
          <select
            aria-label="任务状态"
            className="glass-input"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">全部状态</option>
            {[...new Set(tasks.data?.tasks.map((t) => t.status))].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          {selected.length > 0 && (
            <button
              className="glass-btn-secondary"
              onClick={() => setParams({})}
            >
              清空比价选择
            </button>
          )}
        </div>
        <QueryFeedback
          loading={tasks.isPending}
          error={tasks.error}
          retry={() => void tasks.refetch()}
        />
        {!tasks.isPending && !tasks.error && (
          <>
            <div className="overflow-x-auto">
              <table className="enterprise-table">
                <thead>
                  <tr>
                    {["比价", "任务", "状态", "风险", "部门 / 品类"].map(
                      (h) => (
                        <th key={h}>{h}</th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {filtered.slice((page - 1) * 20, page * 20).map((task) => (
                    <tr key={task.task_id}>
                      <td>
                        <input
                          type="checkbox"
                          aria-label={"选择 " + task.task_id}
                          checked={selected.includes(task.task_id)}
                          disabled={
                            !selected.includes(task.task_id) &&
                            selected.length >= 128
                          }
                          onChange={(e) => {
                            const ids = e.target.checked
                              ? [...selected, task.task_id]
                              : selected.filter((id) => id !== task.task_id);
                            setParams({ task_ids: ids });
                          }}
                        />
                      </td>
                      <td>
                        <Link to={encodeURIComponent(task.task_id)}>
                          {task.title || task.task_id}
                        </Link>
                        <p className="text-xs text-slate-500">{task.task_id}</p>
                      </td>
                      <td>
                        <StatusBadge status={task.status} />
                      </td>
                      <td>
                        <RiskBadge level={task.risk_level} />
                      </td>
                      <td>
                        {task.department_id}
                        <br />
                        {task.category_id}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!filtered.length && (
              <p className="p-6 text-center text-slate-500">
                暂无符合条件的任务
              </p>
            )}
            <Pagination
              page={page}
              total={filtered.length}
              onChange={setPage}
            />
          </>
        )}
      </GlassCard>
      <QuoteComparison taskIds={selected} />
    </div>
  );
}
export function ProcurementTaskPage() {
  const { taskId = "" } = useParams();
  const user = useEnterpriseUser();
  const path = "/procurement/tasks/" + encodeURIComponent(taskId);
  const task = useEnterpriseQuery<Task>(path, true, 5000);
  const state = useEnterpriseQuery<QuoteState>(
    path + "/quote-state",
    !!task.data && !task.error,
    5000,
  );
  const quotes = useEnterpriseQuery<{ quotes: Quote[] }>(
    "/procurement/quotes?task_id=" + encodeURIComponent(taskId),
    !!task.data && !task.error,
    5000,
  );
  const approvalId = task.data?.approval_id;
  const approval = useEnterpriseQuery<{
    status: string;
    requester_user_id: string;
  }>(
    "/approvals/" + encodeURIComponent(approvalId ?? ""),
    !!approvalId && !task.error,
    5000,
  );
  const refresh = () => {
    void task.refetch();
    void state.refetch();
    void quotes.refetch();
    if (approvalId) void approval.refetch();
  };
  const action = useMutation({
    mutationFn: async (kind: "continue" | "recover") => {
      if (kind === "continue")
        return enterpriseJson(
          "/approvals/" + encodeURIComponent(approvalId ?? "") + "/continue",
          { method: "POST" },
        );
      return enterpriseJson(
        path + "/recover-quote?expected_version=" + state.data?.state?.version,
        { method: "POST" },
      );
    },
    onSuccess: refresh,
    onError: refresh,
  });
  if (!task.data || task.error)
    return (
      <div className="p-6">
        <QueryFeedback
          loading={task.isPending}
          error={task.error}
          retry={() => void task.refetch()}
        />
      </div>
    );
  const t = task.data;
  return (
    <div className="space-y-6 p-4 md:p-6">
      <Link className="text-blue-700 underline" to="/enterprise/tasks">
        返回采购任务
      </Link>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">
            {t.title || "采购任务详情"}
          </h1>
          <p className="mt-2 text-sm text-slate-500">{t.task_id}</p>
        </div>
        <button className="glass-btn-secondary" onClick={refresh}>
          刷新状态
        </button>
      </div>
      <GlassCard hoverable={false}>
        <div className="flex flex-wrap gap-4">
          <span>
            原生执行：
            <StatusBadge status={t.status} />
          </span>
          <span>
            采购处理：
            <StatusBadge
              status={state.data?.state?.current_step ?? "not_connected"}
            />
          </span>
          <RiskBadge level={t.risk_level} />
        </div>
        <p className="mt-4 text-sm">{t.risk_reason}</p>
        <p className="mt-2 text-sm text-slate-500">
          部门 {t.department_id} · 品类 {t.category_id} · 发起人 {t.created_by}
        </p>
        <QueryFeedback error={state.error} retry={() => void state.refetch()} />
        <QueryFeedback
          error={approval.error}
          retry={() => void approval.refetch()}
        />
        <QueryFeedback error={action.error} />
        <div className="mt-4 flex flex-wrap gap-4">
          {approvalId && (
            <Link
              className="text-blue-700 underline"
              to={"/enterprise/approvals/" + encodeURIComponent(approvalId)}
            >
              审批详情{approval.data ? " · " + approval.data.status : ""}
            </Link>
          )}
          {t.review_id && (
            <Link
              className="text-blue-700 underline"
              to={
                "/enterprise/human-reviews/" + encodeURIComponent(t.review_id)
              }
            >
              处理人工核验
            </Link>
          )}
          {user.data?.is_operator &&
            approval.data?.status === "approved" &&
            (approval.data.requester_user_id === user.data.user_id ||
              user.data.is_admin) &&
            t.status === "created" && (
              <button
                disabled={action.isPending || !!approval.error}
                className="glass-btn-primary"
                onClick={() => action.mutate("continue")}
              >
                审批通过，手动继续
              </button>
            )}
          {user.data?.is_operator &&
            state.data?.state &&
            !state.error &&
            !quotes.error &&
            quotes.data?.quotes.length === 0 &&
            ["ready", "running"].includes(state.data.state.current_step) && (
              <button
                disabled={action.isPending}
                className="glass-btn-secondary"
                onClick={() => action.mutate("recover")}
              >
                恢复报价状态
              </button>
            )}
        </div>
        <p className="mt-3 text-xs text-slate-500">
          恢复由服务端判断，执行歧义进入人工核验，不自动重放采购动作。
        </p>
      </GlassCard>
      <GlassCard hoverable={false}>
        <h2 className="mb-3 font-semibold">已校验报价与证据</h2>
        <QueryFeedback
          loading={quotes.isPending}
          error={quotes.error}
          retry={() => void quotes.refetch()}
        />
        {!quotes.error &&
          quotes.data?.quotes.map((q) => (
            <div key={q.quote_id} className="mb-3 rounded-lg border p-4">
              <p>
                {q.supplier_id} · {q.material_name} · {q.quantity} unit
              </p>
              <p>
                单价 {q.unit_price_cny} CNY · 运费 {q.freight_cny} CNY
              </p>
              <p className="text-xs text-slate-500">
                报价 {q.quote_id} · Artifact {q.artifact_id}
              </p>
            </div>
          ))}
        {!quotes.error && quotes.data?.quotes.length === 0 && (
          <p className="text-sm text-slate-500">
            尚无已校验报价；原生任务完成不等于报价入库成功。
          </p>
        )}
        <p className="mt-3 text-sm">
          <Link
            className="text-blue-700 underline"
            to={"/tasks/" + encodeURIComponent(taskId) + "/diagnostics"}
          >
            打开原生受权证据
          </Link>{" "}
          ·{" "}
          <Link
            className="text-blue-700 underline"
            to={"/enterprise/audit?task_id=" + encodeURIComponent(taskId)}
          >
            查看审计
          </Link>
        </p>
        <p className="mt-2 text-xs text-slate-500">
          证据访问仍需授权；认证工作流可能因安全策略不留存截图或二进制文件。
        </p>
      </GlassCard>
    </div>
  );
}
