import { describe, expect, it } from "vitest";
import { latinToCyrillic } from "./translit";
import { computeBhmRatio, formatUzs } from "../lib/format";

describe("Uzbek Latin -> Cyrillic transliterator", () => {
  it("converts core Uzbek digraphs and loanwords while preserving interpolation tokens", () => {
    expect(latinToCyrillic("O'zbekiston shartnoma")).toBe("Ўзбекистон шартнома");
    expect(latinToCyrillic("BHM: {{bhm}} kompensatsiya")).toBe("БҲМ: {{bhm}} компенсация");
  });
});

describe("UZS and BHM formatting", () => {
  it("groups thousands with narrow no-break space and computes BHM ratio", () => {
    expect(formatUzs(4500000, "uz_lat")).toBe("4\u202F500\u202F000 so'm");
    expect(formatUzs(4500000, "ru")).toBe("4\u202F500\u202F000 сум");
    expect(computeBhmRatio(3750000, 375000)).toBe(10);
  });
});
