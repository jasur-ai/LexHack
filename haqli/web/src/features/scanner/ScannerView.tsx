import { useEffect, useState } from "react";
import {
  AlertOctagon,
  AlertTriangle,
  Camera,
  CheckCircle2,
  Copy,
  Download,
  HelpCircle,
  ScanLine,
  ArrowLeft,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  api,
  downloadProtectedPdf,
  type CitationItem,
  type ClauseFinding,
  type ContractAuditDTO,
} from "../../lib/api";
import { useAppStore } from "../../lib/store";
import { haptics } from "../../tma/sdk";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { Chip, NeedsReviewChip } from "../../ui/Chip";
import { Gauge } from "../../ui/Gauge";
import { Sheet } from "../../ui/Sheet";

export function ScannerView() {
  const { t } = useTranslation();
  const lang = useAppStore((s) => s.lang);
  const prefill = useAppStore((s) => s.prefill);
  const setPrefill = useAppStore((s) => s.setPrefill);
  const openRecognition = useAppStore((s) => s.openRecognition);
  const pushToast = useAppStore((s) => s.pushToast);

  const [samples, setSamples] = useState<Array<{ id: "rental" | "microloan" | "employment"; title: string; preview: string }>>([]);
  const [text, setText] = useState("");
  const [running, setRunning] = useState(false);
  const [audit, setAudit] = useState<ContractAuditDTO | null>(null);

  // Contextual "Ask about this clause" sheet (Rule 5)
  const [askingClause, setAskingClause] = useState<ClauseFinding | null>(null);
  const [question, setQuestion] = useState("");
  const [askLoading, setAskLoading] = useState(false);
  const [askReply, setAskReply] = useState<{ answer: string; citations: CitationItem[] } | null>(null);

  useEffect(() => {
    api.listScannerSamples(lang).then(setSamples).catch(() => {});
  }, [lang]);

  useEffect(() => {
    if (!prefill || prefill.target !== "scanner") return;
    if (prefill.rawText) setText(prefill.rawText);
    if (prefill.jobId) {
      runAudit({ recognitionJobId: prefill.jobId });
    }
    setPrefill(null);
  }, [prefill, setPrefill]);

  const runAudit = async (payload: { sampleId?: "rental" | "microloan" | "employment"; text?: string; recognitionJobId?: string }) => {
    setRunning(true);
    try {
      const res = await api.runContractAudit({ ...payload, locale: lang });
      setAudit(res);
      haptics.notify(res.safetyScore >= 75 ? "success" : "warning");
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Audit failed", "danger");
    } finally {
      setRunning(false);
    }
  };

  const handleAskClause = async () => {
    if (!askingClause) return;
    setAskLoading(true);
    try {
      const res = await api.askClause({
        clauseText: askingClause.quotedClause,
        question: question.trim() || "Bu band qonunga zidmi?",
        legalRefs: askingClause.legalRefs,
        locale: lang,
      });
      setAskReply(res);
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Failed", "danger");
    } finally {
      setAskLoading(false);
    }
  };

  const copyAlternative = async (txt: string) => {
    await navigator.clipboard.writeText(txt);
    pushToast(t("common.copied"), "success");
  };

  // ---------------- AUDIT REPORT VIEW ----------------
  if (audit) {
    const allFlags = [...audit.redFlags, ...audit.warnings, ...audit.safeClauses];

    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => setAudit(null)}
            className="inline-flex items-center gap-1.5 text-sm font-semibold cursor-pointer"
            style={{ color: "var(--text-muted)" }}
          >
            <ArrowLeft className="h-4 w-4" />
            {t("common.back")}
          </button>
          <NeedsReviewChip />
        </div>

        <Card className="grid grid-cols-1 gap-4 sm:grid-cols-[130px_1fr] items-center">
          <Gauge value={audit.safetyScore} label={t("scanner.scoreTitle")} />
          <div className="space-y-2">
            <h2 className="text-lg font-bold">{audit.title}</h2>
            <div className="flex flex-wrap gap-1.5">
              <Chip tone="danger">
                {t("scanner.redFlags")}: {audit.redFlags.length}
              </Chip>
              <Chip tone="warning">
                {t("scanner.warnings")}: {audit.warnings.length}
              </Chip>
              <Chip tone="success">
                {t("scanner.safeClauses")}: {audit.safeClauses.length}
              </Chip>
            </div>
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                downloadProtectedPdf(audit.pdfUrl, `haqli-audit-${audit.id.slice(0, 8)}.pdf`)
              }
            >
              <Download className="h-4 w-4" />
              {t("common.downloadPdf")}
            </Button>
          </div>
        </Card>

        {/* Clause Cards sorted by severity */}
        <div className="space-y-3">
          {allFlags.map((fl) => {
            const tone = fl.severity === "critical" ? "danger" : fl.severity === "warning" ? "warning" : "success";
            const Icon =
              fl.severity === "critical" ? AlertOctagon : fl.severity === "warning" ? AlertTriangle : CheckCircle2;
            return (
              <Card key={fl.id} className="space-y-2.5">
                <div className="flex items-start justify-between gap-2">
                  <Chip tone={tone}>
                    <Icon className="h-3.5 w-3.5" />
                    <span>{fl.severity.toUpperCase()}</span>
                  </Chip>
                  {fl.hasUnverifiedLegalData && <NeedsReviewChip />}
                </div>

                <blockquote
                  style={{ backgroundColor: "var(--surface-2)", borderColor: "var(--border)" }}
                  className="rounded-xl border-l-4 p-2.5 text-xs italic"
                >
                  “{fl.quotedClause}”
                </blockquote>

                <p className="text-sm leading-snug">{fl.whyRisky}</p>

                <div
                  style={{ backgroundColor: "var(--success-soft)" }}
                  className="rounded-xl p-2.5 text-xs space-y-1.5"
                >
                  <div className="font-bold" style={{ color: "var(--success)" }}>
                    {t("scanner.safeAlt")}
                  </div>
                  <p style={{ color: "var(--text)" }}>{fl.safeAlternative}</p>
                </div>

                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <Button size="sm" variant="secondary" onClick={() => copyAlternative(fl.safeAlternative)}>
                    <Copy className="h-3.5 w-3.5" />
                    {t("common.copy")}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setAskingClause(fl);
                      setQuestion("");
                      setAskReply(null);
                    }}
                  >
                    <HelpCircle className="h-3.5 w-3.5" />
                    {t("scanner.askClauseBtn")}
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>

        {/* Contextual Ask-about-Clause Sheet (Rule 5) */}
        <Sheet
          open={Boolean(askingClause)}
          onClose={() => setAskingClause(null)}
          title={t("scanner.askClauseTitle")}
        >
          {askingClause && (
            <div className="space-y-3">
              <div className="rounded-xl p-2.5 text-xs italic" style={{ backgroundColor: "var(--surface-2)" }}>
                “{askingClause.quotedClause}”
              </div>
              <div className="flex gap-2">
                <input
                  className="haqli-input text-sm"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder={t("scanner.askPlaceholder")}
                />
                <Button loading={askLoading} onClick={handleAskClause}>
                  OK
                </Button>
              </div>
              {askReply && (
                <div className="space-y-2 rounded-xl p-3 text-sm" style={{ backgroundColor: "var(--surface-2)" }}>
                  <p className="whitespace-pre-line">{askReply.answer}</p>
                  {askReply.citations.some((c) => c.status !== "verified") && <NeedsReviewChip />}
                </div>
              )}
            </div>
          )}
        </Sheet>
      </div>
    );
  }

  // ---------------- SCANNER HOME ----------------
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("scanner.title")}</h1>
        <p className="mt-0.5 text-sm" style={{ color: "var(--text-muted)" }}>
          {t("scanner.subtitle")}
        </p>
      </div>

      {/* 3 Quick Demo Samples */}
      <div className="space-y-2">
        <h2 className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
          {t("scanner.samplesTitle")}
        </h2>
        <div className="grid grid-cols-1 gap-2.5">
          {samples.map((s) => (
            <button
              key={s.id}
              type="button"
              disabled={running}
              onClick={() => runAudit({ sampleId: s.id })}
              className="haqli-card p-3.5 text-left transition-all hover:border-[var(--primary)] cursor-pointer"
            >
              <div className="font-bold text-sm" style={{ color: "var(--primary)" }}>
                {s.title}
              </div>
              <p className="mt-1 text-xs line-clamp-2" style={{ color: "var(--text-muted)" }}>
                {s.preview}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Paste or Camera */}
      <Card className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <label className="text-sm font-bold" htmlFor="contract-text">
            {t("scanner.pasteLabel")}
          </label>
          <Button size="sm" variant="secondary" onClick={() => openRecognition("document")}>
            <Camera className="h-3.5 w-3.5" />
            {t("scanner.cameraBtn")}
          </Button>
        </div>
        <textarea
          id="contract-text"
          rows={6}
          className="haqli-input text-sm"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={t("scanner.pastePlaceholder")}
        />
        <Button
          fullWidth
          loading={running}
          disabled={text.trim().length < 20}
          onClick={() => runAudit({ text })}
        >
          <ScanLine className="h-4 w-4" />
          {t("scanner.auditBtn")}
        </Button>
      </Card>
    </div>
  );
}
