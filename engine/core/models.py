"""Core state models for the first Aetherium MVP."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..memory.models import MemoryState
from .human_condition import HumanCondition


@dataclass
class Goal:
    id: str
    description: str
    priority: float = 1.0
    status: str = "active"
    # Optional staged plan. The top-level description remains the durable goal;
    # stages turn it into persistent, inspectable progress rather than a one-shot flag.
    stages: list[str] = field(default_factory=list)
    current_stage: int = 0

    @property
    def current_description(self) -> str:
        if self.stages and self.current_stage < len(self.stages):
            return self.stages[self.current_stage]
        return self.description

    @property
    def progress(self) -> float:
        if not self.stages:
            return 1.0 if self.status == "achieved" else 0.0
        return min(1.0, self.current_stage / len(self.stages))


@dataclass
class CharacterState:
    id: str
    name: str
    traits: list[str] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    goals: list[Goal] = field(default_factory=list)
    needs: list[str] = field(default_factory=list)
    emotions: dict[str, float] = field(default_factory=dict)
    human_condition: HumanCondition = field(default_factory=HumanCondition)
    location: str = ""
    knowledge: set[str] = field(default_factory=set)
    memory: list[str] = field(default_factory=list)
    memory_ids: list[str] = field(default_factory=list)
    # Procedural memory: learned behavioral tendencies by canonical action type.
    # Values range from -1 (avoid) to +1 (prefer) and change through lived outcomes.
    habits: dict[str, float] = field(default_factory=dict)
    # Identity memory: gradual self-beliefs formed from lived evidence.
    # Values range from -1 (the character rejects the identity) to +1
    # (the character strongly identifies with it). This is descriptive
    # self-concept, distinct from normative values.
    identity_beliefs: dict[str, float] = field(default_factory=dict)
    # Bounded-rationality controls. Defaults preserve deterministic utility-only choice.
    decision_noise: float = 0.0
    risk_tolerance: float = 0.0
    # Deprecated mirror; authoritative relationship state is WorldState.relationships.
    relationships: dict[str, float] = field(default_factory=dict)
    possessions: dict[str, int] = field(default_factory=dict)
    abilities: dict[str, float] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    status: str = "active"


@dataclass
class RelationshipState:
    source_id: str
    target_id: str
    trust: float = 50.0
    affection: float = 50.0
    loyalty: float = 50.0
    fear: float = 0.0
    respect: float = 50.0
    resentment: float = 0.0
    rivalry: float = 0.0


@dataclass
class FactionState:
    id: str
    name: str
    goals: list[str] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    members: set[str] = field(default_factory=set)
    resources: dict[str, float] = field(default_factory=dict)
    territory: set[str] = field(default_factory=set)
    allies: set[str] = field(default_factory=set)
    enemies: set[str] = field(default_factory=set)
    stability: float = 50.0
    reputation: float = 50.0


@dataclass
class ActionCandidate:
    id: str
    actor_id: str
    action_type: str
    targets: list[str] = field(default_factory=list)
    motivation: str = ""
    preconditions: list[str] = field(default_factory=list)
    expected_outcomes: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    confidence: float = 0.5
    # Structured intent/provenance used by resolution; it is actor-generated,
    # not hidden world state.
    metadata: dict[str, Any] = field(default_factory=dict)
    difficulty: float = 0.5
    required_ability: str = ""
    score: float = 0.0


@dataclass
class ActionResult:
    status: str  # success / failure / blocked
    reason: str = ""
    probability: float = 1.0


@dataclass
class Consequence:
    target_type: str
    target_id: str
    field: str
    old_value: Any
    new_value: Any
    reason: str = ""


@dataclass
class Event:
    id: str
    tick: int
    timestamp: str
    location: str
    participants: list[str]
    causes: list[str]
    facts: list[str]
    # Structured action identity; causes remain as provenance IDs for compatibility.
    action_type: str = ""
    action_result: ActionResult | None = None
    consequences: list[Consequence] = field(default_factory=list)


@dataclass
class WorldState:
    world_id: str
    tick: int = 0
    timestamp: str = "0001-01-01T00:00:00"
    locations: set[str] = field(default_factory=set)
    characters: dict[str, CharacterState] = field(default_factory=dict)
    relationships: dict[str, RelationshipState] = field(default_factory=dict)
    factions: dict[str, FactionState] = field(default_factory=dict)
    resources: dict[str, float] = field(default_factory=dict)
    event_log: list[Event] = field(default_factory=list)
    memory_state: MemoryState = field(default_factory=MemoryState)
    active_branch: str = "main"
    # Exact PRNG state used by SimulationEngine; persisted so checkpoints can replay future ticks.
    rng_state: tuple | None = None
    # Seed used for deterministic decision noise; a restored snapshot is authoritative.
    simulation_seed: int | None = None

    def add_character(self, character: CharacterState) -> None:
        if character.id in self.characters:
            raise ValueError(f"Character already exists: {character.id}")
        self.characters[character.id] = character

    def add_relationship(self, relationship: RelationshipState) -> None:
        key = f"{relationship.source_id}:{relationship.target_id}"
        self.relationships[key] = relationship

    def get_relationship(self, source_id: str, target_id: str) -> RelationshipState | None:
        return self.relationships.get(f"{source_id}:{target_id}")

    def add_faction(self, faction: FactionState) -> None:
        if faction.id in self.factions:
            raise ValueError(f"Faction already exists: {faction.id}")
        self.factions[faction.id] = faction
