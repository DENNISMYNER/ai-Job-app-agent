import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/utils/cn";

export const Card = ({ className, ...p }: HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("rounded-xl border border-slate-200 bg-white shadow-sm", className)} {...p} />
);
export const CardHeader = ({ title, action, description }: { title: ReactNode; action?: ReactNode; description?: ReactNode }) => (
  <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
    <div><h2 className="text-base font-semibold">{title}</h2>{description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}</div>
    {action}
  </div>
);
export const CardBody = ({ className, ...p }: HTMLAttributes<HTMLDivElement>) => <div className={cn("p-5", className)} {...p} />;
