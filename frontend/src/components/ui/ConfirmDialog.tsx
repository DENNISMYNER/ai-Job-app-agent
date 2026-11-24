import * as Dialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";
import { Button } from "./Button";

interface Props {
  open: boolean; title: string; description: ReactNode; confirmLabel?: string; danger?: boolean; loading?: boolean;
  onConfirm: () => void; onCancel: () => void;
}

/** Accessible modal (focus trap, Esc to close) used for every destructive or irreversible action. */
export const ConfirmDialog = ({ open, title, description, confirmLabel = "Confirm", danger, loading, onConfirm, onCancel }: Props) => (
  <Dialog.Root open={open} onOpenChange={(o) => { if (!o) onCancel(); }}>
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40" />
      <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl bg-white p-6 shadow-xl">
        <Dialog.Title className="text-lg font-semibold">{title}</Dialog.Title>
        <Dialog.Description asChild><div className="mt-2 text-sm text-slate-600">{description}</div></Dialog.Description>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button variant={danger ? "danger" : "primary"} loading={loading} onClick={onConfirm}>{confirmLabel}</Button>
        </div>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
);
