/**
 * Streaming client for the AI lawyer (`POST /api/agent/ask/stream`, Server-Sent Events over fetch).
 * fetch is used instead of EventSource because the request is a POST with a bearer token.
 */
import { authorizedFetch } from "../../lib/api";
import type { AgentSource, AnswerSections } from "./answer";

export interface AgentFinal {
  answer: string;
  sections?: AnswerSections | null;
  sources?: AgentSource[];
  mode?: string;
  elapsed_ms?: number;
  response_language?: string;
  verification?: { passed: boolean; confidence_score?: number; warnings?: string[] };
}

export type AgentEvent =
  | { type: "step"; step: number; total?: number; status?: string; label?: string; elapsed_ms?: number }
  | { type: "sources"; sources: AgentSource[] }
  | { type: "token"; text: string }
  | { type: "replace_answer"; text: string; mode?: string }
  | { type: "done"; elapsed_ms?: number; response: AgentFinal }
  | { type: "error"; code?: string; detail?: string };

export type AgentErrorCode =
  | "agent_unavailable"
  | "agent_timeout"
  | "agent_incomplete"
  | "agent_error"
  | "rate_limited"
  | "network"
  | "http_error";

export class AgentStreamError extends Error {
  code: AgentErrorCode;
  status?: number;
  constructor(code: AgentErrorCode, message: string, status?: number) {
    super(message);
    this.name = "AgentStreamError";
    this.code = code;
    this.status = status;
  }
}

/** Incremental SSE parser: feed it decoded chunks in any split, it emits whole JSON events. */
export function createSseParser(onEvent: (event: AgentEvent) => void) {
  let buffer = "";
  const emitBlock = (block: string) => {
    const data = block
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).replace(/^ /, ""))
      .join("\n");
    if (!data) return;
    try {
      const parsed = JSON.parse(data) as AgentEvent;
      if (parsed && typeof parsed === "object" && "type" in parsed) onEvent(parsed);
    } catch {
      // A malformed event is skipped; the stream continues.
    }
  };
  return {
    push(chunk: string) {
      buffer += chunk.replace(/\r\n?/g, "\n");
      let idx = buffer.indexOf("\n\n");
      while (idx !== -1) {
        emitBlock(buffer.slice(0, idx));
        buffer = buffer.slice(idx + 2);
        idx = buffer.indexOf("\n\n");
      }
    },
    flush() {
      if (buffer.trim()) emitBlock(buffer);
      buffer = "";
    },
  };
}

export function isAbortError(err: unknown): boolean {
  return err instanceof DOMException ? err.name === "AbortError" : (err as { name?: string })?.name === "AbortError";
}

async function errorDetail(resp: Response): Promise<string> {
  try {
    const body = (await resp.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // ignore
  }
  return `HTTP ${resp.status}`;
}

export interface AskOptions {
  context?: string;
  signal?: AbortSignal;
  onEvent: (event: AgentEvent) => void;
}

export async function streamAgentAnswer(query: string, { context, signal, onEvent }: AskOptions): Promise<void> {
  let resp: Response;
  try {
    resp = await authorizedFetch("/api/agent/ask/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(context ? { query, context, answerStyle: "concise" } : { query, answerStyle: "concise" }),
      signal,
    });
  } catch (err) {
    if (isAbortError(err)) throw err;
    throw new AgentStreamError("network", err instanceof Error ? err.message : "network");
  }
  if (resp.status === 429) throw new AgentStreamError("rate_limited", await errorDetail(resp), 429);
  if (!resp.ok) throw new AgentStreamError("http_error", await errorDetail(resp), resp.status);

  const parser = createSseParser(onEvent);
  if (!resp.body) {
    parser.push(await resp.text());
    parser.flush();
    return;
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.push(decoder.decode(value, { stream: true }));
    }
    parser.push(decoder.decode());
    parser.flush();
  } catch (err) {
    if (isAbortError(err)) throw err;
    throw new AgentStreamError("network", err instanceof Error ? err.message : "network");
  } finally {
    reader.releaseLock();
  }
}
