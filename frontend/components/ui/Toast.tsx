"use client";

import { useAppStore } from "@/store/useAppStore";
import type { Toast as IToast } from "@/types";

function ToastItem({ toast }: { toast: IToast }) {
  const removeToast = useAppStore((s) => s.removeToast);
  return (
    <div
      className={`toast toast-${toast.type} fade-in`}
      onClick={() => removeToast(toast.id)}
      role="alert"
    >
      {toast.message}
    </div>
  );
}

export default function ToastContainer() {
  const toasts = useAppStore((s) => s.toasts);
  return (
    <div className="toast-container">
      {toasts.map((t) => <ToastItem key={t.id} toast={t} />)}
    </div>
  );
}
