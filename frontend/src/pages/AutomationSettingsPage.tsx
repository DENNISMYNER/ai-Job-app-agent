import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input, Select } from "@/components/ui/Form";
import { PageHeader } from "@/components/ui/Page";
import { EmptyState, Notice, Spinner } from "@/components/ui/States";
import { useAction, useGet } from "@/hooks/useApi";
import { api } from "@/services/api";
import type { AutomationSettings, Schedule } from "@/types/api";
import { fmtDateTime } from "@/utils/format";

const PRESETS = [
  { label: "Every morning (08:00)", cron: "0 8 * * *" }, { label: "Weekdays 08:00", cron: "0 8 * * 1-5" },
  { label: "Every 6 hours", cron: "0 */6 * * *" }, { label: "Every evening (20:00)", cron: "0 20 * * *" },
];

function Schedules() {
  const { data, isLoading } = useGet<Schedule[]>(["schedules"], "/automation/schedules");
  const status = useGet<{ scheduler: { running: boolean; paused: boolean } }>(["automation-status"], "/automation/status");
  const [f, setF] = useState({ name: "", task_type: "discover_match", cron: "0 8 * * *", keywords: "", remote_only: false, min_score: "75" });
  const [del, setDel] = useState<Schedule | null>(null);
  const inv = [["schedules"], ["automation-status"]];
  const create = useAction(() => api.post("/automation/schedules", { name: f.name, task_type: f.task_type, cron: f.cron,
    params: f.task_type === "discover_match" ? { keywords: f.keywords.split(",").map((s) => s.trim()).filter(Boolean), remote_only: f.remote_only, min_score: Number(f.min_score) || 75 } : {} }),
    { success: "Schedule created", invalidate: inv, onSuccess: () => setF({ ...f, name: "", keywords: "" }) });
  const act = useAction((v: { id: number; action: string }) => api.post(`/automation/schedules/${v.id}/${v.action}`), { invalidate: [...inv, ["notifications"], ["dashboard"], ["jobs"]], success: (_o) => "Done" });
  const remove = useAction((id: number) => api.del(`/automation/schedules/${id}`), { success: "Schedule deleted", invalidate: inv, onSuccess: () => setDel(null) });
  const all = useAction((a: "pause-all" | "resume-all") => api.post(`/automation/${a}`), { success: "Updated", invalidate: inv });
  return (
    <Card>
      <CardHeader title="Scheduled tasks" description="Run locally while this app is running. Scheduled tasks find and score jobs and notify you — they never apply."
        action={<div className="flex gap-2"><Button size="sm" variant="secondary" onClick={() => all.mutate("pause-all")}>Pause all</Button><Button size="sm" variant="secondary" onClick={() => all.mutate("resume-all")}>Resume all</Button></div>} />
      <CardBody className="space-y-5">
        {status.data && <p className="text-sm text-slate-600">Scheduler: {status.data.scheduler.running ? (status.data.scheduler.paused ? <Badge tone="amber">paused</Badge> : <Badge tone="green">running</Badge>) : <Badge>not running</Badge>}</p>}
        <form className="grid gap-3 sm:grid-cols-3" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <Input label="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Morning remote search" required />
          <Select label="Task" value={f.task_type} onChange={(e) => setF({ ...f, task_type: e.target.value })}><option value="discover_match">Search for jobs &amp; notify on high matches</option><option value="daily_report">Daily application report</option></Select>
          <div><Select label="When" value={PRESETS.some((p) => p.cron === f.cron) ? f.cron : "custom"} onChange={(e) => e.target.value !== "custom" && setF({ ...f, cron: e.target.value })}>{PRESETS.map((p) => <option key={p.cron} value={p.cron}>{p.label}</option>)}<option value="custom">Custom cron…</option></Select></div>
          <Input label="Cron expression" value={f.cron} onChange={(e) => setF({ ...f, cron: e.target.value })} hint="minute hour day month weekday" />
          {f.task_type === "discover_match" && (<>
            <Input label="Only jobs mentioning (comma-separated)" value={f.keywords} onChange={(e) => setF({ ...f, keywords: e.target.value })} placeholder="junior, developer" />
            <Input label="Notify at score ≥" inputMode="numeric" value={f.min_score} onChange={(e) => setF({ ...f, min_score: e.target.value })} />
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.remote_only} onChange={(e) => setF({ ...f, remote_only: e.target.checked })} /> Remote jobs only</label></>)}
          <div className="flex items-end"><Button type="submit" loading={create.isPending}>Add schedule</Button></div>
        </form>
        {isLoading ? <Spinner /> : !data?.length ? <EmptyState title="No schedules yet" hint="For example: search for new remote junior roles every morning." /> : (
          <ul className="divide-y rounded-lg border">{data.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
              <div><p className="font-medium">{s.name} {s.enabled ? <Badge tone="green">on</Badge> : <Badge>paused</Badge>}</p>
                <p className="text-slate-500">{s.task_type.replace("_", " ")} · <code>{s.cron}</code></p><p className="text-xs text-slate-400">Last run {fmtDateTime(s.last_run_at)} {s.last_status && `· ${s.last_status}`}</p></div>
              <div className="flex gap-1"><Button size="sm" variant="secondary" loading={act.isPending && act.variables?.id === s.id} onClick={() => act.mutate({ id: s.id, action: "run-now" })}>Run now</Button>
                <Button size="sm" variant="ghost" onClick={() => act.mutate({ id: s.id, action: s.enabled ? "pause" : "resume" })}>{s.enabled ? "Pause" : "Resume"}</Button>
                <Button size="sm" variant="ghost" onClick={() => setDel(s)}>Delete</Button></div></li>))}</ul>)}
      </CardBody>
      <ConfirmDialog open={!!del} danger title="Delete this schedule?" confirmLabel="Delete" loading={remove.isPending} description={<>“{del?.name}” will stop running.</>} onConfirm={() => del && remove.mutate(del.id)} onCancel={() => setDel(null)} />
    </Card>
  );
}

