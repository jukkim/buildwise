import { useState, useEffect, useCallback } from "react";
import clsx from "clsx";

interface ToastMessage {
  id: number;
  text: string;
  type: "error" | "success" | "info";
}

let addToastFn: ((text: string, type?: "error" | "success" | "info") => void) | null = null;

export function showToast(text: string, type: "error" | "success" | "info" = "error") {
  addToastFn?.(text, type);
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  let nextId = 0;

  const addToast = useCallback((text: string, type: "error" | "success" | "info" = "error") => {
    const id = ++nextId;
    setToasts((prev) => [...prev, { id, text, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  }, []);

  useEffect(() => {
    addToastFn = addToast;
    return () => { addToastFn = null; };
  }, [addToast]);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={clsx(
            "flex items-center rounded-lg px-4 py-3 text-sm shadow-lg max-w-sm animate-slide-up",
            t.type === "error" && "bg-red-600 text-white",
            t.type === "success" && "bg-green-600 text-white",
            t.type === "info" && "bg-blue-600 text-white",
          )}
        >
          <span>{t.text}</span>
          <button
            onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
            className="ml-3 opacity-70 hover:opacity-100 shrink-0"
            aria-label="Dismiss"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
