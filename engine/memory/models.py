"""Structured memory models for Aetherium characters."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Memory:
    id: str
    owner_id: str
    event_id: str
    summary: str
    tick: int
    location: str = ""
    participants: list[str] = field(default_factory=list)
    source: str = "experienced"
    emotional_salience: float = 0.5
    personal_importance: float = 0.5
    relationship_importance: float = 0.0
    unresolved: bool = False
    confidence: float = 1.0
    recall_strength: float = 1.0
    tags: set[str] = field(default_factory=set)
    interpretation: str = ""


@dataclass
class Belief:
    id: str
    owner_id: str
    proposition: str
    truth_status: str = "unknown"  # unknown / true / false / mixed
    confidence: float = 0.5
    source_memory_ids: list[str] = field(default_factory=list)
    last_updated_tick: int = 0


@dataclass
class Desire:
    id: str
    owner_id: str
    description: str
    priority: float = 0.5
    need: str = ""
    target_id: str | None = None
    opportunity_window_start: int | None = None
    opportunity_window_end: int | None = None
    cost: float = 0.0
    urgency: float = 0.0
    status: str = "active"  # active / achieved / missed / abandoned / impossible
    reason: str = ""


@dataclass
class MemoryState:
    memories: dict[str, Memory] = field(default_factory=dict)
    beliefs: dict[str, Belief] = field(default_factory=dict)
    desires: dict[str, Desire] = field(default_factory=dict)

    def add_memory(self, memory: Memory) -> None:
        self.memories[memory.id] = memory

    def add_belief(self, belief: Belief) -> None:
        self.beliefs[belief.id] = belief

    def add_desire(self, desire: Desire) -> None:
        self.desires[desire.id] = desire
