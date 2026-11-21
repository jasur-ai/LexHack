"""English names of the acts people ask about most (the official texts exist only in Uzbek and Russian).

Used for English readers: answer labels and source titles say "Labour Code, art. 217" instead of an Uzbek
title the reader may not understand. Keys are canonical lex.uz document ids.
"""

from __future__ import annotations

import re

EN_TITLES: dict[str, str] = {
    "6445145": "Constitution of the Republic of Uzbekistan",
    "6257288": "Labour Code",
    "104720": "Family Code",
    "111189": "Civil Code (Part 1)",
    "180552": "Civil Code (Part 2)",
    "97664": "Code of Administrative Responsibility",
    "111453": "Criminal Code",
    "111460": "Criminal Procedure Code",
    "3517337": "Civil Procedure Code",
    "4674902": "Tax Code",
    "106136": "Housing Code",
    "152653": "Land Code",
    "4704": "Law on Consumer Rights Protection",
    "4680944": "Law on State Duty",
    "3336169": "Law on Appeals of Individuals and Legal Entities",
    "112314": "Law on State Pensions",
    "26477": "Law on Enforcement of Judicial Acts",
    "54458": "Law on Notariat",
    "6502543": "Law on State-Guaranteed Legal Aid",
    "5055690": "Law on Employment",
    "4396419": "Law on Personal Data",
    "6764454": "Law on Road Traffic",
    "1004687": "Law on Consumer Credit",
    "1342474": "Law on Compulsory Motor Third-Party Liability Insurance",
    "7623461": "Law on Residence Registration",
    "4761984": "Law on Citizenship",
    "78717": "Law on Universal Military Duty and Military Service",
    "8151376": "Law on Limited Liability Companies",
    "5511879": "Law on Licensing and Notification Procedures",
    "2006789": "Law on Guarantees of Freedom of Entrepreneurship",
    "4494709": "Law on Protection of Women from Harassment and Violence",
    "7886679": "Law on Social Insurance",
    "practical-facts": "Practical figures (BHM, minimum wage, rates)",
}

_ART_RE = re.compile(r"(\d+(?:[.\-]\d+)?[¹²³⁴⁵⁶⁷⁸⁹]*)")


def en_title(canonical_id: str | None) -> str | None:
    return EN_TITLES.get(str(canonical_id or ""))


def en_article(article: str | None) -> str:
    """'217-modda' / 'Статья 217' -> 'art. 217'."""
    if not article:
        return ""
    m = _ART_RE.search(article)
    return f"art. {m.group(1)}" if m else article
