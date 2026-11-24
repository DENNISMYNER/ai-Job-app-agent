import { Loader2 } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/utils/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";
const styles: Record<Variant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-600/50",
  secondary: "border border-slate-300 bg-white text-slate-800 hover:bg-slate-100 disabled:opacity-50",
  ghost: "text-slate-700 hover:bg-slate-200/60 disabled:opacity-50",
  danger: "bg-red-600 text-white hover:bg-red-700 disabled:bg-red-600/50",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant; size?: "sm" | "md"; loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", loading, disabled, children, type = "button", ...rest }, ref) => (
    <button ref={ref} type={type} disabled={disabled || loading} aria-busy={loading || undefined}
      className={cn("inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed",
        size === "sm" ? "px-2.5 py-1 text-sm" : "px-4 py-2 text-sm", styles[variant], className)} {...rest}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  ),
);
Button.displayName = "Button";
