import { Select } from "@/components/ui/Form";
import { useGet } from "@/hooks/useApi";
import type { Job, Page } from "@/types/api";

export function JobSelect({ value, onChange, label = "Job", allowNone = false }: { value: string; onChange: (v: string) => void; label?: string; allowNone?: boolean }) {
  const { data, isLoading } = useGet<Page<Job>>(["jobs", "picker"], "/jobs?page_size=100&sort=score");
  return (
    <Select label={label} value={value} onChange={(e) => onChange(e.target.value)} disabled={isLoading}>
      <option value="">{allowNone ? "General (not for a specific job)" : isLoading ? "Loading…" : "Choose a job…"}</option>
      {data?.items.map((j) => <option key={j.id} value={j.id}>{j.title} — {j.company}{j.match ? ` (${j.match.score}%)` : ""}</option>)}
    </Select>
  );
}
