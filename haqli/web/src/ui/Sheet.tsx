import React, { useEffect } from "react";
import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";

interface SheetProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

export function Sheet({ open, onClose, title, children }: SheetProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center sm:items-center"
          role="dialog"
          aria-modal="true"
          aria-label={title}
        >
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/45 backdrop-blur-[2px]"
            onClick={onClose}
          />
          <motion.div
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            style={{ backgroundColor: "var(--surface)", borderColor: "var(--border)" }}
            className="relative z-10 max-h-[88vh] w-full max-w-lg overflow-y-auto rounded-t-3xl border p-5 shadow-2xl sm:rounded-2xl"
          >
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-lg font-bold tracking-tight" style={{ color: "var(--text)" }}>
                {title}
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                style={{ backgroundColor: "var(--surface-2)", color: "var(--text-muted)" }}
                className="flex h-9 w-9 items-center justify-center rounded-full cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
