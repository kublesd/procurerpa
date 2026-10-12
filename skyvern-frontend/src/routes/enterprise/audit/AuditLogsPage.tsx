import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { GlassCard } from "@/components/enterprise/GlassCard";
import { ScreenshotDiff } from "@/components/enterprise/ScreenshotDiff";
import { useEnterpriseQuery } from "../shared";
import { Pagination, QueryFeedback } from "../EnterpriseAccess";
type Audit = {
  audit_log_id: string;
  task_id: string;
  action_type: string;
  execution_result: string;
  executor: string;
  created_at: string;
  input_value: string | null;
  error_message: string | null;
  screenshot_before_url: string | null;
  screenshot_after_url: string | null;
};
function localDate(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ""
    : new Date(date.getTime() - date.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 16);
}
export function AuditLogsPage() {
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [filterError, setFilterError] = useState("");
  const queryParams = new URLSearchParams(params);
  queryParams.set("page", String(page));
  queryParams.set("page_size", "20");
  const query = useEnterpriseQuery<{ items: Audit[]; total: number }>(
    "/audit/logs?" + queryParams,
  );
  function filter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFilterError("");
    const values = new FormData(event.currentTarget);
    const next = new URLSearchParams();
    for (const [name, value] of values)
      if (String(value).trim())
        next.set(
          name,
          name.endsWith("_time")
            ? new Date(String(value)).toISOString()
            : String(value).trim(),
        );
    if (
      next.get("start_time") &&
      next.get("end_time") &&
      next.get("start_time")! > next.get("end_time")!
    ) {
      setFilterError("开始时间不能晚于结束时间");
      return;
    }
    setParams(next);
  }
  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">审计追溯</h1>
        <button
          className="glass-btn-secondary"
          onClick={() => void query.refetch()}
        >
          刷新
        </button>
      </div>
      <GlassCard hoverable={false}>
        <form
          key={params.toString()}
          onSubmit={filter}
          className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3"
        >
          {[
            ["task_id", "任务 ID"],
            ["action_type", "动作类型"],
            ["executor", "执行人"],
          ].map(([name, label]) => (
            <label key={name} className="text-sm">
              {label}
              <input
                className="glass-input mt-1 w-full"
                name={name}
                defaultValue={params.get(name!) ?? ""}
              />
            </label>
          ))}
          {[
            ["start_time", "开始时间"],
            ["end_time", "结束时间"],
          ].map(([name, label]) => (
            <label key={name} className="text-sm">
              {label}
              <input
                className="glass-input mt-1 w-full"
                name={name}
                type="datetime-local"
                defaultValue={localDate(params.get(name!))}
              />
            </label>
          ))}
          <div className="flex items-end gap-3">
            <button type="submit" className="glass-btn-primary">
              筛选
            </button>
            <button
              type="button"
              className="glass-btn-secondary"
              onClick={() => {
                setParams({});
                setFilterError("");
              }}
            >
              清空
            </button>
          </div>
        </form>
        {filterError && <p role="alert">{filterError}</p>}
      </GlassCard>
      <QueryFeedback
        loading={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {!query.error && query.data && (
        <>
          <p className="text-sm text-slate-500">
            仅展示当前授权范围内的持久审计。事件结果不等于整个任务的最终状态。
          </p>
          {query.data.items.map((log) => (
            <GlassCard key={log.audit_log_id} hoverable={false}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <Link
                    className="text-blue-700 underline"
                    to={"/enterprise/tasks/" + encodeURIComponent(log.task_id)}
                  >
                    {log.task_id}
                  </Link>
                  <p className="mt-2 font-medium">
                    {log.action_type} · {log.execution_result}
                  </p>
                </div>
                <p className="text-xs text-slate-500">
                  {new Date(log.created_at).toLocaleString()} · {log.executor}
                </p>
              </div>
              <details className="mt-3">
                <summary className="cursor-pointer text-sm text-blue-700">
                  查看安全记录与证据
                </summary>
                {log.input_value && (
                  <pre className="my-3 whitespace-pre-wrap break-all rounded bg-slate-50 p-3 text-xs">
                    {log.input_value}
                  </pre>
                )}
                {log.error_message && (
                  <p className="text-sm text-red-700">{log.error_message}</p>
                )}
                {log.screenshot_before_url || log.screenshot_after_url ? (
                  <ScreenshotDiff
                    beforeUrl={log.screenshot_before_url ?? undefined}
                    afterUrl={log.screenshot_after_url ?? undefined}
                  />
                ) : (
                  <p className="mt-2 text-sm text-slate-500">
                    无可展示截图；可能未留存、受安全策略限制或证据服务不可用。
                  </p>
                )}
              </details>
            </GlassCard>
          ))}
          {!query.data.items.length && (
            <GlassCard hoverable={false}>暂无符合条件的审计记录</GlassCard>
          )}
          <Pagination
            page={page}
            total={query.data.total}
            onChange={(p) => {
              const next = new URLSearchParams(params);
              next.set("page", String(p));
              setParams(next);
            }}
          />
        </>
      )}
    </div>
  );
}
