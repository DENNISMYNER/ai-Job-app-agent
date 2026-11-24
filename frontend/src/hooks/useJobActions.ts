import { useNavigate } from "react-router-dom";
import { useAction } from "@/hooks/useApi";
import { api } from "@/services/api";
import type { Application, Job } from "@/types/api";

/** Shared actions for a job row/card: add to tracker, start an application, dismiss. */
export function useJobActions() {
  const nav = useNavigate();
  const track = useAction((job: Job) => api.post<Application>("/applications", { listing_id: job.id, status: "shortlisted" }), {
    success: "Added to your tracker as Shortlisted", invalidate: [["applications"], ["dashboard"]],
  });
  const prepare = useAction((job: Job) => api.post<Application>("/applications", { listing_id: job.id, status: "preparing" }), {
    success: "Application created. Opening the Application Assistant…", invalidate: [["applications"], ["dashboard"]],
    onSuccess: (a) => nav(`/assistant?app=${a.id}`),
  });
  const dismiss = useAction((job: Job) => api.post(`/jobs/${job.id}/dismiss`), { success: "Job dismissed", invalidate: [["jobs"]] });
  return { track, prepare, dismiss };
}
