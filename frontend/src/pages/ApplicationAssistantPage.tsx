import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Badge, StatusBadge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input, Select, Textarea } from "@/components/ui/Form";
import { PageHeader } from "@/components/ui/Page";
import { EmptyState, ErrorState, Notice, Spinner } from "@/components/ui/States";
import { useAction, useGet } from "@/hooks/useApi";
import { api, qs } from "@/services/api";
import type { AnswerResult, Application, ApplicationDetail, FieldResult, FillReport, Page, SavedAnswer } from "@/types/api";

const fieldTone = (f: FieldResult): Tone => (f.status === "needs_user" && !f.filled ? "red" : f.status === "review" ? "amber" : f.filled ? "green" : "gray");
const fieldText = (f: FieldResult) => (f.status === "needs_user" && !f.filled ? "Needs you" : f.status === "review" ? "Review" : f.filled ? (f.verified ? "Filled ✓" : "Filled") : "Skipped");

export function FillReportView({ report }: { report: FillReport }) {
  if (!report.status) return null;
  return (
    <div className="space-y-4">
      {report.status === "intervention_required" && <Notice tone="warn"><b>Paused — your help is needed.</b> {report.reason} The browser window is still open; finish that step there, then press “Re-scan”.</Notice>}
      {report.status === "no_form_found" && <Notice tone="warn">{report.reason}</Notice>}
      {report.status === "needs_input" && <Notice tone="warn"><b>Some required answers need you.</b> The agent never guesses legal, eligibility or demographic questions. Complete them in the browser window, then press “Re-scan”.</Notice>}
      {report.status === "ready_for_review" && <Notice tone="success"><b>The form is complete and validated.</b> Check the details below and in the browser window, then approve.</Notice>}
      {report.needs_user && report.needs_user.length > 0 && (
        <div><h3 className="mb-1 text-sm font-semibold">Needs your input</h3><ul className="list-disc pl-5 text-sm text-slate-700">{report.needs_user.map((l, i) => <li key={i}>{l}</li>)}</ul></div>
      )}
      {report.pages?.map((pg) => (
        <div key={pg.page} className="overflow-x-auto">
          <h3 className="mb-1 text-sm font-semibold">Form page {pg.page}</h3>
          <table className="w-full text-left text-sm"><caption className="sr-only">Fields on form page {pg.page}</caption>
            <thead className="text-xs uppercase text-slate-500"><tr><th className="py-1.5">Field</th><th>Value</th><th>Source</th><th>Status</th></tr></thead>
            <tbody className="divide-y">{pg.fields.map((f) => (
              <tr key={f.field_id}><td className="py-1.5 pr-3">{f.label}{f.required && <span className="text-red-500" aria-label="required"> *</span>}</td>
                <td className="max-w-xs truncate pr-3 text-slate-700" title={f.value}>{f.value || <span className="text-slate-400">{f.note || "—"}</span>}</td>
                <td className="pr-3 text-slate-500">{f.source || "—"}</td><td><Badge tone={fieldTone(f)}>{fieldText(f)}</Badge></td></tr>))}</tbody></table>
        </div>
      ))}
    </div>
  );
}

