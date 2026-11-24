import { CheckCircle2, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

type Kind = "success" | "error";
interface T { id: number; kind: Kind; text: string }
const Ctx = createContext<{ success: (m: string) => void; error: (m: string) => void }>({ success: () => {}, error: () => {} });
export const useToast = () => useContext(Ctx);

export const ToastProvider = ({ children }: { children: ReactNode }) => {
  const [items, setItems] = useState<T[]>([]);
  const push = useCallback((kind: Kind, text: string) => {
    const id = Date.now() + Math.random();
    setItems((s) => [...s, { id, kind, text }]);
    setTimeout(() => setItems((s) => s.filter((x) => x.id !== id)), kind === "error" ? 7000 : 3500);
  }, []);
  const value = useMemo(() => ({ success: (m: string) => push("success", m), error: (m: string) => push("error", m) }), [push]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2">
        {items.map((t) => (
          <div key={t.id} role={t.kind === "error" ? "alert" : "status"}
            className={`pointer-events-auto flex items-start gap-2 rounded-lg border bg-white p-3 text-sm shadow-lg ${t.kind === "error" ? "border-red-200" : "border-emerald-200"}`}>
            {t.kind === "error" ? <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" /> : <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />}
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
};
