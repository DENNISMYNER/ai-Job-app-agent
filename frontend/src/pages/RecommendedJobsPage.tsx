import { useState } from "react";
import { Link } from "react-router-dom";
import { JobCard } from "@/components/JobCard";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Form";
import { PageHeader } from "@/components/ui/Page";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/States";
import { useAction, useGet } from "@/hooks/useApi";
import { api, qs } from "@/services/api";
import type { Job, Page } from "@/types/api";

export default function RecommendedJobsPage() {
  const [page, setPage] = useState(1);
  const [min, setMin] = useState("45");
  const { data, isLoading, error, refetch } = useGet<Page<Job>>(["jobs", "recommended", page, min], `/jobs/recommended${qs({ page, page_size: 10, min_score: min })}`);
  const rematch = useAction(() => api.post<{ matched: number }>("/matching/run"), { success: (r) => `Re-scored ${r.matched} jobs`, invalidate: [["jobs"], ["dashboard"]] });
  return (
    <>
      <PageHeader title="Recommended Jobs" description="Jobs ranked by how well they fit your profile. Scores are computed from your real skills and experience, with an explanation for each."
        actions={<Button variant="secondary" loading={rematch.isPending} onClick={() => rematch.mutate()}>Re-score all jobs</Button>} />
      <div className="mb-4 max-w-xs"><Select label="Minimum score" value={min} onChange={(e) => { setMin(e.target.value); setPage(1); }}>
        <option value="70">70+ (strong matches)</option><option value="45">45+ (worth considering)</option><option value="0">All scored jobs</option></Select></div>
      {isLoading ? <Spinner /> : error ? <ErrorState error={error} onRetry={refetch} /> : !data?.items.length ? (
        <EmptyState title="No recommended jobs yet" hint="Complete your profile and add a job source or import a job — matches appear here automatically."
          action={<div className="flex gap-2"><Link to="/profile"><Button variant="secondary" size="sm">Edit profile</Button></Link><Link to="/discovery"><Button size="sm">Find jobs</Button></Link></div>} />
      ) : (
        <>
          <div className="space-y-4">{data.items.map((j) => <JobCard key={j.id} job={j} detailed />)}</div>
          <Pagination page={page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
    </>
  );
}
