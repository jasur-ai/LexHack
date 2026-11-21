import { useMemo, useState } from "react";
import { CheckCircle2, RotateCcw, Trash2, ZoomIn, ZoomOut } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { RecognitionResultDTO } from "../../lib/api";
import { useTelegramMainButton } from "../../tma/sdk";
import { Banner } from "../../ui/Banner";
import { Button } from "../../ui/Button";
import { Chip } from "../../ui/Chip";
import { FieldRow } from "./FieldRow";
import { CLOSED_DOC_TYPES, getPrimaryActionLabelKey } from "./routes";

interface ReviewScreenProps {
  result: RecognitionResultDTO;
  previewImageUrl: string;
  confirming: boolean;
  onConfirm: (edits: Array<{ key: string; value: unknown }>, docType: string | null) => void;
  onRetake: () => void;
  onPurge: () => void;
}

export function ReviewScreen({
  result,
  previewImageUrl,
  confirming,
  onConfirm,
  onRetake,
  onPurge,
}: ReviewScreenProps) {
  const { t } = useTranslation();

  const [docType, setDocType] = useState<string>(result.docType || "unknown");
  const [docTypePickerOpen, setDocTypePickerOpen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [highlightedKey, setHighlightedKey] = useState<string | null>(null);
  const [transcript, setTranscript] = useState(result.transcript || "");

  const [values, setValues] = useState<Record<string, string>>(() => {
    const map: Record<string, string> = {};
    for (const f of result.fields) {
      map[f.key] = f.value !== null && f.value !== undefined ? String(f.value) : f.display || "";
    }
    return map;
  });

  const [touchedConfirmed, setTouchedConfirmed] = useState<Record<string, boolean>>({});

  const pendingConfirmCount = useMemo(
    () => result.fields.filter((f) => f.needsConfirm && !touchedConfirmed[f.key]).length,
    [result.fields, touchedConfirmed]
  );

  const canProceed = pendingConfirmCount === 0 && !confirming;
  const primaryLabel = t(getPrimaryActionLabelKey(result.routeHint, docType));

  const triggerConfirm = () => {
    if (!canProceed) return;
    const edits = result.fields.map((f) => ({ key: f.key, value: values[f.key] ?? f.value }));
    onConfirm(edits, docType);
  };

  useTelegramMainButton({
    text: primaryLabel,
    visible: true,
    disabled: !canProceed,
    onClick: triggerConfirm,
  });

  return (
    <div className="space-y-4">
      {/* Top: Image preview with zoom & colored field highlight chips (§10) */}
      {previewImageUrl && (
        <div
          style={{ borderColor: "var(--border)", backgroundColor: "#0B1120" }}
          className="relative overflow-hidden rounded-2xl border"
        >
          <div className="max-h-52 overflow-auto">
            <img
              src={previewImageUrl}
              alt="Captured document"
              style={{ transform: `scale(${zoom})`, transformOrigin: "top left" }}
              className="w-full object-contain transition-transform"
            />
          </div>
          <div className="absolute right-2 top-2 flex gap-1">
            <button
              type="button"
              onClick={() => setZoom((z) => Math.max(1, Number((z - 0.35).toFixed(2))))}
              className="flex h-9 w-9 items-center justify-center rounded-full bg-black/60 text-white cursor-pointer"
              aria-label="Zoom out"
            >
              <ZoomOut className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => setZoom((z) => Math.min(2.4, Number((z + 0.35).toFixed(2))))}
              className="flex h-9 w-9 items-center justify-center rounded-full bg-black/60 text-white cursor-pointer"
              aria-label="Zoom in"
            >
              <ZoomIn className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Editable Voice Transcript (§7) */}
      {result.kind === "voice" && (
        <div className="space-y-1.5">
          <label className="text-xs font-bold" style={{ color: "var(--text-muted)" }}>
            {t("rec.transcriptLabel")}
          </label>
          <textarea
            rows={3}
            className="haqli-input text-sm"
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
          />
        </div>
      )}

      {/* Doc-Type Chip with Tap-to-Override Closed Set (§5.5, §10) */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setDocTypePickerOpen((v) => !v)}
          className="cursor-pointer"
          aria-label={t("rec.overrideDocType")}
        >
          <Chip tone="primary">
            <span>{t(`rec.docTypes.${docType}`, { defaultValue: docType })}</span>
            {result.docTypeConfidence !== null && (
              <span className="font-mono-tabular">· {Math.round(result.docTypeConfidence * 100)}%</span>
            )}
          </Chip>
        </button>
        <span className="text-[11px] font-mono-tabular" style={{ color: "var(--text-muted)" }}>
          {result.engine} · {result.processingTimeMs}ms
        </span>
      </div>

      {docTypePickerOpen && (
        <div className="flex flex-wrap gap-1.5 rounded-xl p-2.5" style={{ backgroundColor: "var(--surface-2)" }}>
          {CLOSED_DOC_TYPES.map((dt) => (
            <button
              key={dt}
              type="button"
              onClick={() => {
                setDocType(dt);
                setDocTypePickerOpen(false);
              }}
              style={{
                backgroundColor: docType === dt ? "var(--primary)" : "var(--surface)",
                color: docType === dt ? "#FFFFFF" : "var(--text)",
              }}
              className="rounded-full px-2.5 py-1 text-xs font-semibold cursor-pointer"
            >
              {t(`rec.docTypes.${dt}`, { defaultValue: dt })}
            </button>
          ))}
        </div>
      )}

      {/* Warnings Block (i18n message keys from backend) */}
      {result.warnings.length > 0 && (
        <Banner tone="warning">
          <ul className="list-disc pl-4 space-y-0.5 text-xs">
            {result.warnings.map((w) => (
              <li key={w}>{t(w, { defaultValue: w })}</li>
            ))}
          </ul>
        </Banner>
      )}

      {/* Field List with Confidence Dots, Source Icons & Inline Confirm Gate (§10) */}
      {result.fields.length === 0 ? (
        <Banner tone="info">{t("rec.noFieldsManual")}</Banner>
      ) : (
        <div className="space-y-2.5">
          {result.fields.map((field) => (
            <FieldRow
              key={field.key}
              field={field}
              value={values[field.key] ?? ""}
              confirmed={Boolean(touchedConfirmed[field.key])}
              highlighted={highlightedKey === field.key}
              onFocus={() => setHighlightedKey(field.key)}
              onChange={(nextVal) => {
                setValues((prev) => ({ ...prev, [field.key]: nextVal }));
                setTouchedConfirmed((prev) => ({ ...prev, [field.key]: true }));
              }}
              onConfirm={() => setTouchedConfirmed((prev) => ({ ...prev, [field.key]: true }))}
            />
          ))}
        </div>
      )}

      {pendingConfirmCount > 0 && (
        <Banner tone="warning">
          {t("rec.confirmPendingNotice", { count: pendingConfirmCount })}
        </Banner>
      )}

      {/* Primary Action (gated until all needs_confirm fields are confirmed, §1 Principle 2, §10) */}
      <Button
        fullWidth
        className="min-h-[48px]"
        disabled={!canProceed}
        loading={confirming}
        onClick={triggerConfirm}
      >
        <CheckCircle2 className="h-4 w-4" />
        {primaryLabel}
      </Button>

      {/* Secondary Actions: Retake & Purge */}
      <div className="grid grid-cols-2 gap-2">
        <Button variant="secondary" className="min-h-[48px]" onClick={onRetake}>
          <RotateCcw className="h-4 w-4" />
          {result.kind === "voice" ? t("rec.reRecord") : t("rec.retake")}
        </Button>
        <Button variant="ghost" className="min-h-[48px]" onClick={onPurge}>
          <Trash2 className="h-4 w-4" />
          {t("rec.deleteJob")}
        </Button>
      </div>

      {/* Privacy Line (§10) */}
      <p className="text-center text-[11px]" style={{ color: "var(--text-muted)" }}>
        {result.kind === "id_mrz" ? t("rec.privacyMrz") : t("rec.privacy24h")}
      </p>
    </div>
  );
}
