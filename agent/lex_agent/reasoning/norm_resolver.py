"""Statutory norm hierarchy, temporal validity, and conflict resolver under Uzbekistan Law O'RQ-682."""

from __future__ import annotations

from datetime import date

from lex_agent.models import NormConflictResolution, NormStatus, RetrievedChunk


class NormConflictResolver:
    """Resolves normative conflicts via lex superior, lex posterior, lex specialis, and temporal checks.

    Grounded in the Law of the Republic of Uzbekistan "On Normative-Legal Acts" (O'RQ-682 of 20.04.2021).
    """

    def resolve(
        self,
        evidence: list[RetrievedChunk],
        *,
        as_of_date: date | None = None,
    ) -> tuple[list[RetrievedChunk], list[NormConflictResolution], list[str]]:
        """Rank evidence by legal authority & validity and detect explicit inter-norm conflicts.

        Returns `(ordered_evidence, conflict_resolutions, temporal_warnings)`.
        """
        if not evidence:
            return [], [], []

        target_date = as_of_date or date.today()
        warnings: list[str] = []
        resolutions: list[NormConflictResolution] = []

        # 1. Temporal status validation
        valid_evidence: list[RetrievedChunk] = []
        for item in evidence:
            c = item.chunk
            if c.status == NormStatus.REPEALED:
                warnings.append(
                    f"REPEALED NORM: '{c.doc_title}' ({c.doc_number or c.doc_id}) is marked as repealed "
                    f"(expiry: {c.expiry_date or 'unspecified'}). Do not treat as currently binding."
                )
            elif c.effective_date and c.effective_date > target_date:
                warnings.append(
                    f"NOT YET EFFECTIVE as of {target_date.isoformat()}: '{c.doc_title}' "
                    f"takes effect on {c.effective_date.isoformat()}."
                )
            elif c.status == NormStatus.AMENDED:
                warnings.append(
                    f"AMENDED NORM: '{c.doc_title}' ({c.doc_number or c.doc_id}) has been amended; "
                    f"verify current editorial wording on {c.url}."
                )
            valid_evidence.append(item)

        # 2. Detect hierarchical (lex superior) and temporal (lex posterior) precedence across distinct acts
        by_doc: dict[str, RetrievedChunk] = {}
        for item in valid_evidence:
            key = item.chunk.canonical_id
            if key not in by_doc or item.final_score > by_doc[key].final_score:
                by_doc[key] = item

        distinct_docs = list(by_doc.values())
        distinct_docs.sort(
            key=lambda x: (
                0 if x.chunk.status == NormStatus.REPEALED else 1,
                x.chunk.legal_force_rank,
                x.chunk.effective_date or date.min,
            ),
            reverse=True,
        )

        # Pairwise conflict check among top authoritative acts sharing a legal branch
        top_docs = distinct_docs[:6]
        seen_pairs: set[tuple[str, str]] = set()
        for i in range(len(top_docs)):
            for j in range(i + 1, len(top_docs)):
                a = top_docs[i].chunk
                b = top_docs[j].chunk
                if a.status == NormStatus.REPEALED or b.status == NormStatus.REPEALED:
                    continue
                shared_branches = set(a.branches) & set(b.branches)
                if not shared_branches:
                    continue
                pair_key = (a.canonical_id, b.canonical_id)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                if a.legal_force_rank > b.legal_force_rank:
                    resolutions.append(
                        NormConflictResolution(
                            higher_norm_doc_id=a.doc_id,
                            higher_norm_title=a.doc_title,
                            lower_or_older_doc_id=b.doc_id,
                            lower_or_older_title=b.doc_title,
                            principle_applied="lex_superior",
                            explanation=(
                                f"Under Law O'RQ-682 (hierarchy of normative-legal acts), '{a.doc_title}' "
                                f"({a.doc_type.value}, rank {a.legal_force_rank}) has higher legal force than "
                                f"'{b.doc_title}' ({b.doc_type.value}, rank {b.legal_force_rank}) and prevails "
                                "in case of contradiction."
                            ),
                        )
                    )
                elif a.legal_force_rank == b.legal_force_rank and a.effective_date and b.effective_date:
                    if a.effective_date != b.effective_date:
                        newer, older = (a, b) if a.effective_date > b.effective_date else (b, a)
                        resolutions.append(
                            NormConflictResolution(
                                higher_norm_doc_id=newer.doc_id,
                                higher_norm_title=newer.doc_title,
                                lower_or_older_doc_id=older.doc_id,
                                lower_or_older_title=older.doc_title,
                                principle_applied="lex_posterior",
                                explanation=(
                                    f"Both acts share equal legal force ({newer.doc_type.value}). "
                                    f"'{newer.doc_title}' (effective {newer.effective_date.isoformat()}) is newer than "
                                    f"'{older.doc_title}' (effective {older.effective_date.isoformat()}); "
                                    "under lex posterior it prevails unless the older act is a lex specialis."
                                ),
                            )
                        )

        # 3. Sort final evidence: in-force first, relevance dominant, legal hierarchy as subtle tie-breaker only
        valid_evidence.sort(
            key=lambda r: (
                0 if r.chunk.status == NormStatus.REPEALED else 1,
                round(r.final_score, 4) + (r.chunk.legal_force_rank / 100000.0),
            ),
            reverse=True,
        )

        # Prune weak noise chunks when high-relevance matches exist
        if len(valid_evidence) > 4:
            top_score = valid_evidence[0].final_score
            if top_score > 0.2:
                pruned = [
                    r for idx, r in enumerate(valid_evidence)
                    if idx < 3 or r.final_score >= top_score * 0.35
                ]
                valid_evidence = pruned

        # Deduplicate warnings while preserving order
        unique_warnings = list(dict.fromkeys(warnings))
        return valid_evidence, resolutions[:5], unique_warnings
