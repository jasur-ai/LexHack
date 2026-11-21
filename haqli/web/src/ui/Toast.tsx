import { useEffect } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useAppStore } from "../lib/store";

export function ToastStack() {
  const toasts = useAppStore((s) => s.toasts);
  const dismissToast = useAppStore((s) => s.dismissToast);

  useEffect(() => {
    if (toasts.length === 0) return;
    const timers = toasts.map((t) => setTimeout(() => dismissToast(t.id), 3400));
    return () => timers.forEach(clearTimeout);
  }, [toasts, dismissToast]);

  const bgMap = {
    info: "var(--accent-navy)",
    success: "var(--success)",
    warning: "var(--warning)",
    danger: "var(--danger)",
  };

  return (
    <div className="pointer-events-none fixed inset-x-0 top-16 z-50 flex flex-col items-center gap-2 px-4">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ y: -16, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -16, opacity: 0 }}
            style={{ backgroundColor: bgMap[toast.tone], color: "#FFFFFF" }}
            className="pointer-events-auto max-w-md rounded-xl px-4 py-2.5 text-sm font-medium shadow-lg"
          >
            {toast.message}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
