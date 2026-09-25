from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NarrativeCanonEntry:
    id: str
    draft_id: str
    version: int
    scene_id: str
    title: str
    prose: str
    source_event_ids: tuple[str, ...]
    participant_ids: tuple[str, ...]
    viewpoint_character_id: str | None
    branch_id: str
    tick: int
    approved_by: str
    approved_at: str
    metadata: dict[str, str]


class NarrativeCanonLedger:
    """Append-only ledger for approved narrative text and its provenance."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: NarrativeCanonEntry) -> None:
        payload = {
            "id": entry.id,
            "draft_id": entry.draft_id,
            "version": entry.version,
            "scene_id": entry.scene_id,
            "title": entry.title,
            "prose": entry.prose,
            "source_event_ids": list(entry.source_event_ids),
            "participant_ids": list(entry.participant_ids),
            "viewpoint_character_id": entry.viewpoint_character_id,
            "branch_id": entry.branch_id,
            "tick": entry.tick,
            "approved_by": entry.approved_by,
            "approved_at": entry.approved_at,
            "metadata": dict(entry.metadata),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def list(self, *, branch_id: str | None = None) -> list[NarrativeCanonEntry]:
        if not self.path.exists():
            return []

        result: list[NarrativeCanonEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            entry = NarrativeCanonEntry(
                id=payload["id"],
                draft_id=payload["draft_id"],
                version=int(payload["version"]),
                scene_id=payload["scene_id"],
                title=payload["title"],
                prose=payload["prose"],
                source_event_ids=tuple(payload.get("source_event_ids", [])),
                participant_ids=tuple(payload.get("participant_ids", [])),
                viewpoint_character_id=payload.get("viewpoint_character_id"),
                branch_id=payload["branch_id"],
                tick=int(payload["tick"]),
                approved_by=payload["approved_by"],
                approved_at=payload["approved_at"],
                metadata=dict(payload.get("metadata", {})),
            )
            if branch_id is not None and entry.branch_id != branch_id:
                continue
            result.append(entry)
        return result

    def by_draft(self, draft_id: str) -> list[NarrativeCanonEntry]:
        return [entry for entry in self.list() if entry.draft_id == draft_id]
