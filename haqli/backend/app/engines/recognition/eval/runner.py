"""Evaluation runner & CI gate checker for Recognition Engine v1.0 (§12)."""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from app.engines.recognition.classify import classify_document_sync
from app.engines.recognition.entities.dates import extract_dates
from app.engines.recognition.entities.money import extract_money
from app.engines.recognition.entities.numbers import parse_number_phrase
from app.engines.recognition.eval.fixtures import (
    NUMERAL_60_TABLE,
    build_document_fixtures,
    build_mrz_fixtures,
    build_voice_fixtures,
)
from app.engines.recognition.normalize import normalize_ocr_text
from app.engines.recognition.parsers.mrz import parse_mrz
from app.engines.recognition.pipeline import run_recognition_pipeline


@dataclass
class EvalSummary:
    doc_type_accuracy: float
    amount_clean_accuracy: float
    date_clean_accuracy: float
    amount_degraded_accuracy: float
    date_degraded_accuracy: float
    mrz_valid_accuracy: float
    mrz_invalid_rejection: float
    mrz_false_accept_rate: float
    spoken_number_accuracy: float
    voice_role_accuracy: float
    p50_latency_ms: float
    p95_latency_ms: float
    gates_passed: bool
    gate_failures: list[str]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, int(round((pct / 100.0) * (len(s) - 1))))
    return round(s[idx], 2)


async def run_evaluation() -> EvalSummary:
    latencies: list[float] = []

    # 1. Documents (150 fixtures across 5 types x 30)
    docs = build_document_fixtures()
    doc_hits = 0
    clean_total = clean_amt = clean_dt = 0
    deg_total = deg_amt = deg_dt = 0

    for item in docs:
        t0 = time.perf_counter()
        norm = normalize_ocr_text(item["text"])
        pred_type, _, _ = classify_document_sync(norm.text)
        moneys = extract_money(norm.text)
        dates = extract_dates(norm.text, today=date(2026, 4, 15))
        latencies.append((time.perf_counter() - t0) * 1000.0)

        if pred_type == item["doc_type"]:
            doc_hits += 1

        amt_ok = any(m.amount == item["amount"] for m in moneys)
        dt_ok = any(d.value == item["date"] for d in dates)
        if item["degraded"]:
            deg_total += 1
            deg_amt += int(amt_ok)
            deg_dt += int(dt_ok)
        else:
            clean_total += 1
            clean_amt += int(amt_ok)
            clean_dt += int(dt_ok)

    # 2. MRZ (50 TD1/TD3 valid + invalid)
    mrz_fixtures = build_mrz_fixtures()
    valid_tot = valid_hits = invalid_tot = invalid_rejected = false_accepts = 0
    for fx in mrz_fixtures:
        res = parse_mrz(fx["raw"], today=date(2026, 4, 15))
        if fx["expect_valid"]:
            valid_tot += 1
            if res["valid"] and res["fields"].get("documentNumber") == fx["doc_number"]:
                valid_hits += 1
        else:
            invalid_tot += 1
            if not res["valid"]:
                invalid_rejected += 1
            else:
                false_accepts += 1

    # 3. 60-case spoken/written numeral table
    num_hits = sum(1 for phrase, expected in NUMERAL_60_TABLE if parse_number_phrase(phrase) == expected)

    # 4. 54 voice utterances through full pipeline
    voice_fx = build_voice_fixtures()
    role_hits = 0
    for vf in voice_fx:
        res, _, _ = await run_recognition_pipeline(kind="voice", text_input=vf["text"])
        role_field = next((f for f in res.fields if f.key == "speakerRole"), None)
        if role_field and role_field.value == vf["role"]:
            role_hits += 1

    summary = EvalSummary(
        doc_type_accuracy=round(doc_hits / len(docs), 4),
        amount_clean_accuracy=round(clean_amt / max(1, clean_total), 4),
        date_clean_accuracy=round(clean_dt / max(1, clean_total), 4),
        amount_degraded_accuracy=round(deg_amt / max(1, deg_total), 4),
        date_degraded_accuracy=round(deg_dt / max(1, deg_total), 4),
        mrz_valid_accuracy=round(valid_hits / max(1, valid_tot), 4),
        mrz_invalid_rejection=round(invalid_rejected / max(1, invalid_tot), 4),
        mrz_false_accept_rate=round(false_accepts / max(1, invalid_tot), 4),
        spoken_number_accuracy=round(num_hits / len(NUMERAL_60_TABLE), 4),
        voice_role_accuracy=round(role_hits / len(voice_fx), 4),
        p50_latency_ms=round(statistics.median(latencies), 2) if latencies else 0.0,
        p95_latency_ms=_percentile(latencies, 95.0),
        gates_passed=True,
        gate_failures=[],
    )

    # Enforce CI gates (§12)
    checks = [
        ("doc_type_accuracy >= 0.90", summary.doc_type_accuracy >= 0.90),
        ("amount_clean_accuracy >= 0.95", summary.amount_clean_accuracy >= 0.95),
        ("date_clean_accuracy >= 0.95", summary.date_clean_accuracy >= 0.95),
        ("amount_degraded_accuracy >= 0.85", summary.amount_degraded_accuracy >= 0.85),
        ("date_degraded_accuracy >= 0.85", summary.date_degraded_accuracy >= 0.85),
        ("mrz_valid_accuracy >= 0.99", summary.mrz_valid_accuracy >= 0.99),
        ("mrz_invalid_rejection == 1.00", summary.mrz_invalid_rejection == 1.00),
        ("spoken_number_accuracy == 1.00", summary.spoken_number_accuracy == 1.00),
        ("p95_latency_ms <= 6000", summary.p95_latency_ms <= 6000.0),
    ]
    summary.gate_failures = [label for label, ok in checks if not ok]
    summary.gates_passed = len(summary.gate_failures) == 0
    return summary


def print_report(summary: EvalSummary, *, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(asdict(summary), indent=2))
        return
    print("=" * 62)
    print("HAQLI RECOGNITION ENGINE v1.0 — EVALUATION REPORT")
    print("=" * 62)
    rows: list[tuple[str, str]] = [
        ("Doc-type accuracy (gate >= 90%)", f"{summary.doc_type_accuracy:.2%}"),
        ("Amount accuracy clean (gate >= 95%)", f"{summary.amount_clean_accuracy:.2%}"),
        ("Date accuracy clean (gate >= 95%)", f"{summary.date_clean_accuracy:.2%}"),
        ("Amount accuracy degraded (gate >= 85%)", f"{summary.amount_degraded_accuracy:.2%}"),
        ("Date accuracy degraded (gate >= 85%)", f"{summary.date_degraded_accuracy:.2%}"),
        ("MRZ valid accuracy (gate >= 99%)", f"{summary.mrz_valid_accuracy:.2%}"),
        ("MRZ invalid rejection (gate 100%)", f"{summary.mrz_invalid_rejection:.2%}"),
        ("Spoken numerals 60-table (gate 100%)", f"{summary.spoken_number_accuracy:.2%}"),
        ("Voice role assignment accuracy", f"{summary.voice_role_accuracy:.2%}"),
        ("Latency p50 / p95 (gate <= 6000 ms)", f"{summary.p50_latency_ms} ms / {summary.p95_latency_ms} ms"),
        ("CI GATES", "PASS" if summary.gates_passed else f"FAIL: {summary.gate_failures}"),
    ]
    for k, v in rows:
        print(f"  {k:<40} {v}")
    print("=" * 62)
