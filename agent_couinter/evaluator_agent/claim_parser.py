"""Zero-Trust Atomic Claim & Citation Parser covering all 26+ Uzbekistan Codes, Laws & statutory assertions."""

from __future__ import annotations

import re
from typing import Any

from evaluator_agent.models import ExtractedClaim

_APOSTROPHE_RE = re.compile(r"[ʻʼ‘’`´ʹʽˈ]")
_LEX_URL_RE = re.compile(r"https?://(?:www\.)?lex\.uz/(?:(?:uz|ru|en)/)?docs/(-?\d+)(?:#\d+)?", re.I)

_SUPERSCRIPT_MAP = str.maketrans({
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
})
_DIGIT_TO_SUPER = str.maketrans({
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
})


def normalize_article_number(raw: str) -> str:
    """Convert Unicode superscript article numbers ('47⁷', '332¹', '27¹') to canonical '47-7', '332-1', '27-1'."""
    s = (raw or "").strip()
    m = re.match(r"^(\d+)([⁰¹²³⁴⁵⁶⁷⁸⁹]+)$", s)
    if m:
        return f"{m.group(1)}-{m.group(2).translate(_SUPERSCRIPT_MAP)}"
    # Also handle embedded superscript inside string like '47⁷-modda'
    s = re.sub(
        r"(\d+)([⁰¹²³⁴⁵⁶⁷⁸⁹]+)",
        lambda match: f"{match.group(1)}-{match.group(2).translate(_SUPERSCRIPT_MAP)}",
        s,
    )
    return s


def article_search_variants(art: str) -> list[str]:
    """Return all representations of an article number ('47-7', '47⁷', '47.7', '47-7-modda', '47⁷-modda')."""
    canon = normalize_article_number(art)
    variants = [canon]
    if "-" in canon:
        base, sub = canon.split("-", 1)
        if sub.isdigit():
            sup = f"{base}{sub.translate(_DIGIT_TO_SUPER)}"
            variants.extend([sup, f"{base}.{sub}"])
    out: list[str] = []
    for v in variants:
        out.extend([v, f"{v}-modda", f"{v}-модда", f"Статья {v}"])
    return list(dict.fromkeys(out))

_CYRL_TO_LATN_MAP: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh",
    "ъ": "'", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
}


def transliterate_cyrl_to_latn(text: str) -> str:
    """Resilient Uzbek Cyrillic -> Latin transliterator for cross-script claim & fact matching."""
    out: list[str] = []
    for ch in text:
        low = ch.lower()
        if low in _CYRL_TO_LATN_MAP:
            rep = _CYRL_TO_LATN_MAP[low]
            out.append(rep.capitalize() if ch.isupper() else rep)
        else:
            out.append(ch)
    return _APOSTROPHE_RE.sub("'", "".join(out))
_DOC_NUM_RE = re.compile(
    r"\b((?:O'RQ|ЎРҚ|ЗРУ|PF|ПФ|УП|PQ|ПҚ|ПП|VMQ|ВМҚ|ПКМ)-?\s*\d{1,5})\b",
    re.I,
)
_ARTICLE_RE = re.compile(
    r"\b(\d+(?:[-.]\d+|[⁰¹²³⁴⁵⁶⁷⁸⁹]+)?)\s*-?\s*(?:modda\w*|модда\w*)|\b(?:стать[еёяйюяи]\w*|ст\.|Article|Art\.)\s*(\d+(?:[-.]\d+|[⁰¹²³⁴⁵⁶⁷⁸⁹]+)?)\b",
    re.I,
)

