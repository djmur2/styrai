"""Cross-platform launcher for the private StyrAI partner demonstration."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any
from urllib.request import ProxyHandler, build_opener


HOST = "127.0.0.1"
PORTS = range(8765, 8776)
PROJECT_ROOT = Path(__file__).resolve().parent
OPENER = build_opener(ProxyHandler({}))
REQUIRED_DATASET_SCHEMA = "styrai.synthetic-ai-outcomes.v1"


def _read_json(port: int, path: str) -> dict[str, Any]:
    with OPENER.open(f"http://{HOST}:{port}{path}", timeout=0.75) as response:
        if response.status != 200:
            raise RuntimeError("Unhealthy response")
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected response")
    return payload


def _is_current_styrai(port: int) -> bool:
    try:
        health = _read_json(port, "/api/health")
        governance = _read_json(port, "/api/governance")
        dataset_schema = _read_json(port, "/api/governance/dataset-schema")
        audit = governance.get("audit")
        enforcement = governance.get("enforcement")
        dataset_formats = dataset_schema.get("formats")
        return bool(
            health.get("status") == "ok"
            and health.get("product") == "StyrAI"
            and governance.get("mode") == "synthetic_local_control_plane"
            and isinstance(governance.get("models"), list)
            and governance["models"]
            and isinstance(governance.get("metrics"), dict)
            and isinstance(enforcement, dict)
            and enforcement.get("inspection_point")
            == "before_provider_boundary"
            and isinstance(audit, dict)
            and audit.get("valid") is True
            # Older StyrAI processes expose the health and governance routes,
            # but cannot execute uploaded-dataset runs. Require this release's
            # versioned upload contract before reusing an existing process.
            and dataset_schema.get("schema") == REQUIRED_DATASET_SCHEMA
            and isinstance(dataset_formats, list)
            and {"csv", "json"}.issubset(dataset_formats)
        )
    except (OSError, RuntimeError, TimeoutError, TypeError, ValueError):
        return False


def _is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((HOST, port))
        except OSError:
            return False
    return True


def main() -> int:
    if sys.version_info < (3, 11):
        print("StyrAI requires Python 3.11 or newer.")
        print(f"Detected: {sys.version.split()[0]}")
        return 1

    first_free: int | None = None
    for port in PORTS:
        if _is_current_styrai(port):
            url = f"http://{HOST}:{port}/?presentation=1"
            print(f"A verified StyrAI demonstration is already running at {url}")
            webbrowser.open(url)
            return 0
        if first_free is None and _is_free(port):
            first_free = port

    if first_free is None:
        print("No free local port was found from 8765 through 8775.")
        print("Close an application using one of those ports and try again.")
        return 1

    url = f"http://{HOST}:{first_free}/?presentation=1"
    print("Starting the private StyrAI demonstration.")
    print(f"The browser will open at {url}")
    print("Keep this window open while using the demo. Press Ctrl+C to stop it.")
    command = [
        sys.executable,
        "-m",
        "murphyos.web",
        "--port",
        str(first_free),
        "--open-browser",
    ]
    try:
        completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
        return completed.returncode
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
