import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input, Select, Textarea } from "@/components/ui/Form";
import { PageHeader } from "@/components/ui/Page";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, Notice, Spinner } from "@/components/ui/States";
import { useAction, useGet } from "@/hooks/useApi";
import { api, qs } from "@/services/api";
import { STATUSES, type Application, type ApplicationDetail, type EmailDraft, type Page } from "@/types/api";
import { fmtDate, fmtDateTime, statusLabel } from "@/utils/format";

function Detail({ id, onClose }: { id: number; onClose: () => void }) {
  const { data: a, isLoading } = useGet<ApplicationDetail>(["application", id], `/applications/${id}`);
  const [notes, setNotes] = useState(""); const [follow, setFollow] = useState("");
  const [iv, setIv] = useState({ scheduled_at: "", kind: "general", notes: "" }); const [rc, setRc] = useState({ name: "", email: "" });
  const [draft, setDraft] = useState<EmailDraft | null>(null);
  useEffect(() => { if (a) { setNotes(a.notes); setFollow(a.follow_up_date?.slice(0, 10) ?? ""); } }, [a?.id, a?.notes, a?.follow_up_date]); // eslint-disable-line react-hooks/exhaustive-deps
  const inv = [["application", id], ["applications"], ["dashboard"]];
  const save = useAction(() => api.patch(`/applications/${id}`, { notes, follow_up_date: follow ? `${follow}T09:00:00Z` : null }), { success: "Saved", invalidate: inv });
  const addIv = useAction(() => api.post(`/applications/${id}/interviews`, { ...iv, scheduled_at: iv.scheduled_at ? new Date(iv.scheduled_at).toISOString() : null }), { success: "Interview added", invalidate: inv, onSuccess: () => setIv({ scheduled_at: "", kind: "general", notes: "" }) });
  const addRc = useAction(() => api.post(`/applications/${id}/recruiters`, rc), { success: "Contact added", invalidate: inv, onSuccess: () => setRc({ name: "", email: "" }) });
  const mkDraft = useAction(() => api.post<EmailDraft>(`/applications/${id}/follow-up-draft`, { to: a?.recruiters[0]?.email ?? "" }), { onSuccess: setDraft });
  if (isLoading || !a) return <Spinner />;
  return (
    <Card>
      <CardHeader title={`${a.position} @ ${a.company}`} action={<Button variant="ghost" size="sm" onClick={onClose}>Close</Button>} description={<a className="underline" href={a.job_url} target="_blank" rel="noopener noreferrer">Job posting</a>} />
      <CardBody className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <Textarea label="Notes" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} />
          <Input label="Follow-up date" type="date" value={follow} onChange={(e) => setFollow(e.target.value)} />
          <div className="text-sm text-slate-600"><p>CV used: {a.cv_id ? `#${a.cv_id}` : "—"} · Cover letter: {a.cover_letter_id ? `#${a.cover_letter_id}` : "—"}</p>
            <p>Applied: {fmtDate(a.applied_at)} {a.confirmation && <>· Confirmation: <i>{a.confirmation.slice(0, 120)}</i></>}</p></div>
          <div className="flex gap-2"><Button loading={save.isPending} onClick={() => save.mutate()}>Save</Button>
            <Link to={`/assistant?app=${a.id}`}><Button variant="secondary">Open in assistant</Button></Link>
            <Button variant="secondary" loading={mkDraft.isPending} onClick={() => mkDraft.mutate()}>Draft follow-up email</Button></div>
          {draft && <Notice tone="info">Draft created (not sent). Review and approve it in <Link className="underline" to="/system">System Settings → Email</Link>.</Notice>}
          <div><h3 className="mb-1 text-sm font-semibold">Recruiter contacts</h3>
            <ul className="mb-2 text-sm">{a.recruiters.map((r) => <li key={r.id}>{r.name} {r.email && <span className="text-slate-500">· {r.email}</span>}</li>)}{!a.recruiters.length && <li className="text-slate-500">None yet.</li>}</ul>
            <div className="flex gap-2"><Input label="Name" value={rc.name} onChange={(e) => setRc({ ...rc, name: e.target.value })} /><Input label="Email" value={rc.email} onChange={(e) => setRc({ ...rc, email: e.target.value })} />
              <div className="flex items-end"><Button variant="secondary" disabled={!rc.name && !rc.email} onClick={() => addRc.mutate()}>Add</Button></div></div></div>
        </div>
        <div className="space-y-4">
          <div><h3 className="mb-1 text-sm font-semibold">Interviews</h3>
            <ul className="mb-2 text-sm">{a.interviews.map((i) => <li key={i.id}>{fmtDateTime(i.scheduled_at)} · {i.kind}{i.notes && <span className="text-slate-500"> — {i.notes}</span>}</li>)}{!a.interviews.length && <li className="text-slate-500">None scheduled.</li>}</ul>
            <div className="grid gap-2 sm:grid-cols-3"><Input label="When" type="datetime-local" value={iv.scheduled_at} onChange={(e) => setIv({ ...iv, scheduled_at: e.target.value })} />
              <Select label="Type" value={iv.kind} onChange={(e) => setIv({ ...iv, kind: e.target.value })}>{["general", "phone", "technical", "behavioral", "final"].map((k) => <option key={k}>{k}</option>)}</Select>
              <div className="flex items-end"><Button variant="secondary" onClick={() => addIv.mutate()} loading={addIv.isPending}>Add interview</Button></div></div></div>
          <div><h3 className="mb-1 text-sm font-semibold">History</h3>
            <ol className="space-y-1 border-l-2 border-slate-200 pl-3 text-sm">{[...a.events].reverse().map((e, i) => <li key={i}><span className="font-medium">{e.type.replace(/_/g, " ")}</span> <span className="text-slate-500">{e.detail}</span><span className="block text-xs text-slate-400">{fmtDateTime(e.created_at)}</span></li>)}</ol></div>
        </div>
      </CardBody>
    </Card>
  );
}

