/**
 * Typed HTTP + WebSocket client for Haqli FastAPI backend (§10).
 */
import { getTelegramInitData } from "../tma/sdk";
import { getDeviceId } from "./device";
import {
  DEFAULT_CONSTANTS,
  useAppStore,
  type ConstantsMeta,
  type LangCode,
  type ThemePref,
  type UserProfile,
  type UserRole,
} from "./store";

export interface CitationItem {
  id: string;
  instrument: string;
  article: string;
  summary: string;
  effectiveFrom: string;
  sourceUrl: string;
  status: string;
  verifiedBy?: string | null;
}

export interface DisputeCaseDTO {
  id: string;
  category: "labor" | "consumer" | "rental" | "traffic" | "debt";
  respondentName: string;
  incidentDate: string | null;
  claimAmountUzs: string;
  delayDays: number;
  computed: Record<string, unknown>;
  structuredFacts: Record<string, unknown>;
  citations: CitationItem[];
  hasUnverifiedLegalData: boolean;
  caseStrength: number;
  strengthBreakdown: Record<string, number>;
  assessmentText: string;
  talabnomaText: string;
  complaintText: string;
  evidenceIds: string[];
  status: string;
  docHash: string | null;
  pdfUrl: string | null;
  localeUsed: LangCode;
  engine: string;
  createdAt: string;
  jobId?: string;
}

export interface TilxatDTO {
  id: string;
  docType: "loan" | "deposit" | "service";
  partyAName: string;
  partyAPassportMasked: string | null;
  partyASignedAt: string | null;
  partyBName: string;
  partyBPassportMasked: string | null;
  partyBSignedAt: string | null;
  amountUzs: string;
  amountInWords: string;
  bhmRatio: string;
  requiresWritten: boolean;
  thresholdSnapshot: Record<string, unknown>;
  dueDate: string;
  dailyPenaltyPercent: string;
  termsSummary: string;
  docHash: string;
  status: "pending_counterparty" | "signed" | "expired" | "revoked";
  expiresAt: string;
  pdfUrl: string | null;
  verifyUrl: string;
  eConfirmNotice: string;
  createdAt: string;
  signToken?: string;
  signDeepLink?: string;
  signWebUrl?: string;
}

export interface ClauseFinding {
  id: string;
  severity: "critical" | "warning" | "safe";
  quotedClause: string;
  startOffset?: number;
  endOffset?: number;
  whyRisky: string;
  safeAlternative: string;
  legalRefs: string[];
  citations: CitationItem[];
  hasUnverifiedLegalData: boolean;
}

export interface ContractAuditDTO {
  id: string;
  title: string;
  source: string;
  languageDetected: string;
  safetyScore: number;
  verdict: "safe" | "caution" | "high_risk";
  redFlags: ClauseFinding[];
  warnings: ClauseFinding[];
  safeClauses: ClauseFinding[];
  docHash: string | null;
  pdfUrl: string;
  engine: string;
  createdAt: string;
}

export interface LawAlertDTO {
  id: string;
  decreeRef: string;
  publishedDate: string;
  tags: string[];
  title: string;
  whatChanged: string;
  walletImpact: string;
  actionLabel: string;
  actionRoute: string;
  legalRefId: string;
  status: string;
}

export interface AdvocateLeadDTO {
  id: string;
  caseId: string;
  advocateId: string | null;
  status: string;
  platformFeePercent: number;
  brief: Record<string, unknown>;
  declineReason: string | null;
  acceptedAt: string | null;
  createdAt: string;
}

export interface RecognitionFieldDTO {
  key: string;
  value: string | number | null;
  display: string;
  confidence: number;
  source: "rule" | "ocr" | "llm" | "user";
  span: [number, number] | null;
  bbox: [number, number, number, number] | null;
  needsConfirm: boolean;
}

export interface RecognitionStageEventDTO {
  jobId: string;
  stage: "received" | "quality" | "preprocess" | "recognize" | "classify" | "parse" | "validate" | "done";
  state: "pending" | "running" | "ok" | "warn" | "failed" | "skipped";
  elapsedMs: number;
  messageKey: string | null;
}

