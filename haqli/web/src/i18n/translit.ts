/**
 * Deterministic Uzbek Latin -> Uzbek Cyrillic transliterator (§8.3).
 */
const LOANWORD_MAP: Record<string, string> = {
  kompensatsiya: "компенсация",
  registratsiya: "регистрация",
  kvalifikatsiya: "квалификация",
  operatsiya: "операция",
  identifikatsiya: "идентификация",
  konstitutsiya: "конституция",
  haqli: "Ҳақли",
};

const MULTI: Array<[string, string]> = [
  ["O'", "Ў"], ["o'", "ў"],
  ["G'", "Ғ"], ["g'", "ғ"],
  ["Sh", "Ш"], ["SH", "Ш"], ["sh", "ш"],
  ["Ch", "Ч"], ["CH", "Ч"], ["ch", "ч"],
  ["Ng", "Нг"], ["NG", "НГ"], ["ng", "нг"],
  ["Ye", "Е"], ["YE", "Е"], ["ye", "е"],
  ["Yo", "Ё"], ["YO", "Ё"], ["yo", "ё"],
  ["Yu", "Ю"], ["YU", "Ю"], ["yu", "ю"],
  ["Ya", "Я"], ["YA", "Я"], ["ya", "я"],
];

const SINGLE: Record<string, string> = {
  A: "А", a: "а", B: "Б", b: "б", D: "Д", d: "д", E: "Э", e: "е",
  F: "Ф", f: "ф", G: "Г", g: "г", H: "Ҳ", h: "ҳ", I: "И", i: "и",
  J: "Ж", j: "ж", K: "К", k: "к", L: "Л", l: "л", M: "М", m: "м",
  N: "Н", n: "н", O: "О", o: "о", P: "П", p: "п", Q: "Қ", q: "қ",
  R: "Р", r: "р", S: "С", s: "с", T: "Т", t: "т", U: "У", u: "у",
  V: "В", v: "в", X: "Х", x: "х", Y: "Й", y: "й", Z: "З", z: "з",
};

export function latinToCyrillic(input: string): string {
  // Preserve interpolation placeholders like {{amount}}
  const tokens: string[] = [];
  const masked = input.replace(/\{\{[^}]+\}\}/g, (m) => {
    tokens.push(m);
    return `__TOK${tokens.length - 1}__`;
  });

  let normalized = masked.replace(/[‘’`ʻʼ]/g, "'");
  for (const [lat, cyr] of Object.entries(LOANWORD_MAP)) {
    normalized = normalized.replace(new RegExp(`\\b${lat}\\b`, "gi"), (match) => {
      if (match[0] && match[0] === match[0].toUpperCase()) {
        return cyr.charAt(0).toUpperCase() + cyr.slice(1);
      }
      return cyr;
    });
  }

  let out = "";
  let i = 0;
  while (i < normalized.length) {
    if (normalized.startsWith("__TOK", i)) {
      const end = normalized.indexOf("__", i + 5);
      if (end !== -1) {
        out += normalized.slice(i, end + 2);
        i = end + 2;
        continue;
      }
    }
    let matched = false;
    for (const [lat, cyr] of MULTI) {
      if (normalized.startsWith(lat, i)) {
        out += cyr;
        i += lat.length;
        matched = true;
        break;
      }
    }
    if (matched) continue;
    const ch = normalized[i] ?? "";
    if (ch === "'") {
      out += "ъ";
    } else if (ch === "e" && (i === 0 || !/[A-Za-z]/.test(normalized[i - 1] ?? ""))) {
      out += "э";
    } else {
      out += SINGLE[ch] ?? ch;
    }
    i += 1;
  }

  return out.replace(/__TOK(\d+)__/g, (_, idx) => tokens[Number(idx)] ?? "");
}

export function transliterateDict(obj: Record<string, unknown>, overrides: Record<string, unknown> = {}): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const ov = overrides[key];
    if (typeof value === "string") {
      result[key] = typeof ov === "string" ? ov : latinToCyrillic(value);
    } else if (value && typeof value === "object" && !Array.isArray(value)) {
      result[key] = transliterateDict(
        value as Record<string, unknown>,
        ov && typeof ov === "object" ? (ov as Record<string, unknown>) : {}
      );
    } else {
      result[key] = value;
    }
  }
  return result;
}
