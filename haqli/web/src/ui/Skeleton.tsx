export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return (
    <div
      style={{ backgroundColor: "var(--surface-2)" }}
      className={`animate-pulse rounded-lg ${className}`}
      aria-hidden="true"
    />
  );
}
