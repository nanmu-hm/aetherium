from __future__ import annotations

import json
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from typing import Any

from ..core.models import (
    ActionResult,
    CharacterState,
    Consequence,
    DesireCarrier,
    Event,
    FactionState,
    Goal,
    RelationshipState,
    WorldState,
)
from ..core.human_condition import HumanCondition
from ..memory.models import (
    Belief,
    Desire,
    DesireHistory,
    KnowledgeFact,
    Memory,
    MemoryRevision,
    MemoryState,
    RelationshipHistoryEntry,
)


SCHEMA_VERSION = 1


def _encode(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: _encode(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, set):
        return {"__set__": [_encode(item) for item in sorted(value)]}
    if isinstance(value, tuple):
        return {"__tuple__": [_encode(item) for item in value]}
    if isinstance(value, dict):
        return {str(key): _encode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"__set__"}:
            return set(_decode(item) for item in value["__set__"])
        if set(value) == {"__tuple__"}:
            return tuple(_decode(item) for item in value["__tuple__"])
        return {key: _decode(item) for key, item in value.items()}
    return value


def world_to_dict(state: WorldState) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "world": _encode(state)}


def world_to_json(state: WorldState, *, indent: int | None = None) -> str:
    return json.dumps(world_to_dict(state), ensure_ascii=False, sort_keys=True, indent=indent)


def _goal(data: dict[str, Any]) -> Goal:
    return Goal(**data)


def _human_condition(data: dict[str, Any]) -> HumanCondition:
    return HumanCondition(**data)


def _character(data: dict[str, Any]) -> CharacterState:
    data = dict(data)
    data["goals"] = [_goal(item) for item in data.get("goals", [])]
    data["human_condition"] = _human_condition(data.get("human_condition", {}))
    data["desire_carriers"] = {
        key: DesireCarrier(**{**item, "consumed_at": item.get("consumed_at"),
                              "consumed_evidence": item.get("consumed_evidence", "")})
        for key, item in data.get("desire_carriers", {}).items()
    }
    return CharacterState(**data)


def _action_result(data: dict[str, Any] | None) -> ActionResult | None:
    return None if data is None else ActionResult(**data)


def _consequence(data: dict[str, Any]) -> Consequence:
    return Consequence(**data)


def _event(data: dict[str, Any]) -> Event:
    data = dict(data)
    data["action_result"] = _action_result(data.get("action_result"))
    data["consequences"] = [_consequence(item) for item in data.get("consequences", [])]
    return Event(**data)


def _relationship(data: dict[str, Any]) -> RelationshipState:
    return RelationshipState(**data)


def _faction(data: dict[str, Any]) -> FactionState:
    return FactionState(**data)


def _memory(data: dict[str, Any]) -> Memory:
    return Memory(**data)


def _belief(data: dict[str, Any]) -> Belief:
    return Belief(**data)


def _desire(data: dict[str, Any]) -> Desire:
    return Desire(**data)


def _desire_history(data: dict[str, Any]) -> DesireHistory:
    return DesireHistory(**data)


def _evidence_tick(event_id: str) -> int:
    """Tick encoded in an event id (``event-{tick}-{actor}-{action}``).

    Canonicalization needs a total order of evidence recency; string order of
    event ids is NOT tick order (``event-105`` < ``event-20`` lexically), so
    the embedded tick is parsed explicitly. Unparseable ids rank lowest.
    """
    parts = event_id.split("-")
    if len(parts) >= 2 and parts[0] == "event" and parts[1].isdigit():
        return int(parts[1])
    return -1


