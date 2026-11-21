/**
 * Recognition job lifecycle hook: upload -> SSE stage streaming -> 8s manual escape -> confirm / purge (§9, §10).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  type RecognitionResultDTO,
  type RecognitionStageEventDTO,
} from "../../lib/api";
import { compressImageBeforeUpload } from "./quality";

const OFFLINE_QUEUE_KEY = "haqli_rec_offline_queue_v1";

export interface UseRecognitionJobState {
  status: "idle" | "uploading" | "processing" | "review" | "error";
  jobId: string | null;
  stages: RecognitionStageEventDTO[];
  result: RecognitionResultDTO | null;
  errorKey: string | null;
  showManualEscape: boolean;
  offlineQueued: boolean;
  startJob: (params: {
    kind: "document" | "receipt" | "id_mrz" | "voice" | "qr";
    file?: File | null;
    text?: string;
    langHint?: string;
  }) => Promise<void>;
  confirmJob: (
    edits: Array<{ key: string; value: unknown }>,
    docType?: string | null
  ) => Promise<{ routeHint: RecognitionResultDTO["routeHint"]; fields: RecognitionResultDTO["fields"] }>;
  purgeJob: () => Promise<void>;
  reset: () => void;
}

export function useRecognitionJob(): UseRecognitionJobState {
  const [status, setStatus] = useState<UseRecognitionJobState["status"]>("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [stages, setStages] = useState<RecognitionStageEventDTO[]>([]);
  const [result, setResult] = useState<RecognitionResultDTO | null>(null);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [showManualEscape, setShowManualEscape] = useState(false);
  const [offlineQueued, setOfflineQueued] = useState(false);

  const esRef = useRef<EventSource | null>(null);
  const escapeTimerRef = useRef<number | null>(null);

  const cleanupStreams = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    if (escapeTimerRef.current !== null) {
      window.clearTimeout(escapeTimerRef.current);
      escapeTimerRef.current = null;
    }
  }, []);

  useEffect(() => cleanupStreams, [cleanupStreams]);

  const reset = useCallback(() => {
    cleanupStreams();
    setStatus("idle");
    setJobId(null);
    setStages([]);
    setResult(null);
    setErrorKey(null);
    setShowManualEscape(false);
    setOfflineQueued(false);
  }, [cleanupStreams]);

  const pollFinalResult = useCallback(async (id: string) => {
    for (let attempt = 0; attempt < 25; attempt++) {
      try {
        const detail = await api.getRecognitionJob(id);
        if (detail.stages?.length) setStages(detail.stages);
        if (detail.status === "done" || detail.status === "failed") {
          setResult(detail.result);
          setStatus("review");
          return;
        }
      } catch {
        // Retry briefly
      }
      await new Promise((r) => setTimeout(r, 350));
    }
    setErrorKey("rec.err.timeout");
    setStatus("error");
  }, []);

  const startJob = useCallback(
    async (params: {
      kind: "document" | "receipt" | "id_mrz" | "voice" | "qr";
      file?: File | null;
      text?: string;
      langHint?: string;
    }) => {
      cleanupStreams();
      setErrorKey(null);
      setStages([]);
      setResult(null);
      setShowManualEscape(false);
      setOfflineQueued(false);

      // Offline handling: queue non-MRZ jobs when offline; never queue MRZ (§10)
      if (typeof navigator !== "undefined" && !navigator.onLine) {
        if (params.kind !== "id_mrz" && params.text) {
          try {
            const existing = JSON.parse(localStorage.getItem(OFFLINE_QUEUE_KEY) || "[]") as unknown[];
            existing.push({ kind: params.kind, text: params.text, queuedAt: Date.now() });
            localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(existing.slice(-5)));
            setOfflineQueued(true);
          } catch {
            // Ignore storage quota errors
          }
        }
        setErrorKey("rec.err.offline");
        setStatus("error");
        return;
      }

      setStatus("uploading");
      // Show manual escape button after 8 seconds (§5, §10)
      escapeTimerRef.current = window.setTimeout(() => setShowManualEscape(true), 8000);

      try {
        const fd = new FormData();
        fd.append("kind", params.kind);
        if (params.text) fd.append("text_input", params.text);
        if (params.langHint) fd.append("lang_hint", params.langHint);
        fd.append("timezone", Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Tashkent");

        if (params.file) {
          const prepared = await compressImageBeforeUpload(params.file);
          fd.append("file", prepared);
        }

        const resp = await api.createRecognitionJob(fd);
        setJobId(resp.jobId);

        // Inline 200 response (e.g. `id_mrz` processed strictly in memory)
        if (resp.result) {
          if (resp.stages) setStages(resp.stages);
          setResult(resp.result);
          setStatus("review");
          cleanupStreams();
          return;
        }

        // Async 202 response -> subscribe to SSE stream + fallback poll
        setStatus("processing");
        const streamUrl = resp.streamUrl || `/api/stream/${resp.jobId}`;
        if (typeof EventSource !== "undefined") {
          const es = new EventSource(streamUrl);
          esRef.current = es;
          es.onmessage = (ev) => {
            try {
              const parsed = JSON.parse(ev.data) as RecognitionStageEventDTO;
              setStages((prev) => {
                const idx = prev.findIndex((p) => p.stage === parsed.stage);
                if (idx >= 0) {
                  const copy = [...prev];
                  copy[idx] = parsed;
                  return copy;
                }
                return [...prev, parsed];
              });
              if (parsed.stage === "done") {
                es.close();
                esRef.current = null;
                pollFinalResult(resp.jobId);
              }
            } catch {
              // Ignore non-JSON comments
            }
          };
          es.onerror = () => {
            es.close();
            esRef.current = null;
            pollFinalResult(resp.jobId);
          };
        } else {
          await pollFinalResult(resp.jobId);
        }
      } catch (err) {
        cleanupStreams();
        setErrorKey(err instanceof Error ? err.message : "rec.err.upload_failed");
        setStatus("error");
      }
    },
    [cleanupStreams, pollFinalResult]
  );

  const confirmJob = useCallback(
    async (edits: Array<{ key: string; value: unknown }>, docType?: string | null) => {
      if (!result) throw new Error("No recognition result to confirm.");
      // Inline MRZ jobs are never persisted to DB — confirm client-side directly (§6.4, §9)
      if (result.kind === "id_mrz") {
        const editMap = new Map(edits.map((e) => [e.key, e.value]));
        const confirmedFields = result.fields.map((f) =>
          editMap.has(f.key)
            ? { ...f, value: String(editMap.get(f.key) ?? ""), display: String(editMap.get(f.key) ?? ""), confidence: 1, source: "user" as const, needsConfirm: false }
            : { ...f, needsConfirm: false }
        );
        return { routeHint: result.routeHint, fields: confirmedFields };
      }
      if (!jobId) throw new Error("Missing job ID.");
      const res = await api.confirmRecognitionJob(jobId, { fields: edits, docType });
      return { routeHint: res.routeHint, fields: res.fields };
    },
    [jobId, result]
  );

  const purgeJob = useCallback(async () => {
    if (jobId && result?.kind !== "id_mrz") {
      try {
        await api.deleteRecognitionJob(jobId);
      } catch {
        // Ignore already-purged
      }
    }
    reset();
  }, [jobId, result?.kind, reset]);

  return {
    status,
    jobId,
    stages,
    result,
    errorKey,
    showManualEscape,
    offlineQueued,
    startJob,
    confirmJob,
    purgeJob,
    reset,
  };
}
