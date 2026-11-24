import { ExternalLink } from "lucide-react";
import { Badge, ScoreBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useJobActions } from "@/hooks/useJobActions";
import type { Job } from "@/types/api";
import { fmtDate } from "@/utils/format";

export function JobCard({ job, detailed = false }: { job: Job; detailed?: boolean }) {
  const { track, prepare, dismiss } = useJobActions();
  const m = job.match;
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold">{job.title}</h3>
          <p className="text-sm text-slate-600">{job.company || "Unknown company"} · {job.location || "Location not stated"}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {job.remote_type && <Badge tone="blue">{job.remote_type}</Badge>}
            {job.experience_level && <Badge>{job.experience_level}</Badge>}
            {job.employment_type && <Badge>{job.employment_type}</Badge>}
            {job.posted_at && <Badge>posted {fmtDate(job.posted_at)}</Badge>}
            {job.injection_flags.length > 0 && <Badge tone="red">suspicious text ignored</Badge>}
          </div>
        </div>
        {m && (
          <div className="text-right">
            <ScoreBadge score={m.score} />
            <p className="mt-1 text-xs font-medium uppercase text-slate-500">{m.recommendation === "apply" ? "Recommended" : m.recommendation === "consider" ? "Consider" : "Skip"}</p>
          </div>
        )}
      </div>
      {detailed && m && (
        <div className="mt-3 space-y-2 text-sm">
          <p className="whitespace-pre-line text-slate-700">{m.explanation}</p>
          {m.missing_skills.length > 0 && <p><span className="font-medium">Missing:</span> {m.missing_skills.map((s) => <Badge key={s} tone="amber" className="mr-1">{s}</Badge>)}</p>}
          {m.matched_skills.length > 0 && <p><span className="font-medium">Matched:</span> {m.matched_skills.map((s) => <Badge key={s} tone="green" className="mr-1">{s}</Badge>)}</p>}
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" onClick={() => prepare.mutate(job)} loading={prepare.isPending}>Prepare application</Button>
        <Button size="sm" variant="secondary" onClick={() => track.mutate(job)} loading={track.isPending}>Add to tracker</Button>
        <a href={job.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-sm text-slate-700 hover:bg-slate-200/60">
          View posting <ExternalLink className="h-3.5 w-3.5" aria-hidden /><span className="sr-only"> (opens in a new tab)</span>
        </a>
        <Button size="sm" variant="ghost" onClick={() => dismiss.mutate(job)}>Dismiss</Button>
      </div>
    </Card>
  );
}
