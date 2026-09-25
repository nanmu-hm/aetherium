from __future__ import annotations

import json
from pathlib import Path

from .models import CanonEntry


class CanonLedger:
    """Append-only provenance ledger for assertions about the world."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: CanonEntry) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.__dict__, ensure_ascii=False, sort_keys=True) + "\n")

    def list(self, *, branch_id: str | None = None, status: str | None = None) -> list[CanonEntry]:
        if not self.path.exists():
            return []
        result = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = CanonEntry(**json.loads(line))
            if branch_id is not None and entry.branch_id != branch_id:
                continue
            if status is not None and entry.status != status:
                continue
            result.append(entry)
        return result

    def by_source(self, source_id: str) -> list[CanonEntry]:
        return [entry for entry in self.list() if entry.source_id == source_id]
