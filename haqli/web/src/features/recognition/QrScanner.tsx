import { useEffect, useRef, useState } from "react";
import { Camera, FileCheck, QrCode, ShieldAlert, ShieldCheck, Upload } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api, type VerifyDocumentResponse } from "../../lib/api";
import { haptics } from "../../tma/sdk";
import { Banner } from "../../ui/Banner";
import { Button } from "../../ui/Button";
import { Chip } from "../../ui/Chip";

export function QrScanner() {
  const { t } = useTranslation();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [scanning, setScanning] = useState(false);
  const [verifyInput, setVerifyInput] = useState("");
  const [verifyFile, setVerifyFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<VerifyDocumentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const stopScan = () => {
    streamRef.current?.getTracks().forEach((tr) => tr.stop());
    streamRef.current = null;
    setScanning(false);
  };

  useEffect(() => stopScan, []);

  const runVerify = async (overridePayload?: string) => {
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      const inputVal = (overridePayload ?? verifyInput).trim();
      if (inputVal.includes("/v/")) fd.append("qr_payload", inputVal);
      else if (inputVal) fd.append("doc_id", inputVal);
      if (verifyFile) fd.append("file", verifyFile);

      const res = await api.verifyDocument(fd);
      setResult(res);
      haptics.notify(res.status === "valid" ? "success" : "error");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setBusy(false);
    }
  };

  const startLiveQrScan = async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError(t("rec.err.camera_denied_desc"));
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setScanning(true);

      // Continuous QR decode via BarcodeDetector if available on browser/WebView
      const BD = (window as unknown as { BarcodeDetector?: new (opts: { formats: string[] }) => { detect: (src: HTMLVideoElement) => Promise<Array<{ rawValue: string }>> } }).BarcodeDetector;
      if (BD && videoRef.current) {
        const detector = new BD({ formats: ["qr_code"] });
        const poll = window.setInterval(async () => {
          if (!videoRef.current || !streamRef.current) {
            window.clearInterval(poll);
            return;
          }
          try {
            const codes = await detector.detect(videoRef.current);
            const first = codes.find((c) => c.rawValue.includes("/v/"));
            if (first) {
              window.clearInterval(poll);
              stopScan();
              setVerifyInput(first.rawValue);
              runVerify(first.rawValue);
            }
          } catch {
            // Keep scanning
          }
        }, 300);
      }
    } catch {
      setError(t("rec.err.camera_denied_desc"));
    }
  };

  return (
    <div className="space-y-4">
      {scanning && (
        <div className="relative aspect-[4/3] overflow-hidden rounded-2xl bg-black">
          <video ref={videoRef} playsInline muted className="h-full w-full object-cover" />
          <div className="absolute inset-x-0 bottom-3 flex justify-center">
            <Button size="sm" variant="secondary" onClick={stopScan}>
              {t("common.close")}
            </Button>
          </div>
        </div>
      )}

      {!scanning && (
        <Button variant="secondary" fullWidth className="min-h-[48px]" onClick={startLiveQrScan}>
          <Camera className="h-4 w-4" />
          <QrCode className="h-4 w-4" />
          <span>{t("rec.scanQrCamera")}</span>
        </Button>
      )}

      <div className="space-y-2">
        <input
          className="haqli-input font-mono-tabular text-sm"
          value={verifyInput}
          onChange={(e) => setVerifyInput(e.target.value)}
          placeholder={t("recognition.verifyPlaceholder")}
        />
        <label
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          className="flex min-h-[48px] cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed p-3 text-xs font-semibold"
        >
          <Upload className="h-4 w-4" style={{ color: "var(--primary)" }} />
          <span>{verifyFile ? verifyFile.name : t("rec.uploadPdfVerify")}</span>
          <input
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={(e) => setVerifyFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <Button fullWidth className="min-h-[48px]" loading={busy} onClick={() => runVerify()}>
          <FileCheck className="h-4 w-4" />
          {t("recognition.verifyBtn")}
        </Button>
      </div>

      {error && <Banner tone="danger">{error}</Banner>}

      {/* Large Green / Red Authenticity Result Card (§8) */}
      {result && (
        <div
          style={{
            backgroundColor:
              result.status === "valid"
                ? "var(--success-soft)"
                : result.status === "tampered"
                  ? "var(--danger-soft)"
                  : "var(--warning-soft)",
            borderColor:
              result.status === "valid"
                ? "var(--success)"
                : result.status === "tampered"
                  ? "var(--danger)"
                  : "var(--warning)",
          }}
          className="rounded-2xl border-2 p-4 space-y-3"
          role="status"
          aria-live="polite"
        >
          <div className="flex items-center gap-3">
            {result.status === "valid" ? (
              <ShieldCheck className="h-10 w-10 shrink-0" style={{ color: "var(--success)" }} />
            ) : (
              <ShieldAlert className="h-10 w-10 shrink-0" style={{ color: "var(--danger)" }} />
            )}
            <div>
              <Chip tone={result.status === "valid" ? "success" : result.status === "tampered" ? "danger" : "warning"}>
                {result.status.toUpperCase()}
              </Chip>
              <div className="mt-1 text-sm font-bold">
                {result.status === "valid"
                  ? t("rec.verify.validTitle")
                  : result.status === "tampered"
                    ? t("rec.verify.tamperedTitle")
                    : t("rec.verify.unknownTitle")}
              </div>
            </div>
          </div>

          {result.mismatchedFields && result.mismatchedFields.length > 0 && (
            <div className="text-xs font-bold" style={{ color: "var(--danger)" }}>
              {t("rec.verify.mismatched")}: {result.mismatchedFields.join(", ")}
            </div>
          )}

          {result.checkedFields && Object.keys(result.checkedFields).length > 0 && (
            <div className="rounded-xl p-2.5 text-xs space-y-1 font-mono-tabular" style={{ backgroundColor: "var(--surface)" }}>
              {Object.entries(result.checkedFields).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2">
                  <span style={{ color: "var(--text-muted)" }}>{k}</span>
                  <span className="font-semibold">{v}</span>
                </div>
              ))}
              {result.docHashShort && (
                <div className="flex justify-between gap-2 border-t pt-1" style={{ borderColor: "var(--border)" }}>
                  <span style={{ color: "var(--text-muted)" }}>SHA-256</span>
                  <span>{result.docHashShort}</span>
                </div>
              )}
            </div>
          )}

          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            {result.eConfirmNotice || result.detail}
          </p>
        </div>
      )}
    </div>
  );
}