function Workspace({ id }: { id: number }) {
  const { data: app, isLoading, error, refetch } = useGet<ApplicationDetail>(["application", id], `/applications/${id}`);
  const [headless, setHeadless] = useState(false); const [useAi, setUseAi] = useState(true);
  const [confirm, setConfirm] = useState(false); const [outcome, setOutcome] = useState<{ result: string; reason?: string } | null>(null);
  const inv = [["application", id], ["applications"], ["dashboard"], ["notifications"]];
  const prepare = useAction(() => api.post<FillReport>(`/applications/${id}/prepare`, { use_ai: useAi, headless }), { invalidate: inv, success: (r) => r.status === "ready_for_review" ? "Form filled and validated" : "Form processed — see the report" });
  const rescan = useAction(() => api.post<FillReport>(`/applications/${id}/rescan${qs({ use_ai: useAi })}`), { invalidate: inv, success: "Form re-checked" });
  const approve = useAction(() => api.post(`/applications/${id}/approve`), { invalidate: inv, success: "Approved. You can now submit." });
  const submit = useAction(() => api.post<{ result: string; reason?: string }>(`/applications/${id}/submit`, { confirm: true }), {
    invalidate: inv, onSuccess: (r) => { setOutcome(r); setConfirm(false); },
  });
  if (isLoading) return <Spinner />;
  if (error || !app) return <ErrorState error={error} onRetry={refetch} />;
  const closed = ["applied", "interview", "assessment", "offer", "rejected", "withdrawn"].includes(app.status);
  const ready = app.status === "awaiting_approval" && app.fill_report.status === "ready_for_review";
  const approved = !!app.approved_at;
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title={<>{app.position} <span className="font-normal text-slate-500">@ {app.company}</span></>} action={<StatusBadge status={app.status} />}
          description={<a className="text-brand-600 underline" href={app.job_url} target="_blank" rel="noopener noreferrer">{app.job_url}</a>} />
        <CardBody className="space-y-4">
          <ol className="grid gap-2 text-sm sm:grid-cols-4" aria-label="Workflow">
            {[["1. Prepare", "CV, cover letter, fill the form"], ["2. Review", "Check every field"], ["3. Approve", "Your explicit go-ahead"], ["4. Submit", "Final click, recorded"]].map(([t, d], i) => {
              const done = i === 0 ? app.status !== "discovered" && app.status !== "shortlisted" : i === 1 ? ready || approved || closed : i === 2 ? approved || closed : closed;
              return <li key={t} className={`rounded-lg border p-2.5 ${done ? "border-emerald-200 bg-emerald-50" : "border-slate-200"}`}><b>{t}</b><br /><span className="text-xs text-slate-600">{d}</span></li>;
            })}
          </ol>
          {closed ? (
            <Notice tone="success">This application is <b>{app.status}</b>. {app.confirmation && <>Confirmation: “{app.confirmation.slice(0, 160)}”</>}</Notice>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <Button loading={prepare.isPending} onClick={() => prepare.mutate()}>{app.fill_report.status ? "Prepare again" : "Prepare & fill form"}</Button>
              <Button variant="secondary" loading={rescan.isPending} disabled={!app.fill_report.status} onClick={() => rescan.mutate()}>Re-scan after my changes</Button>
              <Button variant="secondary" loading={approve.isPending} disabled={!ready || approved} onClick={() => approve.mutate()}>{approved ? "Approved ✓" : "Approve for submission"}</Button>
              <Button variant="danger" disabled={!approved} onClick={() => setConfirm(true)}>Submit application…</Button>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={headless} onChange={(e) => setHeadless(e.target.checked)} /> Run browser hidden</label>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} /> Use local AI for open questions</label>
            </div>
          )}
          {prepare.isPending && <Notice tone="info">The browser is opening and filling the form. A window may appear — you can click in it at any time to take over.</Notice>}
          {outcome && (outcome.result === "success" ? <Notice tone="success">Submitted and confirmed by the site. It is now tracked as Applied.</Notice>
            : <Notice tone={outcome.result === "failed" ? "error" : "warn"}><b>Not completed ({outcome.result}).</b> {outcome.reason}</Notice>)}
        </CardBody>
      </Card>
      {app.fill_report.status && <Card><CardHeader title="Form review" /><CardBody><FillReportView report={app.fill_report} /></CardBody></Card>}
      <ConfirmDialog open={confirm} danger title="Submit this application now?" confirmLabel="Yes, submit" loading={submit.isPending}
        description={<><p>This will click the final <b>Submit</b> button on <b>{app.company}</b>’s application form. Submitted applications cannot be recalled.</p><p className="mt-2">Make sure you have checked every field in the form review and the browser window.</p></>}
        onConfirm={() => submit.mutate()} onCancel={() => setConfirm(false)} />
    </div>
  );
}

