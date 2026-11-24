import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { JobCard } from "@/components/JobCard";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input, Select, Textarea } from "@/components/ui/Form";
import { PageHeader } from "@/components/ui/Page";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, Notice, Spinner } from "@/components/ui/States";
import { useAction, useGet } from "@/hooks/useApi";
import { api, qs } from "@/services/api";
import type { Job, JobSource, Page } from "@/types/api";
import { fmtDateTime } from "@/utils/format";

const KINDS = [
  { v: "greenhouse", label: "Greenhouse board", hint: "Board token, e.g. “acme” from boards.greenhouse.io/acme" },
  { v: "lever", label: "Lever company", hint: "Company slug, e.g. “acme” from jobs.lever.co/acme" },
  { v: "rss", label: "RSS feed", hint: "Full feed URL" },
  { v: "career_page", label: "Public career page", hint: "Page URL (robots.txt is respected)" },
];

function Sources() {
  const { data, isLoading } = useGet<JobSource[]>(["sources"], "/job-sources");
  const [form, setForm] = useState({ name: "", kind: "greenhouse", identifier: "", company: "" });
  const [del, setDel] = useState<JobSource | null>(null);
  const add = useAction(() => api.post("/job-sources", { name: form.name || form.identifier, kind: form.kind, identifier: form.identifier.trim(), config: { company: form.company } }),
    { success: "Source added", invalidate: [["sources"]], onSuccess: () => setForm({ ...form, name: "", identifier: "", company: "" }) });
  const run = useAction((id?: number) => api.post<{ results: { new: number; error: string | null }[]; matched: number }>(`/jobs/discover${qs({ source_id: id })}`),
    { success: (r) => `Found ${r.results.reduce((n, x) => n + x.new, 0)} new jobs; scored ${r.matched}`, invalidate: [["sources"], ["jobs"], ["dashboard"]] });
  const remove = useAction((id: number) => api.del(`/job-sources/${id}`), { success: "Source removed", invalidate: [["sources"]], onSuccess: () => setDel(null) });
  const toggle = useAction((s: JobSource) => api.patch(`/job-sources/${s.id}`, { enabled: !s.enabled }), { invalidate: [["sources"]] });
  const kind = KINDS.find((k) => k.v === form.kind)!;
  return (
    <Card>
      <CardHeader title="Job sources" description="Only public, permitted interfaces are used. Sites that forbid automation are skipped — use manual import instead."
        action={<Button size="sm" loading={run.isPending} onClick={() => run.mutate(undefined)}>Search all sources</Button>} />
      <CardBody className="space-y-4">
        <form className="grid gap-3 sm:grid-cols-5" onSubmit={(e) => { e.preventDefault(); if (form.identifier.trim()) add.mutate(); }}>
          <Select label="Type" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>{KINDS.map((k) => <option key={k.v} value={k.v}>{k.label}</option>)}</Select>
          <Input label="Identifier" value={form.identifier} onChange={(e) => setForm({ ...form, identifier: e.target.value })} hint={kind.hint} required />
          <Input label="Company name" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
          <Input label="Label (optional)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <div className="flex items-end"><Button type="submit" loading={add.isPending} disabled={!form.identifier.trim()}>Add source</Button></div>
        </form>
        {isLoading ? <Spinner /> : !data?.length ? <EmptyState title="No sources yet" hint="Add a Greenhouse or Lever board, an RSS feed, or import a single job below." /> : (
          <div className="overflow-x-auto"><table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-500"><tr><th className="py-2">Source</th><th>Type</th><th>Last run</th><th>Status</th><th /></tr></thead>
            <tbody className="divide-y">{data.map((s) => (
              <tr key={s.id}><td className="py-2 font-medium">{s.name}<div className="text-xs font-normal text-slate-500">{s.identifier}</div></td><td>{s.kind}</td><td>{fmtDateTime(s.last_run_at)}</td>
                <td className={s.last_status.startsWith("error") ? "text-red-600" : "text-slate-600"}>{s.last_status || "—"}</td>
                <td className="space-x-1 text-right whitespace-nowrap">
                  <Button size="sm" variant="secondary" onClick={() => run.mutate(s.id)}>Run</Button>
                  <Button size="sm" variant="ghost" onClick={() => toggle.mutate(s)}>{s.enabled ? "Disable" : "Enable"}</Button>
                  <Button size="sm" variant="ghost" onClick={() => setDel(s)}>Remove</Button></td></tr>))}</tbody></table></div>
        )}
      </CardBody>
      <ConfirmDialog open={!!del} danger title="Remove this source?" confirmLabel="Remove" loading={remove.isPending}
        description={<>Jobs already discovered from <b>{del?.name}</b> are kept.</>} onConfirm={() => del && remove.mutate(del.id)} onCancel={() => setDel(null)} />
    </Card>
  );
}

