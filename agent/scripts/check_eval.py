#!/usr/bin/env python3
"""Fail (exit 1) when a retrieval report from ``lex-agent eval --json-out`` is below the given thresholds.

    python scripts/check_eval.py eval-test.json --min-hit1 0.88 --min-hit5 0.97
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", type=Path)
    ap.add_argument("--min-hit1", type=float, default=0.0)
    ap.add_argument("--min-hit5", type=float, default=0.0)
    ap.add_argument("--max-p95-ms", type=float, default=0.0, help="0 = no latency gate")
    args = ap.parse_args()
    rep = json.loads(args.report.read_text(encoding="utf-8"))
    problems = []
    if rep["hit@1"] < args.min_hit1:
        problems.append(f"hit@1 {rep['hit@1']:.3f} < {args.min_hit1}")
    if rep["hit@5"] < args.min_hit5:
        problems.append(f"hit@5 {rep['hit@5']:.3f} < {args.min_hit5}")
    if args.max_p95_ms and rep.get("p95_ms", 0) > args.max_p95_ms:
        problems.append(f"p95 {rep['p95_ms']} ms > {args.max_p95_ms} ms")
    status = "FAIL" if problems else "ok"
    print(f"{args.report.name}: {status} — {rep['queries']} questions, hit@1 {rep['hit@1']:.3f}, hit@5 {rep['hit@5']:.3f}, "
          f"p95 {rep.get('p95_ms')} ms" + (f" ({'; '.join(problems)})" if problems else ""))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
