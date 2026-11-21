"""Structure-aware hierarchical legal parser & chunker (Section -> Chapter -> Article -> Clause)."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime

from lex_agent.language.transliterator import (
    normalize_uzbek_apostrophes,
    to_searchable_uzbek_latin,
)
from lex_agent.models import (
    LEGAL_FORCE_HIERARCHY,
    DocumentMetadata,
    DocumentType,
    LegalBranch,
    LegalChunk,
)
from lex_agent.reasoning.cross_ref import extract_cross_references

# Structural heading patterns across UZ Latin, UZ Cyrillic, RU, and EN
_SECTION_RE = re.compile(
    r"^(?:(?:[IVXLCDM]+|\d+)\s*-?\s*(?:bo'lim|бўлим)|(?:раздел|section|part)\s+(?:[IVXLCDM]+|\d+))\b.*$",
    re.IGNORECASE,
)
_CHAPTER_RE = re.compile(
    r"^(?:(?:[IVXLCDM]+|\d+(?:-\d+)?)\s*-?\s*(?:bob|боб)|(?:глава|chapter)\s+(?:[IVXLCDM]+|\d+(?:-\d+)?))\b.*$",
    re.IGNORECASE,
)
_ARTICLE_RE = re.compile(
    r"^(?:(?P<num_uz>\d+(?:[-.]\d+)?)\s*-?\s*(?:modda|модда)\.?\s*(?P<title_uz>.*)|"
    r"(?:статья|article)\s+(?P<num_ru_en>\d+(?:[-.]\d+)?)\.?\s*(?P<title_ru_en>.*))$",
    re.IGNORECASE,
)
_CLAUSE_RE = re.compile(
    r"^(?:(?:\d+(?:\.\d+)*\.)|(?:\d+\))|(?:[a-zа-яё]\))|(?:[a-zа-яё]-band))\s+",
    re.IGNORECASE,
)


def parse_date_string(raw: str | date | None) -> date | None:
    """Parse DD.MM.YYYY, YYYY-MM-DD, or ISO timestamp strings into a `date`."""
    if raw is None:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    s = str(raw).strip()
    if not s:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y.%m.%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def classify_document_type(title: str, body_preview: str = "") -> DocumentType:
    """Classify Uzbekistan normative-legal act into its exact legal hierarchy level."""
    combined = normalize_uzbek_apostrophes(f"{title}\n{body_preview[:600]}").lower()

    if re.search(r"o'zbekiston\s+respublikasi\w*\s+konstitutsiya|конституци[яи]\s+республики\s+узбекистан|constitution\s+of\s+the\s+republic\s+of\s+uzbekistan", combined):
        if re.search(r"konstitutsiyaviy\s+qonun|конституционн\w+\s+закон|constitutional\s+law", combined):
            return DocumentType.CONSTITUTIONAL_LAW
        return DocumentType.CONSTITUTION
    if re.search(r"konstitutsiyaviy\s+qonun|конституционн\w+\s+закон|constitutional\s+law", combined):
        return DocumentType.CONSTITUTIONAL_LAW
    if re.search(r"\bkodeks\w*|\bкодекс\w*|\bcode\b", title.lower()):
        return DocumentType.CODE
    if re.search(r"oliy\s+sud\w*\s+plenum|пленум\w*\s+верховного\s+суда|plenum\s+of\s+the\s+supreme\s+court", combined):
        return DocumentType.SUPREME_COURT_PLENUM
    if re.search(r"prezident\w*\s+farmoni|\bpf-\d+|указ\s+президента|\bуп-\d+|presidential\s+decree|decree\s+of\s+the\s+president", combined):
        return DocumentType.PRESIDENTIAL_DECREE
    if re.search(r"prezident\w*\s+qarori|\bpq-\d+|постановление\s+президента|\bпп-\d+|resolution\s+of\s+the\s+president", combined):
        return DocumentType.PRESIDENTIAL_RESOLUTION
    if re.search(r"prezident\w*\s+farmoyishi|распоряжение\s+президента|order\s+of\s+the\s+president", combined):
        return DocumentType.PRESIDENTIAL_ORDER
    if re.search(r"vazirlar\s+mahkama\w*\s+qarori|\bvmq-\d+|кабинет\w*\s+министров|\bпкм-\d+|cabinet\s+of\s+ministers", combined):
        if re.search(r"farmoyishi|распоряжение|order", combined):
            return DocumentType.CABINET_ORDER
        return DocumentType.CABINET_RESOLUTION
    if re.search(r"oliy\s+majlis\w*\s+qarori|палат\w*\s+олий\s+мажлиса", combined):
        return DocumentType.OLIY_MAJLIS_RESOLUTION
    if re.search(r"xalqaro\s+shartnoma|konvensiya|битим|соглашение\s+между\s+правительством|treaty|convention", combined):
        return DocumentType.INTERNATIONAL_TREATY
    if re.search(r"o'zbekiston\s+respublikasi\w*\s+qonuni|\bo'rq-\d+|закон\s+республики\s+узбекистан|\bзру-\d+|\blaw\s+of\s+the\s+republic\s+of\s+uzbekistan", combined):
        return DocumentType.LAW
    if re.search(r"vazirligi|qo'mitasi|agentligi|markaziy\s+bank|министерств|государственн\w+\s+комитет|приказ|buyrug'i", combined):
        return DocumentType.DEPARTMENTAL_ACT
    if re.search(r"hokimi\w*\s+qarori|kengashi\w*\s+qarori|хоким|кенгаш", combined):
        return DocumentType.LOCAL_GOVERNMENT_ACT
    return DocumentType.OTHER


_BRANCH_KEYWORDS: dict[LegalBranch, tuple[str, ...]] = {
    LegalBranch.CONSTITUTIONAL: ("konstitutsiya", "saylov", "oliy majlis", "конституц", "выбор", "constitution", "parliament"),
    LegalBranch.CIVIL: ("fuqarolik", "shartnoma", "mulk", "meros", "majburiyat", "гражданск", "договор", "собственност", "civil", "contract"),
    LegalBranch.CRIMINAL: ("jinoyat", "jazo", "ozodlikdan mahrum", "уголовн", "преступлен", "наказан", "criminal", "offense"),
    LegalBranch.ADMINISTRATIVE: ("ma'muriy javobgarlik", "jarima", "маъмурий", "административн", "штраф", "administrative"),
    LegalBranch.TAX: ("soliq", "qqs", "foyda solig'i", "солиқ", "налог", "ндс", "tax", "vat"),
    LegalBranch.LABOR: ("mehnat", "ish haqi", "xodim", "ish beruvchi", "меҳнат", "трудов", "работник", "зарплат", "labor", "employment"),
    LegalBranch.CORPORATE_COMMERCIAL: ("mchj", "aksiyadorlik", "tadbirkor", "korxona", "банкрот", "ооо", "акционерн", "предпринимат", "corporate", "llc"),
    LegalBranch.BANKING_FINANCE: ("bank", "valyuta", "kredit", "qimmatli qog'oz", "банк", "валют", "кредит", "ценн", "banking", "finance"),
    LegalBranch.CUSTOMS: ("bojxona", "import", "eksport", "божхона", "таможен", "customs", "tariff"),
    LegalBranch.LAND_REAL_ESTATE: ("yer", "kadastr", "ko'chmas mulk", "земельн", "кадастр", "недвижимост", "land", "real estate"),
    LegalBranch.FAMILY: ("oila", "nikoh", "aliment", "семейн", "брак", "алимент", "family", "marriage"),
    LegalBranch.HOUSING: ("uy-joy", "kvartira", "жилищн", "housing"),
    LegalBranch.INTELLECTUAL_PROPERTY: ("mualliflik", "patent", "tovar belgisi", "интеллектуальн", "патент", "copyright", "trademark", "intellectual property"),
    LegalBranch.DIGITAL_IT_DATA: ("shaxsga doir ma'lumot", "kiberxavfsizlik", "raqamli", "elektron tijorat", "персональн", "кибербезопасност", "цифров", "personal data", "digital", "cyber"),
    LegalBranch.ENVIRONMENTAL_NATURAL: ("ekologiya", "tabiat", "suv", "эколог", "природ", "environment"),
    LegalBranch.PROCEDURAL_CIVIL: ("fuqarolik protsessual", "гражданск.*процессуальн", "civil procedure"),
    LegalBranch.PROCEDURAL_ECONOMIC: ("iqtisodiy protsessual", "экономическ.*процессуальн", "economic procedure"),
    LegalBranch.PROCEDURAL_CRIMINAL: ("jinoyat-protsessual", "уголовно-процессуальн", "criminal procedure"),
    LegalBranch.PROCEDURAL_ADMIN: ("ma'muriy sud", "административн.*судопроизводств", "administrative procedure"),
    LegalBranch.INVESTMENT_PPP: ("investitsiya", "dxsh", "инвестиц", "гчп", "investment", "ppp"),
    LegalBranch.SOCIAL_EDUCATION_HEALTH: ("ta'lim", "sog'liqni saqlash", "pensiya", "образован", "здравоохранен", "пенси", "education", "healthcare"),
}


def classify_branches(title: str, body_preview: str = "") -> list[LegalBranch]:
    """Tag a normative-legal act with all relevant Uzbekistan legal branches."""
    text = normalize_uzbek_apostrophes(f"{title}\n{body_preview[:2500]}").lower()
    matched: list[LegalBranch] = []
    for branch, keywords in _BRANCH_KEYWORDS.items():
        if any(re.search(kw, text) for kw in keywords):
            matched.append(branch)
    return matched or [LegalBranch.GENERAL]


class LegalDocumentParser:
    """Parses full Uzbekistan legal documents into hierarchical Section -> Chapter -> Article -> Clause chunks."""

    def __init__(self, max_chunk_chars: int = 1800, chunk_overlap_chars: int = 180) -> None:
        self.max_chunk_chars = max_chunk_chars
        self.chunk_overlap_chars = chunk_overlap_chars

    def parse_to_chunks(
        self,
        metadata: DocumentMetadata,
        raw_text: str,
        *,
        html_links: list[tuple[str, str]] | None = None,
        article_anchors: dict[str, str] | None = None,
    ) -> list[LegalChunk]:
        """Split a legal text into structure-aware chunks preserving statutory hierarchy and cross-references."""
        if not raw_text or not raw_text.strip():
            return []

        article_anchors = article_anchors or {}
        cleaned = normalize_uzbek_apostrophes(raw_text)
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]

        # Ensure metadata has accurate hierarchy rank and branches
        if metadata.legal_force_rank <= 20 and metadata.doc_type != DocumentType.OTHER:
            metadata.legal_force_rank = LEGAL_FORCE_HIERARCHY.get(metadata.doc_type, 20)
        if not metadata.branches or metadata.branches == [LegalBranch.GENERAL]:
            metadata.branches = classify_branches(metadata.title, cleaned[:2500])

        current_section: str | None = None
        current_chapter: str | None = None
        current_article: str | None = None
        current_article_title: str | None = None
        buffer: list[str] = []

        structured_units: list[dict[str, str | None]] = []

        def flush_buffer() -> None:
            if not buffer:
                return
            body = "\n".join(buffer).strip()
            if len(body) >= 20:
                structured_units.append(
                    {
                        "section": current_section,
                        "chapter": current_chapter,
                        "article": current_article,
                        "article_title": current_article_title,
                        "text": body,
                    }
                )
            buffer.clear()

        for line in lines:
            if _SECTION_RE.match(line) and len(line) < 220:
                flush_buffer()
                current_section = line
                current_chapter = None
                continue

            if _CHAPTER_RE.match(line) and len(line) < 220:
                flush_buffer()
                current_chapter = line
                continue

            art_m = _ARTICLE_RE.match(line)
            if art_m and len(line) < 260:
                flush_buffer()
                art_num = art_m.group("num_uz") or art_m.group("num_ru_en")
                art_title = (art_m.group("title_uz") or art_m.group("title_ru_en") or "").strip(" .:-")
                current_article = f"Article {art_num}" if metadata.language.value == "en" else (
                    f"Статья {art_num}" if metadata.language.value == "ru" else f"{art_num}-modda"
                )
                current_article_title = art_title or None
                buffer.append(line)
                continue

            buffer.append(line)

        flush_buffer()

        chunks: list[LegalChunk] = []
        seq = 0
        for unit in structured_units:
            art_label = unit["article"]
            art_num_only = None
            if art_label:
                m_num = re.search(r"(\d+(?:[-.]\d+)?)", art_label)
                art_num_only = m_num.group(1) if m_num else None
            anchor = article_anchors.get(art_num_only or "") if art_num_only else None

            sub_parts = self._split_by_clauses(unit["text"] or "")
            for clause_label, part_text in sub_parts:
                seq += 1
                header_prefix = self._format_header(
                    metadata=metadata,
                    section=unit["section"],
                    chapter=unit["chapter"],
                    article=art_label,
                    article_title=unit["article_title"],
                )
                full_chunk_text = f"{header_prefix}\n{part_text}".strip()
                searchable_latin = to_searchable_uzbek_latin(full_chunk_text, language=metadata.language)
                cross_refs = extract_cross_references(
                    part_text,
                    html_links=html_links if seq == 1 else None,
                    current_doc_id=metadata.doc_id,
                )
                chunk_id = self._make_chunk_id(metadata.doc_id, metadata.language.value, art_label, clause_label, seq)

                chunks.append(
                    LegalChunk(
                        chunk_id=chunk_id,
                        doc_id=metadata.doc_id,
                        canonical_id=metadata.canonical_id,
                        language=metadata.language,
                        doc_type=metadata.doc_type,
                        doc_number=metadata.doc_number,
                        doc_title=metadata.title,
                        issuing_body=metadata.issuing_body,
                        adoption_date=metadata.adoption_date,
                        effective_date=metadata.effective_date,
                        expiry_date=metadata.expiry_date,
                        status=metadata.status,
                        legal_force_rank=metadata.legal_force_rank,
                        branches=metadata.branches,
                        section=unit["section"],
                        chapter=unit["chapter"],
                        article=art_label,
                        article_title=unit["article_title"],
                        clause=clause_label,
                        text=full_chunk_text,
                        normalized_text=searchable_latin,
                        url=metadata.url,
                        anchor=anchor,
                        cross_references=cross_refs,
                    )
                )

        return chunks

    def _split_by_clauses(self, text: str) -> list[tuple[str | None, str]]:
        """Keep articles intact when under limit; otherwise split cleanly on clause/paragraph boundaries."""
        if len(text) <= self.max_chunk_chars:
            return [(None, text)]

        paragraphs = text.splitlines()
        parts: list[tuple[str | None, str]] = []
        current_lines: list[str] = []
        current_len = 0
        current_clause: str | None = None

        for para in paragraphs:
            clause_m = _CLAUSE_RE.match(para)
            detected_clause = clause_m.group(0).strip() if clause_m else None

            if current_lines and current_len + len(para) + 1 > self.max_chunk_chars:
                parts.append((current_clause, "\n".join(current_lines).strip()))
                # Keep small tail overlap if a single paragraph was long
                tail = current_lines[-1][-self.chunk_overlap_chars :] if self.chunk_overlap_chars > 0 else ""
                current_lines = [tail] if tail and len(tail) > 40 else []
                current_len = sum(len(x) for x in current_lines)
                current_clause = detected_clause

            if detected_clause and not current_clause:
                current_clause = detected_clause
            current_lines.append(para)
            current_len += len(para) + 1

        if current_lines:
            parts.append((current_clause, "\n".join(current_lines).strip()))
        return parts

    @staticmethod
    def _format_header(
        *,
        metadata: DocumentMetadata,
        section: str | None,
        chapter: str | None,
        article: str | None,
        article_title: str | None,
    ) -> str:
        bits = [metadata.title]
        if metadata.doc_number:
            bits.append(f"[{metadata.doc_number}]")
        if metadata.adoption_date:
            bits.append(f"({metadata.adoption_date.isoformat()})")
        hierarchy = " > ".join(p for p in (section, chapter, article) if p)
        if hierarchy:
            bits.append(f"| {hierarchy}")
        if article_title:
            bits.append(f"— {article_title}")
        return " ".join(bits)

    @staticmethod
    def _make_chunk_id(
        doc_id: str,
        lang: str,
        article: str | None,
        clause: str | None,
        seq: int,
    ) -> str:
        raw = f"{doc_id}|{lang}|{article or ''}|{clause or ''}|{seq}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
