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