# All 26+ Uzbekistan Codes & Organic Laws mapped to canonical registry names
_CODE_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"konstitutsiya|конституц|constitution", re.I), "Konstitutsiya"),
    (re.compile(r"1995-?yilgi\s+mehnat|1995\s+labor\s+code|трудов\w+\s+кодекс\w*\s+1995", re.I), "Eski Mehnat kodeksi (1995)"),
    (re.compile(r"mehnat\s+kodeks|меҳнат\s+кодекс|трудов\w+\s+кодекс|labor\s+code", re.I), "Mehnat kodeksi"),
    (re.compile(r"soliq\s+kodeks|солиқ\s+кодекс|налогов\w+\s+кодекс|tax\s+code|\bнк\s+руз\b", re.I), "Soliq kodeksi"),
    (re.compile(r"oila\s+kodeks|оила\s+кодекс|семейн\w+\s+кодекс|family\s+code|\bск\s+руз\b", re.I), "Oila kodeksi"),
    (re.compile(r"fuqarolik\s+protsessual|фуқаролик\s+процессуал|гражданск\w+\s+процессуальн|civil\s+procedur", re.I), "Fuqarolik protsessual kodeksi"),
    (re.compile(r"iqtisodiy\s+protsessual|иқтисодий\s+процессуал|экономическ\w+\s+процессуальн|economic\s+procedur", re.I), "Iqtisodiy protsessual kodeksi"),
    (re.compile(r"jinoyat-?protsessual|жиноят-?процессуал|уголовно-?процессуальн|criminal\s+procedur|\bjpk\b|\bупк\b", re.I), "Jinoyat-protsessual kodeksi"),
    (re.compile(r"ma'muriy\s+sud\s+ishlari|маъмурий\s+суд\s+ишлари|административн\w+\s+судопроизводств", re.I), "Ma'muriy sud ishlarini yuritish kodeksi"),
    (re.compile(r"fuqarolik\s+kodeks|фуқаролик\s+кодекс|гражданск\w+\s+кодекс|civil\s+code|\bгк\s+руз\b|\bfk\b", re.I), "Fuqarolik kodeksi"),
    (re.compile(r"jinoyat\s+kodeks|жиноят\s+кодекс|уголовн\w+\s+кодекс|criminal\s+code|\bук\s+руз\b|\bjk\b", re.I), "Jinoyat kodeksi"),
    (re.compile(r"ma'muriy\s+javobgarlik|маъмурий\s+жавобгарлик|мжтк|\bmjtk\b|коао|административн\w+\s+ответственност", re.I), "MJtK"),
    (re.compile(r"bojxona\s+kodeks|божхона\s+кодекс|таможенн\w+\s+кодекс|customs\s+code", re.I), "Bojxona kodeksi"),
    (re.compile(r"yer\s+kodeks|ер\s+кодекс|земельн\w+\s+кодекс|land\s+code", re.I), "Yer kodeksi"),
    (re.compile(r"uy-?joy\s+kodeks|уй-?жой\s+кодекс|жилищн\w+\s+кодекс|housing\s+code", re.I), "Uy-joy kodeksi"),
    (re.compile(r"budjet\s+kodeks|буджет\s+кодекс|бюджетн\w+\s+кодекс|budget\s+code", re.I), "Budjet kodeksi"),
    (re.compile(r"shaharsozlik\s+kodeks|шаҳарсозлик\s+кодекс|градостроительн\w+\s+кодекс|urban\s+planning", re.I), "Shaharsozlik kodeksi"),
    (re.compile(r"saylov\s+kodeks|сайлов\s+кодекс|избирательн\w+\s+кодекс|election\s+code", re.I), "Saylov kodeksi"),
    (re.compile(r"havo\s+kodeks|ҳаво\s+кодекс|воздушн\w+\s+кодекс|air\s+code", re.I), "Havo kodeksi"),
    (re.compile(r"shaxsga\s+doir\s+ma'lumot|персональн\w+\s+данн|personal\s+data|547", re.I), "Shaxsga doir ma'lumotlar to'g'risida"),
    (re.compile(r"normativ-huquqiy|нормативно-правов|normative-legal|682", re.I), "Normativ-huquqiy hujjatlar to'g'risida"),
    (re.compile(r"iste'molchi\w*\s+huquq|защит\w+\s+прав\s+потребител|consumer\s+rights", re.I), "Iste'molchilarning huquqlarini himoya qilish to'g'risida"),
    (re.compile(r"mas'uliyati\s+cheklangan|обществ\w+\s+с\s+ограниченной", re.I), "Mas'uliyati cheklangan jamiyatlar to'g'risida"),
    (re.compile(r"manfaatlar\s+to'qnashuvi|конфликт\w+\s+интересов|conflict\s+of\s+interest|931", re.I), "Manfaatlar to'qnashuvi to'g'risida"),
    (re.compile(r"sudlar\s+to'g'risida|о\s+судах|703", re.I), "Sudlar to'g'risida"),
    (re.compile(r"advokatura\s+to'g'risida|об\s+адвокатуре|law\s+on\s+advocacy", re.I), "Advokatura to'g'risida"),
    (re.compile(r"data\.egov\.uz|ochiq\s+ma'lumotlar\s+portali|6247|open\s+data\s+portal", re.I), "Ochiq ma'lumotlar portali va davlat organlari ochiqligi (PF-6247)"),
    (re.compile(r"organlari\s+faoliyatining\s+ochiqligi|об\s+открытости\s+деятельности|369", re.I), "Davlat hokimiyati va boshqaruvi organlari faoliyatining ochiqligi to'g'risida"),
    (re.compile(r"elektron\s+hukumat|электронн\w+\s+правительств|e-?government|395", re.I), "Elektron hukumat to'g'risida"),
    (re.compile(r"elektron\s+tijorat|электронн\w+\s+коммерц|e-?commerce|792", re.I), "Elektron tijorat to'g'risida"),
    (re.compile(r"jinoyat-?ijroiya|уголовно-исполнительн", re.I), "Jinoyat-ijroiya kodeksi"),
]

