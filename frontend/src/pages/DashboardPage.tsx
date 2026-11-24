import { Link } from "react-router-dom";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { PageHeader, Stat } from "@/components/ui/Page";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";
import { useGet } from "@/hooks/useApi";
import type { Dashboard } from "@/types/api";
import { fmtDate, fmtDateTime, statusLabel } from "@/utils/format";

export default function DashboardPage() {
  const { data, isLoading, error, refetch } = useGet<Dashboard>(["dashboard"], "/dashboard");
  if (isLoading) return <Spinner />;
  if (error || !data) return <ErrorState error={error} onRetry={refetch} />;
  const max = Math.max(1, ...Object.values(data.by_status));
  return (
    <>
      <PageHeader title="Dashboard" description="Your job search at a glance." actions={<Link to="/discovery"><Button>Find jobs</Button></Link>} />
      <section aria-label="Statistics" className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Discovered" value={data.discovered_jobs} />
        <Stat label="Matching" value={data.matching_jobs} hint="above your apply threshold" />
        <Stat label="Submitted" value={data.submitted} />
        <Stat label="Awaiting approval" value={data.awaiting_approval} />
        <Stat label="Interviews" value={data.interviews} />
        <Stat label="Rejections" value={data.rejections} />
      </section>
      {data.awaiting_approval > 0 && (
        <p className="mt-4 rounded-lg border border-violet-200 bg-violet-50 px-4 py-3 text-sm text-violet-900">
          {data.awaiting_approval} application(s) are ready for your review. <Link className="font-medium underline" to="/assistant">Open Application Assistant</Link>
        </p>
      )}
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Applications by status" />
          <CardBody>
            <ul className="space-y-2">
              {Object.entries(data.by_status).map(([s, n]) => (
                <li key={s} className="flex items-center gap-3 text-sm">
                  <span className="w-36 shrink-0 text-slate-600">{statusLabel(s)}</span>
                  <div className="h-2.5 flex-1 rounded-full bg-slate-100" role="presentation"><div className="h-2.5 rounded-full bg-brand-500" style={{ width: `${(n / max) * 100}%` }} /></div>
                  <span className="w-6 text-right tabular-nums">{n}</span>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Upcoming follow-ups" />
          {data.follow_ups.length === 0 ? <EmptyState title="No follow-ups scheduled" hint="Follow-up dates are set automatically a week after you apply." /> : (
            <ul className="divide-y">
              {data.follow_ups.map((f) => (
                <li key={f.id} className="flex justify-between px-5 py-3 text-sm"><span>{f.position} <span className="text-slate-500">@ {f.company}</span></span><span className="text-slate-600">{fmtDate(f.date)}</span></li>
              ))}
            </ul>
          )}
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title="Recent activity" />
          {data.recent_activity.length === 0 ? <EmptyState title="No activity yet" hint="Start by completing your profile, then add a job source." /> : (
            <ul className="divide-y">
              {data.recent_activity.map((a, i) => (
                <li key={i} className="flex justify-between gap-4 px-5 py-2.5 text-sm"><span><span className="font-medium">{a.actor}</span> · {a.action} {a.message && <span className="text-slate-500">— {a.message}</span>}</span><span className="shrink-0 text-slate-400">{fmtDateTime(a.at)}</span></li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
