import type { ReactNode } from "react";
import { cn } from "@/utils/cn";
import { scoreTone } from "@/utils/format";

const tones = {
  gray: "bg-slate-100 text-slate-700", green: "bg-emerald-100 text-emerald-800", amber: "bg-amber-100 text-amber-800",
  red: "bg-red-100 text-red-800", blue: "bg-brand-100 text-brand-700", purple: "bg-violet-100 text-violet-800",
};
export type Tone = keyof typeof tones;

export const Badge = ({ tone = "gray", children, className }: { tone?: Tone; children: ReactNode; className?: string }) => (
  <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", tones[tone], className)}>{children}</span>
);

export const ScoreBadge = ({ score }: { score: number }) => (
  <Badge tone={scoreTone(score) as Tone} className="tabular-nums"><span className="sr-only">Match score </span>{score}%</Badge>
);

const statusTone: Record<string, Tone> = {
  discovered: "gray", shortlisted: "blue", preparing: "amber", awaiting_approval: "purple", applied: "blue",
  interview: "green", assessment: "amber", offer: "green", rejected: "red", withdrawn: "gray",
};
export const StatusBadge = ({ status }: { status: string }) => <Badge tone={statusTone[status] ?? "gray"}>{status.replace(/_/g, " ")}</Badge>;
