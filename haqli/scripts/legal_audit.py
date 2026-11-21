#!/usr/bin/env python3
"""Audit script listing every `needs_review` entry across `backend/app/legal_data/*.json`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

LEGAL_DATA_DIR = Path(__file__).resolve().parent.parent / "backend" / "app" / "legal_data"


def collect_unverified(data_dir: Path = LEGAL_DATA_DIR) -> list[dict[str, str]]:
    unverified: list[dict[str, str]] = []

    constants_path = data_dir / "constants.json"
    if constants_path.exists():
        data = json.loads(constants_path.read_text(encoding="utf-8"))
        for key, entry in data.get("entries", {}).items():
            if entry.get("status") != "verified":
                unverified.append(
                    {
                        "file": "constants.json",
                        "id": key,
                        "status": str(entry.get("status", "missing")),
                        "effective_from": str(entry.get("effective_from", "")),
                        "source_ref": str(entry.get("source_ref", "")),
                    }
                )

    for fname in ("instruments.json", "law_alerts.json"):
        fpath = data_dir / fname
        if not fpath.exists():
            continue
        payload = json.loads(fpath.read_text(encoding="utf-8"))
        items = payload if isinstance(payload, list) else payload.get("items", [])
        for entry in items:
            if entry.get("status") != "verified":
                unverified.append(
                    {
                        "file": fname,
                        "id": str(entry.get("id", "unknown")),
                        "status": str(entry.get("status", "missing")),
                        "effective_from": str(entry.get("effective_from") or entry.get("published_date") or ""),
                        "source_ref": str(entry.get("source_ref") or entry.get("decree_ref") or ""),
                    }
                )
    return unverified


def main() -> int:
    items = collect_unverified()
    print(f"HAQLI Legal Data Audit — {len(items)} entry(ies) require legal verification:\n")
    for idx, it in enumerate(items, start=1):
        print(
            f"  {idx:02d}. [{it['status']}] {it['file']} :: {it['id']} "
            f"(effective: {it['effective_from'] or 'n/a'} | ref: {it['source_ref'] or 'n/a'})"
        )
    if "--strict" in sys.argv and items:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
