import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useEnterpriseUser, canAccess, homeFor, type Access } from "./shared";
export function QueryFeedback({
  loading,
  error,
  retry,
}: {
  loading?: boolean;
  error?: Error | null;
  retry?: () => void;
}) {
  if (error)
    return (
      <div
        role="alert"
        className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800"
      >
        {error.message}{" "}
        {retry && (
          <button className="underline" onClick={retry}>
            重试
          </button>
        )}
      </div>
    );
  return loading ? (
    <p role="status" className="p-4 text-sm text-slate-500">
      正在加载…
    </p>
  ) : null;
}
export function EnterpriseGate({
  children,
  access = "read",
}: {
  children: ReactNode;
  access?: Access;
}) {
  const user = useEnterpriseUser();
  if (!user.data || user.error)
    return (
      <QueryFeedback
        loading={user.isPending}
        error={user.error}
        retry={() => void user.refetch()}
      />
    );
  if (!canAccess(user.data, access))
    return (
      <div role="alert" className="p-6">
        无权限访问此页面。
        <a className="underline" href={homeFor(user.data)}>
          返回工作台
        </a>
      </div>
    );
  return <>{children}</>;
}
export function EnterpriseHome() {
  const user = useEnterpriseUser();
  return user.data && !user.error ? (
    <Navigate to={homeFor(user.data)} replace />
  ) : (
    <QueryFeedback
      loading={user.isPending}
      error={user.error}
      retry={() => void user.refetch()}
    />
  );
}
export function Pagination({
  page,
  total,
  onChange,
}: {
  page: number;
  total: number;
  onChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / 20));
  return (
    <div className="flex flex-wrap items-center justify-end gap-3 text-sm">
      <span>
        共 {total} 条 · 第 {page} / {pages} 页
      </span>
      <button
        className="glass-btn-secondary whitespace-nowrap"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        上一页
      </button>
      <button
        className="glass-btn-secondary whitespace-nowrap"
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
      >
        下一页
      </button>
    </div>
  );
}
