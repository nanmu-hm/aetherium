from __future__ import annotations

import json
from pathlib import Path

from ..core.models import Event
from .codec import _decode, _encode


class JsonEventStore:
    """Append-only JSONL storage for authoritative simulation events."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: Event) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_encode(event), ensure_ascii=False, sort_keys=True) + "\n")

    def append_many(self, events: list[Event]) -> None:
        for event in events:
            self.append(event)

    def read_all(self) -> list[Event]:
        if not self.path.exists():
            return []
        from .codec import _action_result, _consequence
        result = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = _decode(json.loads(line))
            data["action_result"] = _action_result(data.get("action_result"))
            data["consequences"] = [_consequence(item) for item in data.get("consequences", [])]
            result.append(Event(**data))
        return result

    def count(self) -> int:
        return len(self.read_all())
