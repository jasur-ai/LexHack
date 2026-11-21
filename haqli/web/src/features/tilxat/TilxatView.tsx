import { useEffect, useState } from "react";
import QRCode from "qrcode";
import {
  CheckCircle2,
  Copy,
  Download,
  FileCheck2,
  ScanLine,
  Send,
  Sparkles,
  XCircle,
  ArrowLeft,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { api, buildWsUrl, downloadProtectedPdf, type TilxatDTO } from "../../lib/api";
import { computeBhmRatio, formatDateLocalized, formatUzs } from "../../lib/format";
import { useAppStore } from "../../lib/store";
import { haptics, shareViaTelegram } from "../../tma/sdk";
import { Banner } from "../../ui/Banner";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { Chip, NeedsReviewChip } from "../../ui/Chip";

export function TilxatView() {
  const { t } = useTranslation();
  const lang = useAppStore((s) => s.lang);
  const user = useAppStore((s) => s.user);
  const demoMode = useAppStore((s) => s.demoMode);
  const constants = useAppStore((s) => s.constants);
  const prefill = useAppStore((s) => s.prefill);
  const setPrefill = useAppStore((s) => s.setPrefill);
  const openRecognition = useAppStore((s) => s.openRecognition);
  const pushToast = useAppStore((s) => s.pushToast);

  const [items, setItems] = useState<TilxatDTO[]>([]);
  const [active, setActive] = useState<TilxatDTO | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string>("");

  const [docType, setDocType] = useState<"loan" | "deposit" | "service">("loan");
  const [naturalText, setNaturalText] = useState("");
  const [parsing, setParsing] = useState(false);

  const [partyAName, setPartyAName] = useState(user?.fullName || "Azizbek Karimov");
  const [partyAPassport, setPartyAPassport] = useState("");
  const [partyBName, setPartyBName] = useState("");
  const [partyBPassport, setPartyBPassport] = useState("");
  const [amountUzs, setAmountUzs] = useState("5000000");
  const [dueDate, setDueDate] = useState("2026-09-01");
  const [dailyPenalty, setDailyPenalty] = useState("0.1");
  const [creating, setCreating] = useState(false);
  const [signingDemo, setSigningDemo] = useState(false);

  const loadList = async () => {
    try {
      const list = await api.listTilxats();
      setItems(list);
    } catch {
      // Ignore
    }
  };

  useEffect(() => {
    loadList();
  }, []);

  // Consume MRZ or Voice prefill from RecognitionSheet
  useEffect(() => {
    if (!prefill || prefill.target !== "tilxat") return;
    const f = prefill.fields;
    if (f.fullName) setPartyBName(String(f.fullName));
    if (f.documentNumber) setPartyBPassport(String(f.documentNumber));
    if (f.passport) setPartyBPassport(String(f.passport));
    if (f.counterpartyName) setPartyBName(String(f.counterpartyName));
    if (f.amountUzs) setAmountUzs(String(f.amountUzs).replace(/\.00$/, ""));
    if (f.dueDate) setDueDate(String(f.dueDate));
    setActive(null);
    setPrefill(null);
  }, [prefill, setPrefill]);

  // Generate QR + subscribe to real-time signing WebSocket when viewing an active Tilxat
  useEffect(() => {
    if (!active) return;
    const url = active.status === "signed" ? active.verifyUrl : active.signWebUrl || active.verifyUrl;
    QRCode.toDataURL(url, { width: 180, margin: 1 }).then(setQrDataUrl).catch(() => {});

    if (active.status !== "pending_counterparty") return;
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(buildWsUrl(`/ws/tilxat/${active.id}`));
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data) as { event?: string; tilxat?: TilxatDTO };
          if (msg.event === "signed" && msg.tilxat) {
            setActive(msg.tilxat);
            haptics.notify("success");
            loadList();
          }
        } catch {
          // Ignore malformed WS message
        }
      };
    } catch {
      // Fallback gracefully if WS unavailable
    }
    return () => {
      ws?.close();
    };
  }, [active?.id, active?.status]);

  const handleParseText = async () => {
    if (naturalText.trim().length < 3) return;
    setParsing(true);
    try {
      const res = await api.parseTilxatText(naturalText, lang);
      if (res.fields.counterpartyName) setPartyBName(res.fields.counterpartyName);
      if (res.fields.amountUzs) setAmountUzs(res.fields.amountUzs.replace(/\.00$/, ""));
      if (res.fields.dueDate) setDueDate(res.fields.dueDate);
      if (res.fields.passport) setPartyBPassport(res.fields.passport);
      haptics.notify("success");
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Parse error", "danger");
    } finally {
      setParsing(false);
    }
  };

  const handleCreate = async () => {
    if (partyAName.trim().length < 2 || partyBName.trim().length < 2) {
      pushToast("Ikkala tomon F.I.O. ni kiriting", "warning");
      return;
    }
    setCreating(true);
    try {
      const created = await api.createTilxat({
        docType,
        partyAName: partyAName.trim(),
        partyAPassport: partyAPassport.trim() || null,
        partyBName: partyBName.trim(),
        partyBPassport: partyBPassport.trim() || null,
        amountUzs: Number(amountUzs) || 0,
        dueDate,
        dailyPenaltyPercent: Number(dailyPenalty) || 0,
        locale: lang,
      });
      setActive(created);
      haptics.notify("success");
      loadList();
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Create failed", "danger");
    } finally {
      setCreating(false);
    }
  };

  const handleDemoSign = async () => {
    if (!active?.signToken) return;
    setSigningDemo(true);
    try {
      const signed = await api.signPublicTilxat(active.signToken, {
        agreed: true,
        signerName: active.partyBName,
        demoConfirm: true,
      });
      setActive(signed);
      haptics.notify("success");
      loadList();
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Sign failed", "danger");
    } finally {
      setSigningDemo(false);
    }
  };

  const handleRevoke = async () => {
    if (!active) return;
    try {
      const revoked = await api.revokeTilxat(active.id);
      setActive(revoked);
      loadList();
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Revoke failed", "danger");
    }
  };

  // ---------------- ACTIVE SIGNING / DETAIL VIEW ----------------
  if (active) {
    const shareLink = active.signWebUrl || active.verifyUrl;
    const statusTone =
      active.status === "signed" ? "success" : active.status === "revoked" ? "danger" : "warning";

    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => setActive(null)}
            className="inline-flex items-center gap-1.5 text-sm font-semibold cursor-pointer"
            style={{ color: "var(--text-muted)" }}
          >
            <ArrowLeft className="h-4 w-4" />
            {t("common.back")}
          </button>
          <Chip tone={statusTone}>{t(`tilxat.status.${active.status}`)}</Chip>
        </div>

        <Card className="space-y-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold">{t(`tilxat.types.${active.docType}`)}</h2>
              <div className="mt-0.5 text-xl font-bold font-mono-tabular" style={{ color: "var(--primary)" }}>
                {formatUzs(active.amountUzs, lang)}
              </div>
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                ({active.amountInWords})
              </div>
            </div>
            {qrDataUrl && (
              <img
                src={qrDataUrl}
                alt="QR"
                className="h-24 w-24 rounded-xl border p-1 bg-white"
                style={{ borderColor: "var(--border)" }}
              />
            )}
          </div>

          <div className="grid grid-cols-1 gap-2 rounded-xl p-3 text-xs sm:grid-cols-2" style={{ backgroundColor: "var(--surface-2)" }}>
            <div>
              <div style={{ color: "var(--text-muted)" }}>{t("tilxat.partyA")}</div>
              <div className="font-semibold">{active.partyAName}</div>
              {active.partyAPassportMasked && <div className="font-mono-tabular">{active.partyAPassportMasked}</div>}
            </div>
            <div>
              <div style={{ color: "var(--text-muted)" }}>{t("tilxat.partyB")}</div>
              <div className="font-semibold">{active.partyBName}</div>
              {active.partyBPassportMasked && <div className="font-mono-tabular">{active.partyBPassportMasked}</div>}
            </div>
          </div>

          <p className="text-sm leading-relaxed">{active.termsSummary}</p>

          <div className="flex flex-wrap items-center gap-2 text-xs font-mono-tabular" style={{ color: "var(--text-muted)" }}>
            <span>SHA-256: {active.docHash.slice(0, 16)}</span>
            <span>·</span>
            <span>{active.bhmRatio} BHM</span>
            <NeedsReviewChip />
          </div>

          {/* Honest e-confirmation notice (Rule 4) */}
          <Banner tone="warning">{t("common.eConfirmNotice")}</Banner>

          <div className="space-y-2">
            {active.status === "pending_counterparty" && (
              <>
                <Button
                  fullWidth
                  onClick={() =>
                    shareViaTelegram(
                      active.signDeepLink || shareLink,
                      `Haqli Tilxat: ${formatUzs(active.amountUzs, lang)} — tasdiqlash uchun oching`
                    )
                  }
                >
                  <Send className="h-4 w-4" />
                  {t("tilxat.shareTelegram")}
                </Button>
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    variant="secondary"
                    onClick={async () => {
                      await navigator.clipboard.writeText(shareLink);
                      pushToast(t("common.copied"), "success");
                    }}
                  >
                    <Copy className="h-4 w-4" />
                    {t("tilxat.copyLink")}
                  </Button>
                  <Button variant="danger" onClick={handleRevoke}>
                    <XCircle className="h-4 w-4" />
                    {t("tilxat.revokeBtn")}
                  </Button>
                </div>
                {demoMode && (
                  <Button variant="secondary" fullWidth loading={signingDemo} onClick={handleDemoSign}>
                    <CheckCircle2 className="h-4 w-4" />
                    {t("tilxat.demoSignBtn")}
                  </Button>
                )}
              </>
            )}

            {active.status === "signed" && (
              <Button
                fullWidth
                onClick={() =>
                  downloadProtectedPdf(
                    `/api/tilxat/${active.id}/pdf?locale=${lang}`,
                    `haqli-tilxat-${active.id.slice(0, 8)}.pdf`
                  )
                }
              >
                <Download className="h-4 w-4" />
                {t("common.downloadPdf")}
              </Button>
            )}
          </div>
        </Card>
      </div>
    );
  }

  // ---------------- CREATE FORM + LIST VIEW ----------------
  const ratio = computeBhmRatio(Number(amountUzs) || 0, constants.bhm);
  const requiresWritten = ratio > 10;

  return (
    <div className="space-y-5">
      <div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-lg bg-blue-50 px-2 py-0.5 text-xs font-bold text-[#0074ff] dark:bg-blue-950/50">
            3-MODUL
          </span>
          <Chip tone="primary">FK 108-modda: 10 BHM nazorati</Chip>
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight">{t("tilxat.title")}</h1>
        <p className="mt-0.5 text-sm" style={{ color: "var(--text-muted)" }}>
          {t("tilxat.subtitle")}
        </p>
      </div>

      {/* Natural Language Quick Prefill */}
      <Card padding="sm" className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold" style={{ color: "var(--primary)" }}>
            {t("tilxat.voiceParseHint")}
          </span>
        </div>
        <div className="flex gap-2">
          <input
            className="haqli-input text-sm"
            value={naturalText}
            onChange={(e) => setNaturalText(e.target.value)}
            placeholder={t("tilxat.voiceParsePlaceholder")}
          />
          <Button size="md" loading={parsing} onClick={handleParseText}>
            {t("tilxat.parseBtn")}
          </Button>
        </div>
      </Card>

      {/* Main Tilxat Builder */}
      <Card className="space-y-4">
        {/* Type switcher */}
        <div className="grid grid-cols-3 gap-1.5 rounded-xl p-1" style={{ backgroundColor: "var(--surface-2)" }}>
          {(["loan", "deposit", "service"] as const).map((dt) => (
            <button
              key={dt}
              type="button"
              onClick={() => setDocType(dt)}
              style={{
                backgroundColor: docType === dt ? "var(--surface)" : "transparent",
                color: docType === dt ? "var(--primary)" : "var(--text-muted)",
              }}
              className="rounded-lg py-2 text-xs font-bold cursor-pointer"
            >
              {t(`tilxat.types.${dt}`)}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label className="text-xs font-bold">{t("tilxat.partyA")}</label>
            <input className="haqli-input" value={partyAName} onChange={(e) => setPartyAName(e.target.value)} />
            <input
              className="haqli-input text-xs font-mono-tabular"
              value={partyAPassport}
              onChange={(e) => setPartyAPassport(e.target.value)}
              placeholder={t("tilxat.passportOpt")}
            />
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold">{t("tilxat.partyB")}</label>
              <button
                type="button"
                onClick={() => openRecognition("id_mrz")}
                className="inline-flex items-center gap-1 text-[11px] font-bold cursor-pointer"
                style={{ color: "var(--primary)" }}
              >
                <ScanLine className="h-3.5 w-3.5" />
                {t("tilxat.scanMrz")}
              </button>
            </div>
            <input
              className="haqli-input"
              value={partyBName}
              onChange={(e) => setPartyBName(e.target.value)}
              placeholder="Javohir Alimov"
            />
            <input
              className="haqli-input text-xs font-mono-tabular"
              value={partyBPassport}
              onChange={(e) => setPartyBPassport(e.target.value)}
              placeholder={t("tilxat.passportOpt")}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs font-bold">{t("tilxat.amountLabel")}</label>
            <input
              type="number"
              className="haqli-input font-mono-tabular"
              value={amountUzs}
              onChange={(e) => setAmountUzs(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-bold">{t("tilxat.dueDateLabel")}</label>
            <input
              type="date"
              className="haqli-input font-mono-tabular"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-bold">{t("tilxat.penaltyLabel")}</label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="5"
              className="haqli-input font-mono-tabular"
              value={dailyPenalty}
              onChange={(e) => setDailyPenalty(e.target.value)}
            />
          </div>
        </div>

        {requiresWritten && (
          <Banner tone="warning">
            <div className="flex flex-wrap items-center gap-2">
              <span>{t("tilxat.writtenFormWarn", { ratio })}</span>
              <NeedsReviewChip />
            </div>
          </Banner>
        )}

        <Banner tone="info">{t("common.eConfirmNotice")}</Banner>

        <Button fullWidth loading={creating} onClick={handleCreate}>
          <FileCheck2 className="h-4 w-4" />
          {t("tilxat.createBtn")}
        </Button>
      </Card>

      {/* Existing Tilxats */}
      {items.length > 0 && (
        <div className="space-y-2">
          {items.map((item) => (
            <Card
              key={item.id}
              padding="sm"
              className="flex items-center justify-between gap-3 cursor-pointer"
              onClick={() => setActive(item)}
            >
              <div className="min-w-0">
                <div className="font-semibold text-sm leading-snug break-words">
                  {item.partyAName} → {item.partyBName}
                </div>
                <div className="text-xs font-mono-tabular" style={{ color: "var(--text-muted)" }}>
                  {formatUzs(item.amountUzs, lang)} · {formatDateLocalized(item.dueDate, lang)}
                </div>
              </div>
              <Chip tone={item.status === "signed" ? "success" : item.status === "revoked" ? "danger" : "warning"}>
                {t(`tilxat.status.${item.status}`)}
              </Chip>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
