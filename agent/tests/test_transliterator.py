"""Tests for Uzbek Latin <-> Cyrillic transliteration and UZ/RU/EN script detection."""

from lex_agent.language.transliterator import (
    cyrillic_to_latin,
    detect_language,
    latin_to_cyrillic,
    normalize_uzbek_apostrophes,
)
from lex_agent.models import Language


def test_normalize_apostrophes() -> None:
    assert normalize_uzbek_apostrophes("Oʻzbekiston Respublikasi maʼmuriy g‘oya") == "O'zbekiston Respublikasi ma'muriy g'oya"


def test_cyrillic_to_latin() -> None:
    cyr = "Ўзбекистон Республикаси Конституцияси 1-модда"
    lat = cyrillic_to_latin(cyr)
    assert lat == "O'zbekiston Respublikasi Konstitutsiyasi 1-modda"


def test_latin_to_cyrillic() -> None:
    lat = "O'zbekiston Respublikasi Mehnat kodeksi"
    cyr = latin_to_cyrillic(lat)
    assert "Ўзбекистон" in cyr
    assert "Меҳнат" in cyr


def test_language_detection_all_four_variants() -> None:
    assert detect_language("O'zbekiston Respublikasi Mehnat kodeksining 161-moddasi") == Language.UZ_LATN
    assert detect_language("Ўзбекистон Республикаси Меҳнат кодексининг 161-моддаси") == Language.UZ_CYRL
    assert detect_language("Статья 161 Трудового кодекса Республики Узбекистан") == Language.RU
    assert detect_language("What does Article 161 of the Labor Code of Uzbekistan provide?") == Language.EN