export interface RouteHintDTO {
  target: "himoya" | "tilxat" | "skaner" | "jarima" | "none";
  category: string | null;
  prefill: Record<string, unknown>;
}

export interface RecognitionResultDTO {
  jobId: string;
  kind: "document" | "receipt" | "id_mrz" | "voice" | "qr";
  docType: string | null;
  docTypeConfidence: number | null;
  script: "latn" | "cyrl" | "mixed" | "unknown";
  language: "uz" | "ru" | "mixed" | null;
  engine: string;
  fields: RecognitionFieldDTO[];
  rawTextPreview: string;
  warnings: string[];
  routeHint: RouteHintDTO | null;
  processingTimeMs: number;
  clauses?: Array<{ clauseId: string; text: string; span: [number, number] }>;
  transcript?: string | null;
}

export interface RecognitionJobCreateResponse {
  jobId: string;
  status: string;
  streamUrl?: string;
  stages?: RecognitionStageEventDTO[];
  result?: RecognitionResultDTO;
}

export interface RecognitionJobDetailResponse {
  jobId: string;
  kind: string;
  status: string;
  confirmed: boolean;
  confidence: number;
  stages: RecognitionStageEventDTO[];
  result: RecognitionResultDTO;
  expiresAt: string;
}

export interface VerifyDocumentResponse {
  status: "valid" | "tampered" | "unknown";
  docId: string | null;
  docKind?: string;
  docHashShort?: string;
  sealVerified?: boolean;
  chainVerified?: boolean | null;
  mismatchedFields?: string[];
  checkedFields?: Record<string, string>;
  issuedAt?: string;
  eConfirmNotice?: string;
  detail?: string;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export interface AuthResponse {
  accessToken: string;
  user: UserProfile;
  demoMode: boolean;
  constants: { bhm: string; bhmStatus: string; version: string; talabnomaPriceUzs: string };
}

export interface AgentStatusDTO {
  available: boolean;
  answerMode?: "llm" | "extractive" | string;
  indexedChunks?: number;
  version?: string | null;
  latencyMs?: number;
  reason?: string;
}

export interface AgentSourceInfoDTO {
  id: string;
  name: string;
  kind?: string;
  description?: string;
  url?: string;
  license?: string;
  snapshot?: string | null;
  languages?: string[];
  documents?: number;
  chunks?: number;
  available?: boolean;
}

const AUTH_PATH = "/api/auth/telegram";

async function readErrorDetail(resp: Response): Promise<string> {
  let detail = `HTTP ${resp.status}`;
  try {
    const body = (await resp.json()) as { detail?: unknown; title?: string };
    if (typeof body.detail === "string") detail = body.detail;
    else if (Array.isArray(body.detail) && body.detail.length > 0) {
      const first = body.detail[0] as { msg?: string };
      detail = first?.msg || detail;
    } else if (body.title) detail = body.title;
  } catch {
    // Non-JSON error body.
  }
  return detail;
}

function toConstants(raw: AuthResponse["constants"] | undefined): ConstantsMeta {
  return {
    bhm: Number(raw?.bhm) || DEFAULT_CONSTANTS.bhm,
    bhmStatus: raw?.bhmStatus || DEFAULT_CONSTANTS.bhmStatus,
    version: raw?.version || DEFAULT_CONSTANTS.version,
    talabnomaPriceUzs: Number(raw?.talabnomaPriceUzs) || DEFAULT_CONSTANTS.talabnomaPriceUzs,
  };
}

let authInFlight: Promise<AuthResponse> | null = null;

/**
 * Sign in with Telegram initData inside the Mini App, or as a private per-device guest on the web.
 * Concurrent callers share one request; the session is written to the store before the promise resolves.
 */
export function authenticate(): Promise<AuthResponse> {
  if (!authInFlight) {
    authInFlight = (async () => {
      const resp = await fetch(AUTH_PATH, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          initData: getTelegramInitData(),
          deviceId: getDeviceId(),
          demoName: "Azizbek Karimov",
        }),
      });
      if (!resp.ok) throw new ApiError(resp.status, await readErrorDetail(resp));
      const data = (await resp.json()) as AuthResponse;
      useAppStore.getState().setSession({
        token: data.accessToken,
        user: data.user,
        demoMode: data.demoMode,
        constants: toConstants(data.constants),
      });
      return data;
    })().finally(() => {
      authInFlight = null;
    });
  }
  return authInFlight;
}

