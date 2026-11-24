import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "./Button";

export const Spinner = ({ label = "Loading…" }: { label?: string }) => (
  <div role="status" className="flex items-center justify-center gap-2 p-8 text-sm text-slate-500">
    <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> {label}
  </div>
);

export const EmptyState = ({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) => (
  <div className="flex flex-col items-center gap-2 p-10 text-center">
    <Inbox className="h-8 w-8 text-slate-300" aria-hidden />
    <p className="font-medium text-slate-700">{title}</p>
    {hint && <p className="max-w-md text-sm text-slate-500">{hint}</p>}
    {action}
  </div>
);

export const ErrorState = ({ error, onRetry }: { error: unknown; onRetry?: () => void }) => (
  <div role="alert" className="flex flex-col items-center gap-2 p-8 text-center">
    <AlertTriangle className="h-7 w-7 text-red-500" aria-hidden />
    <p className="font-medium text-slate-800">Something went wrong</p>
    <p className="max-w-md text-sm text-slate-600">{error instanceof Error ? error.message : "Unknown error"}</p>
    {onRetry && <Button variant="secondary" size="sm" onClick={onRetry}>Try again</Button>}
  </div>
);

export const Notice = ({ tone = "info", children }: { tone?: "info" | "warn" | "error" | "success"; children: ReactNode }) => {
  const cls = { info: "bg-brand-50 text-brand-700 border-brand-100", warn: "bg-amber-50 text-amber-900 border-amber-200", error: "bg-red-50 text-red-800 border-red-200", success: "bg-emerald-50 text-emerald-900 border-emerald-200" }[tone];
  return <div role={tone === "error" ? "alert" : "status"} className={`rounded-lg border px-4 py-3 text-sm ${cls}`}>{children}</div>;
};
