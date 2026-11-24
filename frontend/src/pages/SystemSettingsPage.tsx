import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input, Textarea } from "@/components/ui/Form";
import { PageHeader } from "@/components/ui/Page";
import { EmptyState, Notice, Spinner } from "@/components/ui/States";
import { useAction, useGet } from "@/hooks/useApi";
import { api } from "@/services/api";
import type { EmailDraft } from "@/types/api";

interface EmailCfg { imap_host?: string; imap_port?: number; smtp_host?: string; smtp_port?: number; username?: string; from_address?: string; has_password?: boolean }

function EmailSettings() {
  const cfg = useGet<EmailCfg>(["email-config"], "/email/config");
  const drafts = useGet<EmailDraft[]>(["email-drafts"], "/email/drafts");
  const [f, setF] = useState<EmailCfg & { password: string }>({ imap_host: "", imap_port: 993, smtp_host: "", smtp_port: 465, username: "", from_address: "", password: "" });
  const [loaded, setLoaded] = useState(false);
  if (cfg.data && !loaded) { setF({ imap_host: cfg.data.imap_host ?? "", imap_port: cfg.data.imap_port ?? 993, smtp_host: cfg.data.smtp_host ?? "", smtp_port: cfg.data.smtp_port ?? 465, username: cfg.data.username ?? "", from_address: cfg.data.from_address ?? "", password: "" }); setLoaded(true); }
  const [sendDraft, setSendDraft] = useState<EmailDraft | null>(null); const [edit, setEdit] = useState<Record<number, string>>({});
  const save = useAction(() => api.put("/email/config", f), { success: "Email settings saved (password stored encrypted)", invalidate: [["email-config"]], onSuccess: () => setF((p) => ({ ...p, password: "" })) });
  const wipe = useAction(() => api.del("/email/config"), { success: "Email settings deleted", invalidate: [["email-config"]], onSuccess: () => setLoaded(false) });
  const poll = useAction(() => api.post<{ found: { label: string }[] }>("/email/poll"), { success: (r) => `${r.found.length} job-related email(s) found`, invalidate: [["notifications"]] });
  const approve = useAction((d: EmailDraft) => api.post(`/email/drafts/${d.id}/approve`, edit[d.id] !== undefined ? { body: edit[d.id] } : {}), { success: "Approved — ready to send", invalidate: [["email-drafts"]] });
  const send = useAction((d: EmailDraft) => api.post<EmailDraft>(`/email/drafts/${d.id}/send`), { invalidate: [["email-drafts"]], success: (d) => d.status === "sent" ? "Email sent" : `Sending failed: ${d.error}`, onSuccess: () => setSendDraft(null) });
  const del = useAction((id: number) => api.del(`/email/drafts/${id}`), { invalidate: [["email-drafts"]] });
  return (
    <Card>
      <CardHeader title="Email assistant (optional)" description="Standard IMAP/SMTP. Detects interview, rejection and recruiter emails. The inbox is opened read-only. Nothing is sent without your approval." />
      <CardBody className="space-y-5">
        <form className="grid gap-3 sm:grid-cols-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
          <Input label="IMAP host" value={f.imap_host} onChange={(e) => setF({ ...f, imap_host: e.target.value })} placeholder="imap.gmail.com" />
          <Input label="SMTP host" value={f.smtp_host} onChange={(e) => setF({ ...f, smtp_host: e.target.value })} placeholder="smtp.gmail.com" />
          <Input label="From address" value={f.from_address} onChange={(e) => setF({ ...f, from_address: e.target.value })} />
          <Input label="Username" value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} autoComplete="off" />
          <Input label="Password / app password" type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} autoComplete="new-password" hint={cfg.data?.has_password ? "A password is stored (encrypted). Leave blank to keep it." : "Stored encrypted, never shown again."} />
          <div className="flex items-end gap-2"><Button type="submit" loading={save.isPending}>Save</Button>
            <Button variant="secondary" loading={poll.isPending} disabled={!cfg.data?.imap_host} onClick={() => poll.mutate()}>Check inbox</Button>
            <Button variant="ghost" disabled={!cfg.data?.username} onClick={() => wipe.mutate()}>Remove</Button></div></form>
        <div><h3 className="mb-2 text-sm font-semibold">Email drafts</h3>
          {drafts.isLoading ? <Spinner /> : !drafts.data?.length ? <EmptyState title="No drafts" hint="Create a follow-up draft from the Application Tracker." /> : (
            <ul className="space-y-3">{drafts.data.map((d) => (
              <li key={d.id} className="space-y-2 rounded-lg border p-3 text-sm">
                <div className="flex items-center justify-between"><p className="font-medium">{d.subject} <Badge tone={d.status === "sent" ? "green" : d.status === "failed" ? "red" : d.status === "approved" ? "blue" : "gray"}>{d.status}</Badge></p>
                  <Button size="sm" variant="ghost" onClick={() => del.mutate(d.id)}>Delete</Button></div>
                <p className="text-slate-500">To: {d.to_address || "(add a recipient)"}</p>
                {d.status === "draft" ? <Textarea label="Message" rows={5} defaultValue={d.body} onChange={(e) => setEdit({ ...edit, [d.id]: e.target.value })} /> : <p className="whitespace-pre-line text-slate-700">{d.body}</p>}
                {d.error && <p role="alert" className="text-red-600">Failed: {d.error}</p>}
                <div className="flex gap-2">{d.status === "draft" && <Button size="sm" variant="secondary" loading={approve.isPending} onClick={() => approve.mutate(d)}>Approve</Button>}
                  {(d.status === "approved" || d.status === "failed") && <Button size="sm" onClick={() => setSendDraft(d)}>Send…</Button>}</div></li>))}</ul>)}</div>
      </CardBody>
      <ConfirmDialog open={!!sendDraft} title="Send this email?" confirmLabel="Send email" loading={send.isPending} description={<>To <b>{sendDraft?.to_address}</b>: “{sendDraft?.subject}”</>} onConfirm={() => sendDraft && send.mutate(sendDraft)} onCancel={() => setSendDraft(null)} />
    </Card>
  );
}

