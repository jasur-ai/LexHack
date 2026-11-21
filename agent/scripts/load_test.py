#!/usr/bin/env python3
"""Load test of a running agent with real questions from the evaluation set.

    python scripts/load_test.py                                   # 20 users, 60 s, http://127.0.0.1:8000
    python scripts/load_test.py https://lex-agent.onrender.com --users 30 --duration 120 --stream 0.5

Each virtual user asks questions back to back (random questions from ``eval/retrieval_gold.jsonl`` plus greetings and
calculations, with a typo-free and a typo half); ``--stream`` is the share of requests sent to ``/api/ask/stream``
(time to first event is measured for those). Output: throughput, error rate, latency percentiles per endpoint,
the answer-mode mix (extractive / cache / llm) and, with ``--pid``, the server's peak RSS memory.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
EXTRA = ["salom", "rahmat", "BHM qancha?", "aliment hisoblab ber: oylik 5 mln, 1 bola", "10 BHM qancha so'm",
         "ish haqi 5 mln 30 kun kechikdi kompensatsiya qancha", "Davlat boji ajrashish uchun qancha?"]


def _questions() -> list[str]:
    rows = [json.loads(line) for line in (ROOT / "eval/retrieval_gold.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    return [r["q"] for r in rows] + EXTRA * 10


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = max(0, min(len(values) - 1, round(p / 100 * (len(values) - 1))))
    return values[k]


def _rss_mb(pid: int) -> float:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


async def user(client: httpx.AsyncClient, questions: list[str], stop_at: float, stream_share: float,
               stats: dict[str, Any]) -> None:
    rng = random.Random()
    while time.perf_counter() < stop_at:
        q = rng.choice(questions)
        streaming = rng.random() < stream_share
        t0 = time.perf_counter()
        try:
            if streaming:
                first = None
                mode = None
                async with client.stream("POST", "/api/ask/stream", json={"query": q}) as resp:
                    ok = resp.status_code == 200
                    async for line in resp.aiter_lines():
                        if line.startswith("data:"):
                            if first is None:
                                first = time.perf_counter() - t0
                            ev = json.loads(line[5:])
                            if ev.get("type") == "done":
                                mode = ev["response"]["mode"]
                            elif ev.get("type") == "error":
                                ok = False
                dt = time.perf_counter() - t0
                stats["stream"].append(dt)
                if first is not None:
                    stats["first_event"].append(first)
            else:
                resp = await client.post("/api/ask", json={"query": q})
                ok = resp.status_code == 200
                dt = time.perf_counter() - t0
                stats["ask"].append(dt)
                mode = resp.json().get("mode") if ok else None
            stats["ok" if ok else "errors"] += 1
            if mode:
                stats["modes"][mode] = stats["modes"].get(mode, 0) + 1
        except (httpx.HTTPError, ValueError) as exc:
            stats["errors"] += 1
            stats["error_samples"].append(f"{type(exc).__name__}: {exc}"[:160])


async def run(args: argparse.Namespace) -> int:
    questions = _questions()
    stats: dict[str, Any] = {"ask": [], "stream": [], "first_event": [], "ok": 0, "errors": 0, "modes": {},
                             "error_samples": []}
    limits = httpx.Limits(max_connections=args.users + 5, max_keepalive_connections=args.users + 5)
    peak_rss = 0.0
    async with httpx.AsyncClient(base_url=args.base_url.rstrip("/"), timeout=args.timeout, limits=limits) as client:
        health = (await client.get("/api/health")).json()
        print(f"target {args.base_url}: chunks={health.get('bm25_chunks')} mode={health.get('answer_mode')}")
        start = time.perf_counter()
        stop_at = start + args.duration
        tasks = [asyncio.create_task(user(client, questions, stop_at, args.stream, stats)) for _ in range(args.users)]
        while not all(t.done() for t in tasks):
            if args.pid:
                peak_rss = max(peak_rss, _rss_mb(args.pid))
            await asyncio.sleep(0.5)
        elapsed = time.perf_counter() - start
    total = stats["ok"] + stats["errors"]
    print(f"\n{args.users} users, {elapsed:.0f} s: {total} requests, {total / elapsed:.1f} req/s, "
          f"errors {stats['errors']} ({100 * stats['errors'] / max(total, 1):.2f}%)")
    for name in ("ask", "stream", "first_event"):
        vals = [v * 1000 for v in stats[name]]
        if vals:
            print(f"  {name:<12} n={len(vals):<5} p50={_pct(vals, 50):7.0f} ms  p95={_pct(vals, 95):7.0f} ms  "
                  f"p99={_pct(vals, 99):7.0f} ms  mean={statistics.mean(vals):7.0f} ms")
    print(f"  answer modes: {stats['modes']}")
    if args.pid:
        print(f"  server peak RSS: {peak_rss:.0f} MB")
    for sample in stats["error_samples"][:5]:
        print(f"  error: {sample}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps({
            "users": args.users, "seconds": round(elapsed, 1), "requests": total, "rps": round(total / elapsed, 2),
            "errors": stats["errors"], "modes": stats["modes"], "peak_rss_mb": round(peak_rss),
            **{f"{n}_p{p}_ms": round(_pct([v * 1000 for v in stats[n]], p)) for n in ("ask", "stream", "first_event")
               for p in (50, 95, 99)},
        }, indent=1), encoding="utf-8")
    error_rate = stats["errors"] / max(total, 1)
    return 1 if error_rate > args.max_error_rate else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base_url", nargs="?", default="http://127.0.0.1:8000")
    ap.add_argument("--users", type=int, default=20)
    ap.add_argument("--duration", type=float, default=60.0)
    ap.add_argument("--stream", type=float, default=0.5, help="share of requests sent to /api/ask/stream")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--pid", type=int, default=0, help="server process id (Linux) to report peak RSS memory")
    ap.add_argument("--max-error-rate", type=float, default=0.01)
    ap.add_argument("--json-out", default="")
    return asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
