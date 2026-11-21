import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, Flashlight, Image as ImageIcon, Sparkles, Upload } from "lucide-react";
import { useTranslation } from "react-i18next";
import { haptics } from "../../tma/sdk";
import { Banner } from "../../ui/Banner";
import { Button } from "../../ui/Button";
import { computeImageDataQuality, type ClientQualitySnapshot } from "./quality";

interface CameraCaptureProps {
  mode: "document" | "receipt" | "id_mrz";
  onCaptureFile: (file: File, previewUrl: string) => void;
  onSubmitText: (text: string) => void;
}

const SAMPLE_TEXTS: Record<CameraCaptureProps["mode"], string> = {
  document:
    "Toshkent shahar IIBB YHXB\nJarima qarori № YHX-2026-90412\nSana: 14.04.2026\nMJtK 128-3-modda, davlat raqami 01 A 777 AA.\nJarima summasi: 1 875 000 so'm",
  receipt:
    "Texnomart Savdo MCHJ\nSTIR: 304567891\nKassa cheki #4421\nSana: 2026-03-18\nSmartfon X12 4 200 000 so'm\nTo'lov turi: Uzcard terminal\nJami: 4 200 000 so'm",
  id_mrz:
    "P<UZBKARIMOV<<AZIZBEK<<<<<<<<<<<<<<<<<<<<<<<\nAD12345676UZB9504126M3204122<<<<<<<<<<<<<<02",
};