def _canonicalize_desires(raw_desires: dict[str, dict[str, Any]]) -> tuple[dict[str, Desire], dict[str, list[DesireHistory]]]:
    """Collapse old multi-row ``desires`` payloads to one current row per identity.

    Identity = ``(owner_id, description)``, stored under the STABLE key
    ``"{owner}:store1:{desc}"``. A new-style payload already holds one row per
    identity (the stable key). An old-style payload may hold several rows for
    the same identity (one per per-event suffix); exactly the most-recent-
    evidence row survives as the current row, and the displaced rows migrate
    into the independent ``desire_history`` container (provenance only).
    Every surviving row is re-keyed to the stable key so ``desires`` is always
    in canonical form after load.
    """
    from collections import defaultdict

    groups: dict[str, list[str]] = defaultdict(list)
    identity_of: dict[str, str] = {}
    for row_id in raw_desires:
        owner = raw_desires[row_id].get("owner_id", "")
        desc = raw_desires[row_id].get("description", "")
        key = f"{owner}:store1:{desc}"
        identity_of[row_id] = key
        groups[key].append(row_id)

    current: dict[str, Desire] = {}
    displaced: dict[str, list[DesireHistory]] = defaultdict(list)
    for key, row_ids in groups.items():
        owner = raw_desires[row_ids[0]].get("owner_id", "")
        desc = raw_desires[row_ids[0]].get("description", "")

        def _recency(rid: str) -> tuple[int, str]:
            d = raw_desires[rid]
            evidence = d.get("latest_evidence_event_id", "") or d.get("source_event_id", "")
            return (_evidence_tick(evidence), rid)

        ranked = sorted(row_ids, key=_recency, reverse=True)
        winner, older = ranked[0], ranked[1:]
        data = dict(raw_desires[winner])
        data["id"] = key
        current[key] = _desire(data)
        for rid in older:
            d = raw_desires[rid]
            displaced[key].append(
                DesireHistory(
                    owner_id=owner,
                    description=desc,
                    status=d.get("status", ""),
                    reason=d.get("reason", ""),
                    source_event_id=d.get("source_event_id", ""),
                    latest_evidence_event_id=d.get("latest_evidence_event_id", ""),
                )
            )
    return current, dict(displaced)


def _knowledge(data: dict[str, Any]) -> KnowledgeFact:
    return KnowledgeFact(**data)


def _relationship_history(data: dict[str, Any]) -> RelationshipHistoryEntry:
    return RelationshipHistoryEntry(**data)


def _memory_revision(data: dict[str, Any]) -> MemoryRevision:
    return MemoryRevision(**data)


def _memory_state(data: dict[str, Any]) -> MemoryState:
    raw_desires = data.get("desires", {})
    desires, canonical_history = _canonicalize_desires(raw_desires)
    # Load-time canonicalization merges any explicitly-saved desire_history with
    # the rows displaced from the old-style `desires` payload. Provenance only.
    saved_history = {
        key: [_desire_history(item) for item in values]
        for key, values in data.get("desire_history", {}).items()
    }
    for key, entries in canonical_history.items():
        saved_history.setdefault(key, []).extend(entries)
    return MemoryState(
        memories={key: _memory(value) for key, value in data.get("memories", {}).items()},
        beliefs={key: _belief(value) for key, value in data.get("beliefs", {}).items()},
        desires=desires,
        desire_history=saved_history,
        relationship_history={
            key: [_relationship_history(item) for item in values]
            for key, values in data.get("relationship_history", {}).items()
        },
        memory_revisions={
            key: [_memory_revision(item) for item in values]
            for key, values in data.get("memory_revisions", {}).items()
        },
        knowledge={
            owner: {proposition: _knowledge(value) for proposition, value in facts.items()}
            for owner, facts in data.get("knowledge", {}).items()
        },
    )


def world_from_dict(payload: dict[str, Any]) -> WorldState:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported world snapshot schema: {payload.get('schema_version')!r}"
        )
    raw = _decode(payload["world"])
    raw = dict(raw)
    raw["characters"] = {
        key: _character(value) for key, value in raw.get("characters", {}).items()
    }
    raw["relationships"] = {
        key: _relationship(value) for key, value in raw.get("relationships", {}).items()
    }
    raw["factions"] = {
        key: _faction(value) for key, value in raw.get("factions", {}).items()
    }
    raw["event_log"] = [_event(item) for item in raw.get("event_log", [])]
    raw["memory_state"] = _memory_state(raw.get("memory_state", {}))
    return WorldState(**raw)


def save_world_json(state: WorldState, path: str | Path, *, indent: int = 2) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(world_to_json(state, indent=indent), encoding="utf-8")


def load_world_json(path: str | Path) -> WorldState:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return world_from_dict(payload)
