import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/AuthStore";
import { authFetch } from "@/util/authFetch";

export type EnterpriseUser = {
  user_id: string;
  org_id: string;
  is_operator: boolean;
  is_approver: boolean;
  is_admin: boolean;
  has_cross_org_read: boolean;
  department_roles: {
    department_id: string;
    department_name: string;
    role: string;
  }[];
};
export async function enterpriseJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await authFetch("/api/v1/enterprise" + path, init);
  if (!response.ok) {
    const messages: Record<number, string> = {
      401: "登录已过期，请重新登录",
      403: "无权限访问此数据或操作",
      404: "记录不存在、不可见或当前环境未开放此功能",
      409: "状态已变化，请刷新后重试",
      422: "参数不符合要求，请检查输入和证据",
    };
    let message = messages[response.status] ?? "请求失败，请稍后重试";
    if (!messages[response.status]) {
      try {
        const body = await response.json();
        if (typeof body.detail === "string") message = body.detail;
      } catch {
        /* Keep the safe status message. */
      }
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
export function useEnterpriseUser() {
  const userId = useAuthStore((s) => s.userId);
  return useQuery({
    queryKey: ["enterprise-user", userId],
    queryFn: ({ signal }) =>
      enterpriseJson<EnterpriseUser>("/auth/me", { signal }),
    staleTime: 30_000,
    retry: false,
  });
}
export function useEnterpriseQuery<T>(
  path: string,
  enabled = true,
  interval: number | false = false,
) {
  const user = useEnterpriseUser();
  return useQuery({
    queryKey: ["enterprise", user.data?.org_id, user.data?.user_id, path],
    queryFn: ({ signal }) => enterpriseJson<T>(path, { signal }),
    enabled: !!user.data && enabled,
    staleTime: 0,
    retry: false,
    refetchInterval: interval,
  });
}
export type Access = "read" | "operator" | "approver" | "audit";
export function canAccess(user: EnterpriseUser, access: Access) {
  if (access === "read") return true;
  if (access === "operator") return user.is_operator;
  if (access === "approver") return user.is_approver;
  return (
    user.is_admin ||
    user.has_cross_org_read ||
    user.department_roles.some((r) => r.role === "viewer")
  );
}
export function homeFor(user: EnterpriseUser) {
  return user.is_operator
    ? "/enterprise/dashboard"
    : user.is_approver
      ? "/enterprise/approvals"
      : "/enterprise/tasks";
}
