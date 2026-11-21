/**
 * Locale-aware currency, BHM ratio, and date formatting utilities (§8.3).
 * Uses narrow no-break space (\u202F) grouping for UZS amounts.
 */
import type { LangCode } from "./store";

export function formatUzs(value: number | string | null | undefined, lang: LangCode = "uz_lat"): string {
  const num = Number(value ?? 0);
  if (!Number.isFinite(num)) return "0";
  const rounded = Math.round(num);
  const grouped = String(rounded).replace(/\B(?=(\d{3})+(?!\d))/g, "\u202F");
  const suffix = lang === "ru" ? "сум" : lang === "uz_cyr" ? "сўм" : "so'm";
  return `${grouped} ${suffix}`;
}

export function formatNumber(value: number | string): string {
  const num = Number(value);
  if (!Number.isFinite(num)) return "0";
  return String(Math.round(num)).replace(/\B(?=(\d{3})+(?!\d))/g, "\u202F");
}

export function formatDateLocalized(iso: string | null | undefined, lang: LangCode = "uz_lat"): string {
  if (!iso) return "—";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return iso;
  const d = String(dt.getDate()).padStart(2, "0");
  const m = String(dt.getMonth() + 1).padStart(2, "0");
  const y = dt.getFullYear();
  if (lang === "ru") {
    return `${d}.${m}.${y}`;
  }
  return `${d}.${m}.${y}`;
}

export function computeBhmRatio(amountUzs: number, bhmUzs: number): number {
  if (!bhmUzs || bhmUzs <= 0 || !Number.isFinite(amountUzs)) return 0;
  return Math.round((amountUzs / bhmUzs) * 100) / 100;
}
