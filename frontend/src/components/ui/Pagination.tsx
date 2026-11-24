import { Button } from "./Button";

export const Pagination = ({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) => {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return <p className="px-1 text-xs text-slate-500">{total} result{total === 1 ? "" : "s"}</p>;
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3 pt-3">
      <p className="text-xs text-slate-500">Page {page} of {pages} · {total} results</p>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</Button>
        <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</Button>
      </div>
    </nav>
  );
};
