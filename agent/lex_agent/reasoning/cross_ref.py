"""Cross-reference extractor for Uzbekistan legal texts across UZ (Latin/Cyrillic), RU, and EN."""

from __future__ import annotations

import re

from lex_agent.language.transliterator import normalize_uzbek_apostrophes
from lex_agent.models import CrossReference

# Well-known Uzbekistan Codes & foundational act names mapped to canonical search hints
CODE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"konstitutsiya|конституци[яи]|constitution", re.I), "Constitution of the Republic of Uzbekistan"),
    (re.compile(r"fuqarolik\s+kodeks|фуқаролик\s+кодекс|гражданск\w+\s+кодекс|civil\s+code", re.I), "Fuqarolik kodeksi"),
    (re.compile(r"jinoyat-?protsessual|жиноят-?процессуал|уголовно-?процессуальн|criminal\s+procedure\s+code", re.I), "Jinoyat-protsessual kodeksi"),
    (re.compile(r"jinoyat\s+kodeks|жиноят\s+кодекс|уголовн\w+\s+кодекс|criminal\s+code", re.I), "Jinoyat kodeksi"),
    (re.compile(r"ma'muriy\s+javobgarlik|маъмурий\s+жавобгарлик|административн\w+\s+ответственност|administrative\s+liability\s+code|коао", re.I), "Ma'muriy javobgarlik to'g'risidagi kodeks"),
    (re.compile(r"ma'muriy\s+sud\s+ish|маъмурий\s+суд|административн\w+\s+судопроизводств", re.I), "Ma'muriy sud ishlarini yuritish to'g'risidagi kodeks"),
    (re.compile(r"mehnat\s+kodeks|меҳнат\s+кодекс|трудов\w+\s+кодекс|labor\s+code|labour\s+code", re.I), "Mehnat kodeksi"),
    (re.compile(r"soliq\s+kodeks|солиқ\s+кодекс|налогов\w+\s+кодекс|tax\s+code", re.I), "Soliq kodeksi"),
    (re.compile(r"bojxona\s+kodeks|божхона\s+кодекс|таможенн\w+\s+кодекс|customs\s+code", re.I), "Bojxona kodeksi"),
    (re.compile(r"yer\s+kodeks|ер\s+кодекс|земельн\w+\s+кодекс|land\s+code", re.I), "Yer kodeksi"),
    (re.compile(r"oila\s+kodeks|оила\s+кодекс|семейн\w+\s+кодекс|family\s+code", re.I), "Oila kodeksi"),
    (re.compile(r"uy-?joy\s+kodeks|уй-?жой\s+кодекс|жилищн\w+\s+кодекс|housing\s+code", re.I), "Uy-joy kodeksi"),
    (re.compile(r"byudjet\s+kodeks|бюджет\s+кодекс|бюджетн\w+\s+кодекс|budget\s+code", re.I), "Byudjet kodeksi"),
    (re.compile(r"shaharsozlik\s+kodeks|шаҳарсозлик\s+кодекс|градостроительн\w+\s+кодекс|urban\s+planning\s+code", re.I), "Shaharsozlik kodeksi"),
    (re.compile(r"iqtisodiy\s+protsessual|иқтисодий\s+процессуал|экономическ\w+\s+процессуальн|economic\s+procedural\s+code", re.I), "Iqtisodiy protsessual kodeksi"),
    (re.compile(r"fuqarolik\s+protsessual|фуқаролик\s+процессуал|гражданск\w+\s+процессуальн|civil\s+procedural\s+code", re.I), "Fuqarolik protsessual kodeksi"),
    (re.compile(r"saylov\s+kodeks|сайлов\s+кодекс|избирательн\w+\s+кодекс|election\s+code", re.I), "Saylov kodeksi"),
    (re.compile(r"havo\s+kodeks|ҳаво\s+кодекс|воздушн\w+\s+кодекс|air\s+code", re.I), "Havo kodeksi"),
]

# Act numbers: O'RQ-682, ЎРҚ-682, ЗРУ-682, PF-158, ПФ-158, УП-158, PQ-450, ПҚ-450, ПП-450, VMQ-123, ПКМ-123
_DOC_NUMBER_RE = re.compile(
    r"\b((?:O'RQ|ЎРҚ|ЗРУ|PF|ПФ|УП|PQ|ПҚ|ПП|VMQ|ВМҚ|ПКМ|F|Ф|Р)-?\s*\d{1,5}(?:-\w+)?)\b",
    re.IGNORECASE,
)

# Direct Lex.uz links embedded in text or extracted HTML links
_LEX_URL_RE = re.compile(
    r"https?://(?:www\.)?lex\.uz/(?:(?:uz|ru|en)/)?docs/(-?\d+)(?:#(\d+))?",
    re.IGNORECASE,
)

