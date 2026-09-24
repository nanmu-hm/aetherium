"""Deterministic memory formation, decay, recall, and opportunity handling."""

from __future__ import annotations

import math

from .models import Belief, Desire, Memory, MemoryState
from ..core.models import Event


class MemoryKernel:
    """Small deterministic kernel; persistence backends can be added later."""

    def __init__(self, decay_rate: float = 0.015) -> None:
        self.decay_rate = decay_rate

    def remember_event(self, state: MemoryState, owner_id: str, event: Event, summary: str,
                       source: str = "experienced", emotional_salience: float = 0.5,
                       personal_importance: float = 0.5, relationship_importance: float = 0.0,
                       unresolved: bool = False, confidence: float = 1.0,
                       tags: set[str] | None = None) -> Memory:
        memory = Memory(
            id=f"memory-{owner_id}-{event.id}", owner_id=owner_id, event_id=event.id,
            summary=summary, tick=event.tick, location=event.location,
            participants=list(event.participants), source=source,
            emotional_salience=max(0.0, min(1.0, emotional_salience)),
            personal_importance=max(0.0, min(1.0, personal_importance)),
            relationship_importance=max(0.0, min(1.0, relationship_importance)),
            unresolved=unresolved, confidence=max(0.0, min(1.0, confidence)),
            tags=set(tags or ()),
        )
        state.add_memory(memory)
        return memory

    def decay(self, state: MemoryState, current_tick: int) -> None:
        for memory in state.memories.values():
            age = max(0, current_tick - memory.tick)
            protection = (
                0.45 * memory.emotional_salience
                + 0.30 * memory.personal_importance
                + 0.15 * memory.relationship_importance
                + 0.10 * float(memory.unresolved)
            )
            effective_rate = self.decay_rate * (1.0 - min(0.9, protection))
            memory.recall_strength = max(0.05, math.exp(-effective_rate * age))

    def recall(self, state: MemoryState, owner_id: str, cue: str = "", limit: int = 5) -> list[Memory]:
        cue_terms = {part.lower() for part in cue.split() if part}
        candidates = [m for m in state.memories.values() if m.owner_id == owner_id]

        def score(memory: Memory) -> float:
            overlap = sum(term in memory.summary.lower() or term in memory.tags for term in cue_terms)
            return memory.recall_strength + 0.2 * overlap + 0.2 * memory.emotional_salience

        return sorted(candidates, key=score, reverse=True)[:limit]

    def add_belief(self, state: MemoryState, belief: Belief) -> None:
        state.add_belief(belief)

    def advance_desires(self, state: MemoryState, current_tick: int) -> None:
        for desire in state.desires.values():
            if desire.status != "active":
                continue
            if desire.opportunity_window_end is not None and current_tick > desire.opportunity_window_end:
                desire.status = "missed"
                desire.reason = "opportunity window closed before the desire was fulfilled"

    def mark_desire(self, state: MemoryState, desire_id: str, status: str, reason: str = "") -> None:
        if status not in {"achieved", "missed", "abandoned", "impossible", "active"}:
            raise ValueError(f"unsupported desire status: {status}")
        desire = state.desires[desire_id]
        desire.status = status
        desire.reason = reason