function AnswersPanel({ listingId }: { listingId?: number | null }) {
  const [q, setQ] = useState(""); const [res, setRes] = useState<AnswerResult | null>(null); const [text, setText] = useState("");
  const saved = useGet<SavedAnswer[]>(["answers"], "/answers");
  const ask = useAction(() => api.post<AnswerResult>("/answers/ask", { question: q, listing_id: listingId ?? null }), { onSuccess: (r) => { setRes(r); setText(r.answer); } });
  const save = useAction((approved: boolean) => api.post("/answers", { question: q, answer: text, approved }), { success: "Answer saved for reuse", invalidate: [["answers"]] });
  const patch = useAction((a: { id: number; approved?: boolean }) => api.patch(`/answers/${a.id}`, { approved: a.approved }), { invalidate: [["answers"]] });
  const del = useAction((id: number) => api.del(`/answers/${id}`), { success: "Answer deleted", invalidate: [["answers"]] });
  return (
    <Card>
      <CardHeader title="Application answers" description="Test how the agent answers a question. Sensitive, legal and eligibility questions are never guessed." />
      <CardBody className="space-y-4">
        <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); if (q.trim().length > 2) ask.mutate(); }}>
          <div className="min-w-64 flex-1"><Input label="Question from an application form" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Why do you want to work here?" /></div>
          <Button type="submit" loading={ask.isPending} disabled={q.trim().length < 3}>Draft answer</Button>
        </form>
        {res && (res.status === "needs_user" ? <Notice tone="warn"><b>Needs your answer.</b> {res.reason}</Notice> : (
          <div className="space-y-2">
            {res.status !== "answered" && <Notice tone="info">{res.reason || "Draft — review before use."}</Notice>}
            <Textarea label={`Answer (${res.source})`} rows={4} value={text} onChange={(e) => setText(e.target.value)} />
            <Button size="sm" disabled={!text.trim()} loading={save.isPending} onClick={() => save.mutate(true)}>Approve &amp; save for reuse</Button>
          </div>))}
        {res?.status === "needs_user" && (
          <div className="space-y-2"><Textarea label="Your answer (you decide; stored only if you approve it)" rows={3} value={text} onChange={(e) => setText(e.target.value)} />
            <Button size="sm" disabled={!text.trim()} onClick={() => save.mutate(true)}>Save my answer</Button></div>)}
        <div>
          <h3 className="mb-1 text-sm font-semibold">Saved answers</h3>
          {saved.isLoading ? <Spinner /> : !saved.data?.length ? <p className="text-sm text-slate-500">No saved answers yet.</p> : (
            <ul className="divide-y rounded-lg border">{saved.data.map((a) => (
              <li key={a.id} className="flex flex-wrap items-start justify-between gap-2 p-3 text-sm">
                <div className="min-w-0 flex-1"><p className="font-medium">{a.question}</p><p className="text-slate-600">{a.answer}</p><p className="text-xs text-slate-400">used {a.times_used}× · {a.sensitive ? "sensitive: never auto-filled" : a.approved ? "approved" : "not approved"}</p></div>
                <div className="flex gap-1"><Button size="sm" variant="ghost" onClick={() => patch.mutate({ id: a.id, approved: !a.approved })}>{a.approved ? "Unapprove" : "Approve"}</Button>
                  <Button size="sm" variant="ghost" onClick={() => del.mutate(a.id)}>Delete</Button></div></li>))}</ul>)}
        </div>
      </CardBody>
    </Card>
  );
}

export default function ApplicationAssistantPage() {
  const [params, setParams] = useSearchParams();
  const list = useGet<Page<Application>>(["applications", "assistant"], "/applications?page_size=100");
  const id = Number(params.get("app")) || 0;
  const open = list.data?.items.filter((a) => !["rejected", "withdrawn"].includes(a.status)) ?? [];
  const current = list.data?.items.find((a) => a.id === id);
  return (
    <>
      <PageHeader title="Application Assistant" description="The agent fills in the application; you review and decide. Nothing is ever submitted without your explicit approval." />
      <div className="space-y-6">
        <div className="max-w-xl">
          <Select label="Application" value={id || ""} onChange={(e) => setParams(e.target.value ? { app: e.target.value } : {})} disabled={list.isLoading}>
            <option value="">{list.isLoading ? "Loading…" : "Choose an application…"}</option>
            {open.map((a) => <option key={a.id} value={a.id}>{a.position} — {a.company} ({a.status.replace(/_/g, " ")})</option>)}
          </Select>
        </div>
        {list.error ? <ErrorState error={list.error} onRetry={list.refetch} /> : !id ? (
          <EmptyState title="Choose an application to work on" hint="Use “Prepare application” on a recommended job, or add one in the Application Tracker." />
        ) : <Workspace key={id} id={id} />}
        <AnswersPanel listingId={current?.listing_id} />
      </div>
    </>
  );
}
