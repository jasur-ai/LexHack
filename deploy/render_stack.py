#!/usr/bin/env python3
"""Create or update the LexHack services on Render and wait until every deploy is live.

The script is idempotent, so running it again is the normal way to roll out a new commit:
* a missing service is created from ``deploy/stack.json`` (Docker runtime, its own root directory);
* an existing service gets the branch, health check, plan and Docker settings re-applied. Its plain environment
  variables are updated, while its secrets are kept (secrets are generated once, when the service is created);
* each service is then deployed and the script waits for the deploy to finish.

If the workspace has no payment method, Render answers HTTP 402 for paid plans. The service is then created on the
free plan without a disk, and the result records that fallback so the report can say so.

Needs ``RENDER_API_KEY`` in the environment. It writes a JSON result (URLs, plans, deploy states, never secrets).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any

import httpx

API = "https://api.render.com/v1"
TERMINAL_OK = {"live"}
TERMINAL_BAD = {"build_failed", "update_failed", "canceled", "pre_deploy_failed", "deactivated"}


class RenderError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


class Render:
    def __init__(self, api_key: str) -> None:
        self.http = httpx.Client(
            base_url=API,
            timeout=60,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )

    def call(self, method: str, path: str, body: Any = None, params: dict[str, Any] | None = None) -> Any:
        for attempt in range(6):
            resp = self.http.request(method, path, json=body, params=params)
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = int(resp.headers.get("Retry-After") or 5 * (attempt + 1))
                time.sleep(min(wait, 60))
                continue
            if resp.status_code >= 400:
                try:
                    message = resp.json().get("message") or resp.text
                except ValueError:
                    message = resp.text
                raise RenderError(resp.status_code, str(message)[:400])
            return resp.json() if resp.content else None
        raise RenderError(resp.status_code, "gave up after retries")

    def owner(self) -> dict[str, Any]:
        owners = [row["owner"] for row in self.call("GET", "/owners", params={"limit": 20})]
        if not owners:
            raise SystemExit("The Render API key has no workspace")
        preferred = os.environ.get("RENDER_OWNER_NAME", "").strip().lower()
        for o in owners:
            if preferred and o.get("name", "").lower() == preferred:
                return o
        return owners[0]

    def find_service(self, owner_id: str, name: str) -> dict[str, Any] | None:
        rows = self.call("GET", "/services", params={"name": name, "ownerId": owner_id, "limit": 50})
        for row in rows or []:
            svc = row.get("service") or {}
            if svc.get("name") == name:
                return svc
        return None


def _random_secret(kind: str) -> str:
    if kind == "fernet":
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
    if kind == "ed25519":
        return base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    return secrets.token_urlsafe(48)


def _resolve(value: str, urls: dict[str, str]) -> str:
    for key, url in urls.items():
        value = value.replace(f"{{{key}.url}}", url)
    return value


def _docker_details(spec: dict[str, Any]) -> dict[str, Any]:
    return {"dockerfilePath": spec.get("dockerfilePath", "./Dockerfile"), "dockerContext": spec.get("dockerContext", ".")}


def _create(render: Render, owner_id: str, spec: dict[str, Any], stack: dict[str, Any], branch: str, env: list[dict[str, Any]]) -> tuple[dict[str, Any], str | None, str, bool]:
    plan = spec.get("plan", "starter")
    disk = spec.get("disk")
    fallback = False
    for attempt in ("paid", "free"):
        details: dict[str, Any] = {
            "runtime": "docker",
            "plan": plan,
            "region": stack["region"],
            "healthCheckPath": spec["healthCheckPath"],
            "numInstances": 1,
            "envSpecificDetails": _docker_details(spec),
        }
        if disk and plan != "free":
            details["disk"] = disk
        body = {
            "type": "web_service",
            "name": spec["name"],
            "ownerId": owner_id,
            "repo": stack["repo"],
            "branch": branch,
            "rootDir": spec["rootDir"],
            "autoDeploy": "yes",
            "envVars": env,
            "serviceDetails": details,
        }
        try:
            created = render.call("POST", "/services", body)
            return created["service"], created.get("deployId"), plan, fallback
        except RenderError as exc:
            if exc.status == 402 and attempt == "paid" and plan != "free":
                print(f"  {spec['name']}: paid plan needs a payment method (HTTP 402); creating it on the free plan")
                plan, fallback = "free", True
                continue
            raise
    raise SystemExit("unreachable")


def _update(render: Render, svc: dict[str, Any], spec: dict[str, Any], branch: str, env_plain: dict[str, str], secret_defaults: dict[str, str], passthrough: dict[str, str]) -> None:
    sid = svc["id"]
    patch: dict[str, Any] = {
        "branch": branch,
        "rootDir": spec["rootDir"],
        "autoDeploy": "yes",
        "serviceDetails": {"healthCheckPath": spec["healthCheckPath"], "envSpecificDetails": _docker_details(spec)},
    }
    render.call("PATCH", f"/services/{sid}", patch)
    existing = {row["envVar"]["key"]: row["envVar"].get("value", "") for row in render.call("GET", f"/services/{sid}/env-vars", params={"limit": 100}) or []}
    merged = dict(existing)
    merged.update(env_plain)
    merged.update({k: v for k, v in passthrough.items() if v})
    for key, value in secret_defaults.items():
        if not merged.get(key):
            merged[key] = value
    render.call("PUT", f"/services/{sid}/env-vars", [{"key": k, "value": v} for k, v in sorted(merged.items())])


def _wait(render: Render, pending: dict[str, tuple[str, str]], timeout: int) -> dict[str, dict[str, Any]]:
    """Poll deploys until each reaches a terminal state. ``pending`` maps key -> (service id, deploy id)."""
    states: dict[str, dict[str, Any]] = {}
    deadline = time.time() + timeout
    last_print: dict[str, str] = {}
    while pending and time.time() < deadline:
        for key, (sid, did) in list(pending.items()):
            dep = render.call("GET", f"/services/{sid}/deploys/{did}")
            status = dep.get("status", "unknown")
            if last_print.get(key) != status:
                print(f"  {key}: deploy {did} -> {status}")
                last_print[key] = status
            if status in TERMINAL_OK | TERMINAL_BAD:
                states[key] = {"id": did, "status": status, "commit": (dep.get("commit") or {}).get("id")}
                pending.pop(key)
        if pending:
            time.sleep(15)
    for key, (_, did) in pending.items():
        states[key] = {"id": did, "status": "timeout"}
    return states


def _print_logs(render: Render, owner_id: str, service_id: str, status: str) -> None:
    """Best effort: show the tail of the build (or runtime) log of a failed deploy in the job log."""
    kind = "build" if status in {"build_failed", "pre_deploy_failed"} else "app"
    try:
        data = render.call("GET", "/logs", params={"ownerId": owner_id, "resource": service_id, "type": kind, "direction": "backward", "limit": 80})
    except RenderError as exc:
        print(f"  (could not read {kind} logs: {exc})")
        return
    rows = (data or {}).get("logs") or []
    print(f"  --- last {len(rows)} {kind} log lines ---")
    for row in reversed(rows):
        print(f"  | {str(row.get('message', '')).rstrip()[:300]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--stack", default="deploy/stack.json")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--out", default="render-result.json")
    parser.add_argument("--only", default="", help="Comma-separated service keys to deploy (default: all)")
    parser.add_argument("--timeout", type=int, default=2400)
    parser.add_argument("--mode", default="deploy", choices=["deploy", "status"], help="status: report only, change nothing")
    args = parser.parse_args()

    api_key = os.environ.get("RENDER_API_KEY", "").strip()
    if not api_key:
        print("RENDER_API_KEY is not set", file=sys.stderr)
        return 2
    stack = json.loads(Path(args.stack).read_text(encoding="utf-8"))
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    render = Render(api_key)
    owner = render.owner()
    print(f"Render workspace: {owner.get('name')} ({owner.get('type')})")

    urls: dict[str, str] = {}
    result: dict[str, Any] = {"owner": {"name": owner.get("name"), "type": owner.get("type")}, "branch": args.branch, "services": {}}
    if args.mode == "status":
        for spec in stack["services"]:
            svc = render.find_service(owner["id"], spec["name"])
            if not svc:
                continue
            deps = render.call("GET", f"/services/{svc['id']}/deploys", params={"limit": 1}) or []
            dep = (deps[0].get("deploy") or {}) if deps else {}
            result["services"][spec["key"]] = {
                "id": svc["id"], "name": svc.get("name"), "url": (svc.get("serviceDetails") or {}).get("url", ""),
                "dashboard": svc.get("dashboardUrl"), "plan": (svc.get("serviceDetails") or {}).get("plan"),
                "plan_fallback_to_free": False, "created": False,
                "deploy": {"id": dep.get("id"), "status": dep.get("status"), "commit": (dep.get("commit") or {}).get("id")},
            }
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        for key, info in result["services"].items():
            print(f"{key}: {info['url']} | plan {info['plan']} | last deploy {info['deploy']['status']}")
        return 0
    pending: dict[str, tuple[str, str]] = {}
    for spec in stack["services"]:
        key = spec["key"]
        if only and key not in only:
            svc = render.find_service(owner["id"], spec["name"])
            if svc:
                urls[key] = (svc.get("serviceDetails") or {}).get("url", "")
            continue
        env_plain = {k: _resolve(v, urls) for k, v in (spec.get("env") or {}).items()}
        passthrough = {k: os.environ.get(k, "").strip() for k in spec.get("passthrough_secrets", [])}
        secret_defaults = {k: _random_secret(kind) for k, kind in (spec.get("random_secrets") or {}).items()}
        svc = render.find_service(owner["id"], spec["name"])
        if svc is None:
            env = [{"key": k, "value": v} for k, v in sorted(env_plain.items())]
            env += [{"key": k, "value": v} for k, v in sorted(secret_defaults.items())]
            env += [{"key": k, "value": v} for k, v in sorted(passthrough.items()) if v]
            env += [{"key": k, "generateValue": True} for k in spec.get("generated", [])]
            print(f"Creating {spec['name']} (plan {spec.get('plan')}, branch {args.branch})")
            svc, deploy_id, plan, fallback = _create(render, owner["id"], spec, stack, args.branch, env)
            if not deploy_id:
                deploy_id = render.call("POST", f"/services/{svc['id']}/deploys", {})["id"]
            created = True
        else:
            print(f"Updating {spec['name']} ({svc['id']})")
            _update(render, svc, spec, args.branch, env_plain, secret_defaults, passthrough)
            deploy_id = render.call("POST", f"/services/{svc['id']}/deploys", {"clearCache": "do_not_clear"})["id"]
            plan = (svc.get("serviceDetails") or {}).get("plan")
            fallback, created = False, False
        url = (svc.get("serviceDetails") or {}).get("url", "")
        urls[key] = url
        pending[key] = (svc["id"], deploy_id)
        result["services"][key] = {
            "id": svc["id"],
            "name": svc.get("name"),
            "url": url,
            "dashboard": svc.get("dashboardUrl"),
            "plan": plan,
            "plan_fallback_to_free": fallback,
            "created": created,
        }

    service_ids = {key: sid for key, (sid, _) in pending.items()}
    deploys = _wait(render, pending, args.timeout)
    ok = True
    for key, dep in deploys.items():
        result["services"][key]["deploy"] = dep
        ok &= dep["status"] == "live"
        if dep["status"] != "live":
            _print_logs(render, owner["id"], service_ids[key], dep["status"])
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for key, info in result["services"].items():
        print(f"{key}: {info['url']} | plan {info['plan']}{' (fallback)' if info['plan_fallback_to_free'] else ''} | deploy {info.get('deploy', {}).get('status')}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
