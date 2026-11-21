#!/usr/bin/env python3
"""Post-deploy smoke test of a running agent: health, JSON answers and the SSE stream contract.

    python scripts/sse_smoke.py                          # http://127.0.0.1:8000
    python scripts/sse_smoke.py https://lex-agent.onrender.com

Checks (exit code 1 on any failure):

* ``GET /api/health`` answers ``status: ok`` with a non-empty index;
* ``POST /api/ask`` returns structured sections, sources with lex.uz URLs and passing answer checks;
* ``POST /api/ask/stream`` emits ``step`` events (running/done), then ``sources``, then ``token`` events, an optional
  ``replace_answer`` and a final ``done`` with the full response — for a legal question, a calculation, a greeting
  (direct routes — greeting, calculation — emit steps 1 and 5 only) and a Russian and an English question; the first
  event arrives quickly;
* the answer is in the language of the question.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import httpx

CASES = [
    {"query": "Yillik mehnat ta'tili necha kun?", "route": "legal", "lang": "uz_latn", "expect": ["21"]},
    {"query": "aliment hisoblab ber: oylik 6 mln, 2 bola", "route": "calculation", "lang": "uz_latn", "expect": ["000"],
     "direct": True},
    {"query": "salom", "route": "greeting", "lang": "uz_latn", "direct": True},
    {"query": "Какой штраф за превышение скорости?", "route": "legal", "lang": "ru", "expect": ["БРВ"]},
    {"query": "How long is the probation period?", "route": "legal", "lang": "en", "expect": ["3 months"]},
]


def _sse_events(resp: httpx.Response) -> list[tuple[float, dict[str, Any]]]:
    events: list[tuple[float, dict[str, Any]]] = []
    t0 = time.perf_counter()
    for line in resp.iter_lines():
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload:
                events.append((time.perf_counter() - t0, json.loads(payload)))
    return events


def check_stream(client: httpx.Client, case: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    t0 = time.perf_counter()
    with client.stream("POST", "/api/ask/stream", json={"query": case["query"]}) as resp:
        if resp.status_code != 200:
            return [f"stream HTTP {resp.status_code}"]
        if "text/event-stream" not in resp.headers.get("content-type", ""):
            problems.append(f"content-type {resp.headers.get('content-type')}")
        events = _sse_events(resp)
    total = time.perf_counter() - t0
    if not events:
        return problems + ["no events"]
    types = [e["type"] for _t, e in events]
    first_latency = events[0][0]
    if types[0] != "step":
        problems.append(f"first event is {types[0]!r}, not a step")
    if types[-1] != "done":
        problems.append(f"last event is {types[-1]!r}, not done")
    if "error" in types:
        problems.append("error event: " + str(next(e for _t, e in events if e["type"] == "error")))
    steps = sorted({e["step"] for _t, e in events if e["type"] == "step"})
    if case.get("direct"):
        if steps != [1, 5]:
            problems.append(f"direct route steps {steps}, expected [1, 5]")
    else:
        if steps != [1, 2, 3, 4, 5]:
            problems.append(f"steps {steps}, expected 1..5")
        if "sources" not in types or "token" not in types:
            problems.append("missing sources or token events")
        elif types.index("sources") > types.index("token"):
            problems.append("sources arrive after the first token")
    done = events[-1][1] if types[-1] == "done" else {}
    resp_obj = done.get("response") or {}
    if resp_obj:
        if resp_obj.get("route") != case["route"]:
            problems.append(f"route {resp_obj.get('route')!r}, expected {case['route']!r}")
        if resp_obj.get("response_language") != case["lang"]:
            problems.append(f"language {resp_obj.get('response_language')!r}, expected {case['lang']!r}")
        answer = resp_obj.get("answer") or ""
        for word in case.get("expect", []):
            if word not in answer:
                problems.append(f"answer lacks {word!r}")
        checks = (resp_obj.get("verification") or {}).get("checks") or {}
        failed = [k for k, v in checks.items() if v is False]
        if failed:
            problems.append(f"answer checks failed: {failed}")
    if first_latency > 3.0:
        problems.append(f"first event after {first_latency:.2f}s")
    print(f"  stream {case['query'][:48]!r}: {len(events)} events, first {first_latency * 1000:.0f} ms, "
          f"total {total * 1000:.0f} ms, route={resp_obj.get('route')} {'OK' if not problems else 'FAIL'}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base_url", nargs="?", default="http://127.0.0.1:8000")
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args()
    failures: list[str] = []
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=args.timeout) as client:
        health = client.get("/api/health")
        h = health.json() if health.status_code == 200 else {}
        if h.get("status") != "ok" or not h.get("index_ready"):
            failures.append(f"health: HTTP {health.status_code} {h}")
        print(f"health: {h.get('status')} chunks={h.get('bm25_chunks')} mode={h.get('answer_mode')} "
              f"lex_sync={json.dumps(h.get('lex_sync'), ensure_ascii=False)}")
        r = client.post("/api/ask", json={"query": "Ishdan bo'shatishdi, nima qilishim kerak?"})
        body = r.json() if r.status_code == 200 else {}
        if r.status_code != 200 or not (body.get("sections") or {}).get("structured"):
            failures.append(f"/api/ask: HTTP {r.status_code}")
        elif not body.get("sources") or not all(str(s.get("url", "")).startswith("https://") for s in body["sources"]):
            failures.append("/api/ask: sources without URLs")
        print(f"  ask: HTTP {r.status_code}, {len(body.get('sources') or [])} sources, {body.get('elapsed_ms')} ms")
        for case in CASES:
            failures += [f"{case['query'][:40]!r}: {p}" for p in check_stream(client, case)]
    if failures:
        print("FAILED:\n  " + "\n  ".join(failures))
        return 1
    print("SSE smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
