export const fmtDate = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "—";

export const fmtDateTime = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—";

export const statusLabel = (s: string) => s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

export const scoreTone = (score: number) =>
  score >= 70 ? "green" : score >= 45 ? "amber" : "red";
