import { Camera, Mic, QrCode, Receipt, ScanLine } from "lucide-react";
import { useTranslation } from "react-i18next";
import { haptics } from "../../tma/sdk";

export type RecTabMode = "document" | "receipt" | "id_mrz" | "voice" | "verify";

const TABS: Array<{ id: RecTabMode; Icon: typeof Camera; labelKey: string }> = [
  { id: "document", Icon: Camera, labelKey: "recognition.modes.document" },
  { id: "receipt", Icon: Receipt, labelKey: "recognition.modes.receipt" },
  { id: "id_mrz", Icon: ScanLine, labelKey: "recognition.modes.id_mrz" },
  { id: "voice", Icon: Mic, labelKey: "recognition.modes.voice" },
  { id: "verify", Icon: QrCode, labelKey: "recognition.modes.verify" },
];

export function ModeTabs({
  active,
  onChange,
}: {
  active: RecTabMode;
  onChange: (next: RecTabMode) => void;
}) {
  const { t } = useTranslation();

  return (
    <div
      role="tablist"
      aria-label={t("recognition.title")}
      style={{ backgroundColor: "var(--surface-2)" }}
      className="grid grid-cols-5 gap-1 rounded-2xl p-1"
    >
      {TABS.map(({ id, Icon, labelKey }) => {
        const isSelected = active === id;
        return (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={isSelected}
            onClick={() => {
              haptics.selection();
              onChange(id);
            }}
            style={{
              backgroundColor: isSelected ? "var(--surface)" : "transparent",
              color: isSelected ? "var(--primary)" : "var(--text-muted)",
            }}
            className="flex min-h-[48px] flex-col items-center justify-center gap-0.5 rounded-xl px-1 text-[10px] font-bold transition-colors cursor-pointer"
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span className="truncate max-w-full">{t(labelKey)}</span>
          </button>
        );
      })}
    </div>
  );
}
