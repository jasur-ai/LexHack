"""Canonical (storage-independent) payloads for hash-chained documents.

The same tilxat must hash identically when it is created, when it is signed and when it is verified later —
even though the database hands values back in a different shape (SQLite drops timezone info from datetimes,
``Numeric`` columns add trailing zeros, ...). Every hashed value therefore goes through one formatter here.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.security.crypto import get_crypto

_MONEY_Q = Decimal("0.01")
_PERCENT_Q = Decimal("0.001")


def canonical_money(value: Any) -> str:
    return str(Decimal(str(value)).quantize(_MONEY_Q))


def canonical_percent(value: Any) -> str:
    return str(Decimal(str(value)).quantize(_PERCENT_Q))


def canonical_timestamp(value: datetime) -> str:
    """UTC, microsecond precision, explicit ``Z`` — naive datetimes are treated as UTC (how they are stored)."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.isoformat(timespec="microseconds") + "Z"


def tilxat_draft_payload(
    *,
    doc_type: str,
    party_a: str,
    party_b: str,
    amount_uzs: Any,
    due_date: date,
    penalty_percent: Any,
    terms: str,
) -> dict[str, Any]:
    return {
        "docType": doc_type,
        "partyA": party_a,
        "partyB": party_b,
        "amountUzs": canonical_money(amount_uzs),
        "dueDate": due_date.isoformat(),
        "penalty": canonical_percent(penalty_percent),
        "terms": terms,
    }


def tilxat_signed_payload(
    *,
    tilxat_id: str,
    prev_hash: str,
    party_a_tg: int | None,
    party_b_tg: int | None,
    signed_at: datetime,
    amount_uzs: Any,
) -> dict[str, Any]:
    return {
        "id": tilxat_id,
        "prevHash": prev_hash,
        "partyATg": party_a_tg,
        "partyBTg": party_b_tg,
        "signedAt": canonical_timestamp(signed_at),
        "amountUzs": canonical_money(amount_uzs),
    }


def _number_variants(value: Any) -> list[str]:
    """Spellings older releases may have hashed (raw request value vs. DB value with trailing zeros)."""
    raw = str(value)
    out = [raw]
    try:
        dec = Decimal(raw)
    except InvalidOperation:
        return out
    normalized = format(dec.normalize(), "f")
    for cand in (normalized, f"{dec:.1f}", f"{dec:.2f}", f"{dec:.3f}"):
        if cand not in out:
            out.append(cand)
    return out


def _legacy_timestamps(value: datetime) -> list[str]:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    naive = aware.astimezone(timezone.utc).replace(tzinfo=None)
    return list(dict.fromkeys([aware.isoformat(), naive.isoformat()]))


def tilxat_hash_candidates(t: Any) -> list[str]:
    """Hashes a genuine tilxat may carry: the canonical one first, then legacy encodings (pre-2.2 releases)."""
    crypto = get_crypto()
    if t.status == "signed" and t.party_b_signed_at:
        canonical = crypto.chain_hash(
            t.chain_prev_hash,
            tilxat_signed_payload(
                tilxat_id=t.id,
                prev_hash=t.chain_prev_hash,
                party_a_tg=t.party_a_tg_id,
                party_b_tg=t.party_b_tg_id,
                signed_at=t.party_b_signed_at,
                amount_uzs=t.amount_uzs,
            ),
        )
        out = [canonical]
        for ts in _legacy_timestamps(t.party_b_signed_at):
            legacy = {
                "id": t.id,
                "prevHash": t.chain_prev_hash,
                "partyATg": t.party_a_tg_id,
                "partyBTg": t.party_b_tg_id,
                "signedAt": ts,
                "amountUzs": str(t.amount_uzs),
            }
            out.append(crypto.chain_hash(t.chain_prev_hash, legacy))
        return list(dict.fromkeys(out))

    out = [
        crypto.chain_hash(
            t.chain_prev_hash,
            tilxat_draft_payload(
                doc_type=t.doc_type,
                party_a=t.party_a_name,
                party_b=t.party_b_name,
                amount_uzs=t.amount_uzs,
                due_date=t.due_date,
                penalty_percent=t.daily_penalty_percent,
                terms=t.terms_summary,
            ),
        )
    ]
    for amount in _number_variants(t.amount_uzs):
        for penalty in _number_variants(t.daily_penalty_percent):
            legacy = {
                "docType": t.doc_type,
                "partyA": t.party_a_name,
                "partyB": t.party_b_name,
                "amountUzs": amount,
                "dueDate": t.due_date.isoformat(),
                "penalty": penalty,
                "terms": t.terms_summary,
            }
            out.append(crypto.chain_hash(t.chain_prev_hash, legacy))
    return list(dict.fromkeys(out))
