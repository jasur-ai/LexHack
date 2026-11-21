#!/usr/bin/env python3
"""Deliver deploy credentials to one GitHub Actions run without storing them anywhere in plain text.

Repository secrets are the usual way to give a workflow API tokens. This module covers the case where the person
deploying can push to the repository but cannot manage its secrets. It uses an ephemeral key exchange:

1. ``receive`` (inside the workflow run) generates an X25519 key pair in memory. It publishes the public key as a
   commit status (``deploy-handshake/<run id>``) on the commit being deployed.
2. ``seal`` (on the deployer's machine) reads that public key and verifies the status was created by
   ``github-actions[bot]`` for the expected commit. It encrypts the tokens with a libsodium sealed box and writes
   ``deploy/sealed/<run id>.json``, which is then pushed to the branch.
3. ``receive`` polls the branch for that file, decrypts it, masks every value in the job log and exports the
   values to the following steps through ``$GITHUB_ENV``.

The private key only ever exists in the memory of that single run, so the committed file cannot be decrypted by
anyone, including later runs. Only the names in ``ALLOWED_NAMES`` are accepted.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ALLOWED_NAMES = ("RENDER_API_KEY", "CLOUDFLARE_API_TOKEN", "GEMINI_API_KEY")
STATUS_PREFIX = "deploy-handshake/"
SEALED_DIR = "deploy/sealed"


def _github(method: str, path: str, body: dict | None = None) -> tuple[int, dict | list | None]:
    """Call the GitHub REST API with the workflow token (inside Actions)."""
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        return exc.code, None


def _set_status(repo: str, sha: str, context: str, state: str, description: str) -> None:
    code, _ = _github("POST", f"/repos/{repo}/statuses/{sha}", {"state": state, "context": context, "description": description[:140]})
    if code >= 300:
        raise SystemExit(f"could not set commit status {context}: HTTP {code}")


def receive(args: argparse.Namespace) -> int:
    from nacl.public import PrivateKey, SealedBox

    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["GITHUB_SHA"]
    run_id = os.environ["GITHUB_RUN_ID"]
    branch = os.environ.get("GITHUB_HEAD_REF") or os.environ["GITHUB_REF_NAME"]
    context = f"{STATUS_PREFIX}{run_id}"

    secret_key = PrivateKey.generate()
    public_b64 = base64.b64encode(bytes(secret_key.public_key)).decode("ascii")
    _set_status(repo, sha, context, "pending", f"pk:{public_b64}")
    print(f"Waiting for {SEALED_DIR}/{run_id}.json on {branch} (public key published as status {context})")

    deadline = time.time() + args.timeout
    path = f"/repos/{repo}/contents/{SEALED_DIR}/{run_id}.json?ref={branch}"
    while time.time() < deadline:
        code, payload = _github("GET", path)
        if code == 200 and isinstance(payload, dict) and payload.get("content"):
            sealed = json.loads(base64.b64decode(payload["content"]))
            box = SealedBox(secret_key)
            received: list[str] = []
            env_file = os.environ.get("GITHUB_ENV")
            for name, ciphertext in sorted((sealed.get("values") or {}).items()):
                if name not in ALLOWED_NAMES:
                    continue
                value = box.decrypt(base64.b64decode(ciphertext)).decode("utf-8").strip()
                if not value or "\n" in value:
                    continue
                print(f"::add-mask::{value}")
                if env_file:
                    with open(env_file, "a", encoding="utf-8") as fh:
                        fh.write(f"{name}={value}\n")
                received.append(name)
            _set_status(repo, sha, context, "success", f"received {', '.join(received) or 'nothing'}")
            print(f"Received: {', '.join(received) or 'nothing'}")
            return 0 if received else 1
        time.sleep(args.poll)
    _set_status(repo, sha, context, "failure", "timed out waiting for sealed credentials")
    print("Timed out waiting for sealed credentials", file=sys.stderr)
    return 1


def _gh_cli(path: str) -> dict | list:
    out = subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def seal(args: argparse.Namespace) -> int:
    from nacl.public import PublicKey, SealedBox

    repo = args.repo
    context = f"{STATUS_PREFIX}{args.run_id}"
    deadline = time.time() + args.timeout
    public_b64 = ""
    while time.time() < deadline and not public_b64:
        statuses = _gh_cli(f"/repos/{repo}/commits/{args.sha}/statuses?per_page=100")
        for st in statuses if isinstance(statuses, list) else []:
            creator = (st.get("creator") or {}).get("login")
            if st.get("context") == context and creator == "github-actions[bot]" and str(st.get("description", "")).startswith("pk:"):
                public_b64 = st["description"][3:]
                break
        if not public_b64:
            time.sleep(5)
    if not public_b64:
        print(f"No public key published for run {args.run_id} on {args.sha}", file=sys.stderr)
        return 1

    box = SealedBox(PublicKey(base64.b64decode(public_b64)))
    values = {}
    for name in ALLOWED_NAMES:
        value = os.environ.get(name, "").strip()
        if value:
            values[name] = base64.b64encode(box.encrypt(value.encode("utf-8"))).decode("ascii")
    if not values:
        print("No credentials found in the environment", file=sys.stderr)
        return 1
    out = Path(SEALED_DIR) / f"{args.run_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"run_id": args.run_id, "sha": args.sha, "values": values}, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out} with sealed {', '.join(sorted(values))}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("receive", help="inside GitHub Actions: publish a public key and wait for sealed values")
    r.add_argument("--timeout", type=int, default=900)
    r.add_argument("--poll", type=int, default=8)
    s = sub.add_parser("seal", help="on the deployer's machine: encrypt values from the environment for one run")
    s.add_argument("--repo", required=True)
    s.add_argument("--run-id", required=True)
    s.add_argument("--sha", required=True)
    s.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    return receive(args) if args.cmd == "receive" else seal(args)


if __name__ == "__main__":
    raise SystemExit(main())
