import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Select } from "@/components/ui/Form";
import { PageHeader } from "@/components/ui/Page";
import { EmptyState, Notice, Spinner } from "@/components/ui/States";
import { useAction, useGet } from "@/hooks/useApi";
import { api } from "@/services/api";
import type { Application, Interview, Page } from "@/types/api";
import { fmtDateTime } from "@/utils/format";

interface Prep {
  company_research: { source: string; company: string; role: string; what_they_ask_for: string[]; nice_to_have: string[]; seniority: string; work_mode: string; to_research_yourself: string[]; gaps_to_prepare: string[] };
  technical_questions: string[]; technical_exercises: { skill: string; exercise: string }[];
  behavioral: { question: string; star_guidance: string; suggested_basis: { situation: string; task: string; action: string; result: string } | null }[];
  questions_to_ask_them: string[]; ai_questions?: string[];
}

export default function InterviewPrepPage() {
  const apps = useGet<Page<Application>>(["applications", "prep"], "/applications?page_size=100");
  const upcoming = useGet<Interview[]>(["interviews"], "/interviews?upcoming=true");
  const [id, setId] = useState(""); const [useAi, setUseAi] = useState(true); const [prep, setPrep] = useState<Prep | null>(null);
  const gen = useAction(() => api.post<{ prep: Prep }>(`/applications/${id}/interview-prep`, { use_ai: useAi }), { success: "Preparation ready", invalidate: [["interviews"]], onSuccess: (r) => setPrep(r.prep) });
  const sel = apps.data?.items.find((a) => String(a.id) === id);
  return (
    <>
      <PageHeader title="Interview Preparation" description="Likely questions, exercises and STAR guidance built from your real experience and the job ad." />
      <div className="space-y-6">
        <Card><CardHeader title="Prepare for an application" /><CardBody className="space-y-3">
          <div className="max-w-xl"><Select label="Application" value={id} onChange={(e) => { setId(e.target.value); setPrep(null); }}>
            <option value="">Choose…</option>{apps.data?.items.map((a) => <option key={a.id} value={a.id}>{a.position} — {a.company}</option>)}</Select></div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} /> Ask the local AI for extra questions</label>
          <Button disabled={!id} loading={gen.isPending} onClick={() => gen.mutate()}>Generate preparation</Button></CardBody></Card>
        {gen.isPending && <Spinner label="Preparing…" />}
        {prep && sel && (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card><CardHeader title="Company & role notes" /><CardBody className="space-y-3 text-sm">
              <Notice tone="info">{prep.company_research.source} Research the company yourself using the checklist below.</Notice>
              <p><b>Asked for:</b> {prep.company_research.what_they_ask_for.map((s) => <Badge key={s} className="mr-1">{s}</Badge>)}</p>
              {prep.company_research.gaps_to_prepare.length > 0 && <p><b>Gaps to prepare:</b> {prep.company_research.gaps_to_prepare.map((s) => <Badge key={s} tone="amber" className="mr-1">{s}</Badge>)}</p>}
              <p><b>Seniority:</b> {prep.company_research.seniority} · <b>Work mode:</b> {prep.company_research.work_mode}</p>
              <ul className="list-disc pl-5">{prep.company_research.to_research_yourself.map((x) => <li key={x}>{x}</li>)}</ul></CardBody></Card>
            <Card><CardHeader title="Technical questions" /><CardBody><ul className="list-disc space-y-1 pl-5 text-sm">{[...prep.technical_questions, ...(prep.ai_questions ?? [])].map((q, i) => <li key={i}>{q}</li>)}</ul></CardBody></Card>
            <Card className="lg:col-span-2"><CardHeader title="Behavioural questions (STAR)" /><CardBody className="space-y-4">
              {prep.behavioral.map((b, i) => (<div key={i} className="rounded-lg border border-slate-200 p-3 text-sm"><p className="font-medium">{b.question}</p><p className="text-slate-500">{b.star_guidance}</p>
                {b.suggested_basis && <dl className="mt-2 grid gap-x-3 gap-y-1 sm:grid-cols-[6rem_1fr]">{(["situation", "task", "action", "result"] as const).map((k) => (<div key={k} className="contents"><dt className="font-medium capitalize text-slate-600">{k}</dt><dd>{b.suggested_basis![k]}</dd></div>))}</dl>}</div>))}</CardBody></Card>
            <Card><CardHeader title="Practice exercises" /><CardBody>{!prep.technical_exercises.length ? <p className="text-sm text-slate-500">No standard exercises for this role’s skills.</p> : <ul className="space-y-2 text-sm">{prep.technical_exercises.map((e) => <li key={e.skill}><Badge className="mr-2">{e.skill}</Badge>{e.exercise}</li>)}</ul>}</CardBody></Card>
            <Card><CardHeader title="Questions to ask them" /><CardBody><ul className="list-disc space-y-1 pl-5 text-sm">{prep.questions_to_ask_them.map((q) => <li key={q}>{q}</li>)}</ul></CardBody></Card>
          </div>)}
        <Card><CardHeader title="Upcoming interviews" />
          {upcoming.isLoading ? <Spinner /> : !upcoming.data?.length ? <EmptyState title="No upcoming interviews" hint="Add interviews from the Application Tracker." /> : (
            <ul className="divide-y">{upcoming.data.map((i) => <li key={i.id} className="px-5 py-3 text-sm"><b>{fmtDateTime(i.scheduled_at)}</b> · {i.kind} {i.notes && <span className="text-slate-500">— {i.notes}</span>}</li>)}</ul>)}</Card>
      </div>
    </>
  );
}