export function CameraCapture({ mode, onCaptureFile, onSubmitText }: CameraCaptureProps) {
  const { t } = useTranslation();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const prevLumaRef = useRef<Uint8Array | null>(null);
  const stableSinceRef = useRef<number | null>(null);
  const autoFiredRef = useRef(false);

  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<"denied" | "unavailable" | null>(null);
  const [torchOn, setTorchOn] = useState(false);
  const [quality, setQuality] = useState<ClientQualitySnapshot | null>(null);
  const [blurAttempts, setBlurAttempts] = useState(0);
  const [pasteText, setPasteText] = useState("");
  const [showTextBox, setShowTextBox] = useState(false);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((tr) => tr.stop());
    streamRef.current = null;
    setCameraActive(false);
    setTorchOn(false);
  }, []);

  useEffect(() => stopCamera, [stopCamera]);

  const startCamera = async () => {
    setCameraError(null);
    autoFiredRef.current = false;
    stableSinceRef.current = null;
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError("unavailable");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1920 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraActive(true);
    } catch (err) {
      const name = err instanceof Error ? err.name : "";
      setCameraError(name === "NotAllowedError" ? "denied" : "unavailable");
    }
  };

  const captureFrame = useCallback(() => {
    const video = videoRef.current;
    if (!video || !video.videoWidth || !video.videoHeight) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0);
    haptics.impact("medium");
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const file = new File([blob], `haqli-${mode}-${Date.now()}.jpg`, { type: "image/jpeg" });
        const preview = URL.createObjectURL(blob);
        stopCamera();
        onCaptureFile(file, preview);
      },
      "image/jpeg",
      0.88
    );
  }, [mode, onCaptureFile, stopCamera]);

  // 200ms client quality loop + 600ms stable auto-capture (§5.1, §10)
  useEffect(() => {
    if (!cameraActive) return;
    const sampleCanvas = document.createElement("canvas");
    sampleCanvas.width = 240;
    sampleCanvas.height = 180;
    const ctx = sampleCanvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return;

    const id = window.setInterval(() => {
      const video = videoRef.current;
      if (!video || video.readyState < 2 || autoFiredRef.current) return;
      ctx.drawImage(video, 0, 0, 240, 180);
      const data = ctx.getImageData(0, 0, 240, 180);
      const { snapshot, luma } = computeImageDataQuality(data.data, 240, 180, prevLumaRef.current);
      prevLumaRef.current = luma;
      setQuality(snapshot);

      if (snapshot.ok) {
        if (stableSinceRef.current === null) {
          stableSinceRef.current = Date.now();
        } else if (Date.now() - stableSinceRef.current >= 600) {
          autoFiredRef.current = true;
          captureFrame();
        }
      } else {
        stableSinceRef.current = null;
        if (snapshot.hintKey === "rec.hint.hold_still") {
          setBlurAttempts((n) => n + 1);
        }
      }
    }, 200);

    return () => window.clearInterval(id);
  }, [cameraActive, captureFrame]);

  const toggleTorch = async () => {
    const track = streamRef.current?.getVideoTracks()[0];
    if (!track) return;
    const next = !torchOn;
    try {
      await track.applyConstraints({ advanced: [{ torch: next } as MediaTrackConstraintSet] });
      setTorchOn(next);
    } catch {
      // Device does not support torch
    }
  };

  const handleGalleryPick = (file: File | undefined) => {
    if (!file) return;
    const preview = file.type.startsWith("image/") ? URL.createObjectURL(file) : "";
    stopCamera();
    onCaptureFile(file, preview);
  };

  const bracketColor = quality?.ok ? "var(--primary)" : "#FFFFFF";

  return (
    <div className="space-y-3">
      {mode === "id_mrz" && <Banner tone="info">{t("recognition.mrzNotice")}</Banner>}

      {cameraError === "denied" && (
        <Banner tone="warning" title={t("rec.err.camera_denied_title")}>
          {t("rec.err.camera_denied_desc")}
        </Banner>
      )}
      {blurAttempts > 15 && (
        <Banner tone="warning">{t("rec.err.blurry_gallery_hint")}</Banner>
      )}

      {/* Camera Preview Frame with Edge Brackets & MRZ Guide Strip (§10) */}
      <div
        style={{ backgroundColor: "#0B1120", borderColor: "var(--border)" }}
        className="relative aspect-[4/3] w-full overflow-hidden rounded-2xl border flex items-center justify-center"
      >
        <video
          ref={videoRef}
          playsInline
          muted
          className={`h-full w-full object-cover ${cameraActive ? "block" : "hidden"}`}
        />

        {cameraActive ? (
          <>
            {/* Rounded corner brackets turning white -> teal when stable */}
            <div className="pointer-events-none absolute inset-5">
              <div className="absolute left-0 top-0 h-7 w-7 rounded-tl-xl border-l-4 border-t-4 transition-colors" style={{ borderColor: bracketColor }} />
              <div className="absolute right-0 top-0 h-7 w-7 rounded-tr-xl border-r-4 border-t-4 transition-colors" style={{ borderColor: bracketColor }} />
              <div className="absolute bottom-0 left-0 h-7 w-7 rounded-bl-xl border-b-4 border-l-4 transition-colors" style={{ borderColor: bracketColor }} />
              <div className="absolute bottom-0 right-0 h-7 w-7 rounded-br-xl border-b-4 border-r-4 transition-colors" style={{ borderColor: bracketColor }} />

              {mode === "id_mrz" && (
                <div
                  style={{ borderColor: bracketColor }}
                  className="absolute inset-x-2 bottom-3 h-14 rounded-lg border-2 border-dashed bg-black/30 flex items-center justify-center text-[11px] font-mono-tabular text-white/90"
                >
                  P&lt;UZB &middot;&middot;&middot;&middot;&middot;&middot;&middot;&middot; MRZ &middot;&middot;&middot;&middot;&middot;&middot;&middot;&middot;
                </div>
              )}
            </div>

            {/* Single status hint chip above shutter */}
            <div
              aria-live="polite"
              style={{
                backgroundColor: quality?.ok ? "var(--primary)" : "rgba(11, 17, 32, 0.78)",
                color: "#FFFFFF",
              }}
              className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full px-3.5 py-1 text-xs font-bold shadow"
            >
              {t(quality?.hintKey ?? "rec.hint.hold_still")}
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center gap-3 p-5 text-center text-white">
            <Camera className="h-9 w-9 opacity-80" />
            <Button onClick={startCamera}>
              <Camera className="h-4 w-4" />
              {t("rec.openCamera")}
            </Button>
          </div>
        )}
      </div>

      {/* Lower Controls: Gallery · Shutter · Torch (touch targets >= 48px, §10) */}
      <div className="flex items-center justify-between gap-2">
        <label
          style={{ backgroundColor: "var(--surface-2)", color: "var(--text)" }}
          className="flex min-h-[48px] flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-xl px-3 text-xs font-bold"
        >
          <ImageIcon className="h-4 w-4" style={{ color: "var(--primary)" }} />
          <span>{t("rec.gallery")}</span>
          <input
            type="file"
            accept="image/*,application/pdf"
            className="hidden"
            onChange={(e) => handleGalleryPick(e.target.files?.[0])}
          />
        </label>

        {cameraActive && (
          <>
            <button
              type="button"
              onClick={captureFrame}
              aria-label={t("rec.shutter")}
              style={{ borderColor: "var(--primary)" }}
              className="flex h-14 w-14 items-center justify-center rounded-full border-4 bg-white shadow-lg cursor-pointer active:scale-95"
            >
              <span className="h-10 w-10 rounded-full" style={{ backgroundColor: "var(--primary)" }} />
            </button>
            <button
              type="button"
              onClick={toggleTorch}
              aria-label={t("rec.torch")}
              style={{
                backgroundColor: torchOn ? "var(--primary)" : "var(--surface-2)",
                color: torchOn ? "#FFFFFF" : "var(--text)",
              }}
              className="flex min-h-[48px] min-w-[48px] items-center justify-center rounded-xl cursor-pointer"
            >
              <Flashlight className="h-5 w-5" />
            </button>
          </>
        )}

        <Button
          variant="secondary"
          className="min-h-[48px]"
          onClick={() => onSubmitText(SAMPLE_TEXTS[mode])}
        >
          <Sparkles className="h-4 w-4" />
          <span>{t("recognition.sampleBtn")}</span>
        </Button>
      </div>

      {/* Collapsible Manual / Text Paste Fallback */}
      <div className="pt-1">
        <button
          type="button"
          onClick={() => setShowTextBox((v) => !v)}
          className="text-xs font-semibold underline cursor-pointer"
          style={{ color: "var(--text-muted)" }}
        >
          {t("rec.pasteTextFallback")}
        </button>
        {showTextBox && (
          <div className="mt-2 space-y-2">
            <textarea
              rows={4}
              className="haqli-input text-xs font-mono-tabular"
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder={SAMPLE_TEXTS[mode]}
            />
            <Button
              fullWidth
              disabled={pasteText.trim().length < 5}
              onClick={() => onSubmitText(pasteText)}
            >
              <Upload className="h-4 w-4" />
              {t("recognition.runBtn")}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
