import { describe, expect, it } from "vitest";
import { answerToShareText, parseAnswer, plainText, tokenizeInline } from "./answer";

const FULL = [
  "### ANSWER",
  "Ha, yillik asosiy ta'til kamida 21 kalendar kun [1].",
  "",
  "### KEY POINTS",
  "- Mehnat kodeksi, 217-modda: eng kam ta'til 21 kun [1]",
  "- Voyaga yetmaganlarga 30 kun [2][3]",
  "",
  "### STEPS",
  "1. Ish beruvchiga yozma ariza bering",
  "2. Rad etsa, mehnat inspeksiyasiga murojaat qiling",
  "",
  "### CAUTION",
  "Jamoa shartnomasida uzoqroq muddat bo'lishi mumkin.",
  "",
  "### FOLLOW-UPS",
  "- Ta'til puli qachon beriladi",
  "- Ta'tilni bo'lib olsa bo'ladimi?",
].join("\n");

describe("parseAnswer", () => {
  it("parses every section of the concise format", () => {
    const s = parseAnswer(FULL);
    expect(s.structured).toBe(true);
    expect(s.answer).toBe("Ha, yillik asosiy ta'til kamida 21 kalendar kun [1].");
    expect(s.key_points).toHaveLength(2);
    expect(s.steps).toEqual(["Ish beruvchiga yozma ariza bering", "Rad etsa, mehnat inspeksiyasiga murojaat qiling"]);
    expect(s.caution).toContain("Jamoa shartnomasida");
    expect(s.follow_ups).toEqual(["Ta'til puli qachon beriladi?", "Ta'tilni bo'lib olsa bo'ladimi?"]);
  });

  it("accepts translated and bold headings", () => {
    const s = parseAnswer("**Ответ:**\nДа, 21 день [1].\n\n**Что делать**\n1. Подайте заявление");
    expect(s.structured).toBe(true);
    expect(s.answer).toBe("Да, 21 день [1].");
    expect(s.steps).toEqual(["Подайте заявление"]);
  });

  it("treats unmarked text as a plain answer", () => {
    const s = parseAnswer("Oddiy javob matni.");
    expect(s.structured).toBe(false);
    expect(s.answer).toBe("Oddiy javob matni.");
  });

  it("holds back a half-received heading while streaming", () => {
    const s = parseAnswer("### ANSWER\nHa, 21 kun [1].\n### KEY PO", { streaming: true });
    expect(s.answer).toBe("Ha, 21 kun [1].");
    expect(s.key_points).toEqual([]);
  });
});

describe("tokenizeInline", () => {
  it("splits bold text and citation groups", () => {
    expect(tokenizeInline("Muddat **10 kun** [1][3] va [2, 4].")).toEqual([
      { kind: "text", value: "Muddat " },
      { kind: "bold", value: "10 kun" },
      { kind: "cite", n: 1 },
      { kind: "cite", n: 3 },
      { kind: "text", value: " va" },
      { kind: "cite", n: 2 },
      { kind: "cite", n: 4 },
      { kind: "text", value: "." },
    ]);
  });

  it("leaves ordinary brackets alone", () => {
    expect(tokenizeInline("1) birinchi [izoh] 2026")).toEqual([{ kind: "text", value: "1) birinchi [izoh] 2026" }]);
  });
});

describe("share text", () => {
  it("strips markers and lists sources", () => {
    expect(plainText("21 kun [1]. **Muhim**")).toBe("21 kun. Muhim");
    const text = answerToShareText("Ta'til necha kun?", parseAnswer(FULL), [
      {
        n: 1,
        doc_id: "-6257288",
        title: "Mehnat kodeksi",
        full_title: "Mehnat kodeksi",
        article: "217-modda",
        excerpt: "",
        url: "https://lex.uz/uz/docs/-6257288",
        language: "uz_latn",
        status: "in_force",
      },
    ]);
    expect(text).toContain("❓ Ta'til necha kun?");
    expect(text).toContain("• Mehnat kodeksi, 217-modda: eng kam ta'til 21 kun");
    expect(text).not.toContain("[1]");
    expect(text).toContain("📘 Mehnat kodeksi, 217-modda — https://lex.uz/uz/docs/-6257288");
  });
});