function ManualImport() {
  const qc = useQueryClient();
  const [url, setUrl] = useState(""); const [paste, setPaste] = useState({ title: "", company: "", description: "" });
  const done = () => { qc.invalidateQueries({ queryKey: ["jobs"] }); qc.invalidateQueries({ queryKey: ["dashboard"] }); };
  const byUrl = useAction(() => api.post<Job>("/jobs/import-url", { url }), { success: "Job imported and scored", onSuccess: () => { setUrl(""); done(); } });
  const byText = useAction(() => api.post<Job>("/jobs/import-text", paste), { success: "Job imported and scored", onSuccess: () => { setPaste({ title: "", company: "", description: "" }); done(); } });
  return (
    <Card>
      <CardHeader title="Import a job manually" description="Use this when a site cannot be searched automatically." />
      <CardBody className="grid gap-6 lg:grid-cols-2">
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); byUrl.mutate(); }}>
          <Input label="Job posting URL" type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" hint="Fetched politely; blocked if the site's robots.txt forbids it." />
          <Button type="submit" loading={byUrl.isPending} disabled={!url}>Import from URL</Button>
        </form>
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); byText.mutate(); }}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Job title" value={paste.title} onChange={(e) => setPaste({ ...paste, title: e.target.value })} required />
            <Input label="Company" value={paste.company} onChange={(e) => setPaste({ ...paste, company: e.target.value })} />
          </div>
          <Textarea label="Paste the job description" rows={4} value={paste.description} onChange={(e) => setPaste({ ...paste, description: e.target.value })} />
          <Button type="submit" loading={byText.isPending} disabled={!paste.title || paste.description.length < 20}>Import pasted job</Button>
        </form>
      </CardBody>
    </Card>
  );
}

export default function JobDiscoveryPage() {
  const [f, setF] = useState({ q: "", technology: "", level: "", remote: "", employment_type: "", location: "", salary_min: "", sort: "newest" });
  const [page, setPage] = useState(1);
  const { data, isLoading, error, refetch } = useGet<Page<Job>>(["jobs", "all", f, page], `/jobs${qs({ ...f, page, page_size: 10 })}`);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => { setF({ ...f, [k]: e.target.value }); setPage(1); };
  return (
    <>
      <PageHeader title="Job Discovery" description="Find jobs from public boards and feeds, or import one yourself. Every job is scored against your profile." />
      <div className="space-y-6">
        <Sources />
        <ManualImport />
        <Card>
          <CardHeader title="Discovered jobs" />
          <CardBody className="space-y-4">
            <div role="search" aria-label="Filter jobs" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Input label="Search" value={f.q} onChange={set("q")} placeholder="Title, company, keyword" />
              <Input label="Technology" value={f.technology} onChange={set("technology")} placeholder="e.g. React" />
              <Input label="Location" value={f.location} onChange={set("location")} />
              <Input label="Min salary" inputMode="numeric" value={f.salary_min} onChange={set("salary_min")} />
              <Select label="Level" value={f.level} onChange={set("level")}><option value="">Any</option>{["intern", "junior", "mid", "senior"].map((x) => <option key={x}>{x}</option>)}</Select>
              <Select label="Remote" value={f.remote} onChange={set("remote")}><option value="">Any</option><option>remote</option><option>hybrid</option><option>onsite</option></Select>
              <Input label="Employment type" value={f.employment_type} onChange={set("employment_type")} placeholder="full-time…" />
              <Select label="Sort by" value={f.sort} onChange={set("sort")}><option value="newest">Newest</option><option value="score">Best match</option><option value="company">Company</option></Select>
            </div>
            {isLoading ? <Spinner /> : error ? <ErrorState error={error} onRetry={refetch} /> : !data?.items.length ? (
              <EmptyState title="No jobs found" hint="Add a source and press “Search all sources”, import a job, or loosen the filters." />
            ) : (<><div className="space-y-4">{data.items.map((j) => <JobCard key={j.id} job={j} />)}</div><Pagination page={page} pageSize={data.page_size} total={data.total} onPage={setPage} /></>)}
            <Notice tone="info">Discovery only finds and scores jobs. It never applies for you.</Notice>
          </CardBody>
        </Card>
      </div>
    </>
  );
}
