/**
 * Typed HTTP + WebSocket client for Haqli FastAPI backend (§10).
 */
import { useAppStore, type LangCode, type ThemePref, type UserProfile, type UserRole } from "./store";

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
  target: "himoya" | "tilxat" | "skaner" | "none";
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

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = useAppStore.getState().token;
  const headers = new Headers(init.headers);
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const resp = await fetch(path, { ...init, headers });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const errBody = (await resp.json()) as { detail?: string; title?: string };
      detail = errBody.detail || errBody.title || detail;
    } catch {
      // Ignore parse error
    }
    throw new ApiError(resp.status, detail);
  }
  return (await resp.json()) as T;
}

export const api = {
  authTelegram(initData: string, demoName?: string) {
    return request<{
      accessToken: string;
      user: UserProfile;
      demoMode: boolean;
      constants: { bhm: string; bhmStatus: string; version: string; talabnomaPriceUzs: string };
    }>("/api/auth/telegram", {
      method: "POST",
      body: JSON.stringify({ initData, demoName }),
    });
  },

  patchPreferences(payload: {
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
  const token = useAppStore.getState().token;
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const resp = await fetch(url, { headers });
  if (!resp.ok) throw new Error(`PDF download failed (${resp.status})`);
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
