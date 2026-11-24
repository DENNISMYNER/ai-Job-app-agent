import type { ReactNode } from "react";

export const PageHeader = ({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) => (
  <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
    <div><h1 className="text-2xl font-semibold tracking-tight">{title}</h1>{description && <p className="mt-1 max-w-2xl text-sm text-slate-600">{description}</p>}</div>
    {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
  </header>
);

export const Stat = ({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) => (
  <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
    <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
    <p className="mt-1 text-3xl font-semibold tabular-nums">{value}</p>
    {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
  </div>
);
