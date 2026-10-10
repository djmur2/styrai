"""Hash-chained JSON Lines audit evidence for the StyrAI prototype."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AuditIntegrityError(RuntimeError):
    """Raised when an audit chain cannot be verified."""


class HashChainedAuditLog:
    GENESIS_HASH = "0" * 64

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _canonical(record: dict[str, Any]) -> bytes:
        return json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    def _records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise AuditIntegrityError(
                    f"Invalid audit JSON at line {line_number}."
                ) from exc
        return records

    def append(
        self, event_type: str, action_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        existing = self._records()
        previous_hash = (
            existing[-1]["record_hash"] if existing else self.GENESIS_HASH
        )
        unsigned = {
            "index": len(existing),
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "event_type": event_type,
            "action_id": action_id,
            "payload": payload,
            "previous_hash": previous_hash,
        }
        record_hash = hashlib.sha256(self._canonical(unsigned)).hexdigest()
        signed = {**unsigned, "record_hash": record_hash}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(signed, sort_keys=True, ensure_ascii=False) + "\n")
        return signed

    def rotate(self) -> Path | None:
        """Move a non-empty log aside so an explicit reset preserves evidence."""

        if not self.path.exists() or self.path.stat().st_size == 0:
            return None
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        rotated = self.path.with_name(
            f"{self.path.stem}.reset-{timestamp}{self.path.suffix}"
        )
        counter = 1
        while rotated.exists():
            rotated = self.path.with_name(
                f"{self.path.stem}.reset-{timestamp}-{counter}{self.path.suffix}"
            )
            counter += 1
        self.path.replace(rotated)
        return rotated

    def verify(self) -> bool:
        previous_hash = self.GENESIS_HASH
        for expected_index, record in enumerate(self._records()):
            actual_hash = record.get("record_hash")
            unsigned = {key: value for key, value in record.items() if key != "record_hash"}
            calculated_hash = hashlib.sha256(self._canonical(unsigned)).hexdigest()
            if record.get("index") != expected_index:
                raise AuditIntegrityError(
                    f"Unexpected index at audit record {expected_index}."
                )
            if record.get("previous_hash") != previous_hash:
                raise AuditIntegrityError(
                    f"Broken chain at audit record {expected_index}."
                )
            if actual_hash != calculated_hash:
                raise AuditIntegrityError(
                    f"Hash mismatch at audit record {expected_index}."
                )
            previous_hash = actual_hash
        return True

    def records(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._records())
