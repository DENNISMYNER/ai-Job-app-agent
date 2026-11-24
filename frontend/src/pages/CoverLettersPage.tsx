import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { JobSelect } from "@/components/JobSelect";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input, Select, Textarea } from "@/components/ui/Form";
import { PageHeader } from "@/components/ui/Page";
import { EmptyState, Notice, Spinner } from "@/components/ui/States";
import { useAction, useGet } from "@/hooks/useApi";
import { api, downloadUrl } from "@/services/api";
import type { CoverLetter } from "@/types/api";
import { cn } from "@/utils/cn";

export default function CoverLettersPage() {
  const { data, isLoading } = useGet<CoverLetter[]>(["letters"], "/cover-letters");
  const [jobId, setJobId] = useState(""); const [tone, setTone] = useState("professional"); const [guidance, setGuidance] = useState("");
  const [selected, setSelected] = useState<CoverLetter | null>(null); const [text, setText] = useState(""); const [warnings, setWarnings] = useState<string[]>([]);
  const [del, setDel] = useState(false);
  useEffect(() => { setText(selected?.content ?? ""); }, [selected]);
  const gen = useAction(() => api.post<{ letter: CoverLetter; warnings: string[] }>("/cover-letters", { listing_id: Number(jobId), tone, guidance, use_ai: true }),
    { success: "Cover letter generated", invalidate: [["letters"]], onSuccess: (r) => { setSelected(r.letter); setWarnings(r.warnings); } });
  const save = useAction(() => api.put<CoverLetter>(`/cover-letters/${selected!.id}`, { content: text }), { success: "Changes saved", invalidate: [["letters"]], onSuccess: setSelected });
  const remove = useAction(() => api.del(`/cover-letters/${selected!.id}`), { success: "Cover letter deleted", invalidate: [["letters"]], onSuccess: () => { setSelected(null); setDel(false); } });
  const dirty = selected && text !== selected.content;
  return (
    <>
      <PageHeader title="Cover Letters" description="Personalised for each job from your real experience. Edit freely, regenerate, preview and download as PDF." />
      <div className="grid gap-6 lg:grid-cols-[22rem_1fr]">
        <div className="space-y-6">
          <Card><CardHeader title="Generate" /><CardBody className="space-y-3">
            <JobSelect label="For which job?" value={jobId} onChange={setJobId} />
            <Select label="Tone" value={tone} onChange={(e) => setTone(e.target.value)}><option>professional</option><option>friendly</option><option>concise</option><option>enthusiastic</option></Select>
            <Input label="Extra guidance (optional)" value={guidance} onChange={(e) => setGuidance(e.target.value)} placeholder="e.g. mention my open-source work" />
            <Button className="w-full" disabled={!jobId} loading={gen.isPending} onClick={() => gen.mutate()}>{selected ? "Generate new version" : "Generate cover letter"}</Button>
          </CardBody></Card>
          <Card><CardHeader title="Saved letters" />
            {isLoading ? <Spinner /> : !data?.length ? <EmptyState title="No letters yet" /> : (
              <ul className="max-h-80 divide-y overflow-auto">{data.map((l) => (
                <li key={l.id}><button onClick={() => { setSelected(l); setWarnings([]); }} className={cn("w-full px-5 py-3 text-left text-sm hover:bg-slate-50", selected?.id === l.id && "bg-brand-50")}>
                  <span className="block font-medium">{l.title}</span><span className="text-xs text-slate-500">v{l.version} · {l.method}</span></button></li>))}</ul>)}
          </Card>
        </div>
        <Card>
          <CardHeader title={selected ? selected.title : "Preview & edit"} action={selected && (
            <div className="flex gap-2"><a href={downloadUrl(`/cover-letters/${selected.id}/download`)} download><Button size="sm" variant="secondary"><Download className="h-4 w-4" aria-hidden /> PDF</Button></a>
              <Button size="sm" variant="ghost" onClick={() => setDel(true)}>Delete</Button></div>)} />
          <CardBody className="space-y-3">
            {!selected ? <EmptyState title="Select or generate a letter" hint="Letters only mention skills and experience that are in your profile." /> : (<>
              {warnings.map((w, i) => <Notice key={i} tone="warn">{w}</Notice>)}
              <Textarea label="Letter text" rows={18} value={text} onChange={(e) => setText(e.target.value)} />
              <div className="flex items-center justify-between"><span className="text-xs text-slate-500">{text.trim().split(/\s+/).filter(Boolean).length} words</span>
                <Button disabled={!dirty} loading={save.isPending} onClick={() => save.mutate()}>Save changes</Button></div></>)}
          </CardBody>
        </Card>
      </div>
      <ConfirmDialog open={del} danger title="Delete this cover letter?" confirmLabel="Delete" loading={remove.isPending} description="This cannot be undone." onConfirm={() => remove.mutate()} onCancel={() => setDel(false)} />
    </>
  );
}
