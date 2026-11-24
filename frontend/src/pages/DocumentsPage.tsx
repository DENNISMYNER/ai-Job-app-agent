import { Download, FileText, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { JobSelect } from "@/components/JobSelect";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input } from "@/components/ui/Form";
import { PageHeader } from "@/components/ui/Page";
import { EmptyState, ErrorState, Notice, Spinner } from "@/components/ui/States";
import { useAction, useGet } from "@/hooks/useApi";
import { api, downloadUrl } from "@/services/api";
import type { CV, DocumentFile } from "@/types/api";

export default function DocumentsPage() {
  const cvs = useGet<CV[]>(["cvs"], "/cvs");
  const docs = useGet<DocumentFile[]>(["documents"], "/documents");
  const [jobId, setJobId] = useState(""); const [category, setCategory] = useState("general"); const [useAi, setUseAi] = useState(true);
  const [delCv, setDelCv] = useState<CV | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const gen = useAction(() => api.post<CV>("/cvs", { listing_id: jobId ? Number(jobId) : null, category, use_ai: useAi }),
    { success: (c) => `CV version ${c.version} created`, invalidate: [["cvs"]] });
  const delCvM = useAction((id: number) => api.del(`/cvs/${id}`), { success: "CV deleted", invalidate: [["cvs"]], onSuccess: () => setDelCv(null) });
  const upload = useAction((f: File) => { const fd = new FormData(); fd.append("file", f); fd.append("kind", "cv"); return api.upload("/documents", fd); }, { success: "Document uploaded", invalidate: [["documents"]] });
  const delDoc = useAction((id: number) => api.del(`/documents/${id}`), { success: "Document deleted", invalidate: [["documents"]] });
  return (
    <>
      <PageHeader title="CV & Documents" description="Generate tailored CVs from your profile. Wording can be polished, but facts are never invented — every CV is checked against your profile." />
      <div className="space-y-6">
        <Card>
          <CardHeader title="Generate a CV" />
          <CardBody className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <JobSelect label="Tailor for a job" value={jobId} onChange={setJobId} allowNone />
              <Input label="Category / version name" value={category} onChange={(e) => setCategory(e.target.value)} hint="e.g. backend, frontend, support" />
            </div>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} /> Polish wording with the local AI model (falls back automatically if unavailable)</label>
            <Button loading={gen.isPending} onClick={() => gen.mutate()}>Generate CV</Button>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Generated CVs" description="Every generation is saved as a new version." />
          {cvs.isLoading ? <Spinner /> : cvs.error ? <ErrorState error={cvs.error} onRetry={cvs.refetch} /> : !cvs.data?.length ? (
            <EmptyState title="No CVs yet" hint="Complete your profile first, then generate your first CV." />
          ) : (
            <ul className="divide-y">{cvs.data.map((c) => (
              <li key={c.id} className="space-y-2 px-5 py-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div><p className="font-medium">{c.title}</p><p className="text-xs text-slate-500">Version {c.version} · {c.category} · {c.method}</p></div>
                  <div className="flex gap-2">
                    <a href={downloadUrl(`/cvs/${c.id}/download/pdf`)} download><Button size="sm" variant="secondary"><Download className="h-4 w-4" aria-hidden /> PDF<span className="sr-only"> for {c.title}</span></Button></a>
                    <a href={downloadUrl(`/cvs/${c.id}/download/docx`)} download><Button size="sm" variant="secondary"><Download className="h-4 w-4" aria-hidden /> DOCX<span className="sr-only"> for {c.title}</span></Button></a>
                    <Button size="sm" variant="ghost" aria-label={`Delete ${c.title}`} onClick={() => setDelCv(c)}><Trash2 className="h-4 w-4" /></Button>
                  </div>
                </div>
                {c.ats_keywords.length > 0 && <p className="text-xs"><span className="text-slate-500">ATS keywords matched: </span>{c.ats_keywords.map((k) => <Badge key={k} tone="green" className="mr-1">{k}</Badge>)}</p>}
                {c.warnings.map((w, i) => <Notice key={i} tone="warn">{w}</Notice>)}
              </li>))}</ul>
          )}
        </Card>
        <Card>
          <CardHeader title="Uploaded documents" description="Your own CV files (PDF or DOCX, up to 10 MB). Stored only on this computer."
            action={<><input ref={file} type="file" accept=".pdf,.docx" className="sr-only" aria-label="Upload document" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = ""; }} />
              <Button size="sm" variant="secondary" loading={upload.isPending} onClick={() => file.current?.click()}><Upload className="h-4 w-4" aria-hidden /> Upload</Button></>} />
          {docs.isLoading ? <Spinner /> : !docs.data?.length ? <EmptyState title="No uploaded documents" /> : (
            <ul className="divide-y">{docs.data.map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
                <span className="flex items-center gap-2"><FileText className="h-4 w-4 text-slate-400" aria-hidden />{d.filename} <span className="text-slate-400">({Math.round(d.size / 1024)} KB)</span></span>
                <span className="flex gap-1"><a href={downloadUrl(`/documents/${d.id}/download`)} download><Button size="sm" variant="ghost">Download</Button></a>
                  <Button size="sm" variant="ghost" aria-label={`Delete ${d.filename}`} onClick={() => delDoc.mutate(d.id)}><Trash2 className="h-4 w-4" /></Button></span></li>))}</ul>
          )}
        </Card>
      </div>
      <ConfirmDialog open={!!delCv} danger title="Delete this CV version?" confirmLabel="Delete" loading={delCvM.isPending}
        description="The PDF and DOCX files for this version are removed." onConfirm={() => delCv && delCvM.mutate(delCv.id)} onCancel={() => setDelCv(null)} />
    </>
  );
}