function Privacy() {
  const sys = useGet<{ retention_days: number }>(["settings", "system"], "/settings/system");
  const [open, setOpen] = useState(false); const [typed, setTyped] = useState("");
  const retention = useAction((n: number) => api.put("/settings/system", { retention_days: n }), { success: "Retention saved", invalidate: [["settings", "system"]] });
  const purge = useAction(() => api.post<{ removed: Record<string, number> }>("/data/apply-retention"), { success: (r) => `Cleanup done (${Object.values(r.removed).reduce((a, b) => a + b, 0)} items removed)` });
  const exp = useAction(async () => {
    const data = await api.get<unknown>("/data/export");
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const a = document.createElement("a"); a.href = url; a.download = "job-agent-export.json"; a.click(); URL.revokeObjectURL(url);
  }, { success: "Export downloaded" });
  const wipe = useAction(() => api.post("/data/delete-all", { confirm: typed }), { success: "All personal data deleted", invalidate: [["profile"], ["dashboard"], ["applications"], ["jobs"], ["cvs"], ["letters"], ["documents"], ["answers"]], onSuccess: () => { setOpen(false); setTyped(""); } });
  return (
    <Card>
      <CardHeader title="Your data & privacy" description="Everything is stored locally on this computer. Email passwords are encrypted. Logs mask emails and phone numbers." />
      <CardBody className="space-y-5">
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-60"><Input label="Delete old logs & notifications after (days)" inputMode="numeric" defaultValue={sys.data?.retention_days ?? 0} key={sys.data?.retention_days} hint="0 = keep forever" onBlur={(e) => retention.mutate(Math.max(0, Number(e.target.value) || 0))} /></div>
          <Button variant="secondary" loading={purge.isPending} onClick={() => purge.mutate()}>Clean up now</Button></div>
        <div className="flex flex-wrap gap-3"><Button variant="secondary" loading={exp.isPending} onClick={() => exp.mutate()}>Export my data (JSON)</Button>
          <Button variant="danger" onClick={() => setOpen(true)}>Delete all my data…</Button></div>
        <Notice tone="info">Deleting removes your profile, CVs, letters, applications, answers, uploaded files and email settings from this computer.</Notice>
      </CardBody>
      <ConfirmDialog open={open} danger title="Delete ALL personal data?" confirmLabel="Delete everything" loading={wipe.isPending}
        description={<><p>This cannot be undone. Consider exporting first. Type <b>DELETE</b> to confirm.</p><input aria-label="Type DELETE to confirm" className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2" value={typed} onChange={(e) => setTyped(e.target.value)} /></>}
        onConfirm={() => typed === "DELETE" && wipe.mutate()} onCancel={() => { setOpen(false); setTyped(""); }} />
    </Card>
  );
}

export default function SystemSettingsPage() {
  return (<><PageHeader title="System Settings" description="Email, privacy, data export and deletion." /><div className="space-y-6"><Privacy /><EmailSettings /></div></>);
}