function Policy() {
  const { data, isLoading } = useGet<AutomationSettings>(["settings", "automation"], "/settings/automation");
  const [warn, setWarn] = useState(false);
  const save = useAction((p: Partial<AutomationSettings>) => api.put("/settings/automation", p), { success: "Policy saved", invalidate: [["settings", "automation"]], onSuccess: () => setWarn(false) });
  const check = useAction(() => api.get<{ browser: { ok: boolean; chromium?: string; hint?: string; error?: string } }>("/automation/status?check_browser=true"));
  if (isLoading || !data) return <Spinner />;
  return (
    <Card>
      <CardHeader title="Submission policy & browser" />
      <CardBody className="space-y-4">
        <Notice tone="success"><b>Default (recommended):</b> every final submission needs your explicit approval and confirmation. CAPTCHA, MFA and sign-in steps are always left to you.</Notice>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Notify me about matches at score ≥" inputMode="numeric" defaultValue={data.notify_min_score} onBlur={(e) => save.mutate({ notify_min_score: Number(e.target.value) || 75 })} />
          <label className="flex items-center gap-2 pt-6 text-sm"><input type="checkbox" checked={data.headless} onChange={(e) => save.mutate({ headless: e.target.checked })} /> Run the browser hidden by default (you cannot take over a hidden window)</label>
        </div>
        <div className="rounded-lg border border-amber-200 p-4">
          <label className="flex items-start gap-2 text-sm font-medium"><input type="checkbox" className="mt-1" checked={data.auto_submit_enabled} onChange={(e) => e.target.checked ? setWarn(true) : save.mutate({ auto_submit_enabled: false, require_approval: true })} />
            <span>Advanced: skip the separate “Approve” click for very strong matches<span className="block font-normal text-slate-600">Only affects the Submit step for jobs scoring at least {data.auto_submit_min_score}, up to {data.auto_submit_daily_limit} per day. Required fields are still validated and a submission is still only started by you — scheduled searches never apply.</span></span></label>
          {data.auto_submit_enabled && <div className="mt-3 grid gap-3 sm:grid-cols-2"><Input label="Minimum score" inputMode="numeric" defaultValue={data.auto_submit_min_score} onBlur={(e) => save.mutate({ auto_submit_min_score: Number(e.target.value) || 85 })} /><Input label="Daily limit" inputMode="numeric" defaultValue={data.auto_submit_daily_limit} onBlur={(e) => save.mutate({ auto_submit_daily_limit: Number(e.target.value) || 5 })} /></div>}
        </div>
        <div className="flex items-center gap-3"><Button variant="secondary" loading={check.isPending} onClick={() => check.mutate()}>Check browser setup</Button>
          {check.data && (check.data.browser.ok ? <Badge tone="green">Chromium {check.data.browser.chromium} ready</Badge> : <span role="alert" className="text-sm text-red-600">{check.data.browser.error} — {check.data.browser.hint}</span>)}</div>
      </CardBody>
      <ConfirmDialog open={warn} danger title="Reduce the approval step?" confirmLabel="Enable" loading={save.isPending}
        description="Strong-match applications will no longer need a separate approval click before the Submit action. Submitted applications cannot be recalled. Keep this off unless you fully trust your profile and answers."
        onConfirm={() => save.mutate({ auto_submit_enabled: true, require_approval: false })} onCancel={() => setWarn(false)} />
    </Card>
  );
}

export default function AutomationSettingsPage() {
  return (<><PageHeader title="Automation Settings" description="Control scheduled searches, the submission policy and the browser." /><div className="space-y-6"><Policy /><Schedules /></div></>);
}
