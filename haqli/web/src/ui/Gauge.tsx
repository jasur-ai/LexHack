/**
 * Hand-built accessible radial gauge (`role="meter"`) for Case Strength & Contract Safety (§8.2).
 */
export function Gauge({
  value,
  label,
  size = 112,
}: {
  value: number;
  label: string;
  size?: number;
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  const stroke = 10;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (clamped / 100) * circumference;

  const color =
    clamped >= 75 ? "var(--success)" : clamped >= 45 ? "var(--warning)" : "var(--danger)";

  return (
    <div
      className="flex flex-col items-center justify-center"
      role="meter"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--surface-2)"
            strokeWidth={stroke}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 450ms ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono-tabular text-2xl font-bold" style={{ color }}>
            {clamped}
          </span>
          <span className="text-[11px] font-medium" style={{ color: "var(--text-muted)" }}>
            / 100
          </span>
        </div>
      </div>
      <span className="mt-1.5 text-xs font-semibold text-center" style={{ color: "var(--text-muted)" }}>
        {label}
      </span>
    </div>
  );
}
