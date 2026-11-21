import { useEffect, useState } from "react";
import { CheckCircle2, ShieldAlert, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api, type TilxatDTO, type VerifyDocumentResponse } from "../../lib/api";
import { formatDateLocalized, formatUzs } from "../../lib/format";
import { getTelegramInitData, haptics } from "../../tma/sdk";
import { Banner } from "../../ui/Banner";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { Chip, NeedsReviewChip } from "../../ui/Chip";

export function PublicVerifyPage({ docId }: { docId: string }) {
  const [res, setRes] = useState<VerifyDocumentResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .verifyDocumentById(docId)
      .then(setRes)
      .catch(() => setRes({ status: "unknown", docId, detail: "Verification lookup failed." }))
      .finally(() => setLoading(false));
  }, [docId]);

  return (
    <div className="mx-auto max-w-md px-4 py-10 space-y-4">
      <div className="text-center">
        <div className="text-2xl font-bold" style={{ color: "var(--primary)" }}>
          haqli
        </div>
        <div className="text-xs" style={{ color: "var(--text-muted)" }}>
          Kriptografik hujjat tekshiruvi / Document Verification
        </div>
      </div>

      <Card className="space-y-4">
        {loading ? (
          <div className="py-6 text-center text-sm">Tekshirilmoqda…</div>
        ) : res ? (
          <>
            <div className="flex items-center gap-3">
              {res.status === "valid" ? (
                <ShieldCheck className="h-10 w-10" style={{ color: "var(--success)" }} />
              ) : (
                <ShieldAlert className="h-10 w-10" style={{ color: "var(--danger)" }} />
              )}
              <div>
                <Chip tone={res.status === "valid" ? "success" : res.status === "tampered" ? "danger" : "warning"}>
                  {res.status.toUpperCase()}
                </Chip>
                <div className="mt-1 font-mono-tabular text-xs" style={{ color: "var(--text-muted)" }}>
                  ID: {res.docId}
                </div>
              </div>
            </div>

            {res.docHashShort && (
              <div className="rounded-xl p-3 text-xs font-mono-tabular space-y-1" style={{ backgroundColor: "var(--surface-2)" }}>
                <div>Type: {res.docKind}</div>
                <div>SHA-256: {res.docHashShort}</div>
                <div>Ed25519 Seal: {res.sealVerified ? "VALID" : "INVALID"}</div>
              </div>
            )}

            <Banner tone="warning">{res.eConfirmNotice || res.detail}</Banner>
          </>
        ) : null}
      </Card>
    </div>
  );
}

export function PublicSignTilxatPage({ token }: { token: string }) {
  const { t } = useTranslation();
  const [item, setItem] = useState<TilxatDTO | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [signerName, setSignerName] = useState("");
  const [signerPassport, setSignerPassport] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .getPublicTilxat(token)
      .then((d) => {
        setItem(d);
        setSignerName(d.partyBName);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Not found"));
  }, [token]);

  const handleSign = async () => {
    if (!agreed) return;
    setSubmitting(true);
    try {
      const signed = await api.signPublicTilxat(token, {
        initData: getTelegramInitData(),
        signerName: signerName.trim(),
        signerPassport: signerPassport.trim() || null,
        agreed: true,
        demoConfirm: !getTelegramInitData(),
      });
      setItem(signed);
      haptics.notify("success");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Signing failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg px-4 py-8 space-y-4">
      <div className="text-center">
        <div className="text-2xl font-bold" style={{ color: "var(--primary)" }}>
          haqli
        </div>
        <h1 className="text-lg font-bold mt-1">{t("tilxat.publicSignTitle")}</h1>
      </div>

      {error && <Banner tone="danger">{error}</Banner>}

      {item && (
        <Card className="space-y-4">
          <div className="flex items-center justify-between">
            <Chip tone={item.status === "signed" ? "success" : "warning"}>
              {t(`tilxat.status.${item.status}`)}
            </Chip>
            <NeedsReviewChip />
          </div>

          <div className="font-mono-tabular text-2xl font-bold" style={{ color: "var(--primary)" }}>
            {formatUzs(item.amountUzs, "uz_lat")}
          </div>
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>
            ({item.amountInWords}) · Muddat: {formatDateLocalized(item.dueDate, "uz_lat")}
          </div>

          <p className="text-sm leading-relaxed">{item.termsSummary}</p>

          <Banner tone="warning">{item.eConfirmNotice}</Banner>

          {item.status === "pending_counterparty" ? (
            <div className="space-y-3">
              <input
                className="haqli-input"
                value={signerName}
                onChange={(e) => setSignerName(e.target.value)}
                placeholder="F.I.O."
              />
              <input
                className="haqli-input font-mono-tabular text-sm"
                value={signerPassport}
                onChange={(e) => setSignerPassport(e.target.value)}
                placeholder={t("tilxat.passportOpt")}
              />
              <label className="flex items-start gap-2 text-xs cursor-pointer">
                <input
                  type="checkbox"
                  checked={agreed}
                  onChange={(e) => setAgreed(e.target.checked)}
                  className="mt-0.5 h-4 w-4 accent-[var(--primary)]"
                />
                <span>{t("tilxat.publicAgree")}</span>
              </label>
              <Button fullWidth disabled={!agreed} loading={submitting} onClick={handleSign}>
                <CheckCircle2 className="h-4 w-4" />
                {t("tilxat.publicSignBtn")}
              </Button>
            </div>
          ) : (
            <Banner tone="success">
              Ikki tomonlama tasdiqlangan · SHA-256: {item.docHash.slice(0, 16)}
            </Banner>
          )}
        </Card>
      )}
    </div>
  );
}
