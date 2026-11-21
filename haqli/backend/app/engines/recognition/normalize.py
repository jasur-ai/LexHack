"""Uzbek/Russian OCR text normalization with exact character-level offset map back to OCR lines & bboxes (§5.4)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

try:
    from rapidfuzz import fuzz, process  # type: ignore

    _HAS_RAPIDFUZZ = True
except Exception:
    _HAS_RAPIDFUZZ = False

from app.engines.recognition.types import OcrLine

# Bundled Uzbek Cyrillic legal & commercial dictionary for lookalike repair (у/к/г/х -> ў/қ/ғ/ҳ)
UZ_CYR_LEGAL_WORDS: tuple[str, ...] = (
    "ўзбекистон", "ҳуқуқ", "ҳуқуқий", "ҳужжат", "қонун", "қонунчилик", "қонуний",
    "қарз", "қарздор", "қайтариш", "қайтарилсин", "қўшимча", "қоида", "қоидабузарлик",
    "қарор", "қарори", "сўм", "тўлов", "тўлаш", "тўланмаган", "тўлиқ", "ўз", "ўзгартириш",
    "ўртасида", "ўрнатилган", "ўтказиш", "ғоя", "маблағ", "маблағи", "маблағни",
    "шартнома", "талабнома", "тилхат", "ҳисоб", "ҳисоблаш", "ҳақ", "ҳақи", "иш ҳақи",
    "ҳафта", "ҳар", "ҳам", "ҳолат", "ҳимоя", "ҳудуд", "қабул", "қилиш", "қилинади",
    "қилинган", "қисм", "қисми", "қисман", "қоплаш", "қуйидаги", "бўйича", "бўлган",
    "бўлиб", "бўлим", "кўра", "кўрсатилган", "кўрсатиш", "кўриб", "кўчмас", "тўғрисида",
    "тўғри", "муғобира", "суғурта", "маълумот", "масъул", "фаолият", "фуқаро", "фуқаролик",
    "меҳнат", "жарима", "шикоят", "даъво", "ариза", "судгача", "муддат", "фоиз",
    "депозит", "ижара", "микроқарз", "кредит", "кафолат", "маҳсулот", "истеъмолчи",
    "сотувчи", "харидор", "ходим", "иш берувчи", "раҳбар", "ташкилот", "корхона",
    "паспорт", "рақам", "рақами", "сана", "манзил", "имзо", "тасдиқ", "тасдиқлаш",
    "муҳр", "нақд", "карта", "квитанция", "чек", "жами", "ққс", "стир",
    "ўттиз", "тўрт", "тўққиз", "ўн", "қирқ", "тўқсон", "ўғли", "қизи",
)

_APOS_VARIANTS = {"'", "ʻ", "ʼ", "’", "‘", "`", "´"}
_NUMERIC_LOOKALIKE_TOKEN = re.compile(r"^[0-9OoОоlI]+$")
_NUMERIC_O_TO_0 = str.maketrans({"O": "0", "o": "0", "О": "0", "о": "0", "l": "1", "I": "1"})


@dataclass
class SourceLocation:
    orig_index: int
    line_index: int
    bbox: tuple[float, float, float, float] | None = None


@dataclass
class NormalizedText:
    """Normalized text paired with a 1-to-1 offset map back to the original text & OCR line bboxes."""

    text: str
    numeric_view: str
    offset_map: list[SourceLocation] = field(default_factory=list)
    original_text: str = ""

    def span_to_original(self, start: int, end: int) -> tuple[int, int]:
        if not self.offset_map or start >= len(self.offset_map):
            return (start, end)
        clamped_end = max(start, min(end - 1, len(self.offset_map) - 1))
        return (self.offset_map[start].orig_index, self.offset_map[clamped_end].orig_index + 1)

    def span_to_bbox(self, start: int, end: int) -> tuple[float, float, float, float] | None:
        if not self.offset_map or start >= len(self.offset_map):
            return None
        boxes = [
            loc.bbox
            for loc in self.offset_map[start : min(end, len(self.offset_map))]
            if loc.bbox is not None
        ]
        if not boxes:
            return None
        return (
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        )


def _repair_cyrillic_token(token: str) -> str:
    """Fix у/к/г/х -> ў/қ/ғ/ҳ confusions using bundled dictionary with rapidfuzz score >= 90 (§5.4)."""
    low = token.lower()
    if len(low) < 3 or not re.fullmatch(r"[а-яёўқғҳ]+", low):
        return token
    if low in UZ_CYR_LEGAL_WORDS or not any(ch in low for ch in ("у", "к", "г", "х")):
        return token
    if not _HAS_RAPIDFUZZ:
        # Lightweight exact skeleton fallback when rapidfuzz is absent
        skel = low.translate(str.maketrans({"ў": "у", "қ": "к", "ғ": "г", "ҳ": "х"}))
        for cand in UZ_CYR_LEGAL_WORDS:
            cand_skel = cand.translate(str.maketrans({"ў": "у", "қ": "к", "ғ": "г", "ҳ": "х"}))
            if cand_skel == skel and cand != low:
                return cand.capitalize() if token[0].isupper() else cand
        return token

    match = process.extractOne(low, UZ_CYR_LEGAL_WORDS, scorer=fuzz.ratio)
    if match and match[1] >= 90.0:
        cand = match[0]
        # Only replace if same length and difference is solely in ў/қ/ғ/ҳ lookalikes
        if len(cand) == len(low):
            cand_skel = cand.translate(str.maketrans({"ў": "у", "қ": "к", "ғ": "г", "ҳ": "х"}))
            low_skel = low.translate(str.maketrans({"ў": "у", "қ": "к", "ғ": "г", "ҳ": "х"}))
            if cand_skel == low_skel:
                return cand.capitalize() if token[0].isupper() else cand
    return token


def normalize_ocr_text(
    text: str,
    *,
    lines: list[OcrLine] | None = None,
    apostrophe: str = "ʻ",
) -> NormalizedText:
    """Normalize Uzbek/Russian text while preserving an exact character offset map (§5.4)."""
    nfc = unicodedata.normalize("NFC", text)
    # Build line index & bbox lookup per character in original text
    char_line: list[tuple[int, tuple[float, float, float, float] | None]] = []
    if lines:
        for l_idx, ln in enumerate(lines):
            for _ in ln.text:
                char_line.append((l_idx, ln.bbox))
            char_line.append((l_idx, ln.bbox))  # newline
    else:
        l_idx = 0
        for ch in nfc:
            char_line.append((l_idx, None))
            if ch == "\n":
                l_idx += 1

    def _loc(orig_i: int) -> SourceLocation:
        if orig_i < len(char_line):
            li, bb = char_line[orig_i]
            return SourceLocation(orig_index=orig_i, line_index=li, bbox=bb)
        return SourceLocation(orig_index=orig_i, line_index=0, bbox=None)

    chars: list[str] = []
    omap: list[SourceLocation] = []
    i = 0
    n = len(nfc)

    while i < n:
        ch = nfc[i]
        # Drop soft hyphens
        if ch == "\u00ad":
            i += 1
            continue
        # Join words broken by line-end hyphen: "shart-\nnoma" -> "shartnoma"
        if ch == "-" and i + 2 < n and nfc[i + 1] == "\n" and nfc[i + 2].isalpha():
            i += 2
            continue
        # Normalize apostrophe variants
        if ch in _APOS_VARIANTS:
            chars.append(apostrophe)
            omap.append(_loc(i))
            i += 1
            continue
        # Normalize non-breaking / thin spaces to regular space
        if ch in ("\u00a0", "\u202f", "\t", "\r"):
            if ch == "\r":
                i += 1
                continue
            ch = " "
        # Collapse consecutive horizontal spaces
        if ch == " " and chars and chars[-1] == " ":
            i += 1
            continue
        chars.append(ch)
        omap.append(_loc(i))
        i += 1

    # Token-level repairs preserving exact length so offset_map remains 1-to-1
    joined = "".join(chars)
    repaired_chars = list(joined)
    tokens = list(re.finditer(r"[^\s\n]+", joined))
    for t_idx, m in enumerate(tokens):
        tok = m.group(0)
        s, e = m.span()
        # 1. Numeric-context 0<->O, 1<->l/I repair (token contains >= 50% digits)
        digits = sum(1 for c in tok if c.isdigit())
        if len(tok) >= 2 and digits / len(tok) >= 0.5:
            fixed = tok.translate(_NUMERIC_O_TO_0)
            repaired_chars[s:e] = list(fixed)
            continue
        # 1b. Thousands group inside a space-grouped amount: "4 5OO 000" -> "4 500 000"
        if digits and len(tok) <= 3 and _NUMERIC_LOOKALIKE_TOKEN.match(tok):
            prev_tok = tokens[t_idx - 1] if t_idx > 0 else None
            next_tok = tokens[t_idx + 1] if t_idx + 1 < len(tokens) else None
            near_number = (
                prev_tok is not None and prev_tok.end() == s - 1 and joined[s - 1] == " " and prev_tok.group(0).isdigit()
            ) or (
                next_tok is not None and next_tok.start() == e + 1 and joined[e] == " " and next_tok.group(0).isdigit()
            )
            if near_number:
                repaired_chars[s:e] = list(tok.translate(_NUMERIC_O_TO_0))
                continue
        # 2. Uzbek Cyrillic lookalike repair (length-preserving)
        fixed_cyr = _repair_cyrillic_token(tok)
        if len(fixed_cyr) == len(tok):
            repaired_chars[s:e] = list(fixed_cyr)

    final_text = "".join(repaired_chars)

    # Parallel numeric view: decimal comma -> dot, space-grouped numbers kept clean
    numeric_view = re.sub(r"(\d),(\d{1,2})\b", r"\1.\2", final_text)

    return NormalizedText(
        text=final_text,
        numeric_view=numeric_view,
        offset_map=omap,
        original_text=nfc,
    )
