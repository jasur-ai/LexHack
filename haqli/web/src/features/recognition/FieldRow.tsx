import { Bot, Check, Cpu, ScanText, UserCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { RecognitionFieldDTO } from "../../lib/api";
import { haptics } from "../../tma/sdk";

interface FieldRowProps {
  field: RecognitionFieldDTO;
  value: string;
  confirmed: boolean;
  highlighted?: boolean;
  onChange: (nextValue: string) => void;
  onConfirm: () => void;
  onFocus?: () => void;
}

function getInputMeta(key: string): { type: "text" | "number" | "date"; inputMode?: "decimal" | "numeric" | "text" } {
  const low = key.toLowerCase();
  if (low.includes("date") || low === "dob" || low === "expiry") {
    return { type: "date" };
  }
  if (low.includes("amount") || low.includes("total") || low.includes("uzs")) {
    return { type: "number", inputMode: "decimal" };
  }
  return { type: "text" };
}

export function FieldRow({
  field,
  value,
  confirmed,
  highlighted = false,
  onChange,
  onConfirm,
  onFocus,
}: FieldRowProps) {
  const { t } = useTranslation();
  const mustTouch = field.needsConfirm && !confirmed;
  const confPct = Math.round((confirmed ? 1 : field.confidence) * 100);

  const dotColor =
    confirmed || field.confidence >= 0.9
      ? "var(--success)"
      : field.confidence >= 0.75
        ? "var(--warning)"
        : "var(--danger)";

  const SourceIcon =
    confirmed || field.source === "user"
      ? UserCheck
      : field.source === "llm"
        ? Bot
        : field.source === "ocr"
          ? ScanText
          : Cpu;

  const inputMeta = getInputMeta(field.key);

  return (
    <div
      style={{
        backgroundColor: mustTouch ? "var(--warning-soft)" : "var(--surface)",
        borderColor: highlighted ? "var(--primary)" : mustTouch ? "var(--warning)" : "var(--border)",
      }}
      className="rounded-xl border p-3 transition-colors space-y-1.5"
    >
      <div className="flex items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-1.5 font-semibold min-w-0">
          <span
            className="h-2.5 w-2.5 shrink-0 rounded-full"
            style={{ backgroundColor: dotColor }}
            aria-hidden="true"
          />
          <span className="truncate">{t(`rec.fields.${field.key}`, { defaultValue: field.key })}</span>
          {mustTouch && (
            <span
              style={{ color: "var(--danger)" }}
              className="rounded-md px-1.5 py-0.5 text-[10px] font-bold uppercase"
            >
              {t("rec.checkField")}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 font-mono-tabular shrink-0" style={{ color: "var(--text-muted)" }}>
          <SourceIcon className="h-3.5 w-3.5" aria-label={field.source} />
          <span>{confPct}%</span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <input
          type={inputMeta.type}
          inputMode={inputMeta.inputMode}
          aria-label={field.key}
          value={value}
          onFocus={onFocus}
          onChange={(e) => onChange(e.target.value)}
          className="haqli-input min-h-[44px] flex-1 text-sm"
        />
        {mustTouch && (
          <button
            type="button"
            onClick={() => {
              haptics.impact("light");
              onConfirm();
            }}
            style={{ backgroundColor: "var(--primary)", color: "#FFFFFF" }}
            className="flex h-11 min-w-[44px] items-center justify-center rounded-xl px-3 text-xs font-bold cursor-pointer"
            aria-label={t("rec.confirmField")}
          >
            <Check className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
