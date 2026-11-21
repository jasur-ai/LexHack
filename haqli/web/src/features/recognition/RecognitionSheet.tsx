import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Circle, Loader2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslation } from "react-i18next";
import { useAppStore } from "../../lib/store";
import { haptics, useTelegramBackButton } from "../../tma/sdk";
import { Banner } from "../../ui/Banner";
import { Button } from "../../ui/Button";
import { Skeleton } from "../../ui/Skeleton";
import { CameraCapture } from "./CameraCapture";
import { ModeTabs, type RecTabMode } from "./ModeTabs";
import { QrScanner } from "./QrScanner";
import { ReviewScreen } from "./ReviewScreen";
import { mapRouteHintToPrefill } from "./routes";
import { useRecognitionJob } from "./useRecognitionJob";

const DISPLAY_STAGES = ["quality", "preprocess", "recognize", "classify", "parse", "validate"] as const;

export function RecognitionSheet() {
  const { t } = useTranslation();
  const open = useAppStore((s) => s.recognitionOpen);
  const initialMode = useAppStore((s) => s.recognitionInitialMode);
  const close = useAppStore((s) => s.closeRecognition);
  const lang = useAppStore((s) => s.lang);
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const setPrefill = useAppStore((s) => s.setPrefill);
  const pushToast = useAppStore((s) => s.pushToast);

  const [mode, setMode] = useState<RecTabMode>(initialMode);
  const [previewUrl, setPreviewUrl] = useState("");
  const [confirming, setConfirming] = useState(false);

  const job = useRecognitionJob();

  useEffect(() => {
    if (open) {
      setMode(initialMode);
      setPreviewUrl("");
      job.reset();
    }
  }, [open, initialMode]);

  useTelegramBackButton(open, () => {
    if (job.status !== "idle") {
      job.reset();
    } else {
      close();
    }
  });

  const handleClose = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl("");
    job.reset();
    close();
  };

  const handleConfirmAndRoute = async (
    edits: Array<{ key: string; value: unknown }>,
    docType: string | null
  ) => {
    if (!job.result) return;
    setConfirming(true);
    try {
      const confirmed = await job.confirmJob(edits, docType);
      const { tab, prefill } = mapRouteHintToPrefill(confirmed.routeHint, confirmed.fields, {
        jobId: job.jobId ?? undefined,
        rawText: job.result.transcript || job.result.rawTextPreview,
        docType,
      });
      setPrefill(prefill);
      setActiveTab(tab);
      haptics.notify("success");
      handleClose();
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Confirmation failed", "danger");
    } finally {
      setConfirming(false);
    }
  };

  const handleManualEscape = () => {
    job.reset();
    setActiveTab(mode === "id_mrz" ? "tilxat" : "himoya");
    handleClose();
  };

  const langHint = lang === "ru" ? "ru" : "uz";

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ y: "100%" }}
          animate={{ y: 0 }}
          exit={{ y: "100%" }}
          transition={{ duration: 0.24, ease: "easeOut" }}
          role="dialog"
          aria-modal="true"
          aria-label={t("recognition.title")}
          style={{ backgroundColor: "var(--bg)", paddingTop: "var(--safe-top)" }}
          className="fixed inset-0 z-50 flex flex-col overflow-hidden"
        >
          {/* Top Bar */}
          <div
            style={{ backgroundColor: "var(--surface)", borderColor: "var(--border)" }}
            className="flex h-14 shrink-0 items-center justify-between border-b px-4"
          >
            <h2 className="text-base font-bold">{t("recognition.title")}</h2>
            <button
              type="button"
              onClick={handleClose}
              aria-label={t("common.close")}
              style={{ backgroundColor: "var(--surface-2)", color: "var(--text)" }}
              className="flex h-11 w-11 items-center justify-center rounded-full cursor-pointer"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Scrollable Body */}
          <div className="mx-auto w-full max-w-lg flex-1 overflow-y-auto px-4 py-4 space-y-4">
            {job.status === "idle" && (
              <>
                <ModeTabs
                  active={mode}
                  onChange={(next) => {
                    setMode(next);
                    setPreviewUrl("");
                  }}
                />

                {mode === "verify" ? (
                  <QrScanner />
                ) : (
                  <CameraCapture
                    mode={mode}
                    onCaptureFile={(file, preview) => {
                      setPreviewUrl(preview);
                      job.startJob({ kind: mode, file, langHint });
                    }}
                    onSubmitText={(text) => {
                      setPreviewUrl("");
                      job.startJob({ kind: mode, text, langHint });
                    }}
                  />
                )}
              </>
            )}

            {/* Real SSE Stage Progress Screen (§10) */}
            {(job.status === "uploading" || job.status === "processing") && (
              <div className="space-y-4" aria-live="polite">
                <div className="haqli-card p-4 space-y-3">
                  <div className="text-sm font-bold">{t("rec.processingTitle")}</div>
                  <div className="space-y-2.5">
                    {DISPLAY_STAGES.map((st) => {
                      const ev = job.stages.find((s) => s.stage === st);
                      const state = ev?.state ?? "pending";
                      return (
                        <div key={st} className="flex items-center justify-between text-sm">
                          <div className="flex items-center gap-2.5">
                            {state === "ok" || state === "skipped" ? (
                              <CheckCircle2 className="h-4 w-4" style={{ color: "var(--success)" }} />
                            ) : state === "warn" || state === "failed" ? (
                              <AlertTriangle className="h-4 w-4" style={{ color: "var(--warning)" }} />
                            ) : state === "running" ? (
                              <Loader2 className="h-4 w-4 animate-spin" style={{ color: "var(--primary)" }} />
                            ) : (
                              <Circle className="h-4 w-4" style={{ color: "var(--border)" }} />
                            )}
                            <span>{t(`rec.stages.${st}`)}</span>
                          </div>
                          {ev && (
                            <span className="text-xs font-mono-tabular" style={{ color: "var(--text-muted)" }}>
                              {ev.elapsedMs}ms
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                <Skeleton className="h-24 w-full" />

                {job.showManualEscape && (
                  <Button variant="secondary" fullWidth className="min-h-[48px]" onClick={handleManualEscape}>
                    {t("rec.manualEntry")}
                  </Button>
                )}
              </div>
            )}

            {/* Review Screen (§10) */}
            {job.status === "review" && job.result && (
              <ReviewScreen
                result={job.result}
                previewImageUrl={previewUrl}
                confirming={confirming}
                onConfirm={handleConfirmAndRoute}
                onRetake={() => {
                  setPreviewUrl("");
                  job.reset();
                }}
                onPurge={async () => {
                  await job.purgeJob();
                  pushToast(t("rec.jobDeleted"), "info");
                }}
              />
            )}

            {/* Designed Error State (§10) */}
            {job.status === "error" && (
              <div className="space-y-3" aria-live="polite">
                <Banner tone="danger">
                  {t(job.errorKey ?? "rec.err.upload_failed", { defaultValue: job.errorKey ?? "Error" })}
                </Banner>
                {job.offlineQueued && <Banner tone="info">{t("rec.offlineQueuedNotice")}</Banner>}
                <div className="grid grid-cols-2 gap-2">
                  <Button variant="secondary" className="min-h-[48px]" onClick={() => job.reset()}>
                    {t("rec.retake")}
                  </Button>
                  <Button className="min-h-[48px]" onClick={handleManualEscape}>
                    {t("rec.manualEntry")}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
