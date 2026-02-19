import { useEffect, useRef } from "react";

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  pending?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmDialog({
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  pending = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Focus cancel button on mount + Escape key + focus trap
  useEffect(() => {
    cancelRef.current?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onCancel]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div ref={dialogRef} className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl animate-fade-in-scale">
        <div className="flex gap-3">
          {destructive && (
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100">
              <svg className="h-5 w-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
          )}
          <div>
            <h3 id="confirm-title" className="text-lg font-semibold text-gray-900">{title}</h3>
            <p className="mt-1 text-sm text-gray-500">{message}</p>
          </div>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button
            ref={cancelRef}
            onClick={onCancel}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={pending}
            className={
              destructive
                ? "rounded bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700 disabled:opacity-50"
                : "rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            }
          >
            {pending ? "..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
