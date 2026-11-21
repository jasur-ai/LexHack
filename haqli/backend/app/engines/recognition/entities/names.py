"""Uzbek/Russian person-name candidate extractor with patronymic markers & cue-word ranking (§6.5)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_STOPLIST = {
    "shartnoma", "shartnomasi", "toshkent", "samarqand", "buxoro", "andijon", "namangan", "farg'ona",
    "mchj", "ooo", "ооо", "мчж", "xk", "хк", "yatt", "ятт", "ip", "ип", "aj", "аж",
    "yhxx", "yhxb", "iib", "iibb", "mjtk", "respublikasi", "o'zbekiston", "uzbekiston",
    "ўзбекистон", "республикаси", "тошкент", "шартнома", "талабнома", "тилхат",
    "договор", "расписка", "претензия", "ташкент", "постановление", "штраф", "итого",
    "jami", "kassa", "chek", "kvitansiya", "fuqarolik", "kodeksi", "mehnat", "qonuni",
    "pasport", "паспорт", "sana", "дата", "summa", "сумма", "kredit", "mikroqarz", "ijara",
    "men", "mening", "biz", "u", "я", "мы", "он", "она", "от", "до", "по",
}

_PATRONYMIC_RE = r"(?:o['ʻ’]?g['ʻ’]?li|qizi|ўғли|қизи|ogli|оглы|кызы)"
_CAP_TOK = r"[A-ZА-ЯЁЎҚҒҲ][a-zа-яёўқғҳ'ʻ’\-]{1,28}"
_NAME_RE = re.compile(
    rf"\b({_CAP_TOK})(?:\s+({_CAP_TOK}))(?:\s+({_CAP_TOK}))?(?:\s+({_PATRONYMIC_RE}))?\b"
)

_CUE_PATTERNS = [
    re.compile(r"(?:men|mening|я|fuqaro|фуқаро|гражданин)\s*[:,\-]?\s*$", re.IGNORECASE),
    re.compile(r"(?:qarz\s+oluvchi|oluvchi|beruvchi|qarz\s+beruvchi|заемщик|заёмщик|займодавец|получил\s+от)\s*[:,\-]?\s*$", re.IGNORECASE),
    re.compile(r"(?:tomon|сторона|ответчик|javobgar|ijarachi|арендатор)\s*[:,\-]?\s*$", re.IGNORECASE),
]


@dataclass(frozen=True)
class NameCandidate:
    name: str
    span: tuple[int, int]
    confidence: float
    cue_matched: bool = False


def _clean_uz_case(token: str) -> str:
    """Strip common Uzbek dative/ablative case endings from surnames (e.g. 'Rahimovga' -> 'Rahimov')."""
    for suf in ("ovga", "evga", "ovdan", "evdan", "ovning", "evning", "ovaga", "evaga"):
        if token.lower().endswith(suf) and len(token) > len(suf) + 2:
            return token[: -(len(suf) - 2)]
    for suf in ("ga", "dan", "ning"):
        if token.lower().endswith(suf) and len(token) > len(suf) + 3 and token[: -len(suf)].lower().endswith(("ov", "ev", "ova", "eva")):
            return token[: -len(suf)]
    return token


def extract_names(text: str) -> list[NameCandidate]:
    """Extract 2-3 token capitalized person names (Latin/Cyrillic) ranked by cue proximity."""
    candidates: list[NameCandidate] = []
    seen: set[str] = set()

    for m in _NAME_RE.finditer(text):
        parts = [p for p in m.groups() if p]
        if len(parts) < 2:
            continue
        # Reject if any non-patronymic token is in stoplist
        bad = False
        cleaned_parts: list[str] = []
        for idx, p in enumerate(parts):
            norm_p = p.replace("‘", "'").replace("’", "'").replace("ʻ", "'").lower()
            if idx == len(parts) - 1 and re.fullmatch(_PATRONYMIC_RE, norm_p):
                cleaned_parts.append(p)
                continue
            cleaned_tok = _clean_uz_case(p)
            if cleaned_tok.lower() in _STOPLIST or norm_p in _STOPLIST:
                bad = True
                break
            cleaned_parts.append(cleaned_tok)
        if bad or len(cleaned_parts) < 2:
            continue

        full_name = " ".join(cleaned_parts)
        if full_name.lower() in seen:
            continue
        seen.add(full_name.lower())

        s, e = m.span()
        before = text[max(0, s - 36) : s]
        cue_hit = any(cp.search(before) for cp in _CUE_PATTERNS)
        has_patronymic = bool(m.group(4))
        conf = 0.90 if cue_hit else (0.86 if has_patronymic else 0.78)
        candidates.append(NameCandidate(name=full_name, span=(s, e), confidence=conf, cue_matched=cue_hit))

    candidates.sort(key=lambda c: (-int(c.cue_matched), -c.confidence, c.span[0]))
    return candidates
