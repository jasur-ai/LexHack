#!/usr/bin/env python3
"""Smoke-test the deployed stack the way a user reaches it.

Agent: health, a plain answer in three languages and the SSE stream. haqli: the web app shell, health and readiness,
a private guest session, the AI-lawyer status and one question through haqli's streaming proxy to the agent.

Free Render instances sleep when idle, so every first request waits up to two minutes. The result is written as
JSON and, inside GitHub Actions, as a Markdown table in the job summary. The exit code is 1 if any check fails.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

QUESTIONS = [
    ("uz_latn", "Ish haqim 2 oydan beri berilmayapti, nima qilay?"),
    ("ru", "Какой срок исковой давности по гражданским делам?"),
    ("uz_cyrl", "Ажрашиш учун давлат божи қанча?"),
]


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, name: str, ok: bool, detail: str, ms: float | None = None) -> None:
        self.rows.append({"check": name, "ok": bool(ok), "detail": detail[:300], "ms": None if ms is None else round(ms)})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail[:200]}" + (f" ({ms:.0f} ms)" if ms is not None else ""))

    @property
    def ok(self) -> bool:
        return all(r["ok"] for r in self.rows)


def _wake(client: httpx.Client, url: str, deadline_s: int = 240) -> tuple[int, float]:
    start = time.perf_counter()
    last = 0
    while time.perf_counter() - start < deadline_s:
        try:
            resp = client.get(url, timeout=120)
            last = resp.status_code
            if resp.status_code < 500:
                return resp.status_code, (time.perf_counter() - start) * 1000
        except httpx.HTTPError:
            pass
        time.sleep(5)
    return last, (time.perf_counter() - start) * 1000


def _stream(client: httpx.Client, url: str, body: dict[str, Any], headers: dict[str, str] | None = None) -> tuple[list[str], dict[str, Any] | None, float | None, float]:
    t0 = time.perf_counter()
    first = None
    types: list[str] = []
    done = None
    with client.stream("POST", url, json=body, headers=headers or {}, timeout=120) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[5:])
            if first is None:
                first = (time.perf_counter() - t0) * 1000
            types.append(str(event.get("type")))
            if event.get("type") == "done":
                done = event.get("response")
    return types, done, first, (time.perf_counter() - t0) * 1000


def check_agent(client: httpx.Client, base: str, checks: Checks) -> None:
    code, ms = _wake(client, f"{base}/api/health")
    health = client.get(f"{base}/api/health").json() if code == 200 else {}
    chunks = health.get("bm25_chunks")
    checks.add("agent /api/health", code == 200, f"HTTP {code}, chunks {chunks}, mode {health.get('answer_mode')}", ms)
    for lang, question in QUESTIONS:
        t0 = time.perf_counter()
        resp = client.post(f"{base}/api/ask", json={"query": question, "response_language": lang, "answer_style": "concise"}, timeout=120)
        ms = (time.perf_counter() - t0) * 1000
        data = resp.json() if resp.status_code == 200 else {}
        ok = resp.status_code == 200 and bool(data.get("answer")) and len(data.get("sources") or []) > 0
        checks.add(f"agent /api/ask ({lang})", ok, f"HTTP {resp.status_code}, mode {data.get('mode')}, sources {len(data.get('sources') or [])}: {str(data.get('answer') or '')[:90]}", ms)
    types, done, first, total = _stream(client, f"{base}/api/ask/stream", {"query": QUESTIONS[0][1], "response_language": "uz_latn"})
    order_ok = bool(types) and types[0] == "step" and types[-1] == "done" and "sources" in types
    checks.add("agent /api/ask/stream", order_ok and bool(done and done.get("answer")), f"events {'>'.join(dict.fromkeys(types))}, first event {first or 0:.0f} ms", total)


def check_haqli(client: httpx.Client, base: str, checks: Checks) -> None:
    code, ms = _wake(client, f"{base}/healthz")
    checks.add("haqli /healthz", code == 200, f"HTTP {code}", ms)
    page = client.get(f"{base}/", timeout=60)
    checks.add("haqli web app", page.status_code == 200 and 'id="root"' in page.text, f"HTTP {page.status_code}, {len(page.text)} bytes")
    ready = client.get(f"{base}/readyz", timeout=60)
    checks.add("haqli /readyz", ready.status_code == 200, f"HTTP {ready.status_code}")
    auth = client.post(f"{base}/api/auth/telegram", json={"initData": "", "deviceId": f"smoke-{uuid.uuid4().hex}", "demoName": "Smoke Test"}, timeout=60)
    token = (auth.json() if auth.status_code == 200 else {}).get("accessToken")
    checks.add("haqli guest session", bool(token), f"HTTP {auth.status_code}")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    status = client.get(f"{base}/api/agent/status", headers=headers, timeout=120)
    sdata = status.json() if status.status_code == 200 else {}
    checks.add("haqli -> agent status", bool(sdata.get("available")), f"HTTP {status.status_code}, {json.dumps(sdata)[:160]}")
    types, done, first, total = _stream(client, f"{base}/api/agent/ask/stream", {"query": "Meni ogohlantirmasdan ishdan bo'shatishdi, nima qilsam bo'ladi?", "locale": "uz_lat", "answer_style": "concise"}, headers)
    answer = str((done or {}).get("answer") or "")
    checks.add("haqli -> agent chat stream", bool(answer) and "error" not in types, f"events {'>'.join(dict.fromkeys(types))}, first event {first or 0:.0f} ms: {answer[:90]}", total)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--render-result", default="render-result.json")
    parser.add_argument("--agent-url", default="")
    parser.add_argument("--haqli-url", default="")
    parser.add_argument("--out", default="smoke.json")
    args = parser.parse_args()
    services: dict[str, Any] = {}
    if Path(args.render_result).exists():
        services = json.loads(Path(args.render_result).read_text(encoding="utf-8")).get("services", {})
    agent_url = (args.agent_url or services.get("agent", {}).get("url", "")).rstrip("/")
    haqli_url = (args.haqli_url or services.get("haqli", {}).get("url", "")).rstrip("/")

    checks = Checks()
    with httpx.Client(follow_redirects=True, headers={"User-Agent": "lexhack-smoke/1.0"}) as client:
        if agent_url:
            check_agent(client, agent_url, checks)
        if haqli_url:
            check_haqli(client, haqli_url, checks)
    report = {"agent_url": agent_url, "haqli_url": haqli_url, "ok": checks.ok, "checks": checks.rows}
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        lines = [f"### Smoke test: {'all checks passed' if checks.ok else 'FAILED'}", "", f"* haqli: {haqli_url}", f"* agent: {agent_url}", "", "| Check | Result | Time | Detail |", "|---|---|---|---|"]
        lines += [f"| {r['check']} | {'✅' if r['ok'] else '❌'} | {'' if r['ms'] is None else str(r['ms']) + ' ms'} | {r['detail'].replace('|', '/')} |" for r in checks.rows]
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n\n")
    return 0 if checks.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