function withAuth(init: RequestInit): RequestInit {
  const token = useAppStore.getState().token;
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body !== undefined && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return { ...init, headers };
}

/**
 * fetch() with the session token. Sessions are short-lived JWTs, so a 401 triggers one silent
 * re-login and a single retry; the user never sees an "expired session" error.
 */
export async function authorizedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const resp = await fetch(path, withAuth(init));
  if (resp.status !== 401 || path === AUTH_PATH || init.body instanceof ReadableStream) return resp;
  try {
    await authenticate();
  } catch {
    return resp;
  }
  return fetch(path, withAuth(init));
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await authorizedFetch(path, init);
  if (!resp.ok) throw new ApiError(resp.status, await readErrorDetail(resp));
  return (await resp.json()) as T;
}

export const api = {
  agentStatus() {
    return request<AgentStatusDTO>("/api/agent/status");
  },
  agentSources() {
    return request<{ sources: AgentSourceInfoDTO[]; totalChunks: number }>("/api/agent/sources");
  },

  patchPreferences(payload: {
    fullName?: string;
    language?: LangCode;
    role?: UserRole;
    inviteCode?: string;
    licenseNumber?: string;
    profileTags?: string[];
    themePref?: ThemePref;
    pushEnabled?: boolean;
  }) {
    return request<{ user: UserProfile; accessToken: string }>("/api/auth/preferences", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  grantConsent(version = "2026-v1") {
    return request<{ ok: boolean; consentVersion: string }>("/api/auth/consent", {
      method: "POST",
      body: JSON.stringify({ version, scope: "core_document_processing" }),
    });
  },

  deleteMyData() {
    return request<{ deleted: boolean }>("/api/auth/me", { method: "DELETE" });
  },

  // Himoya (Disputes)
  listDisputes() {
    return request<DisputeCaseDTO[]>("/api/disputes");
  },
  createDisputeDraft(payload: Record<string, unknown>) {
    return request<DisputeCaseDTO>("/api/disputes/drafts", { method: "POST", body: JSON.stringify(payload) });
  },
  patchDisputeDraft(id: string, payload: Record<string, unknown>) {
    return request<DisputeCaseDTO>(`/api/disputes/drafts/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  analyzeDispute(payload: Record<string, unknown>) {
    return request<DisputeCaseDTO>("/api/disputes/analyze", { method: "POST", body: JSON.stringify(payload) });
  },
  payDispute(caseId: string) {
    return request<{ paymentId: string; provider: string; status: string; amountUzs: string }>(
      `/api/disputes/${caseId}/pay`,
      { method: "POST" }
    );
  },
  generateDisputeDocument(caseId: string, type: "talabnoma" | "complaint", locale: LangCode) {
    return request<{ docId: string; type: string; pdfUrl: string; docHash: string }>(
      `/api/disputes/${caseId}/documents?type=${type}&locale=${locale}`,
      { method: "POST" }
    );
  },

  // Tilxat
  listTilxats() {
    return request<TilxatDTO[]>("/api/tilxat");
  },
  parseTilxatText(text: string, locale: LangCode) {
    return request<{ fields: Record<string, string | null>; confidences: Record<string, number> }>("/api/tilxat/parse", {
      method: "POST",
      body: JSON.stringify({ text, locale }),
    });
  },
  createTilxat(payload: Record<string, unknown>) {
    return request<TilxatDTO>("/api/tilxat", { method: "POST", body: JSON.stringify(payload) });
  },
  getPublicTilxat(token: string) {
    return request<TilxatDTO>(`/api/tilxat/public/${token}`);
  },
  signPublicTilxat(token: string, payload: Record<string, unknown>) {
    return request<TilxatDTO>(`/api/tilxat/public/${token}/sign`, { method: "POST", body: JSON.stringify(payload) });
  },
  revokeTilxat(id: string) {
    return request<TilxatDTO>(`/api/tilxat/${id}/revoke`, { method: "POST" });
  },

  // Scanner
  listScannerSamples(locale: LangCode) {
    return request<Array<{ id: "rental" | "microloan" | "employment"; title: string; preview: string }>>(
      `/api/scanner/samples?locale=${locale}`
    );
  },
  runContractAudit(payload: Record<string, unknown>) {
    return request<ContractAuditDTO>("/api/scanner/audit", { method: "POST", body: JSON.stringify(payload) });
  },
  askClause(payload: { clauseText: string; question: string; legalRefs: string[]; locale: LangCode }) {
    return request<{ answer: string; citations: CitationItem[]; engine: string }>("/api/scanner/ask-clause", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // Recognition & Verify (§9)
  createRecognitionJob(formData: FormData) {
    return request<RecognitionJobCreateResponse>("/api/recognition/jobs", {
      method: "POST",
      body: formData,
    });
  },
  getRecognitionJob(jobId: string) {
    return request<RecognitionJobDetailResponse>(`/api/recognition/jobs/${encodeURIComponent(jobId)}`);
  },
  confirmRecognitionJob(
    jobId: string,
    payload: { fields: Array<{ key: string; value: unknown }>; docType?: string | null }
  ) {
    return request<{ jobId: string; confirmed: boolean; routeHint: RouteHintDTO; fields: RecognitionFieldDTO[] }>(
      `/api/recognition/jobs/${encodeURIComponent(jobId)}/confirm`,
      { method: "POST", body: JSON.stringify(payload) }
    );
  },
  deleteRecognitionJob(jobId: string) {
    return request<{ purged: boolean; jobId: string }>(`/api/recognition/jobs/${encodeURIComponent(jobId)}`, {
      method: "DELETE",
    });
  },
  verifyDocument(formData: FormData) {
    return request<VerifyDocumentResponse>("/api/recognition/verify-document", {
      method: "POST",
      body: formData,
    });
  },
  verifyDocumentById(docId: string) {
    return request<VerifyDocumentResponse>(`/api/verify/${encodeURIComponent(docId)}`);
  },

  // Radar
  listRadarAlerts(tags: string[], locale: LangCode) {
    const q = new URLSearchParams({ locale });
    if (tags.length > 0) q.set("tags", tags.join(","));
    return request<{ items: LawAlertDTO[]; nextCursor: string | null }>(`/api/radar/alerts?${q.toString()}`);
  },
  simulateRadarAlert() {
    return request<{ alert: LawAlertDTO }>("/api/radar/simulate", { method: "POST" });
  },

  // Advocate MSO
  escalateCase(caseId: string) {
    return request<AdvocateLeadDTO>(`/api/mso/escalate/${caseId}`, { method: "POST" });
  },
  listMsoLeads(params?: { status?: string; category?: string }) {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.category) q.set("category", params.category);
    const suffix = q.toString() ? `?${q.toString()}` : "";
    return request<AdvocateLeadDTO[]>(`/api/mso/leads${suffix}`);
  },
  acceptLead(leadId: string) {
    return request<AdvocateLeadDTO>(`/api/mso/leads/${leadId}/accept`, { method: "POST" });
  },
  requestLeadInfo(leadId: string, message: string) {
    return request<AdvocateLeadDTO>(`/api/mso/leads/${leadId}/request-info`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
  },
  declineLead(leadId: string, reason: string) {
    return request<AdvocateLeadDTO>(`/api/mso/leads/${leadId}/decline`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },
  getMsoMetrics() {
    return request<{
      newLeads: number;
      acceptedThisMonth: number;
      avgIntakeTimeSavedMin: number;
      platformFeePercent: number;
      complianceBanner: string;
    }>("/api/mso/metrics");
  },
};

export async function downloadProtectedPdf(url: string, filename: string): Promise<void> {
  const resp = await authorizedFetch(url);
  if (!resp.ok) throw new ApiError(resp.status, await readErrorDetail(resp));
  const blob = await resp.blob();
  const objUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(objUrl), 2500);
}

export function buildWsUrl(path: string): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${path}`;
}
