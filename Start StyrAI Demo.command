#!/bin/zsh

cd -- "$(dirname -- "$0")" || {
  echo "StyrAI could not open its demo folder."
  read -r "reply?Press Return to close this window..."
  exit 1
}

echo ""
echo "  StyrAI investor demonstration"
echo "  --------------------------------"
echo "  Preparing the local AI governance control plane..."
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found. Install Python 3.11 or newer, then try again."
  echo ""
  read -r "reply?Press Return to close this window..."
  exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "This demonstration needs Python 3.11 or newer."
  echo "Your installed version is: $(python3 --version 2>&1)"
  echo ""
  read -r "reply?Press Return to close this window..."
  exit 1
fi

PORT_START=8765
PORT_END=8775
RUNNING_PORT=""
FREE_PORT=""

server_is_current_styrai() {
  python3 - "$1" <<'PY'
import json
import sys
from urllib.request import ProxyHandler, build_opener

port = int(sys.argv[1])
opener = build_opener(ProxyHandler({}))

def read_json(path):
    with opener.open(f"http://127.0.0.1:{port}{path}", timeout=0.75) as response:
        if response.status != 200:
            raise RuntimeError("unhealthy response")
        value = json.loads(response.read().decode("utf-8"))
        if not isinstance(value, dict):
            raise RuntimeError("unexpected response")
        return value

try:
    health = read_json("/api/health")
    governance = read_json("/api/governance")
    audit = governance.get("audit")
    enforcement = governance.get("enforcement")
    healthy = (
        health.get("status") == "ok"
        and health.get("product") == "StyrAI"
        and governance.get("mode") == "synthetic_local_control_plane"
        and isinstance(governance.get("models"), list)
        and bool(governance["models"])
        and isinstance(governance.get("metrics"), dict)
        and isinstance(enforcement, dict)
        and enforcement.get("inspection_point") == "before_provider_boundary"
        and isinstance(audit, dict)
        and audit.get("valid") is True
    )
except (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
    json.JSONDecodeError,
):
    healthy = False

raise SystemExit(0 if healthy else 1)
PY
}

port_is_free() {
  python3 - "$1" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
    try:
        probe.bind(("127.0.0.1", port))
    except OSError:
        raise SystemExit(1)
raise SystemExit(0)
PY
}

# Search the whole range before starting another process. This lets the
# launcher reuse a verified current StyrAI instance on a later port, while an
# old build or unrelated application on 8765 is left untouched.
for (( candidate_port = PORT_START; candidate_port <= PORT_END; candidate_port++ )); do
  if server_is_current_styrai "$candidate_port"; then
    RUNNING_PORT="$candidate_port"
    break
  fi
  if [[ -z "$FREE_PORT" ]] && port_is_free "$candidate_port"; then
    FREE_PORT="$candidate_port"
  fi
done

if [[ -n "$RUNNING_PORT" ]]; then
  DEMO_URL="http://127.0.0.1:${RUNNING_PORT}/?presentation=1"
  echo "A healthy StyrAI governance demo is already running on port ${RUNNING_PORT}."
  echo "Opening presenter mode now."
  open "$DEMO_URL"
  echo ""
  echo "You may close this window; the existing demo server will keep running."
  read -r "reply?Press Return to close this window..."
  exit 0
fi

if [[ -z "$FREE_PORT" ]]; then
  echo "StyrAI could not find a free local port from ${PORT_START} through ${PORT_END}."
  echo "Close one of the applications using those ports, then try again."
  echo ""
  read -r "reply?Press Return to close this window..."
  exit 1
fi

DEMO_PORT="$FREE_PORT"
echo "Starting StyrAI at http://127.0.0.1:${DEMO_PORT}"
echo "Your browser will open automatically when the demo is ready."
echo "Keep this window open while presenting. Press Control-C to stop the demo."
echo ""

python3 -m murphyos.web --port "$DEMO_PORT" --open-browser
server_status=$?

echo ""
if [[ $server_status -eq 0 ]]; then
  echo "The StyrAI demonstration has stopped."
else
  echo "StyrAI could not start on port ${DEMO_PORT}."
  echo "If needed, use the Terminal instructions in README.md."
fi
read -r "reply?Press Return to close this window..."
exit $server_status
