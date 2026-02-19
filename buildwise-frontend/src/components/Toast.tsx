import { useState, useEffect, useCallback, useRef } from "react";
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
  const nextIdRef = useRef(0);

  const addToast = useCallback((text: string, type: "error" | "success" | "info" = "error") => {
    const id = ++nextIdRef.current;
    setToasts((prev) => {
      const next = [...prev, { id, text, type }];
      // Keep max 3 toasts — remove oldest if exceeded
      return next.length > 3 ? next.slice(-3) : next;
    });
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
          {t.type === "success" && (
            <svg className="mr-2 h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          )}
          {t.type === "error" && (
            <svg className="mr-2 h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
          {t.type === "info" && (
            <svg className="mr-2 h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
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
