"""All lexicon rows, grouped by domain modules (see :mod:`lex_agent.knowledge.lexicon` for the format)."""

from __future__ import annotations

from lex_agent.knowledge import rows_civil, rows_family, rows_labour, rows_public, rows_state

CONCEPTS = [*rows_labour.ROWS, *rows_family.ROWS, *rows_civil.ROWS, *rows_public.ROWS, *rows_state.ROWS]