# Article references across UZ Latin, UZ Cyrillic, RU, and EN
_ARTICLE_REF_PATTERNS: list[re.Pattern[str]] = [
    # UZ Latin / Cyrillic: "168-moddasida", "148-1-modda", "155-моддасига"
    re.compile(
        r"([A-ZА-ЯЎҚҒҲa-zа-яўқғҳ'\-\s]{0,65}?)\b(\d+(?:[-.]\d+)?)\s*-?\s*(?:modda\w*|модда\w*)",
        re.IGNORECASE,
    ),
    # Russian: "статьей 155 Трудового кодекса", "ст. 168 УК"
    re.compile(
        r"\b(?:стать[еёяйюяи]\w*|ст\.)\s*(\d+(?:[-.]\d+)?)\s*([A-ZА-ЯЁa-zа-яё\-\s]{0,60})",
        re.IGNORECASE,
    ),
    # English: "Article 155 of the Labor Code", "Art. 168"
    re.compile(
        r"\b(?:Article|Art\.)\s*(\d+(?:[-.]\d+)?)(?:\s+of\s+(?:the\s+)?([A-Za-z\-\s]{0,60}))?",
        re.IGNORECASE,
    ),
]


def _detect_code_hint(context: str) -> str | None:
    for pattern, hint in CODE_PATTERNS:
        if pattern.search(context):
            return hint
    return None


def extract_cross_references(
    text: str,
    *,
    html_links: list[tuple[str, str]] | None = None,
    current_doc_id: str | None = None,
) -> list[CrossReference]:
    """Extract structured cross-references to other articles, codes, laws, and Lex.uz IDs."""
    refs: list[CrossReference] = []
    seen_keys: set[tuple[str | None, str | None, str | None, str | None]] = set()
    norm = normalize_uzbek_apostrophes(text)

    def _add(ref: CrossReference) -> None:
        key = (ref.target_doc_id, ref.target_doc_number, ref.target_doc_hint, ref.target_article)
        if key not in seen_keys:
            seen_keys.add(key)
            refs.append(ref)

    # 1. Explicit HTML anchor links from Lex.uz (<a href="/docs/123456">...</a>)
    if html_links:
        for href, anchor_text in html_links:
            m = re.search(r"/docs/(-?\d+)(?:#(\d+))?", href)
            if not m:
                continue
            target_id = m.group(1)
            if current_doc_id and target_id == current_doc_id:
                continue
            full_url = href if href.startswith("http") else f"https://lex.uz{href}"
            art_match = re.search(r"(\d+(?:[-.]\d+)?)\s*-?\s*(?:modda|модда)|(?:ст\.|стать\w+|Article)\s*(\d+(?:[-.]\d+)?)", anchor_text, re.I)
            art = (art_match.group(1) or art_match.group(2)) if art_match else None
            _add(
                CrossReference(
                    raw_text=anchor_text.strip()[:200] or full_url,
                    target_doc_id=target_id,
                    target_doc_hint=_detect_code_hint(anchor_text) or anchor_text.strip()[:120],
                    target_article=art,
                    target_url=full_url,
                )
            )

    # 2. Inline Lex.uz URLs
    for m in _LEX_URL_RE.finditer(norm):
        target_id = m.group(1)
        if current_doc_id and target_id == current_doc_id:
            continue
        _add(
            CrossReference(
                raw_text=m.group(0),
                target_doc_id=target_id,
                target_url=m.group(0),
            )
        )

    # 3. Normative act numbers (O'RQ-682, PF-158, PQ-450, VMQ-123, ЗРУ-682, ПКМ-123)
    for m in _DOC_NUMBER_RE.finditer(norm):
        doc_num = re.sub(r"\s+", "", m.group(1).upper())
        window = norm[max(0, m.start() - 80) : min(len(norm), m.end() + 80)]
        art_match = re.search(r"(\d+(?:[-.]\d+)?)\s*-?\s*(?:modda|модда)|(?:ст\.|стать\w+|Article)\s*(\d+(?:[-.]\d+)?)", window, re.I)
        art = (art_match.group(1) or art_match.group(2)) if art_match else None
        _add(
            CrossReference(
                raw_text=window.strip()[:180],
                target_doc_number=doc_num,
                target_doc_hint=_detect_code_hint(window),
                target_article=art,
            )
        )

    # 4. Article mentions referencing named codes or same/external statutes
    for idx, pat in enumerate(_ARTICLE_REF_PATTERNS):
        for m in pat.finditer(norm):
            if idx == 0:
                context, art_num = m.group(1) or "", m.group(2)
            else:
                art_num, context = m.group(1), m.group(2) or ""
            # Also inspect surrounding context for code names
            around = norm[max(0, m.start() - 90) : min(len(norm), m.end() + 90)]
            hint = _detect_code_hint(context) or _detect_code_hint(around)
            if hint:
                _add(
                    CrossReference(
                        raw_text=m.group(0).strip()[:160],
                        target_doc_hint=hint,
                        target_article=art_num,
                    )
                )

    return refs[:25]
