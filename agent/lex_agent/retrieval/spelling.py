"""Typo-tolerant questions: map words the corpus has never seen to the closest real word.

People type fast on phones: "alimet" (aliment), "sinof" (sinov), "darmod" (daromad), "murojat" (murojaat),
"увалнение". Correction works on *surface words* — the unstemmed, folded words of the corpus with their document
frequency, stored next to the index at build time — and only then stems the replacement, so the result always
matches indexed terms. Distance is optimal string alignment (a transposition counts as one edit): one edit for
words up to six letters, two for longer ones. Among equally close words a same-length one (a substitution) wins,
then the more frequent. Indexes built before the surface word list existed fall back to stemmed terms.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import TYPE_CHECKING

from lex_agent.language.textproc import stem_token, surface_tokens

if TYPE_CHECKING:
    from lex_agent.retrieval.bm25_store import BM25Store

logger = logging.getLogger(__name__)

try:  # rapidfuzz is a declared dependency; the fallback keeps the agent working if it is missing
    from rapidfuzz.distance import OSA

    def _distance(a: str, b: str, cutoff: int) -> int:
        return OSA.distance(a, b, score_cutoff=cutoff)

except Exception:  # pragma: no cover - exercised only without rapidfuzz

    def _distance(a: str, b: str, cutoff: int) -> int:
        if abs(len(a) - len(b)) > cutoff:
            return cutoff + 1
        prev2: list[int] = []
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i] + [0] * len(b)
            for j, cb in enumerate(b, 1):
                cost = 0 if ca == cb else 1
                cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
                if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                    cur[j] = min(cur[j], prev2[j - 2] + 1)
            prev2, prev = prev, cur
        return min(prev[-1], cutoff + 1)


def _norm(word: str) -> str:
    return word.replace("x", "h").replace("q", "k")


def _same_family(typed: str, fixed: str) -> bool:
    """A correction that keeps the word recognisable (same first four letters after x/h, q/k merging)."""
    a, b = _norm(typed), _norm(fixed)
    return a == b or a[:4] == b[:4]


def max_edits(word: str) -> int:
    n = len(word)
    if n < 4:
        return 0
    return 1 if n <= 6 else 2


_MISSING = object()

class SpellingCorrector:
    """Nearest-corpus-word lookup, bucketed by (first letter, length) for speed."""

    def __init__(self, store: BM25Store, *, min_doc_freq: int = 2) -> None:
        self.store = store
        self.min_doc_freq = min_doc_freq
        self._buckets: dict[tuple[str, int], list[tuple[str, int]]] | None = None
        self._known: dict[str, int] = {}
        self._stems: set[str] = set()
        self._surface = False
        self._lock = threading.Lock()
        self._cache: dict[str, str | None] = {}
        self._prefix_cache: dict[int, dict[str, list[str]]] = {}

    # ------------------------------------------------------------------ vocabulary
    def _ensure(self) -> None:
        if self._buckets is not None:
            return
        with self._lock:
            if self._buckets is not None:
                return
            words = [(w, df) for w, df in self.store.surface_vocabulary() if df >= self.min_doc_freq]
            self._surface = bool(words)
            if not words:  # older index: fall back to stemmed terms
                words = self.store.vocabulary(min_doc_freq=self.min_doc_freq)
            buckets: dict[tuple[str, int], list[tuple[str, int]]] = defaultdict(list)
            known: dict[str, int] = {}
            for term, df in words:
                if not term.isalpha() or len(term) < 3:
                    continue
                known[term] = df
                buckets[(term[0], len(term))].append((term, df))
            self._known = known
            self._stems = {t for t, _ in self.store.vocabulary(min_doc_freq=1)} if self._surface else set(known)
            self._buckets = dict(buckets)
            logger.info("Spelling vocabulary ready: %d words (%s).", len(known), "surface" if self._surface else "stems")

    def reset(self) -> None:
        with self._lock:
            self._buckets = None
            self._known = {}
            self._stems = set()
            self._cache.clear()

    def warm_up(self) -> None:
        self._ensure()

    def is_known(self, word: str) -> bool:
        self._ensure()
        return word in self._known

    # ------------------------------------------------------------------ correction
    def nearest(self, word: str) -> str | None:
        """Closest known word for an unknown ``word`` (None when it is known, too short or nothing is close)."""
        if not word.isalpha():
            return None
        self._ensure()
        if word in self._known:
            return None
        cached = self._cache.get(word, _MISSING)  # one lookup: another thread may clear the cache in between
        if cached is not _MISSING:
            return cached
        edits = max_edits(word)
        best: tuple[int, int, int, str] | None = None
        if edits and self._buckets:
            first = word[0]
            for length in range(len(word) - edits, len(word) + edits + 1):
                for cand, df in self._buckets.get((first, length), ()):
                    d = _distance(word, cand, edits)
                    if d > edits:
                        continue
                    key = (d, abs(len(cand) - len(word)), -df, cand)
                    if best is None or key < best:
                        best = key
        result = best[3] if best else None
        if len(self._cache) > 50_000:
            self._cache.clear()
        self._cache[word] = result
        return result

    # Backwards-compatible name used by older callers
    correct = nearest

    def correct_query(
        self, text: str, *, language: str, protected: frozenset[str] | set[str] = frozenset()
    ) -> dict[str, str]:
        """{stem typed: stem of the corrected word} for every misspelt word of a question."""
        return {typed: fixed for typed, fixed, _w, _f in self.corrections(text, language=language, protected=protected)}

    def corrections(
        self, text: str, *, language: str, protected: frozenset[str] | set[str] = frozenset()
    ) -> list[tuple[str, str, str, str]]:
        """(typed stem, corrected stem, typed word, corrected word) for every misspelt word of a question.

        Words the situation lexicon knows ("shtraf", "otpusk") are only corrected within their own family
        ("nikox" -> "nikoh", "murojat" -> "murojaat"), never into another word ("shtraf" -> "sharaf").
        """
        self._ensure()
        out: list[tuple[str, str, str, str]] = []
        seen: set[str] = set()
        for word in surface_tokens(text, language=language):
            if len(word) < 4 or not word.isalpha() or word in seen:
                continue
            seen.add(word)
            typed_stem = stem_token(word)
            if self._surface:
                if word in self._known or typed_stem in self._stems:
                    continue
                fixed = self.nearest(word)
                if not fixed:
                    continue
                fixed_stem = stem_token(fixed)
            else:
                if typed_stem in self._known:
                    continue
                fixed = self.nearest(typed_stem) or ""
                fixed_stem = fixed
            if not fixed_stem or fixed_stem == typed_stem:
                continue
            if self._is_protected(word, protected) and not _same_family(word, fixed):
                continue
            out.append((typed_stem, fixed_stem, word, fixed))
        return out

    def _is_protected(self, word: str, protected: frozenset[str] | set[str]) -> bool:
        """Colloquial words the situation lexicon understands match by prefix ("shtrafni", "zarplatam")."""
        if not protected:
            return False
        key = id(protected)
        index = self._prefix_cache.get(key)
        if index is None:
            index = defaultdict(list)
            for p in protected:
                if len(p) >= 5:
                    index[p[:3]].append(p)
            self._prefix_cache = {key: index}
        norm = word.replace("x", "h").replace("q", "k")
        return any(norm.startswith(p) for p in index.get(norm[:3], ()))

    def correct_terms(self, terms: list[str]) -> dict[str, str]:
        """{unknown term: replacement} for analysed terms (fallback when the raw question is not available)."""
        out: dict[str, str] = {}
        for t in terms:
            fixed = self.nearest(t)
            if fixed and fixed != t:
                out[t] = stem_token(fixed) if self._surface else fixed
        return out
