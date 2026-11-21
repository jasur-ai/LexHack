#!/usr/bin/env python3
"""Publish the deploy results as check-run annotations (readable through the GitHub API without log access).

Reads ``render-result.json``, ``smoke.json`` and ``counter-audit.json`` when present and prints one ``::notice``
workflow command per topic. GitHub keeps at most 10 notices per step, so the output stays well below that.
"""

from __future__ import annotations

import json
from pathlib import Path


def _notice(title: str, lines: list[str]) -> None:
    message = "\n".join(lines).replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    print(f"::notice title={title}::{message}")


def main() -> int:
    render = Path("render-result.json")
    if render.exists():
        data = json.loads(render.read_text(encoding="utf-8"))
        lines = [f"workspace {data.get('owner', {}).get('name')} ({data.get('owner', {}).get('type')}), branch {data.get('branch')}"]
        for key, svc in (data.get("services") or {}).items():
            dep = svc.get("deploy") or {}
            lines.append(
                f"{key}: {svc.get('url')} | plan {svc.get('plan')}{' (fallback from paid)' if svc.get('plan_fallback_to_free') else ''}"
                f" | deploy {dep.get('status', 'n/a')} {str(dep.get('commit') or '')[:7]} | {svc.get('dashboard')}"
            )
        _notice("render", lines)
    smoke = Path("smoke.json")
    if smoke.exists():
        data = json.loads(smoke.read_text(encoding="utf-8"))
        lines = [f"overall {'PASS' if data.get('ok') else 'FAIL'}"]
        for row in data.get("checks") or []:
            ms = "" if row.get("ms") is None else f" {row['ms']} ms"
            lines.append(f"{'PASS' if row.get('ok') else 'FAIL'} {row.get('check')}{ms}: {str(row.get('detail'))[:160]}")
        _notice("smoke", lines)
    audit = Path("counter-audit.json")
    if audit.exists():
        data = json.loads(audit.read_text(encoding="utf-8"))
        o = data.get("overall") or {}
        lines = [f"{o.get('n')} cases: {o.get('pass')} PASS, {o.get('partial')} PARTIAL, {o.get('fail')} FAIL, mean {o.get('mean_score')}"]
        for name, b in (data.get("by_suite") or {}).items():
            lines.append(f"suite {name}: n {b['n']} pass {b['pass']} partial {b['partial']} fail {b['fail']} mean {b['mean_score']}")
        for name, b in (data.get("by_category") or {}).items():
            lines.append(f"category {name}: n {b['n']} pass {b['pass']} partial {b['partial']} fail {b['fail']} mean {b['mean_score']}")
        lines.append("codes: " + ", ".join(f"{k} {v}" for k, v in (data.get("error_codes") or {}).items()))
        _notice("counter-audit", lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
