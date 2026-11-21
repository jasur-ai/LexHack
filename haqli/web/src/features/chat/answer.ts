/**
 * Client-side model of the AI-lawyer answer.
 *
 * The agent answers in a fixed, scannable format (### ANSWER / KEY POINTS / STEPS / CAUTION / FOLLOW-UPS with
 * [n] source markers). The server sends parsed sections with the final event; this parser renders the same
 * structure progressively while tokens are still streaming, so the card never shows raw markdown.
 */

export interface AgentSource {
  n: number;
  doc_id: string;
  title: string;
  full_title: string;
  article?: string | null;
  article_title?: string | null;
  excerpt: string;
  lead?: string | null;
  url: string;
  language: string;
  status: string;
  source?: string;
  snapshot?: string | null;
  doc_type?: string;
}

export interface AnswerSections {
  structured: boolean;
  answer: string;
  key_points: string[];
  steps: string[];
  caution: string;
  follow_ups: string[];
}

type SectionKey = "answer" | "key_points" | "steps" | "caution" | "follow_ups";

const SECTION_ALIASES: Record<string, SectionKey> = {
  answer: "answer",
  "short answer": "answer",
  javob: "answer",
  "qisqa javob": "answer",
  "жавоб": "answer",
  "ответ": "answer",
  "key points": "key_points",
  "asosiy qoidalar": "key_points",
  "asosiy nuqtalar": "key_points",
  "основные положения": "key_points",
  steps: "steps",
  "next steps": "steps",
  "nima qilish kerak": "steps",
  qadamlar: "steps",
  "что делать": "steps",
  "шаги": "steps",
  caution: "caution",
  diqqat: "caution",
  "важно": "caution",
  "внимание": "caution",
  "follow-ups": "follow_ups",
  "follow ups": "follow_ups",
  "followups": "follow_ups",
  "qo'shimcha savollar": "follow_ups",
  "дополнительные вопросы": "follow_ups",
};

const HEADING_RE = /^\s*(?:#{1,4}\s*|\*\*)\s*([^#*:]{3,40}?)\s*:?\s*(?:\*\*)?\s*:?\s*$/;
const BULLET_RE = /^(?:[-*•]|\d+[.)])\s+(.*)$/;

export const EMPTY_SECTIONS: AnswerSections = {
  structured: false,
  answer: "",
  key_points: [],
  steps: [],
  caution: "",
  follow_ups: [],
};

function bullets(lines: string[]): string[] {
  const items: string[] = [];
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    const m = BULLET_RE.exec(line);
    if (m && m[1] !== undefined) items.push(m[1].trim());
    else if (items.length > 0) items[items.length - 1] = `${items[items.length - 1]} ${line}`;
    else items.push(line);
  }
  return items.filter(Boolean);
}

function paragraph(lines: string[]): string {
  return lines.join("\n").trim().replace(/\n{3,}/g, "\n\n");
}

/**
 * Parse the marker format. With `streaming`, an unfinished last line that looks like the start of a heading
 * ("### KEY PO") is held back so it never flashes as body text.
 */
export function parseAnswer(text: string, options: { streaming?: boolean } = {}): AnswerSections {
  let source = (text || "").replace(/\r\n/g, "\n");
  if (options.streaming) {
    const lastBreak = source.lastIndexOf("\n");
    const tail = source.slice(lastBreak + 1);
    if (/^\s*(#|\*\*)/.test(tail)) source = source.slice(0, Math.max(0, lastBreak));
  }
  const sections: Partial<Record<SectionKey, string[]>> = {};
  let current: SectionKey = "answer";
  let structured = false;
  for (const rawLine of source.split("\n")) {
    const line = rawLine.replace(/\s+$/, "");
    const m = HEADING_RE.exec(line);
    if (m && m[1] !== undefined) {
      const key = SECTION_ALIASES[m[1].trim().toLowerCase().replace(/[ʻʼ‘’`]/g, "'")];
      if (key) {
        current = key;
        structured = true;
        sections[current] ??= [];
        continue;
      }
    }
    (sections[current] ??= []).push(line);
  }
  return {
    structured,
    answer: paragraph(sections.answer ?? []),
    key_points: bullets(sections.key_points ?? []),
    steps: bullets(sections.steps ?? []),
    caution: paragraph(sections.caution ?? []),
    follow_ups: bullets(sections.follow_ups ?? [])
      .map((q) => `${q.replace(/\?+$/, "")}?`)
      .slice(0, 3),
  };
}

export type InlineToken =
  | { kind: "text"; value: string }
  | { kind: "bold"; value: string }
  | { kind: "cite"; n: number };

const INLINE_RE = /\*\*([^*\n]+)\*\*|\[(\d{1,2}(?:\s*[,;]\s*\d{1,2})*)\]/g;

/** Split a line into plain text, **bold** spans and [n] / [1, 3] citation markers. */
export function tokenizeInline(text: string): InlineToken[] {
  const tokens: InlineToken[] = [];
  let last = 0;
  INLINE_RE.lastIndex = 0;
  for (let m = INLINE_RE.exec(text); m !== null; m = INLINE_RE.exec(text)) {
    if (m.index > last) tokens.push({ kind: "text", value: text.slice(last, m.index) });
    if (m[1] !== undefined) {
      tokens.push({ kind: "bold", value: m[1] });
    } else if (m[2] !== undefined) {
      for (const part of m[2].split(/[,;]/)) {
        const n = Number(part.trim());
        if (Number.isFinite(n) && n > 0) tokens.push({ kind: "cite", n });
      }
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) tokens.push({ kind: "text", value: text.slice(last) });
  // Drop the space the model leaves before a marker ("21 kun [1]") so the chip hugs the word.
  for (let i = 0; i < tokens.length - 1; i += 1) {
    const cur = tokens[i];
    const next = tokens[i + 1];
    if (cur && next && cur.kind === "text" && next.kind === "cite") cur.value = cur.value.replace(/\s+$/, "");
  }
  return tokens.filter((t) => t.kind !== "text" || t.value.length > 0);
}

/** Remove [n] markers and ** emphasis for clipboard / share text. */
export function plainText(text: string): string {
  return text
    .replace(/\s*\[(\d{1,2}(?:\s*[,;]\s*\d{1,2})*)\]/g, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .trim();
}

/** Human label for the place a source lives ("lex.uz", "gazeta.uz"). */
export function sourceHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "lex.uz";
  }
}

/** Compose a shareable plain-text version of an answer. */
export function answerToShareText(question: string, sections: AnswerSections, sources: AgentSource[]): string {
  const lines: string[] = [];
  if (question) lines.push(`❓ ${question}`, "");
  if (sections.answer) lines.push(plainText(sections.answer), "");
  for (const point of sections.key_points) lines.push(`• ${plainText(point)}`);
  if (sections.key_points.length) lines.push("");
  sections.steps.forEach((step, i) => lines.push(`${i + 1}. ${plainText(step)}`));
  if (sections.steps.length) lines.push("");
  if (sections.caution) lines.push(`⚠️ ${plainText(sections.caution)}`, "");
  const cited = sources.slice(0, 3);
  if (cited.length) {
    for (const s of cited) lines.push(`📘 ${s.title}${s.article ? `, ${s.article}` : ""} — ${s.url}`);
  }
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}
