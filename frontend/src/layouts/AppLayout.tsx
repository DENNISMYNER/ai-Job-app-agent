import { Bell, Bot, Briefcase, ClipboardList, FileText, GraduationCap, LayoutDashboard, Mail, Menu, Search, Settings, Sparkles, UserCircle, Wand2, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useGet } from "@/hooks/useApi";
import { useAction } from "@/hooks/useApi";
import { api } from "@/services/api";
import type { AppNotification } from "@/types/api";
import { cn } from "@/utils/cn";
import { fmtDateTime } from "@/utils/format";

export const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/profile", label: "My Profile", icon: UserCircle },
  { to: "/discovery", label: "Job Discovery", icon: Search },
  { to: "/recommended", label: "Recommended Jobs", icon: Sparkles },
  { to: "/documents", label: "CV & Documents", icon: FileText },
  { to: "/cover-letters", label: "Cover Letters", icon: Mail },
  { to: "/assistant", label: "Application Assistant", icon: Wand2 },
  { to: "/tracker", label: "Application Tracker", icon: ClipboardList },
  { to: "/interviews", label: "Interview Preparation", icon: GraduationCap },
  { to: "/automation", label: "Automation Settings", icon: Bot },
  { to: "/ai", label: "AI Settings", icon: Briefcase },
  { to: "/system", label: "System Settings", icon: Settings },
] as const;

function Bell_() {
  const [open, setOpen] = useState(false);
  const { data } = useGet<AppNotification[]>(["notifications"], "/notifications", { refetchInterval: 30000 });
  const readAll = useAction(() => api.post("/notifications/read-all"), { invalidate: [["notifications"]] });
  const unread = data?.filter((n) => !n.read).length ?? 0;
  return (
    <div className="relative">
      <button aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`} onClick={() => setOpen((o) => !o)} className="relative rounded-lg p-2 hover:bg-slate-200/60">
        <Bell className="h-5 w-5" />
        {unread > 0 && <span className="absolute right-1 top-1 h-2.5 w-2.5 rounded-full bg-red-500" />}
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-2 w-80 rounded-xl border border-slate-200 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b px-4 py-2">
            <span className="text-sm font-semibold">Notifications</span>
            {unread > 0 && <button className="text-xs text-brand-600" onClick={() => readAll.mutate()}>Mark all read</button>}
          </div>
          <ul className="max-h-80 overflow-auto">
            {!data?.length && <li className="p-4 text-sm text-slate-500">Nothing yet.</li>}
            {data?.slice(0, 15).map((n) => (
              <li key={n.id} className={cn("border-b px-4 py-2 text-sm last:border-0", !n.read && "bg-brand-50")}>
                <p className="font-medium">{n.title}</p>
                {n.body && <p className="text-slate-600">{n.body}</p>}
                <p className="text-xs text-slate-400">{fmtDateTime(n.created_at)}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function AppLayout() {
  const [menu, setMenu] = useState(false);
  const nav = (
    <nav aria-label="Main" className="flex flex-col gap-0.5 p-3">
      {NAV.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={to} end={to === "/"} onClick={() => setMenu(false)}
          className={({ isActive }) => cn("flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium", isActive ? "bg-brand-50 text-brand-700" : "text-slate-700 hover:bg-slate-100")}>
          <Icon className="h-4 w-4 shrink-0" aria-hidden /> {label}
        </NavLink>
      ))}
    </nav>
  );
  return (
    <div className="min-h-screen lg:flex">
      <aside className="hidden w-64 shrink-0 border-r border-slate-200 bg-white lg:block">
        <div className="flex h-14 items-center gap-2 border-b px-5 font-semibold"><Briefcase className="h-5 w-5 text-brand-600" /> Job Agent</div>
        {nav}
        <p className="px-5 py-3 text-xs text-slate-400">Runs locally. Your data stays on this computer.</p>
      </aside>
      {menu && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setMenu(false)} />
          <aside className="absolute left-0 top-0 h-full w-72 bg-white shadow-xl">
            <div className="flex h-14 items-center justify-between border-b px-4"><span className="font-semibold">Job Agent</span>
              <button aria-label="Close menu" onClick={() => setMenu(false)}><X className="h-5 w-5" /></button></div>
            {nav}
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4">
          <button aria-label="Open menu" className="rounded-lg p-2 hover:bg-slate-100 lg:hidden" onClick={() => setMenu(true)}><Menu className="h-5 w-5" /></button>
          <span className="hidden text-sm text-slate-500 lg:block">Final submissions always need your approval.</span>
          <Bell_ />
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 p-4 sm:p-6"><Outlet /></main>
      </div>
    </div>
  );
}
