import React from "react";
import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";

interface ChipProps {
  tone?: "neutral" | "primary" | "success" | "warning" | "danger" | "info";
  children: React.ReactNode;
  className?: string;
}

const TONE_MAP: Record<NonNullable<ChipProps["tone"]>, React.CSSProperties> = {
  neutral: { backgroundColor: "var(--surface-2)", color: "var(--text-muted)" },
  primary: { backgroundColor: "var(--primary-soft)", color: "var(--primary)" },
  success: { backgroundColor: "var(--success-soft)", color: "var(--success)" },
  warning: { backgroundColor: "var(--warning-soft)", color: "var(--warning)" },
  danger: { backgroundColor: "var(--danger-soft)", color: "var(--danger)" },
  info: { backgroundColor: "var(--info-soft)", color: "var(--info)" },
};

export function Chip({ tone = "neutral", children, className = "" }: ChipProps) {
  return (
    <span
      style={TONE_MAP[tone]}
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${className}`}
    >
      {children}
    </span>
  );
}

/** Rule 3 chip shown on any output referencing unverified legal_data entries. */
export function NeedsReviewChip({ className = "" }: { className?: string }) {
  const { t } = useTranslation();
  return (
    <Chip tone="warning" className={className}>
      <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
      <span>{t("common.needsReview")}</span>
    </Chip>
  );
}
