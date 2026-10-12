import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { GlassCard } from "@/components/enterprise/GlassCard";
import { StatusBadge } from "@/components/enterprise/StatusBadge";
import { RiskBadge } from "@/components/enterprise/RiskBadge";
import {
  enterpriseJson,
  useEnterpriseQuery,
  useEnterpriseUser,
} from "../shared";
import { QueryFeedback } from "../EnterpriseAccess";
type Approval = {
  approval_id: string;
  task_id: string;
  status: string;
  risk_level: string;
  risk_reason: string;
  operation_description: string | null;
  requester_user_id: string;
  department_id: string;
  category_id: string | null;
  approver_department_id: string;
  requested_at: string;
  total_amount_cny: string | null;
  matched_threshold_cny: string | null;
  policy_version: string | null;
};
export function ApprovalsPage() {
  const approvals = useEnterpriseQuery<Approval[]>("/approvals/pending");
  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">审批中心</h1>
          <p className="mt-2 text-sm text-slate-500">
            待办以当前部门、品类与审批策略为准。
          </p>
        </div>
        <button
          className="glass-btn-secondary"
          onClick={() => void approvals.refetch()}
        >
          刷新
        </button>
      </div>
      <QueryFeedback
        loading={approvals.isPending}
        error={approvals.error}
        retry={() => void approvals.refetch()}
      />
      {!approvals.error && approvals.data?.length === 0 && (
        <GlassCard hoverable={false}>暂无待审批事项</GlassCard>
      )}
      {!approvals.error &&
        approvals.data?.map((a) => (
          <GlassCard key={a.approval_id} hoverable={false}>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <RiskBadge level={a.risk_level} />
                <h2 className="my-3 font-semibold">
                  {a.operation_description || a.task_id}
                </h2>
                <p className="text-sm text-slate-600">{a.risk_reason}</p>
                <p className="mt-2 text-sm">
                  {a.total_amount_cny ?? "金额未记录"}
                  {a.total_amount_cny != null ? " CNY" : ""} ·{" "}
                  {new Date(a.requested_at).toLocaleString()}
                </p>
              </div>
              <Link
                className="glass-btn-primary"
                to={encodeURIComponent(a.approval_id)}
              >
                查看并审批
              </Link>
            </div>
          </GlassCard>
        ))}
    </div>
  );
}
export function ApprovalDetailPage() {
  const { approvalId = "" } = useParams();
  const path = "/approvals/" + encodeURIComponent(approvalId);
  const query = useEnterpriseQuery<Approval>(path);
  const user = useEnterpriseUser();
  const pending = useEnterpriseQuery<Approval[]>(
    "/approvals/pending",
    !!user.data?.is_approver,
  );
  const client = useQueryClient();
  const [note, setNote] = useState("");
  const data = query.data;
  useEffect(() => {
    if (data?.status !== "pending") return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function watch() {
      try {
        try {
          await enterpriseJson(path + "/updates", {
            signal: controller.signal,
          });
        } catch {
          if (controller.signal.aborted) return;
          await enterpriseJson(path, { signal: controller.signal });
        }
      } catch {
        /* Database query below renders errors and remains authoritative. */
      }
      if (controller.signal.aborted) return;
      await client.invalidateQueries({
        queryKey: ["enterprise", user.data?.org_id, user.data?.user_id, path],
      });
      if (!controller.signal.aborted)
        timer = setTimeout(() => void watch(), 2000);
    }
    void watch();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [path, data?.status, client, user.data?.org_id, user.data?.user_id]);
  const action = useMutation({
    mutationFn: (kind: string) =>
      enterpriseJson(path + "/" + kind, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: kind === "continue" ? undefined : JSON.stringify({ note }),
      }),
    onSettled: () => {
      void query.refetch();
      if (user.data?.is_approver) void pending.refetch();
    },
  });
  if (!data || query.error)
    return (
      <div className="p-6">
        <QueryFeedback
          loading={query.isPending}
          error={query.error}
          retry={() => void query.refetch()}
        />
      </div>
    );
  const canDecide =
    data.status === "pending" &&
    !pending.error &&
    pending.data?.some((a) => a.approval_id === approvalId);
  return (
    <div className="space-y-6 p-4 md:p-6">
      <h1 className="text-2xl font-semibold">审批详情</h1>
      <GlassCard hoverable={false}>
        <div className="flex gap-3">
          <StatusBadge status={data.status} />
          <RiskBadge level={data.risk_level} />
        </div>
        <h2 className="my-4 font-semibold">
          {data.operation_description || data.task_id}
        </h2>
        <p>{data.risk_reason}</p>
        <dl className="my-4 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-slate-500">采购金额</dt>
            <dd>
              {data.total_amount_cny ?? "未记录"}{" "}
              {data.total_amount_cny != null && "CNY"}
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">审批策略 / 命中阈值</dt>
            <dd>
              {data.policy_version ?? "旧记录未记录"} /{" "}
              {data.matched_threshold_cny ?? "未记录"}
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">审批部门</dt>
            <dd>{data.approver_department_id}</dd>
          </div>
          <div>
            <dt className="text-slate-500">请求人</dt>
            <dd>{data.requester_user_id}</dd>
          </div>
        </dl>
        <QueryFeedback error={action.error} />
        <QueryFeedback error={pending.error} />
        {canDecide && (
          <div className="space-y-3">
            <label className="block">
              审批备注
              <textarea
                className="glass-input mt-2 w-full"
                maxLength={2000}
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
            <div className="flex gap-3">
              <button
                className="glass-btn-primary"
                disabled={action.isPending}
                onClick={() => action.mutate("approve")}
              >
                批准
              </button>
              <button
                className="glass-btn-secondary"
                disabled={action.isPending}
                onClick={() => action.mutate("reject")}
              >
                拒绝
              </button>
            </div>
          </div>
        )}
        <p className="my-4 text-sm text-slate-500">
          批准仅记录审批决定；采购任务仍需申请人显式继续。
        </p>
        {data.status === "approved" &&
          user.data?.is_operator &&
          (data.requester_user_id === user.data.user_id ||
            user.data.is_admin) && (
            <Link
              className="glass-btn-primary mr-3"
              to={"/enterprise/tasks/" + encodeURIComponent(data.task_id)}
            >
              前往任务手动继续
            </Link>
          )}
        <Link
          className="text-blue-700 underline"
          to={"/enterprise/tasks/" + encodeURIComponent(data.task_id)}
        >
          查看采购任务
        </Link>
        <button
          className="glass-btn-secondary ml-3"
          onClick={() => void query.refetch()}
        >
          刷新
        </button>
      </GlassCard>
    </div>
  );
}
