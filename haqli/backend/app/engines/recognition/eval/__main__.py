"""CLI entrypoint: `python -m app.engines.recognition.eval [--json]` (§12)."""

from __future__ import annotations

import asyncio
import sys

from app.engines.recognition.eval.runner import print_report, run_evaluation


def main() -> int:
    as_json = "--json" in sys.argv
    summary = asyncio.run(run_evaluation())
    print_report(summary, as_json=as_json)
    return 0 if summary.gates_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
