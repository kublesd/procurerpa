import { NavLink, useNavigate } from "react-router-dom";
import { Icon, type IconName } from "@/components/Icon";
import { useI18n } from "@/i18n/useI18n";
import { useAuthStore } from "@/store/AuthStore";
import {
  canAccess,
  useEnterpriseUser,
  type Access,
} from "@/routes/enterprise/shared";

const items: {
  zh: string;
  en: string;
  to: string;
  icon: IconName;
  access: Access;
}[] = [
  {
    zh: "总览",
    en: "Overview",
    to: "dashboard",
    icon: "dashboard",
    access: "operator",
  },
  {
    zh: "报价采集",
    en: "Collect quotes",
    to: "procurement",
    icon: "task",
    access: "operator",
  },
  {
    zh: "采购任务",
    en: "Procurement tasks",
    to: "tasks",
    icon: "task",
    access: "read",
  },
  {
    zh: "审批中心",
    en: "Approvals",
    to: "approvals",
    icon: "approval",
    access: "approver",
  },
  {
    zh: "人工核验",
    en: "Human reviews",
    to: "human-reviews",
    icon: "check-circle",
    access: "operator",
  },
  {
    zh: "工作流模板",
    en: "Templates",
    to: "templates",
    icon: "workflow",
    access: "operator",
  },
  { zh: "审计追溯", en: "Audit", to: "audit", icon: "audit", access: "audit" },
];
export function EnterpriseSideNav({
  collapsed = false,
}: {
  collapsed?: boolean;
}) {
  const { locale, t } = useI18n();
  const user = useEnterpriseUser();
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  return (
    <nav
      aria-label={locale === "zh" ? "主导航" : "Navigation"}
      className="flex-1 overflow-y-auto py-2"
    >
      <p className="mb-3 px-3 text-xs text-slate-500">
        {collapsed ? "PR" : "PROCUREMENT"}
      </p>
      {user.data &&
        items
          .filter((item) => canAccess(user.data, item.access))
          .map((item) => (
            <NavLink
              key={item.to}
              to={"/enterprise/" + item.to}
              title={locale === "zh" ? item.zh : item.en}
              className={({ isActive }) =>
                "glass-nav-item " +
                (isActive ? "active" : "") +
                (collapsed ? "justify-center" : "")
              }
            >
              <Icon name={item.icon} size={19} />
              {!collapsed && (locale === "zh" ? item.zh : item.en)}
            </NavLink>
          ))}
      <details className="mt-6 border-t pt-4">
        <summary className="cursor-pointer px-3 text-xs text-slate-500">
          {locale === "zh" ? "技术工具" : "Technical tools"}
        </summary>
        {[
          ["/discover", t("nav.discover")],
          ["/tasks", t("nav.tasks")],
          ["/workflows", t("nav.workflows")],
          ["/runs", t("nav.runs")],
          ["/settings", t("nav.settings")],
        ].map(([to, label]) => (
          <NavLink
            key={to}
            to={to ?? "/"}
            title={label}
            className="glass-nav-item text-sm"
          >
            {collapsed ? label?.slice(0, 2) : label}
          </NavLink>
        ))}
      </details>
      <button
        className="glass-nav-item mt-6 w-full"
        title={t("auth.logout")}
        onClick={() => {
          logout();
          navigate("/login");
        }}
      >
        <Icon name="logout" size={19} />
        {!collapsed && t("auth.logout")}
      </button>
    </nav>
  );
}
