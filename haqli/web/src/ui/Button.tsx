import React from "react";
import { haptics } from "../tma/sdk";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  fullWidth?: boolean;
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  fullWidth = false,
  className = "",
  disabled,
  onClick,
  children,
  ...rest
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 font-semibold rounded-xl transition-all duration-150 select-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]";
  const sizes = {
    sm: "min-h-[36px] px-3 text-sm",
    md: "min-h-[44px] px-4 text-[15px]",
    lg: "min-h-[48px] px-5 text-base",
  }[size];

  const styles: Record<NonNullable<ButtonProps["variant"]>, React.CSSProperties> = {
    primary: { backgroundColor: "var(--primary)", color: "#FFFFFF" },
    secondary: {
      backgroundColor: "var(--surface-2)",
      color: "var(--text)",
      border: "1px solid var(--border)",
    },
    ghost: { backgroundColor: "transparent", color: "var(--text-muted)" },
    danger: { backgroundColor: "var(--danger)", color: "#FFFFFF" },
  };

  return (
    <button
      type={rest.type ?? "button"}
      disabled={disabled || loading}
      style={styles[variant]}
      className={`${base} ${sizes} ${fullWidth ? "w-full" : ""} ${className}`}
      onClick={(e) => {
        haptics.impact("light");
        onClick?.(e);
      }}
      {...rest}
    >
      {loading && (
        <span
          className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
          aria-hidden="true"
        />
      )}
      {children}
    </button>
  );
}
