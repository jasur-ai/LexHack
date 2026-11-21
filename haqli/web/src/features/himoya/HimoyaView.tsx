import { useEffect, useState } from "react";
import {
  Briefcase,
  ShoppingBag,
  Home,
  Car,
  Wallet,
  Sparkles,
  FileText,
  Scale,
  ArrowLeft,
  CheckCircle2,
  Copy,
  Download,
  ExternalLink,
  ShieldAlert,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { api, downloadProtectedPdf, type CitationItem, type DisputeCaseDTO } from "../../lib/api";
import { computeBhmRatio, formatDateLocalized, formatUzs } from "../../lib/format";
import { useAppStore } from "../../lib/store";
import { haptics, useTelegramBackButton } from "../../tma/sdk";
import { Banner } from "../../ui/Banner";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { Chip, NeedsReviewChip } from "../../ui/Chip";
import { Gauge } from "../../ui/Gauge";
import { Sheet } from "../../ui/Sheet";
import { Stepper } from "../../ui/Stepper";

type CategoryId = "labor" | "consumer" | "rental" | "traffic" | "debt";

const CATEGORIES: Array<{ id: CategoryId; Icon: typeof Briefcase }> = [
  { id: "labor", Icon: Briefcase },
  { id: "consumer", Icon: ShoppingBag },
  { id: "rental", Icon: Home },
  { id: "traffic", Icon: Car },
  { id: "debt", Icon: Wallet },
];

export function HimoyaView() {
  const { t } = useTranslation();
  const lang = useAppStore((s) => s.lang);
  const constants = useAppStore((s) => s.constants);
  const prefill = useAppStore((s) => s.prefill);
  const setPrefill = useAppStore((s) => s.setPrefill);
  const openRecognition = useAppStore((s) => s.openRecognition);
  const pushToast = useAppStore((s) => s.pushToast);

  const [mode, setMode] = useState<"home" | "wizard" | "result">("home");
  const [recentCases, setRecentCases] = useState<DisputeCaseDTO[]>([]);
  const [step, setStep] = useState(0);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [category, setCategory] = useState<CategoryId>("consumer");
  const [respondentName, setRespondentName] = useState("");
  const [claimAmount, setClaimAmount] = useState("4500000");
  const [incidentDate, setIncidentDate] = useState("2026-04-01");
  const [delayDays, setDelayDays] = useState("14");
  const [description, setDescription] = useState("");
  const [hasWrittenEvidence, setHasWrittenEvidence] = useState(true);

  const [analyzing, setAnalyzing] = useState(false);
  const [activeCase, setActiveCase] = useState<DisputeCaseDTO | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null);
  const [payModalOpen, setPayModalOpen] = useState(false);
  const [paying, setPaying] = useState(false);
  const [complaintOpen, setComplaintOpen] = useState(false);
  const [escalating, setEscalating] = useState(false);

  const loadRecent = async () => {
    try {
      const list = await api.listDisputes();
      setRecentCases(list);
    } catch {
      // Ignore initial load errors
    }
  };

  useEffect(() => {
    loadRecent();
  }, []);

  // Consume prefill coming from Recognition Sheet or Radar deep-link
  useEffect(() => {
    if (!prefill || prefill.target !== "himoya") return;
    if (prefill.category) setCategory(prefill.category);
    const f = prefill.fields;
    if (f.seller || f.issuingAuthority || f.counterpartyName) {
      setRespondentName(String(f.seller || f.issuingAuthority || f.counterpartyName || ""));
    }
    if (f.totalUzs || f.fineAmountUzs || f.amountUzs) {
      setClaimAmount(String(f.totalUzs || f.fineAmountUzs || f.amountUzs).replace(/\.00$/, ""));
    }
    if (f.purchaseDate || f.decisionDate || f.dueDate) {
      setIncidentDate(String(f.purchaseDate || f.decisionDate || f.dueDate));
    }
    if (prefill.rawText) {
      setDescription(prefill.rawText.slice(0, 400));
    }
    setMode("wizard");
    setStep(0);
    setPrefill(null);
  }, [prefill, setPrefill]);

  useTelegramBackButton(mode !== "home", () => {
    if (mode === "wizard" && step > 0) setStep((s) => s - 1);
    else setMode("home");
  });

  const startCategory = async (cat: CategoryId) => {
    haptics.selection();
    setCategory(cat);
    setDraftId(null);
    setStep(0);
    setMode("wizard");
    try {
      const d = await api.createDisputeDraft({ category: cat, locale: lang });
      setDraftId(d.id);
    } catch {
      // Draft autosave is optional
    }
  };

  const handleNextStep = async () => {
    if (step === 0 && respondentName.trim().length < 2) {
      pushToast(t("himoya.wizard.respondentLabel"), "warning");
      return;
    }
    if (draftId) {
      api
        .patchDisputeDraft(draftId, {
          respondentName,
          claimAmountUzs: Number(claimAmount) || 0,
          incidentDate,
          delayDays: Number(delayDays) || 0,
          locale: lang,
        })
        .catch(() => {});
    }
    setStep((s) => Math.min(3, s + 1));
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const res = await api.analyzeDispute({
        caseId: draftId,
        category,
        respondentName: respondentName.trim() || "Javobgar tashkilot",
        incidentDate,
        claimAmountUzs: Number(claimAmount) || 0,
        delayDays: Math.max(0, Number(delayDays) || 0),
        description,
        hasWrittenEvidence,
        locale: lang,
      });
      setActiveCase(res);
      setMode("result");
      haptics.notify("success");
      loadRecent();
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Analysis failed", "danger");
    } finally {
      setAnalyzing(false);
    }
  };

  const handlePayAndDownload = async () => {
    if (!activeCase) return;
    setPaying(true);
    try {
      if (activeCase.status !== "paid" && activeCase.status !== "escalated") {
        await api.payDispute(activeCase.id);
      }
      const doc = await api.generateDisputeDocument(activeCase.id, "talabnoma", lang);
      setActiveCase({ ...activeCase, status: "paid", pdfUrl: doc.pdfUrl });
      setPayModalOpen(false);
      haptics.notify("success");
      await downloadProtectedPdf(doc.pdfUrl, `haqli-talabnoma-${activeCase.id.slice(0, 8)}.pdf`);
      pushToast(t("himoya.result.talabnomaPaid"), "success");
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Payment/PDF failed", "danger");
    } finally {
      setPaying(false);
    }
  };

  const handleEscalate = async () => {
    if (!activeCase) return;
    setEscalating(true);
    try {
      await api.escalateCase(activeCase.id);
      setActiveCase({ ...activeCase, status: "escalated" });
      haptics.notify("success");
      pushToast("Advokat navbatiga muvaffaqiyatli yuborildi (MSO)", "success");
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Escalation failed", "danger");
    } finally {
      setEscalating(false);
    }
  };

  const copyText = async (txt: string) => {
    try {
      await navigator.clipboard.writeText(txt);
      pushToast(t("common.copied"), "success");
    } catch {
      pushToast("Clipboard blocked", "warning");
    }
  };

  // ---------------- HOME VIEW ----------------
  if (mode === "home") {
    return (
      <div className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-lg bg-blue-50 px-2 py-0.5 text-xs font-bold text-[#0074ff] dark:bg-blue-950/50">
                2-MODUL
              </span>
              <Chip tone="primary" className="font-mono-tabular">
                {t("himoya.bhmChip", { bhm: formatUzs(constants.bhm, lang) })}
              </Chip>
              {constants.bhmStatus !== "verified" && <NeedsReviewChip />}
            </div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight">{t("himoya.title")}</h1>
            <p className="mt-0.5 text-sm" style={{ color: "var(--text-muted)" }}>
              {t("himoya.subtitle")}
            </p>
          </div>
        </div>

        {/* 5 Category Cards (§9.1) */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {CATEGORIES.map(({ id, Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => startCategory(id)}
              className="haqli-card p-4 text-left transition-all hover:border-[var(--primary)] active:scale-[0.99] cursor-pointer flex items-start gap-3"
            >
              <div
                style={{ backgroundColor: "var(--primary-soft)", color: "var(--primary)" }}
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl"
              >
                <Icon className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <div className="font-bold text-[15px]">{t(`himoya.categories.${id}.title`)}</div>
                <p className="mt-0.5 text-xs leading-snug" style={{ color: "var(--text-muted)" }}>
                  {t(`himoya.categories.${id}.desc`)}
                </p>
              </div>
            </button>
          ))}
        </div>

        {/* Recent Cases & Drafts */}
        {recentCases.length > 0 && (
          <div className="space-y-2.5">
            <h2 className="text-sm font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
              {t("himoya.recentTitle")}
            </h2>
            {recentCases.slice(0, 5).map((c) => (
              <Card
                key={c.id}
                padding="sm"
                className="flex items-center justify-between gap-3 cursor-pointer"
                onClick={() => {
                  setActiveCase(c);
                  setMode(c.status === "draft" ? "wizard" : "result");
                  if (c.status === "draft") {
                    setCategory(c.category);
                    setDraftId(c.id);
                    setRespondentName(c.respondentName);
                    setClaimAmount(c.claimAmountUzs);
                  }
                }}
              >
                <div className="min-w-0">
                  <div className="font-semibold text-sm leading-snug break-words">
                    {c.respondentName || t(`himoya.categories.${c.category}.title`)}
                  </div>
                  <div className="text-xs font-mono-tabular" style={{ color: "var(--text-muted)" }}>
                    {formatUzs(c.claimAmountUzs, lang)} · {formatDateLocalized(c.createdAt, lang)}
                  </div>
                </div>
                <Chip tone={c.status === "paid" || c.status === "escalated" ? "success" : "neutral"}>
                  {c.status}
                </Chip>
              </Card>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ---------------- 4-STEP WIZARD (§9.1) ----------------
  if (mode === "wizard") {
    const ratio = computeBhmRatio(Number(claimAmount) || 0, constants.bhm);
    const steps = [
      t("himoya.wizard.step1"),
      t("himoya.wizard.step2"),
      t("himoya.wizard.step3"),
      t("himoya.wizard.step4"),
    ];

    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => setMode("home")}
            className="inline-flex items-center gap-1.5 text-sm font-semibold cursor-pointer"
            style={{ color: "var(--text-muted)" }}
          >
            <ArrowLeft className="h-4 w-4" />
            {t("common.back")}
          </button>
          <Chip tone="primary">{t(`himoya.categories.${category}.title`)}</Chip>
        </div>

        <Stepper steps={steps} current={step} />

        <Card className="space-y-4">
          {step === 0 && (
            <>
              <div className="flex items-center justify-between gap-2">
                <label className="text-sm font-semibold" htmlFor="respondent-input">
                  {t("himoya.wizard.respondentLabel")}
                </label>
                <Button size="sm" variant="secondary" onClick={() => openRecognition("document")}>
                  <Sparkles className="h-3.5 w-3.5" />
                  {t("himoya.wizard.prefillBtn")}
                </Button>
              </div>
              <input
                id="respondent-input"
                className="haqli-input"
                value={respondentName}
                onChange={(e) => setRespondentName(e.target.value)}
                placeholder={t("himoya.wizard.respondentPlaceholder")}
              />
            </>
          )}

          {step === 1 && (
            <div className="space-y-3.5">
              <div>
                <label className="mb-1 block text-sm font-semibold" htmlFor="amount-input">
                  {t("himoya.wizard.amountLabel")}
                </label>
                <input
                  id="amount-input"
                  type="number"
                  min={0}
                  className="haqli-input font-mono-tabular"
                  value={claimAmount}
                  onChange={(e) => setClaimAmount(e.target.value)}
                />
                <div className="mt-1.5 flex items-center gap-2 text-xs" style={{ color: "var(--primary)" }}>
                  <span className="font-mono-tabular font-semibold">
                    {t("himoya.wizard.bhmRatioHint", { ratio })}
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-sm font-semibold" htmlFor="date-input">
                    {t("himoya.wizard.incidentDateLabel")}
                  </label>
                  <input
                    id="date-input"
                    type="date"
                    className="haqli-input font-mono-tabular"
                    value={incidentDate}
                    onChange={(e) => setIncidentDate(e.target.value)}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-semibold" htmlFor="delay-input">
                    {t("himoya.wizard.delayDaysLabel")}
                  </label>
                  <input
                    id="delay-input"
                    type="number"
                    min={0}
                    max={3650}
                    className="haqli-input font-mono-tabular"
                    value={delayDays}
                    onChange={(e) => setDelayDays(e.target.value)}
                  />
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-3.5">
              <div>
                <label className="mb-1 block text-sm font-semibold" htmlFor="desc-input">
                  {t("himoya.wizard.descLabel")}
                </label>
                <textarea
                  id="desc-input"
                  rows={4}
                  className="haqli-input"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={t("himoya.wizard.descPlaceholder")}
                />
              </div>
              <label className="flex items-center gap-2.5 text-sm font-medium cursor-pointer">
                <input
                  type="checkbox"
                  checked={hasWrittenEvidence}
                  onChange={(e) => setHasWrittenEvidence(e.target.checked)}
                  className="h-4 w-4 accent-[var(--primary)]"
                />
                <span>{t("himoya.wizard.hasWritten")}</span>
              </label>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-3 text-sm">
              <div className="flex justify-between border-b pb-2" style={{ borderColor: "var(--border)" }}>
                <span style={{ color: "var(--text-muted)" }}>{t("himoya.wizard.step1")}</span>
                <span className="font-semibold">{respondentName}</span>
              </div>
              <div className="flex justify-between border-b pb-2" style={{ borderColor: "var(--border)" }}>
                <span style={{ color: "var(--text-muted)" }}>{t("himoya.wizard.amountLabel")}</span>
                <span className="font-mono-tabular font-semibold">{formatUzs(claimAmount, lang)}</span>
              </div>
              <div className="flex justify-between border-b pb-2" style={{ borderColor: "var(--border)" }}>
                <span style={{ color: "var(--text-muted)" }}>{t("himoya.wizard.incidentDateLabel")}</span>
                <span className="font-mono-tabular">{incidentDate}</span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: "var(--text-muted)" }}>{t("himoya.wizard.delayDaysLabel")}</span>
                <span className="font-mono-tabular">{delayDays}</span>
              </div>
              <Banner tone="info">{t("common.legalDisclaimer")}</Banner>
            </div>
          )}

          <div className="flex items-center gap-2 pt-2">
            {step > 0 && (
              <Button variant="secondary" onClick={() => setStep((s) => s - 1)}>
                {t("common.back")}
              </Button>
            )}
            {step < 3 ? (
              <Button fullWidth onClick={handleNextStep}>
                {t("common.next")}
              </Button>
            ) : (
              <Button fullWidth loading={analyzing} onClick={handleAnalyze}>
                <Scale className="h-4 w-4" />
                {t("himoya.wizard.analyzeBtn")}
              </Button>
            )}
          </div>
        </Card>
      </div>
    );
  }

  // ---------------- RESULT SCREEN (§9.1) ----------------
  if (!activeCase) return null;
  const computed = activeCase.computed as Record<string, unknown>;
  const isPaid = activeCase.status === "paid" || activeCase.status === "escalated";
  const priceLabel = formatUzs(String(computed.talabnomaPriceUzs ?? constants.talabnomaPriceUzs), lang);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setMode("home")}
          className="inline-flex items-center gap-1.5 text-sm font-semibold cursor-pointer"
          style={{ color: "var(--text-muted)" }}
        >
          <ArrowLeft className="h-4 w-4" />
          {t("common.back")}
        </button>
        {activeCase.hasUnverifiedLegalData && <NeedsReviewChip />}
      </div>

      {/* Strength & Money Summary */}
      <Card className="grid grid-cols-1 gap-4 sm:grid-cols-[130px_1fr] items-center">
        <Gauge value={activeCase.caseStrength} label={t("himoya.result.strengthTitle")} />
        <div className="space-y-2">
          <div className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            {t("himoya.result.moneyTitle")}
          </div>
          <div className="flex justify-between text-sm">
            <span style={{ color: "var(--text-muted)" }}>{t("himoya.result.principal")}</span>
            <span className="font-mono-tabular font-semibold">{formatUzs(String(computed.claimAmountUzs ?? 0), lang)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span style={{ color: "var(--text-muted)" }}>{t("himoya.result.penalty")}</span>
            <span className="font-mono-tabular font-semibold" style={{ color: "var(--primary)" }}>
              +{formatUzs(String(computed.penaltyUzs ?? 0), lang)}
            </span>
          </div>
          <div
            className="flex justify-between border-t pt-2 text-base font-bold"
            style={{ borderColor: "var(--border)" }}
          >
            <span>{t("himoya.result.total")}</span>
            <span className="font-mono-tabular">{formatUzs(String(computed.totalUzs ?? 0), lang)}</span>
          </div>
          <div className="rounded-lg px-2.5 py-1.5 text-xs font-mono-tabular" style={{ backgroundColor: "var(--surface-2)", color: "var(--text-muted)" }}>
            {String(computed.formula ?? "")}
          </div>
        </div>
      </Card>

      {/* Assessment & Strength Breakdown */}
      <Card className="space-y-3">
        <p className="text-sm leading-relaxed whitespace-pre-line">{activeCase.assessmentText}</p>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(activeCase.strengthBreakdown || {}).map(([k, v]) => (
            <Chip key={k} tone={v > 0 ? "success" : "neutral"}>
              {k.replace(/_/g, " ")}: +{v}
            </Chip>
          ))}
        </div>
      </Card>

      {/* Legal Citations (grounded in instruments.json) */}
      <Card className="space-y-2.5">
        <h3 className="text-sm font-bold">{t("himoya.result.citationsTitle")}</h3>
        <div className="space-y-2">
          {activeCase.citations.map((ci) => (
            <button
              key={ci.id}
              type="button"
              onClick={() => setSelectedCitation(ci)}
              style={{ backgroundColor: "var(--surface-2)" }}
              className="w-full rounded-xl p-3 text-left transition-opacity hover:opacity-90 cursor-pointer"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold" style={{ color: "var(--primary)" }}>
                  {ci.instrument} · {ci.article}
                </span>
                {ci.status !== "verified" && <NeedsReviewChip />}
              </div>
              <p className="mt-1 text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
                {ci.summary}
              </p>
            </button>
          ))}
        </div>
      </Card>

      {/* Actions */}
      <div className="space-y-2.5">
        {isPaid ? (
          <Button fullWidth loading={paying} onClick={handlePayAndDownload}>
            <Download className="h-4 w-4" />
            {t("himoya.result.talabnomaPaid")}
          </Button>
        ) : (
          <Button fullWidth onClick={() => setPayModalOpen(true)}>
            <FileText className="h-4 w-4" />
            {t("himoya.result.talabnomaAction", { price: priceLabel })}
          </Button>
        )}

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <Button variant="secondary" fullWidth onClick={() => setComplaintOpen(true)}>
            <Copy className="h-4 w-4" />
            {t("himoya.result.complaintAction")}
          </Button>
          <Button
            variant="secondary"
            fullWidth
            loading={escalating}
            disabled={activeCase.status === "escalated"}
            onClick={handleEscalate}
          >
            <ShieldAlert className="h-4 w-4" />
            {activeCase.status === "escalated" ? "MSO ✓" : t("himoya.result.escalateAction")}
          </Button>
        </div>
      </div>

      {/* Citation Detail Sheet */}
      <Sheet
        open={Boolean(selectedCitation)}
        onClose={() => setSelectedCitation(null)}
        title={selectedCitation ? `${selectedCitation.instrument} (${selectedCitation.article})` : ""}
      >
        {selectedCitation && (
          <div className="space-y-3">
            {selectedCitation.status !== "verified" && <NeedsReviewChip />}
            <p className="text-sm leading-relaxed">{selectedCitation.summary}</p>
            <a
              href={selectedCitation.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm font-semibold"
              style={{ color: "var(--primary)" }}
            >
              <span>Lex.uz</span>
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        )}
      </Sheet>

      {/* Simulated Payment Modal (§1 Rule 1) */}
      <Sheet open={payModalOpen} onClose={() => setPayModalOpen(false)} title={t("himoya.result.payModalTitle")}>
        <div className="space-y-4">
          <Banner tone="info">{t("himoya.result.payModalDesc")}</Banner>
          <Button fullWidth loading={paying} onClick={handlePayAndDownload}>
            <CheckCircle2 className="h-4 w-4" />
            {t("himoya.result.payConfirm", { price: priceLabel })}
          </Button>
        </div>
      </Sheet>

      {/* State Organ Complaint Copy Sheet */}
      <Sheet open={complaintOpen} onClose={() => setComplaintOpen(false)} title={t("himoya.result.complaintAction")}>
        <div className="space-y-3">
          <pre
            style={{ backgroundColor: "var(--surface-2)" }}
            className="max-h-72 overflow-y-auto whitespace-pre-wrap rounded-xl p-3 text-xs leading-relaxed"
          >
            {activeCase.complaintText}
          </pre>
          <Button fullWidth onClick={() => copyText(activeCase.complaintText)}>
            <Copy className="h-4 w-4" />
            {t("common.copy")}
          </Button>
        </div>
      </Sheet>
    </div>
  );
}
