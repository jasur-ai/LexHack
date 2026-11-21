import { useEffect, useState } from "react";
import { Briefcase, CheckCircle2, Clock, Lock, MessageSquare, ShieldCheck, XCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api, type AdvocateLeadDTO } from "../../lib/api";
import { formatDateLocalized, formatUzs } from "../../lib/format";
import { useAppStore } from "../../lib/store";
import { haptics } from "../../tma/sdk";
import { Banner } from "../../ui/Banner";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { Chip, NeedsReviewChip } from "../../ui/Chip";
import { Gauge } from "../../ui/Gauge";
import { Sheet } from "../../ui/Sheet";

export function AdvocateView() {
  const { t } = useTranslation();
  const user = useAppStore((s) => s.user);
  const lang = useAppStore((s) => s.lang);
  const setUser = useAppStore((s) => s.setUser);
  const pushToast = useAppStore((s) => s.pushToast);

  const [inviteCode, setInviteCode] = useState("HAQLI-ADV-2026");
  const [licenseNum, setLicenseNum] = useState("UZ-ADV-0042");
  const [unlocking, setUnlocking] = useState(false);

  const [leads, setLeads] = useState<AdvocateLeadDTO[]>([]);
  const [metrics, setMetrics] = useState<{
    newLeads: number;
    acceptedThisMonth: number;
    avgIntakeTimeSavedMin: number;
    platformFeePercent: number;
  } | null>(null);
  const [filterCat, setFilterCat] = useState<string>("");
  const [selectedLead, setSelectedLead] = useState<AdvocateLeadDTO | null>(null);
  const [actionBusy, setActionBusy] = useState(false);

  const isAdvocate = user?.role === "advocate";

  const loadDashboard = async () => {
    if (!isAdvocate) return;
    try {
      const [ld, met] = await Promise.all([
        api.listMsoLeads(filterCat ? { category: filterCat } : undefined),
        api.getMsoMetrics(),
      ]);
      setLeads(ld);
      setMetrics(met);
    } catch {
      // Ignore
    }
  };

  useEffect(() => {
    loadDashboard();
  }, [isAdvocate, filterCat]);

  const handleUnlock = async () => {
    setUnlocking(true);
    try {
      const res = await api.patchPreferences({
        role: "advocate",
        inviteCode: inviteCode.trim(),
        licenseNumber: licenseNum.trim(),
      });
      setUser(res.user, res.accessToken);
      haptics.notify("success");
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Invalid invite code", "danger");
    } finally {
      setUnlocking(false);
    }
  };

  const handleAccept = async (lead: AdvocateLeadDTO) => {
    setActionBusy(true);
    try {
      const updated = await api.acceptLead(lead.id);
      setSelectedLead(updated);
      haptics.notify("success");
      loadDashboard();
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Failed", "danger");
    } finally {
      setActionBusy(false);
    }
  };

  const handleRequestInfo = async (lead: AdvocateLeadDTO) => {
    setActionBusy(true);
    try {
      const updated = await api.requestLeadInfo(lead.id, "Iltimos, qo'shimcha dalil va cheklarni yuklang.");
      setSelectedLead(updated);
      pushToast("Mijozga so'rov yuborildi", "info");
      loadDashboard();
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Failed", "danger");
    } finally {
      setActionBusy(false);
    }
  };

  const handleDecline = async (lead: AdvocateLeadDTO) => {
    setActionBusy(true);
    try {
      const updated = await api.declineLead(lead.id, "Bandlik sababli rad etildi");
      setSelectedLead(updated);
      loadDashboard();
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Failed", "danger");
    } finally {
      setActionBusy(false);
    }
  };

  // ---------------- INVITE GATE (§9.5) ----------------
  if (!isAdvocate) {
    return (
      <div className="space-y-4">
        <Banner tone="info">{t("advocate.compliance")}</Banner>
        <Card className="space-y-4">
          <div className="flex items-center gap-2.5">
            <div
              style={{ backgroundColor: "var(--primary-soft)", color: "var(--primary)" }}
              className="flex h-10 w-10 items-center justify-center rounded-xl"
            >
              <Lock className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold">{t("advocate.gateTitle")}</h1>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                {t("advocate.gateDesc")}
              </p>
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-bold">{t("advocate.inviteLabel")}</label>
              <input
                className="haqli-input font-mono-tabular uppercase"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-bold">{t("advocate.licenseLabel")}</label>
              <input
                className="haqli-input font-mono-tabular"
                value={licenseNum}
                onChange={(e) => setLicenseNum(e.target.value)}
              />
            </div>
          </div>

          <Button fullWidth loading={unlocking} onClick={handleUnlock}>
            <ShieldCheck className="h-4 w-4" />
            {t("advocate.unlockBtn")}
          </Button>
        </Card>
      </div>
    );
  }

  // ---------------- ADVOCATE MSO WORKSPACE ----------------
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("advocate.title")}</h1>
        <Banner tone="info" className="mt-2">
          {t("advocate.compliance")}
        </Banner>
      </div>

      {/* KPI Strip */}
      {metrics && (
        <div className="grid grid-cols-3 gap-2.5">
          <Card padding="sm" className="text-center">
            <div className="font-mono-tabular text-2xl font-bold" style={{ color: "var(--primary)" }}>
              {metrics.newLeads}
            </div>
            <div className="text-[11px] font-semibold" style={{ color: "var(--text-muted)" }}>
              {t("advocate.kpiNew")}
            </div>
          </Card>
          <Card padding="sm" className="text-center">
            <div className="font-mono-tabular text-2xl font-bold" style={{ color: "var(--success)" }}>
              {metrics.acceptedThisMonth}
            </div>
            <div className="text-[11px] font-semibold" style={{ color: "var(--text-muted)" }}>
              {t("advocate.kpiAccepted")}
            </div>
          </Card>
          <Card padding="sm" className="text-center">
            <div className="font-mono-tabular text-2xl font-bold">
              {metrics.avgIntakeTimeSavedMin}m
            </div>
            <div className="text-[11px] font-semibold" style={{ color: "var(--text-muted)" }}>
              {t("advocate.kpiSaved")}
            </div>
          </Card>
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex flex-wrap gap-1.5">
        {["", "labor", "consumer", "rental", "traffic", "debt"].map((cat) => (
          <button
            key={cat || "all"}
            type="button"
            onClick={() => setFilterCat(cat)}
            style={{
              backgroundColor: filterCat === cat ? "var(--primary)" : "var(--surface-2)",
              color: filterCat === cat ? "#FFFFFF" : "var(--text-muted)",
            }}
            className="rounded-full px-3 py-1 text-xs font-semibold cursor-pointer"
          >
            {cat ? t(`himoya.categories.${cat}.title`) : "Barchasi"}
          </button>
        ))}
      </div>

      {/* Lead Queue */}
      <div className="space-y-3">
        {leads.map((ld) => {
          const brief = ld.brief;
          const strength = Number(brief.caseStrength ?? 75);
          const tone =
            ld.status === "accepted" ? "success" : ld.status === "declined" ? "danger" : "primary";
          return (
            <Card
              key={ld.id}
              className="space-y-2.5 cursor-pointer hover:border-[var(--primary)]"
              onClick={() => setSelectedLead(ld)}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  <Briefcase className="h-4 w-4" style={{ color: "var(--primary)" }} />
                  <span className="font-bold text-sm">{String(brief.respondentName ?? "Ish")}</span>
                </div>
                <Chip tone={tone}>{ld.status}</Chip>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <span className="font-mono-tabular font-bold" style={{ color: "var(--primary)" }}>
                  {formatUzs(String(brief.claimAmountUzs ?? 0), lang)}
                </span>
                <span className="flex items-center gap-1" style={{ color: "var(--text-muted)" }}>
                  <Clock className="h-3.5 w-3.5" />
                  {formatDateLocalized(ld.createdAt, lang)} · Strength: {strength}/100
                </span>
              </div>
            </Card>
          );
        })}
      </div>

      {/* 1-Page Brief Drawer (§9.5) */}
      <Sheet
        open={Boolean(selectedLead)}
        onClose={() => setSelectedLead(null)}
        title={selectedLead ? String(selectedLead.brief.respondentName ?? "Case Brief") : ""}
      >
        {selectedLead && (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <Gauge value={Number(selectedLead.brief.caseStrength ?? 70)} label="Case Strength" size={96} />
              <div className="space-y-1 text-sm">
                <div className="font-mono-tabular font-bold text-lg" style={{ color: "var(--primary)" }}>
                  {formatUzs(String(selectedLead.brief.claimAmountUzs ?? 0), lang)}
                </div>
                <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Client: {String(selectedLead.brief.clientName ?? "—")}
                </div>
                <div className="text-xs font-semibold">
                  Contact: {String(selectedLead.brief.clientContact ?? t("advocate.contactLocked"))}
                </div>
                <NeedsReviewChip />
              </div>
            </div>

            <div className="rounded-xl p-3 text-xs leading-relaxed whitespace-pre-line" style={{ backgroundColor: "var(--surface-2)" }}>
              {String(selectedLead.brief.assessment ?? "")}
            </div>

            <div className="space-y-2">
              {selectedLead.status !== "accepted" && (
                <Button fullWidth loading={actionBusy} onClick={() => handleAccept(selectedLead)}>
                  <CheckCircle2 className="h-4 w-4" />
                  {t("advocate.acceptBtn")}
                </Button>
              )}
              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant="secondary"
                  loading={actionBusy}
                  onClick={() => handleRequestInfo(selectedLead)}
                >
                  <MessageSquare className="h-4 w-4" />
                  {t("advocate.requestInfoBtn")}
                </Button>
                <Button variant="danger" loading={actionBusy} onClick={() => handleDecline(selectedLead)}>
                  <XCircle className="h-4 w-4" />
                  {t("advocate.declineBtn")}
                </Button>
              </div>
            </div>
          </div>
        )}
      </Sheet>
    </div>
  );
}
