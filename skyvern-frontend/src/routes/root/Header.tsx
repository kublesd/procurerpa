import { useLocation, useMatch, useSearchParams } from "react-router-dom";
import { NavigationHamburgerMenu } from "./NavigationHamburgerMenu";
import { LanguageSwitcher } from "@/components/enterprise/LanguageSwitcher";
import { useAuthStore } from "@/store/AuthStore";
function Header() {
  const [params] = useSearchParams();
  const location = useLocation();
  const match = useMatch("/workflows/:workflowPermanentId/edit");
  const displayName = useAuthStore((s) => s.displayName);
  if (
    match ||
    location.pathname.includes("build") ||
    location.pathname.includes("debug") ||
    params.get("embed") === "true"
  )
    return null;
  return (
    <header className="border-b border-slate-200 bg-white/80">
      <div className="flex h-16 items-center gap-3 px-6">
        <NavigationHamburgerMenu />
        <span className="text-sm font-semibold text-slate-600 lg:ml-64">
          ProcureRPA Enterprise
        </span>
        <div className="ml-auto flex items-center gap-4">
          <LanguageSwitcher />
          <span className="hidden text-sm text-slate-600 sm:inline">
            {displayName}
          </span>
        </div>
      </div>
    </header>
  );
}
export { Header };