# Topic-to-(Code, Article) inference when Target Agent makes an implicit statutory claim without citing the article number
_IMPLICIT_TOPIC_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"aliment|алимент|26[,.]5\s*%|mhtekm|мрот", re.I), "Oila kodeksi", "99"),
    (re.compile(r"sinov\s+muddat|dastlabki\s+sinov|испытательн\w+\s+срок", re.I), "Mehnat kodeksi", "129"),
    (re.compile(r"mehnat\s+ta'til|yillik\s+asosiy\s+.*ta'til|15\s+ish\s+kuni|21\s+kalendar|трудов\w+\s+отпуск", re.I), "Mehnat kodeksi", "217"),
    (re.compile(r"ishdan\s+bo'shatish\s+nafaqa|выходн\w+\s+пособи", re.I), "Mehnat kodeksi", "173"),
    (re.compile(r"\bqqs\b|\bндс\b|qo'shilgan\s+qiymat\s+solig", re.I), "Soliq kodeksi", "258"),
    (re.compile(r"50\s*%\s*chegirma|50\s*%\s*чегирма|soddalashtirilgan.*jarima", re.I), "MJtK", "332-1"),
    (re.compile(r"tilxat|расписк|qarz\s+shartnoma.*yozma", re.I), "Fuqarolik kodeksi", "733"),
    (re.compile(r"neustoykani\s+kamaytir|penya.*kamaytir|уменьшить\s+неустойк", re.I), "Fuqarolik kodeksi", "326"),
    (re.compile(r"48\s+soat|48\s+час|habeas\s+corpus", re.I), "Konstitutsiya", "27"),
    (re.compile(r"manfaatlar\s+to'qnashuvi|конфликт\w+\s+интересов", re.I), "Manfaatlar to'qnashuvi to'g'risida", "21"),
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
    protected = re.sub(r"\b(ст|ч|п|пп|г|art|no|y)\.\s+(?=\d)", r"\1<ABBR_DOT> ", norm_text, flags=re.I)
    sentences = [
        s.replace("<ABBR_DOT>", ".").strip()
        for s in re.split(r"(?<=[.!?\n])\s+", protected)
        if len(s.strip()) >= 15
    ]

    last_code_hint: str | None = None
    for sent in sentences:
        urls = list(_LEX_URL_RE.finditer(sent))
        doc_nums = [re.sub(r"\s+", "", m.group(1).upper()) for m in _DOC_NUM_RE.finditer(sent)]
        arts = [normalize_article_number(a or b) for a, b in _ARTICLE_RE.findall(sent) if (a or b)]
        code_hint = _detect_code_title(sent) or (last_code_hint if arts else None)
        if code_hint:
            last_code_hint = code_hint
        claimed_status = _detect_claimed_status(sent)

        if not (urls or doc_nums or arts or code_hint):
            continue

        url_id = urls[0].group(1) if urls else None
        url_str = urls[0].group(0) if urls else None
        doc_num = doc_nums[0] if doc_nums else None

        if not arts:
            for t_pat, t_code, t_art in _IMPLICIT_TOPIC_RULES:
                if t_pat.search(sent):
                    code_hint = code_hint or t_code
                    arts = [t_art]
                    break

        if arts:
            for art in list(dict.fromkeys(arts))[:5]:
                key = (url_id, doc_num, code_hint, art)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                seq += 1
                claims.append(
                    ExtractedClaim(
                        claim_id=f"CLM-{seq:02d}",
                        claim_text=sent[:400],
                        cited_doc_id=url_id,
                        cited_doc_number=doc_num,
                        cited_doc_title=code_hint,
                        cited_article=art,
                        cited_url=url_str,
                        claimed_status=claimed_status,
                    )
                )
        elif urls or doc_nums or code_hint:
            key = (url_id, doc_num, code_hint, None)
            if key not in seen_keys:
                seen_keys.add(key)
                seq += 1
                claims.append(
                    ExtractedClaim(
                        claim_id=f"CLM-{seq:02d}",
                        claim_text=sent[:400],
                        cited_doc_id=url_id,
                        cited_doc_number=doc_num,
                        cited_doc_title=code_hint,
                        cited_url=url_str,
                        claimed_status=claimed_status,
                    )
                )

    # Also treat structured citations returned by Target Agent as UNTRUSTED claims to cross-check independently
    for rc in (reported_citations or [])[:10]:
        doc_id = str(rc.get("doc_id") or "").strip() or None
        doc_num = str(rc.get("doc_number") or "").strip() or None
        title = str(rc.get("doc_title") or "").strip() or None
        if title:
            detected = _detect_code_title(title)
            if detected:
                title = detected
        raw_art = normalize_article_number(str(rc.get("article") or "").strip())
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

    return claims[:24]
