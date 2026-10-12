import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { GlassCard } from "@/components/enterprise/GlassCard";
import { StatusBadge } from "@/components/enterprise/StatusBadge";
import { enterpriseJson, useEnterpriseQuery } from "../shared";
import { Pagination, QueryFeedback } from "../EnterpriseAccess";
type Review = {
  review_id: string;
  task_id: string;
  status: string;
  reason_code: string;
  safe_error_summary: string;
  artifact_id: string | null;
  created_at: string;
  resolution_action: string | null;
  resolution_note: string | null;
  resolved_by: string | null;
};
export function HumanReviewsPage() {
  const [status, setStatus] = useState("pending");
  const [page, setPage] = useState(1);
  const query = useEnterpriseQuery<{ reviews: Review[]; total: number }>(
    "/procurement/human-reviews" + (status ? "?status=" + status : ""),
  );
  const rows = query.data?.reviews ?? [];
  return (
    <div className="space-y-6 p-4 md:p-6">
      <h1 className="text-2xl font-semibold">人工核验</h1>
      <p className="text-sm text-slate-500">
        处理抽取异常与执行歧义。人工结果单独标记，不冒充原生采集。
      </p>
      <div className="flex gap-3">
        <select
          aria-label="核验状态"
          className="glass-input"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="pending">待核验</option>
          <option value="resolved">已处理</option>
          <option value="terminated">已终止</option>
          <option value="">全部</option>
        </select>
        <button
          className="glass-btn-secondary"
          onClick={() => void query.refetch()}
        >
          刷新
        </button>
      </div>
      <QueryFeedback
        loading={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {!query.error && query.data && (
        <GlassCard hoverable={false}>
          <div className="overflow-x-auto">
            <table className="enterprise-table">
              <thead>
                <tr>
                  <th>核验 / 任务</th>
                  <th>状态</th>
                  <th>原因</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                {rows.slice((page - 1) * 20, page * 20).map((r) => (
                  <tr key={r.review_id}>
                    <td>
                      <Link to={encodeURIComponent(r.review_id)}>
                        {r.review_id}
                      </Link>
                      <p className="text-xs">{r.task_id}</p>
                    </td>
                    <td>
                      <StatusBadge
                        status={
                          r.status === "pending" ? "needs_human" : r.status
                        }
                      />
                    </td>
                    <td>{r.safe_error_summary}</td>
                    <td>{new Date(r.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!rows.length && <p className="p-6 text-center">暂无核验事项</p>}
          <Pagination page={page} total={rows.length} onChange={setPage} />
        </GlassCard>
      )}
    </div>
  );
}
export function HumanReviewPage() {
  const { reviewId = "" } = useParams();
  const path = "/procurement/human-reviews/" + encodeURIComponent(reviewId);
  const query = useEnterpriseQuery<Review>(path);
  const [action, setAction] = useState("manual_complete");
  const [note, setNote] = useState("");
  const mutation = useMutation({
    mutationFn: (body: unknown) =>
      enterpriseJson(path + "/resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSettled: () => void query.refetch(),
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mutation.isPending) return;
    const fields = new FormData(event.currentTarget);
    const manual = Object.fromEntries(fields);
    const body =
      action === "manual_complete"
        ? {
            action,
            note,
            manual_result: {
              ...manual,
              unit: "unit",
              currency: "CNY",
              delivery_days: Number(fields.get("delivery_days")),
            },
          }
        : { action, note };
    mutation.mutate(body);
  }
  const review = query.data;
  if (!review || query.error)
    return (
      <div className="p-6">
        <QueryFeedback
          loading={query.isPending}
          error={query.error}
          retry={() => void query.refetch()}
        />
      </div>
    );
  return (
    <div className="space-y-6 p-4 md:p-6">
      <Link className="text-blue-700 underline" to="/enterprise/human-reviews">
        返回人工核验
      </Link>
      <h1 className="text-2xl font-semibold">核验详情</h1>
      <GlassCard hoverable={false}>
        <StatusBadge
          status={review.status === "pending" ? "needs_human" : review.status}
        />
        <p className="my-4">{review.safe_error_summary}</p>
        <p className="text-xs text-slate-500">
          {review.reason_code} · {review.review_id}
        </p>
        <p className="my-3 text-sm">
          <Link
            className="text-blue-700 underline"
            to={"/enterprise/tasks/" + encodeURIComponent(review.task_id)}
          >
            任务详情
          </Link>{" "}
          ·{" "}
          <Link
            className="text-blue-700 underline"
            to={"/tasks/" + encodeURIComponent(review.task_id) + "/diagnostics"}
          >
            受权原生证据
          </Link>
        </p>
        <p className="mb-4 text-sm">
          证据：
          {review.artifact_id ??
            "未关联证据；人工补录必须提供同任务受权 Artifact"}
        </p>
        <QueryFeedback error={mutation.error} />
        {review.status === "pending" ? (
          <form className="space-y-4" onSubmit={submit}>
            <label className="block">
              处理方式
              <select
                className="glass-input ml-3"
                value={action}
                onChange={(e) => setAction(e.target.value)}
                disabled={mutation.isPending}
              >
                <option value="manual_complete">人工补录报价</option>
                <option value="skip_step">跳过此步骤（不生成报价）</option>
                <option value="terminate">终止任务</option>
              </select>
            </label>
            {action === "manual_complete" && (
              <fieldset
                disabled={mutation.isPending}
                className="grid gap-4 sm:grid-cols-2"
              >
                <legend className="mb-3 text-sm text-slate-500">
                  仅 CNY / unit；金额以十进制原值提交，由服务端校验。
                </legend>
                {[
                  ["supplier_id", "供应商 ID"],
                  ["material_name", "物料名称"],
                  ["quantity", "数量"],
                  ["unit_price_cny", "单价（CNY）"],
                  ["freight_cny", "运费（CNY）"],
                  ["moq", "起订量"],
                  ["delivery_days", "交期（天）"],
                  ["artifact_id", "证据 Artifact ID"],
                ].map(([name, label]) => (
                  <label className="block text-sm" key={name}>
                    {label}
                    <input
                      className="glass-input mt-1 w-full"
                      name={name}
                      required
                      maxLength={name === "material_name" ? 256 : 128}
                      defaultValue={
                        name === "artifact_id"
                          ? review.artifact_id ?? ""
                          : ["freight_cny", "moq"].includes(name ?? "")
                            ? "0"
                            : ""
                      }
                      type={name === "delivery_days" ? "number" : "text"}
                      min={name === "delivery_days" ? 0 : undefined}
                      max={name === "delivery_days" ? 3650 : undefined}
                      step={name === "delivery_days" ? 1 : undefined}
                      inputMode={
                        [
                          "quantity",
                          "unit_price_cny",
                          "freight_cny",
                          "moq",
                        ].includes(name ?? "")
                          ? "decimal"
                          : undefined
                      }
                      pattern={
                        [
                          "quantity",
                          "unit_price_cny",
                          "freight_cny",
                          "moq",
                        ].includes(name ?? "")
                          ? "[0-9]+(\\.[0-9]+)?"
                          : undefined
                      }
                    />
                  </label>
                ))}
              </fieldset>
            )}
            {action !== "manual_complete" && (
              <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
                {action === "skip_step"
                  ? "跳过会结束该报价步骤，不生成有效报价，不自动继续浏览器动作。"
                  : "终止会提交任务处置决定，请核对任务后提交。"}
              </p>
            )}
            <label className="block">
              处理说明
              <textarea
                className="glass-input mt-1 w-full"
                maxLength={2000}
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
            <button
              type="submit"
              className="glass-btn-primary"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? "提交中…" : "提交核验结果"}
            </button>
          </form>
        ) : (
          <div className="rounded-lg bg-slate-50 p-4">
            <p>
              {review.resolution_action === "manual_complete"
                ? "已人工补录（manual_completed）"
                : review.resolution_action === "skip_step"
                  ? "已跳过，未生成报价"
                  : review.resolution_action === "terminate"
                    ? "已终止"
                    : "处理结果未记录"}
            </p>
            <p>{review.resolution_note}</p>
            <p className="text-xs text-slate-500">
              处理人：{review.resolved_by}
            </p>
          </div>
        )}
        <button
          className="glass-btn-secondary mt-4"
          onClick={() => void query.refetch()}
        >
          刷新
        </button>
      </GlassCard>
    </div>
  );
}
