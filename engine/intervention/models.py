from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InterventionRequest:
    id: str
    intervention_type: str
    target_path: str
    new_value: Any
    effective_tick: int | None = None
    created_by: str = "user"
    reason: str = ""


@dataclass
class ImpactItem:
    category: str
    identifier: str
    reason: str
    severity: float = 0.0


@dataclass
class ImpactReport:
    request_id: str
    items: list[ImpactItem] = field(default_factory=list)

    @property
    def affected_count(self) -> int:
        return len(self.items)


@dataclass
class ConflictFinding:
    category: str
    message: str
    severity: float = 0.0
    source_ids: list[str] = field(default_factory=list)


@dataclass
class InterventionPlan:
    request_id: str
    action: str
    reason: str
    impact: ImpactReport
    conflicts: list[ConflictFinding] = field(default_factory=list)
