import React from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, Info } from "lucide-react";

interface BannerProps {
  tone?: "info" | "warning" | "danger" | "success";
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export function Banner({ tone = "info", title, children, className = "" }: BannerProps) {
  const styles: Record<NonNullable<BannerProps["tone"]>, { bg: string; color: string; Icon: typeof Info }> = {
    info: { bg: "var(--info-soft)", color: "var(--info)", Icon: Info },
    warning: { bg: "var(--warning-soft)", color: "var(--warning)", Icon: AlertTriangle },
    danger: { bg: "var(--danger-soft)", color: "var(--danger)", Icon: AlertCircle },
    success: { bg: "var(--success-soft)", color: "var(--success)", Icon: CheckCircle2 },
  };
  const cfg = styles[tone];
  const Icon = cfg.Icon;

  return (
    <div
      style={{ backgroundColor: cfg.bg, color: cfg.color }}
      className={`flex items-start gap-2.5 rounded-xl p-3 text-[13px] leading-snug ${className}`}
      role="status"
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 flex-1">
        {title && <div className="font-semibold mb-0.5">{title}</div>}
        <div>{children}</div>
      </div>
    </div>
  );
}
