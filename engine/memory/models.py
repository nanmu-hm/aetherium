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
class KnowledgeFact:
    id: str
    owner_id: str
    proposition: str
    source: str = "direct_experience"
    source_event_id: str | None = None
    confidence: float = 1.0
    first_learned_tick: int = 0
    last_confirmed_tick: int = 0


@dataclass
class RelationshipHistoryEntry:
    id: str
    relationship_id: str
    event_id: str
    tick: int
    actor_id: str
    target_id: str
    action_type: str
    outcome: str
    changes: dict[str, tuple[float, float]] = field(default_factory=dict)
    summary: str = ""


@dataclass
class MemoryRevision:
    id: str
    memory_id: str
    owner_id: str
    tick: int
    previous_interpretation: str
    new_interpretation: str
    reason: str = ""
    evidence_memory_ids: list[str] = field(default_factory=list)
    confidence: float = 1.0


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
    status: str = "active"
    reason: str = ""


@dataclass
class MemoryState:
    memories: dict[str, Memory] = field(default_factory=dict)
    beliefs: dict[str, Belief] = field(default_factory=dict)
    desires: dict[str, Desire] = field(default_factory=dict)
    relationship_history: dict[str, list[RelationshipHistoryEntry]] = field(default_factory=dict)
    memory_revisions: dict[str, list[MemoryRevision]] = field(default_factory=dict)
    knowledge: dict[str, dict[str, KnowledgeFact]] = field(default_factory=dict)

    def add_memory(self, memory: Memory) -> None:
        self.memories[memory.id] = memory

    def add_belief(self, belief: Belief) -> None:
        self.beliefs[belief.id] = belief

    def add_desire(self, desire: Desire) -> None:
        self.desires[desire.id] = desire

    def add_knowledge(self, fact: KnowledgeFact) -> None:
        self.knowledge.setdefault(fact.owner_id, {})[fact.proposition] = fact

    def get_knowledge(self, owner_id: str, proposition: str) -> KnowledgeFact | None:
        return self.knowledge.get(owner_id, {}).get(proposition)

    def add_relationship_history(self, entry: RelationshipHistoryEntry) -> None:
        self.relationship_history.setdefault(entry.relationship_id, []).append(entry)

    def add_memory_revision(self, revision: MemoryRevision) -> None:
        self.memory_revisions.setdefault(revision.memory_id, []).append(revision)