export default function TrackerPage() {
  const [f, setF] = useState({ q: "", status: "", sort: "newest" }); const [page, setPage] = useState(1);
  const [open, setOpen] = useState<number | null>(null); const [del, setDel] = useState<Application | null>(null);
  const [form, setForm] = useState({ company: "", position: "", url: "", status: "shortlisted" });
  const { data, isLoading, error, refetch } = useGet<Page<Application>>(["applications", f, page], `/applications${qs({ ...f, page, page_size: 15 })}`);
  const inv = [["applications"], ["dashboard"]];
  const create = useAction(() => api.post("/applications", { company: form.company, position: form.position, url: form.url, status: form.status }),
    { success: "Application added", invalidate: inv, onSuccess: () => setForm({ company: "", position: "", url: "", status: "shortlisted" }) });
  const setStatus = useAction((v: { id: number; status: string }) => api.patch(`/applications/${v.id}`, { status: v.status }), { success: "Status updated", invalidate: [...inv, ["application"]] });
  const remove = useAction((id: number) => api.del(`/applications/${id}`), { success: "Application deleted", invalidate: inv, onSuccess: () => { setDel(null); setOpen(null); } });
  return (
    <>
      <PageHeader title="Application Tracker" description="Every application in one place. Update statuses manually any time; duplicates are detected automatically." />
      <div className="space-y-6">
        <Card><CardHeader title="Add an application you made elsewhere" />
          <CardBody><form className="grid gap-3 sm:grid-cols-5" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
            <Input label="Company" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} required />
            <Input label="Position" value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} required />
            <Input label="Job URL" type="url" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} required />
            <Select label="Status" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>{STATUSES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}</Select>
            <div className="flex items-end"><Button type="submit" loading={create.isPending}>Add</Button></div></form>
            {create.error && <p role="alert" className="mt-2 text-sm text-red-600">{create.error.message}</p>}</CardBody></Card>
        <Card>
          <CardHeader title="Applications" />
          <CardBody className="space-y-4">
            <div role="search" aria-label="Filter applications" className="grid gap-3 sm:grid-cols-3">
              <Input label="Search" value={f.q} onChange={(e) => { setF({ ...f, q: e.target.value }); setPage(1); }} placeholder="Company or position" />
              <Select label="Status" value={f.status} onChange={(e) => { setF({ ...f, status: e.target.value }); setPage(1); }}><option value="">All</option>{STATUSES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}</Select>
              <Select label="Sort" value={f.sort} onChange={(e) => setF({ ...f, sort: e.target.value })}><option value="newest">Newest</option><option value="company">Company</option><option value="status">Status</option><option value="follow_up">Follow-up date</option></Select>
            </div>
            {isLoading ? <Spinner /> : error ? <ErrorState error={error} onRetry={refetch} /> : !data?.items.length ? (
              <EmptyState title="No applications yet" hint="Add jobs from Recommended Jobs, or record one above." />
            ) : (<>
              <div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">Applications</caption>
                <thead className="text-xs uppercase text-slate-500"><tr><th className="py-2">Position</th><th>Company</th><th>Status</th><th>Applied</th><th>Follow-up</th><th /></tr></thead>
                <tbody className="divide-y">{data.items.map((a) => (
                  <tr key={a.id}><td className="py-2 font-medium"><button className="text-left hover:underline" onClick={() => setOpen(a.id)}>{a.position}</button></td><td>{a.company}</td>
                    <td><label className="sr-only" htmlFor={`st-${a.id}`}>Status for {a.position}</label>
                      <select id={`st-${a.id}`} value={a.status} onChange={(e) => setStatus.mutate({ id: a.id, status: e.target.value })} className="rounded-md border border-slate-300 bg-white px-1.5 py-1 text-xs">{STATUSES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}</select>
                      <span className="ml-2 hidden sm:inline"><StatusBadge status={a.status} /></span></td>
                    <td>{fmtDate(a.applied_at)}</td><td>{fmtDate(a.follow_up_date)}</td>
                    <td className="text-right whitespace-nowrap"><Button size="sm" variant="ghost" onClick={() => setOpen(a.id)}>Details</Button><Button size="sm" variant="ghost" onClick={() => setDel(a)}>Delete</Button></td></tr>))}</tbody></table></div>
              <Pagination page={page} pageSize={data.page_size} total={data.total} onPage={setPage} /></>)}
          </CardBody>
        </Card>
        {open && <Detail id={open} onClose={() => setOpen(null)} />}
      </div>
      <ConfirmDialog open={!!del} danger title="Delete this application?" confirmLabel="Delete" loading={remove.isPending}
        description={<>“{del?.position}” at {del?.company}, with its history, interviews and contacts, will be permanently removed.</>} onConfirm={() => del && remove.mutate(del.id)} onCancel={() => setDel(null)} />
    </>
  );
}
