"""Zero-Trust Atomic Claim & Citation Parser extracting every legal assertion from the Target Agent's response."""

from __future__ import annotations

import re
from typing import Any

from evaluator_agent.models import ExtractedClaim

_APOSTROPHE_RE = re.compile(r"[ʻʼ‘’`´ʹʽˈ]")
_LEX_URL_RE = re.compile(r"https?://(?:www\.)?lex\.uz/(?:(?:uz|ru|en)/)?docs/(-?\d+)(?:#\d+)?", re.I)
_DOC_NUM_RE = re.compile(
    r"\b((?:O'RQ|ЎРҚ|ЗРУ|PF|ПФ|УП|PQ|ПҚ|ПП|VMQ|ВМҚ|ПКМ)-?\s*\d{1,5})\b",
    re.I,
)
_ARTICLE_RE = re.compile(
    r"\b(\d+(?:[-.]\d+)?)\s*-?\s*(?:modda\w*|модда\w*)|\b(?:стать[еёяйюяи]\w*|ст\.|Article|Art\.)\s*(\d+(?:[-.]\d+)?)\b",
    re.I,
)

_CODE_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"konstitutsiya|конституц|constitution", re.I), "Konstitutsiya"),
    (re.compile(r"mehnat\s+kodeks|меҳнат\s+кодекс|трудов\w+\s+кодекс|labor\s+code", re.I), "Mehnat kodeksi"),
    (re.compile(r"soliq\s+kodeks|солиқ\s+кодекс|налогов\w+\s+кодекс|tax\s+code", re.I), "Soliq kodeksi"),
    (re.compile(r"oila\s+kodeks|оила\s+кодекс|семейн\w+\s+кодекс|family\s+code", re.I), "Oila kodeksi"),
    (re.compile(r"fuqarolik\s+kodeks|фуқаролик\s+кодекс|гражданск\w+\s+кодекс|civil\s+code", re.I), "Fuqarolik kodeksi"),
    (re.compile(r"jinoyat\s+kodeks|жиноят\s+кодекс|уголовн\w+\s+кодекс|criminal\s+code", re.I), "Jinoyat kodeksi"),
    (re.compile(r"ma'muriy\s+javobgarlik|маъмурий\s+жавобгарлик|мжтк|коао|административн\w+\s+ответственност", re.I), "MJtK"),
    (re.compile(r"bojxona\s+kodeks|божхона\s+кодекс|таможенн\w+\s+кодекс|customs\s+code", re.I), "Bojxona kodeksi"),
    (re.compile(r"yer\s+kodeks|ер\s+кодекс|земельн\w+\s+кодекс|land\s+code", re.I), "Yer kodeksi"),
    (re.compile(r"shaxsga\s+doir\s+ma'lumot|персональн\w+\s+данн|personal\s+data", re.I), "Shaxsga doir ma'lumotlar to'g'risida"),
    (re.compile(r"normativ-huquqiy|нормативно-правов|normative-legal", re.I), "Normativ-huquqiy hujjatlar to'g'risida"),
]


def _norm(text: str) -> str:
    return _APOSTROPHE_RE.sub("'", text)


def _detect_code_title(sentence: str) -> str | None:
    for pat, label in _CODE_HINTS:
        if pat.search(sentence):
            return label
    return None


def _detect_claimed_status(sentence: str) -> str | None:
    low = _norm(sentence).lower()
    if any(k in low for k in ("kuchini yo'qot", "бекор қилин", "утратил силу", "repealed", "bekor qilingan")):
        return "repealed"
    if any(k in low for k in ("o'zgartiril", "tahririda", "в редакции", "amended")):
        return "amended"
    if any(k in low for k in ("amalda", "действу", "in force")):
        return "in_force"
    return None


def parse_claims_and_citations(
    answer_text: str,
    reported_citations: list[dict[str, Any]] | None = None,
) -> list[ExtractedClaim]:
    """Decompose the Target Agent's answer & reported citations into atomic claims for zero-trust auditing."""
    claims: list[ExtractedClaim] = []
    seen_keys: set[tuple[str | None, str | None, str | None, str | None]] = set()
    seq = 0

    norm_text = _norm(answer_text or "")
    # Protect legal abbreviations (ст. 258, ч. 2, п. 4, Art. 161, No. 682) before sentence splitting
    protected = re.sub(r"\b(ст|ч|п|пп|г|art|no|y)\.\s+(?=\d)", r"\1<ABBR_DOT> ", norm_text, flags=re.I)
    sentences = [
        s.replace("<ABBR_DOT>", ".").strip()
        for s in re.split(r"(?<=[.!?\n])\s+", protected)
        if len(s.strip()) >= 15
    ]

    for sent in sentences:
        urls = list(_LEX_URL_RE.finditer(sent))
        doc_nums = [re.sub(r"\s+", "", m.group(1).upper()) for m in _DOC_NUM_RE.finditer(sent)]
        arts = [a or b for a, b in _ARTICLE_RE.findall(sent) if (a or b)]
        code_hint = _detect_code_title(sent)
        claimed_status = _detect_claimed_status(sent)

        if not (urls or doc_nums or arts):
            continue

        url_id = urls[0].group(1) if urls else None
        url_str = urls[0].group(0) if urls else None
        doc_num = doc_nums[0] if doc_nums else None

        if arts:
            for art in list(dict.fromkeys(arts))[:4]:
                key = (url_id, doc_num, code_hint, art)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                seq += 1
                claims.append(
                    ExtractedClaim(
                        claim_id=f"CLM-{seq:02d}",
                        claim_text=sent[:380],
                        cited_doc_id=url_id,
                        cited_doc_number=doc_num,
                        cited_doc_title=code_hint,
                        cited_article=art,
                        cited_url=url_str,
                        claimed_status=claimed_status,
                    )
                )
        else:
            key = (url_id, doc_num, code_hint, None)
            if key not in seen_keys:
                seen_keys.add(key)
                seq += 1
                claims.append(
                    ExtractedClaim(
                        claim_id=f"CLM-{seq:02d}",
                        claim_text=sent[:380],
                        cited_doc_id=url_id,
                        cited_doc_number=doc_num,
                        cited_doc_title=code_hint,
                        cited_url=url_str,
                        claimed_status=claimed_status,
                    )
                )

    # Also treat structured citations returned by Target Agent as UNTRUSTED claims to cross-check independently
    for rc in (reported_citations or [])[:8]:
        doc_id = str(rc.get("doc_id") or "").strip() or None
        doc_num = str(rc.get("doc_number") or "").strip() or None
        title = str(rc.get("doc_title") or "").strip() or None
        raw_art = str(rc.get("article") or "").strip()
        art_m = re.search(r"(\d+(?:[-.]\d+)?)", raw_art)
        art = art_m.group(1) if art_m else None
        url = str(rc.get("url") or "").strip() or None
        status = str(rc.get("status") or "").strip() or None

        key = (doc_id, doc_num, title, art)
        if key in seen_keys or not (doc_id or doc_num or title):
            continue
        seen_keys.add(key)
        seq += 1
        claims.append(
            ExtractedClaim(
                claim_id=f"CLM-{seq:02d}",
                claim_text=f"[Target Agent Citation Card] {title or doc_id} {raw_art}".strip(),
                cited_doc_id=doc_id,
                cited_doc_number=doc_num,
                cited_doc_title=title,
                cited_article=art,
                cited_url=url,
                claimed_status=status,
            )
        )

    return claims[:20]
