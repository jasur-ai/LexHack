import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, MicOff, Pause, Play, Sparkles, Square, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { haptics } from "../../tma/sdk";
import { Banner } from "../../ui/Banner";
import { Button } from "../../ui/Button";

interface VoiceCaptureProps {
  onSubmitAudio: (file: File) => void;
  onSubmitText: (text: string) => void;
}

const MAX_DURATION_SEC = 120;
const SILENCE_THRESHOLD_DB = -45;
const SILENCE_STOP_MS = 2500;

const SAMPLE_VOICE =
  "Alisher Rahimovga besh million so'm qarz berdim, 25-dekabr 2026 kuni qaytaradi, pasport AD4512987";

function selectBestAudioMime(): string {
  if (typeof MediaRecorder === "undefined") return "";
  const candidates = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"];
  return candidates.find((m) => MediaRecorder.isTypeSupported(m)) ?? "";
}

export function VoiceCapture({ onSubmitAudio, onSubmitText }: VoiceCaptureProps) {
  const { t } = useTranslation();
  const [consentGiven, setConsentGiven] = useState(false);
  const [state, setState] = useState<"idle" | "recording" | "paused">("idle");
  const [elapsedSec, setElapsedSec] = useState(0);
  const [bars, setBars] = useState<number[]>(Array(16).fill(12));
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [manualText, setManualText] = useState("");

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const rafRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);
  const spokeOnceRef = useRef(false);
  const silenceStartRef = useRef<number | null>(null);
  const cancelledRef = useRef(false);

  const cleanupAudio = useCallback(() => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    if (timerRef.current !== null) window.clearInterval(timerRef.current);
    rafRef.current = null;
    timerRef.current = null;
    streamRef.current?.getTracks().forEach((tr) => tr.stop());
    streamRef.current = null;
    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;
  }, []);

  useEffect(() => {
    const onHide = () => {
      if (document.hidden && recorderRef.current?.state === "recording") {
        recorderRef.current.pause();
        setState("paused");
      }
    };
    document.addEventListener("visibilitychange", onHide);
    return () => {
      document.removeEventListener("visibilitychange", onHide);
      cleanupAudio();
    };
  }, [cleanupAudio]);

  const stopRecording = useCallback((discard = false) => {
    cancelledRef.current = discard;
    haptics.impact("light");
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    } else {
      cleanupAudio();
      setState("idle");
    }
  }, [cleanupAudio]);

  const startRecording = async () => {
    setErrorKey(null);
    cancelledRef.current = false;
    spokeOnceRef.current = false;
    silenceStartRef.current = null;
    setElapsedSec(0);

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setErrorKey("rec.err.mic_unavailable");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = selectBestAudioMime();
      const rec = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      chunksRef.current = [];

      rec.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunksRef.current.push(ev.data);
      };
      rec.onstop = () => {
        const finalMime = rec.mimeType || mimeType || "audio/webm";
        const ext = finalMime.includes("ogg") ? "ogg" : finalMime.includes("mp4") ? "m4a" : "webm";
        const blob = new Blob(chunksRef.current, { type: finalMime });
        cleanupAudio();
        setState("idle");
        if (!cancelledRef.current && blob.size > 0) {
          onSubmitAudio(new File([blob], `haqli-voice-${Date.now()}.${ext}`, { type: finalMime }));
        }
      };

      // Live AnalyserNode waveform + -45 dB silence auto-stop (§7)
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      const dataArr = new Uint8Array(analyser.frequencyBinCount);
      const timeArr = new Float32Array(analyser.fftSize);

      const tick = () => {
        analyser.getByteFrequencyData(dataArr);
        analyser.getFloatTimeDomainData(timeArr);
        let sumSq = 0;
        for (let i = 0; i < timeArr.length; i++) {
          const s = timeArr[i] ?? 0;
          sumSq += s * s;
        }
        const rms = Math.sqrt(sumSq / timeArr.length);
        const db = rms > 0 ? 20 * Math.log10(rms) : -100;

        if (db > SILENCE_THRESHOLD_DB + 6) {
          spokeOnceRef.current = true;
          silenceStartRef.current = null;
        } else if (spokeOnceRef.current && db < SILENCE_THRESHOLD_DB) {
          if (silenceStartRef.current === null) {
            silenceStartRef.current = Date.now();
          } else if (Date.now() - silenceStartRef.current >= SILENCE_STOP_MS) {
            stopRecording(false);
            return;
          }
        }

        const nextBars = Array.from({ length: 16 }, (_, idx) => {
          const val = dataArr[idx * 3] ?? 0;
          return Math.max(10, Math.min(100, Math.round((val / 255) * 100)));
        });
        setBars(nextBars);
        rafRef.current = requestAnimationFrame(tick);
      };

      recorderRef.current = rec;
      rec.start(250);
      haptics.impact("light");
      setState("recording");
      rafRef.current = requestAnimationFrame(tick);

      timerRef.current = window.setInterval(() => {
        setElapsedSec((prev) => {
          if (prev + 1 >= MAX_DURATION_SEC) {
            stopRecording(false);
            return MAX_DURATION_SEC;
          }
          return prev + 1;
        });
      }, 1000);
    } catch (err) {
      const name = err instanceof Error ? err.name : "";
      if (name === "NotAllowedError") setErrorKey("rec.err.mic_denied");
      else if (name === "NotFoundError") setErrorKey("rec.err.mic_not_found");
      else setErrorKey("rec.err.mic_unavailable");
    }
  };

  const togglePause = () => {
    const rec = recorderRef.current;
    if (!rec) return;
    if (rec.state === "recording") {
      rec.pause();
      setState("paused");
    } else if (rec.state === "paused") {
      rec.resume();
      setState("recording");
    }
  };

  const mm = String(Math.floor(elapsedSec / 60)).padStart(2, "0");
  const ss = String(elapsedSec % 60).padStart(2, "0");

  return (
    <div className="space-y-4">
      {!consentGiven && state === "idle" && (
        <Banner tone="info" title={t("rec.voiceConsentTitle")}>
          <div className="space-y-2">
            <p>{t("rec.voiceConsentDesc")}</p>
            <Button
              size="sm"
              onClick={() => {
                setConsentGiven(true);
                startRecording();
              }}
            >
              <Mic className="h-4 w-4" />
              {t("rec.voiceAllowAndStart")}
            </Button>
          </div>
        </Banner>
      )}

      {errorKey && <Banner tone="warning">{t(errorKey)}</Banner>}

      {/* Waveform & Recording Deck */}
      <div
        style={{ backgroundColor: "var(--surface-2)" }}
        className="flex flex-col items-center gap-4 rounded-2xl p-5"
      >
        <div className="flex h-16 items-end gap-1.5" aria-hidden="true">
          {bars.map((h, i) => (
            <div
              key={i}
              style={{
                height: `${state === "recording" ? h : 16}%`,
                backgroundColor: state === "recording" ? "var(--primary)" : "var(--border)",
              }}
              className="w-2 rounded-full transition-all duration-75"
            />
          ))}
        </div>

        <div className="font-mono-tabular text-lg font-bold" aria-live="polite">
          {mm}:{ss} <span className="text-xs font-normal" style={{ color: "var(--text-muted)" }}>/ 02:00</span>
        </div>

        {state === "idle" ? (
          <div className="flex flex-wrap items-center justify-center gap-2">
            <Button
              className="min-h-[48px]"
              onClick={() => {
                setConsentGiven(true);
                startRecording();
              }}
            >
              <Mic className="h-4 w-4" />
              {t("recognition.voiceRecord")}
            </Button>
            <Button variant="secondary" className="min-h-[48px]" onClick={() => onSubmitText(SAMPLE_VOICE)}>
              <Sparkles className="h-4 w-4" />
              {t("recognition.sampleBtn")}
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Button variant="secondary" className="min-h-[48px]" onClick={togglePause}>
              {state === "recording" ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            </Button>
            <Button variant="primary" className="min-h-[48px]" onClick={() => stopRecording(false)}>
              <Square className="h-4 w-4" />
              {t("recognition.voiceStop")}
            </Button>
            <Button variant="danger" className="min-h-[48px]" onClick={() => stopRecording(true)} aria-label={t("common.cancel")}>
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

      {/* Native Keyboard Dictation / Text Fallback (§7, §10) */}
      <div className="space-y-2">
        <div className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
          <MicOff className="h-3.5 w-3.5" />
          <span>{t("rec.voiceManualHint")}</span>
        </div>
        <textarea
          rows={3}
          className="haqli-input text-sm"
          value={manualText}
          onChange={(e) => setManualText(e.target.value)}
          placeholder={SAMPLE_VOICE}
        />
        <Button fullWidth disabled={manualText.trim().length < 5} onClick={() => onSubmitText(manualText)}>
          {t("recognition.runBtn")}
        </Button>
      </div>
    </div>
  );
}
