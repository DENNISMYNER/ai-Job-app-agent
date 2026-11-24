import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/services/api";

export const useGet = <T,>(key: QueryKey, path: string, opts: { enabled?: boolean; refetchInterval?: number } = {}) =>
  useQuery<T>({ queryKey: key, queryFn: () => api.get<T>(path), ...opts });

/** Mutation that toasts success/error and invalidates the given query keys. */
export function useAction<TIn = void, TOut = unknown>(
  fn: (input: TIn) => Promise<TOut>,
  opts: { success?: string | ((out: TOut) => string); invalidate?: QueryKey[]; onSuccess?: (out: TOut) => void } = {},
) {
  const toast = useToast(); const qc = useQueryClient();
  return useMutation<TOut, Error, TIn>({
    mutationFn: fn,
    onSuccess: (out) => {
      if (opts.success) toast.success(typeof opts.success === "function" ? opts.success(out) : opts.success);
      opts.invalidate?.forEach((k) => qc.invalidateQueries({ queryKey: k }));
      opts.onSuccess?.(out);
    },
    onError: (e) => toast.error(e.message),
  });
}
