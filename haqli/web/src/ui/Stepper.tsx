import { Check } from "lucide-react";

export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <div className="flex items-center gap-1.5" role="list" aria-label="Progress">
      {steps.map((label, idx) => {
        const done = idx < current;
        const active = idx === current;
        return (
          <div key={label} className="flex flex-1 flex-col gap-1" role="listitem">
            <div
              className="h-1.5 w-full rounded-full transition-colors"
              style={{
                backgroundColor: done || active ? "var(--primary)" : "var(--surface-2)",
              }}
            />
            <div className="flex items-center gap-1 text-[11px] font-medium truncate">
              {done && <Check className="h-3 w-3 shrink-0" style={{ color: "var(--primary)" }} />}
              <span
                className="truncate"
                style={{ color: active || done ? "var(--text)" : "var(--text-muted)" }}
              >
                {label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
