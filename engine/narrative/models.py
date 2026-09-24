"""Narrative-layer data models.

The narrative layer observes simulation history. It does not mutate world state.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NarrativeSignal:
    """A detected condition that may matter to a future story."""

    signal_type: str
    strength: float
    participants: list[str] = field(default_factory=list)
    source_event_ids: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class NarrativeThread:
    """A persistent thread tracked across otherwise independent events."""

    id: str
    thread_type: str
    title: str
    participants: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    tension: float = 0.0
    status: str = "open"
    unresolved_question: str = ""


@dataclass
class InformationGap:
    """A proposition known by some characters but not others."""

    id: str
    proposition: str
    source_event_ids: list[str] = field(default_factory=list)
    known_by: list[str] = field(default_factory=list)
    unknown_by: list[str] = field(default_factory=list)
    confidence_range: tuple[float, float] = (0.0, 0.0)
    strength: float = 0.0
    description: str = ""


@dataclass
class RevelationCandidate:
    """A causally grounded opportunity for one character to learn an asymmetric fact."""

    id: str
    proposition: str
    source_character_id: str
    target_character_id: str
    source_event_id: str | None = None
    confidence: float = 0.0
    strength: float = 0.0
    reason: str = ""


@dataclass
class CharacterArc:
    """A derived trajectory from persistent character changes."""

    id: str
    character_id: str
    event_ids: list[str] = field(default_factory=list)
    identity_changes: list[str] = field(default_factory=list)
    emotional_changes: list[str] = field(default_factory=list)
    goal_changes: list[str] = field(default_factory=list)
    relationship_changes: list[str] = field(default_factory=list)
    change_score: float = 0.0
    phase: str = "stable"
    description: str = ""


@dataclass
class NarrativeImportance:
    """Derived importance of an event to an emerging story."""

    event_id: str
    historical_size: float = 0.0
    narrative_score: float = 0.0
    pressure_factor: float = 0.0
    relationship_factor: float = 0.0
    character_change_factor: float = 0.0
    information_factor: float = 0.0
    causal_reach_factor: float = 0.0
    description: str = ""


@dataclass
class ThreadConvergence:
    """A derived point where previously separate threads begin to interact."""

    id: str
    thread_ids: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    strength: float = 0.0
    description: str = ""


@dataclass
class ForeshadowingLink:
    """A candidate setup/callback relation discovered after both events exist."""

    setup_event_id: str
    payoff_event_id: str
    shared_keys: list[str] = field(default_factory=list)
    confidence: float = 0.0
    causal: bool = False
    description: str = ""


@dataclass
class NarrativeDilemma:
    """A derived conflict between viable actions aligned with different values."""

    id: str
    character_id: str
    action_ids: list[str] = field(default_factory=list)
    competing_values: list[str] = field(default_factory=list)
    strength: float = 0.0
    utility_gap: float = 0.0
    description: str = ""


@dataclass
class RhythmState:
    """Derived narrative rhythm; it never changes authoritative world state."""

    phase: str = "calm"
    pressure: float = 0.0
    previous_pressure: float = 0.0
    trend: str = "flat"
    breathing_needed: bool = False
    high_pressure_streak: int = 0


@dataclass
class NarrativeBeat:
    """A compact story unit selected from simulation history."""

    id: str
    tick: int
    beat_type: str
    event_ids: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    pressure: float = 0.0
    description: str = ""


@dataclass
class NarrativeState:
    """Derived narrative observations; safe to recompute from the event log."""

    pressure: float = 0.0
    recent_climax_tick: int | None = None
    unresolved_threads: list[NarrativeThread] = field(default_factory=list)
    signals: list[NarrativeSignal] = field(default_factory=list)
    beats: list[NarrativeBeat] = field(default_factory=list)
    dilemmas: list[NarrativeDilemma] = field(default_factory=list)
    rhythm: RhythmState = field(default_factory=RhythmState)
    threads: list[NarrativeThread] = field(default_factory=list)
    arcs: list[CharacterArc] = field(default_factory=list)
    information_gaps: list[InformationGap] = field(default_factory=list)
    revelations: list[RevelationCandidate] = field(default_factory=list)
    importance: list[NarrativeImportance] = field(default_factory=list)
    convergences: list[ThreadConvergence] = field(default_factory=list)
    foreshadowing: list[ForeshadowingLink] = field(default_factory=list)
