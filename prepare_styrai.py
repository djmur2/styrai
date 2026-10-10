"""Restore email-transported assets, then launch the StyrAI partner demo."""

from __future__ import annotations

from pathlib import Path

from launch_styrai import main as launch


PROJECT_ROOT = Path(__file__).resolve().parent
TRANSPORTED_APP = PROJECT_ROOT / "web" / "app.source.txt"
RUNTIME_APP = PROJECT_ROOT / "web" / "app.js"


def restore_frontend() -> None:
    if RUNTIME_APP.exists():
        return
    if not TRANSPORTED_APP.exists():
        raise FileNotFoundError(
            "The transported web/app.source.txt file is missing. "
            "Extract the complete StyrAI package and try again."
        )
    RUNTIME_APP.write_bytes(TRANSPORTED_APP.read_bytes())


def main() -> int:
    restore_frontend()
    return launch()


if __name__ == "__main__":
    raise SystemExit(main())
