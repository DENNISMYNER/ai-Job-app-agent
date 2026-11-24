import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Input } from "@/components/ui/Form";
import { PageHeader } from "@/components/ui/Page";
import { Notice, Spinner } from "@/components/ui/States";
import { useAction, useGet } from "@/hooks/useApi";
import { api } from "@/services/api";
import type { AIStatus, MatchingSettings } from "@/types/api";

const WEIGHT_LABELS: Record<string, string> = { skills: "Skills", experience: "Experience", location: "Location", title: "Job title" };

export default function AISettingsPage() {
  const status = useGet<AIStatus>(["ai-status"], "/ai/status");
  const ai = useGet<{ enabled: boolean; model: string | null; embedding_model: string | null; use_embeddings: boolean }>(["settings", "ai"], "/settings/ai");
  const match = useGet<MatchingSettings>(["settings", "matching"], "/settings/matching");
  const [a, setA] = useState({ enabled: true, model: "", embedding_model: "", use_embeddings: true });
  const [m, setM] = useState<{ min_apply_score: string; min_consider_score: string; weights: Record<string, number>; target_titles: string; excluded_keywords: string } | null>(null);
  useEffect(() => { if (ai.data) setA({ enabled: ai.data.enabled, model: ai.data.model ?? "", embedding_model: ai.data.embedding_model ?? "", use_embeddings: ai.data.use_embeddings }); }, [ai.data]);
  useEffect(() => { if (match.data) setM({ min_apply_score: String(match.data.min_apply_score), min_consider_score: String(match.data.min_consider_score), weights: match.data.weights, target_titles: match.data.target_titles.join(", "), excluded_keywords: match.data.excluded_keywords.join(", ") }); }, [match.data]);
  const saveAi = useAction(() => api.put("/settings/ai", { enabled: a.enabled, model: a.model || null, embedding_model: a.embedding_model || null, use_embeddings: a.use_embeddings }), { success: "AI settings saved", invalidate: [["settings", "ai"], ["ai-status"]] });
  const saveM = useAction(() => api.put("/settings/matching", { min_apply_score: Number(m!.min_apply_score), min_consider_score: Number(m!.min_consider_score), weights: m!.weights,
    target_titles: m!.target_titles.split(",").map((s) => s.trim()).filter(Boolean), excluded_keywords: m!.excluded_keywords.split(",").map((s) => s.trim()).filter(Boolean) }), { success: "Matching preferences saved — press “Re-score” on Recommended Jobs to apply them", invalidate: [["settings", "matching"]] });
  const s = status.data;
  return (
    <>
      <PageHeader title="AI Settings" description="Everything runs on your computer through Ollama. No paid AI service or API key is ever needed." />
      <div className="space-y-6">
        <Card><CardHeader title="Local AI engine (Ollama)" action={<Button size="sm" variant="secondary" loading={status.isFetching} onClick={() => status.refetch()}>Re-check</Button>} />
          <CardBody className="space-y-3">
            {status.isLoading ? <Spinner /> : s && (<>
              <p className="text-sm">Ollama: {s.reachable ? <Badge tone="green">running</Badge> : <Badge tone="red">not reachable</Badge>} · Chat model <code>{s.chat_model}</code>: {s.chat_model_installed ? <Badge tone="green">installed</Badge> : <Badge tone="amber">not installed</Badge>} · Embedding model <code>{s.embedding_model}</code>: {s.embedding_model_installed ? <Badge tone="green">installed</Badge> : <Badge tone="amber">not installed</Badge>}</p>
              {!s.reachable && <Notice tone="warn">{s.message} <br />The app keeps working without AI: scoring, CVs and answers fall back to deterministic templates.</Notice>}
              {s.reachable && !s.chat_model_installed && <Notice tone="warn">{s.message}</Notice>}
              {s.models.length > 0 && <p className="text-xs text-slate-500">Installed models: {s.models.join(", ")}</p>}</>)}
            <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); saveAi.mutate(); }}>
              <Input label="Chat model" value={a.model} onChange={(e) => setA({ ...a, model: e.target.value })} placeholder="qwen3:4b (default)" hint="Any instruction-tuned model you have pulled, e.g. llama3.2:3b" />
              <Input label="Embedding model" value={a.embedding_model} onChange={(e) => setA({ ...a, embedding_model: e.target.value })} placeholder="nomic-embed-text (default)" />
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={a.enabled} onChange={(e) => setA({ ...a, enabled: e.target.checked })} /> Enable AI features</label>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={a.use_embeddings} onChange={(e) => setA({ ...a, use_embeddings: e.target.checked })} /> Use semantic matching (embeddings)</label>
              <div><Button type="submit" loading={saveAi.isPending}>Save AI settings</Button></div></form>
          </CardBody></Card>
        <Card><CardHeader title="Matching preferences" description="Scores are always computed from structured data, so a job ad cannot talk its way to a higher score." />
          <CardBody>{!m ? <Spinner /> : (
            <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); saveM.mutate(); }}>
              <div className="grid gap-3 sm:grid-cols-2">
                <Input label="“Apply” threshold (score ≥)" inputMode="numeric" value={m.min_apply_score} onChange={(e) => setM({ ...m, min_apply_score: e.target.value })} />
                <Input label="“Consider” threshold (score ≥)" inputMode="numeric" value={m.min_consider_score} onChange={(e) => setM({ ...m, min_consider_score: e.target.value })} /></div>
              <fieldset><legend className="mb-1 text-sm font-medium">Importance of each factor</legend>
                <div className="grid gap-3 sm:grid-cols-4">{Object.keys(WEIGHT_LABELS).map((k) => (
                  <label key={k} className="text-sm">{WEIGHT_LABELS[k]}: <b>{Math.round(m.weights[k] * 100)}%</b>
                    <input type="range" min={0} max={100} value={Math.round(m.weights[k] * 100)} aria-label={`${WEIGHT_LABELS[k]} weight`} className="w-full" onChange={(e) => setM({ ...m, weights: { ...m.weights, [k]: Number(e.target.value) / 100 } })} /></label>))}</div>
                <p className="text-xs text-slate-500">Weights are normalised automatically.</p></fieldset>
              <Input label="Target job titles" value={m.target_titles} onChange={(e) => setM({ ...m, target_titles: e.target.value })} hint="Comma-separated, e.g. junior developer, support engineer" />
              <Input label="Exclude jobs containing" value={m.excluded_keywords} onChange={(e) => setM({ ...m, excluded_keywords: e.target.value })} hint="Comma-separated, e.g. unpaid, commission only" />
              <Button type="submit" loading={saveM.isPending}>Save matching preferences</Button></form>)}</CardBody></Card>
      </div>
    </>
  );
}
