import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "@/utils/cn";

const base = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm placeholder:text-slate-400 disabled:bg-slate-100";

export const Field = ({ label, error, hint, children, htmlFor }: { label: string; error?: string; hint?: string; children: ReactNode; htmlFor?: string }) => (
  <div className="space-y-1">
    <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-700">{label}</label>
    {children}
    {hint && !error && <p className="text-xs text-slate-500">{hint}</p>}
    {error && <p role="alert" className="text-xs text-red-600">{error}</p>}
  </div>
);

interface FProps { label: string; error?: string; hint?: string }

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & FProps>(
  ({ label, error, hint, className, id, ...rest }, ref) => {
    const auto = useId(); const fid = id ?? auto;
    return (
      <Field label={label} error={error} hint={hint} htmlFor={fid}>
        <input ref={ref} id={fid} aria-invalid={!!error} className={cn(base, error && "border-red-400", className)} {...rest} />
      </Field>
    );
  });
Input.displayName = "Input";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & FProps>(
  ({ label, error, hint, className, id, rows = 4, ...rest }, ref) => {
    const auto = useId(); const fid = id ?? auto;
    return (
      <Field label={label} error={error} hint={hint} htmlFor={fid}>
        <textarea ref={ref} id={fid} rows={rows} aria-invalid={!!error} className={cn(base, error && "border-red-400", className)} {...rest} />
      </Field>
    );
  });
Textarea.displayName = "Textarea";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement> & FProps>(
  ({ label, error, hint, className, id, children, ...rest }, ref) => {
    const auto = useId(); const fid = id ?? auto;
    return (
      <Field label={label} error={error} hint={hint} htmlFor={fid}>
        <select ref={ref} id={fid} className={cn(base, className)} {...rest}>{children}</select>
      </Field>
    );
  });
Select.displayName = "Select";
