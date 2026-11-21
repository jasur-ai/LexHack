/**
 * Prefill routing map from confirmed Recognition Engine `RouteHint` -> Haqli screens (§2, §10).
 */
import type { RecognitionFieldDTO, RouteHintDTO } from "../../lib/api";
import type { NavTab, RecognitionPrefill } from "../../lib/store";

export const CLOSED_DOC_TYPES = [
  "rental_contract",
  "employment_contract",
  "microloan_contract",
  "receipt",
  "fine_decision",
  "demand_letter",
  "tilxat",
  "passport_data_page",
  "unknown",
] as const;

export type ClosedDocType = (typeof CLOSED_DOC_TYPES)[number];

export function mapRouteHintToPrefill(
  routeHint: RouteHintDTO | null | undefined,
  fields: RecognitionFieldDTO[],
  options: { jobId?: string; rawText?: string; docType?: string | null }
): { tab: NavTab; prefill: RecognitionPrefill } {
  const flat: Record<string, string | null> = {};
  for (const f of fields) {
    flat[f.key] = f.value !== null && f.value !== undefined ? String(f.value) : null;
  }
  if (routeHint?.prefill) {
    for (const [k, v] of Object.entries(routeHint.prefill)) {
      if (typeof v === "string" || typeof v === "number") {
        flat[k] = String(v);
      }
    }
  }

  let target: "himoya" | "tilxat" | "scanner" = "himoya";
  let category: RecognitionPrefill["category"] = "consumer";

  const hintTarget = routeHint?.target;
  if (hintTarget === "tilxat" || options.docType === "passport_data_page" || options.docType === "tilxat") {
    target = "tilxat";
  } else if (
    hintTarget === "skaner" ||
    options.docType === "rental_contract" ||
    options.docType === "employment_contract" ||
    options.docType === "microloan_contract"
  ) {
    target = "scanner";
  } else {
    target = "himoya";
    const cat = routeHint?.category;
    if (cat === "labor" || cat === "consumer" || cat === "rental" || cat === "traffic" || cat === "debt") {
      category = cat;
    } else if (options.docType === "fine_decision") {
      category = "traffic";
    } else if (options.docType === "receipt") {
      category = "consumer";
    }
  }

  return {
    tab: target,
    prefill: {
      target,
      category,
      fields: flat,
      rawText: options.rawText,
      jobId: options.jobId,
    },
  };
}

export function getPrimaryActionLabelKey(routeHint: RouteHintDTO | null | undefined, docType?: string | null): string {
  const target = routeHint?.target;
  if (target === "tilxat" || docType === "passport_data_page" || docType === "tilxat") {
    return "rec.cta.tilxat";
  }
  if (
    target === "skaner" ||
    docType === "rental_contract" ||
    docType === "employment_contract" ||
    docType === "microloan_contract"
  ) {
    return "rec.cta.scanner";
  }
  return "rec.cta.himoya";
}
