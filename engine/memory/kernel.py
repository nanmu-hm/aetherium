"""Deterministic memory formation, decay, recall, and opportunity handling."""

from __future__ import annotations

import math

from .models import (
    Belief,
    Desire,
    KnowledgeFact,
    Memory,
    MemoryRevision,
    MemoryState,
    RelationshipHistoryEntry,
)
from ..core.models import Event
from ..core.action_types import event_action_type


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

    def learn_fact(
        self,
        state: MemoryState,
        owner_id: str,
        proposition: str,
        tick: int,
        source: str = "direct_experience",
        source_event_id: str | None = None,
        confidence: float = 1.0,
        source_owner_id: str | None = None,
        parent_fact_id: str | None = None,
        transmission_depth: int = 0,
    ) -> KnowledgeFact:
        """Record what one character knows without changing world truth."""
        existing = state.get_knowledge(owner_id, proposition)
        bounded_confidence = max(0.0, min(1.0, confidence))
        if existing is None:
            owner_knowledge = state.knowledge.get(owner_id, {})
            fact = KnowledgeFact(
                id=f"knowledge-{owner_id}-{len(owner_knowledge) + 1}",
                owner_id=owner_id,
                proposition=proposition,
                source=source,
                source_event_id=source_event_id,
                source_owner_id=source_owner_id,
                parent_fact_id=parent_fact_id,
                transmission_depth=max(0, transmission_depth),
                confidence=bounded_confidence,
                first_learned_tick=tick,
                last_confirmed_tick=tick,
            )
        else:
            if bounded_confidence > existing.confidence:
                existing.confidence = bounded_confidence
                existing.source = source
                existing.source_event_id = source_event_id
                existing.source_owner_id = source_owner_id
                existing.parent_fact_id = parent_fact_id
                existing.transmission_depth = max(0, transmission_depth)
            existing.last_confirmed_tick = tick
            fact = existing
        state.add_knowledge(fact)
        return fact

    def transmit_knowledge(
        self,
        state: MemoryState,
        source_owner_id: str,
        recipient_id: str,
        proposition: str,
        tick: int,
        confidence_decay: float = 0.80,
    ) -> KnowledgeFact:
        """Transmit a known fact between characters without making it world truth."""
        if source_owner_id == recipient_id:
            raise ValueError("source and recipient must be different characters")
        if not 0.0 < confidence_decay <= 1.0:
            raise ValueError("confidence_decay must be in (0, 1]")

        source = state.get_knowledge(source_owner_id, proposition)
        if source is None:
            raise KeyError(
                f"{source_owner_id!r} does not know the proposition: {proposition!r}"
            )

        confidence = source.confidence * confidence_decay
        return self.learn_fact(
            state,
            recipient_id,
            proposition,
            tick=tick,
            source="heard",
            source_event_id=source.source_event_id,
            source_owner_id=source_owner_id,
            parent_fact_id=source.id,
            transmission_depth=source.transmission_depth + 1,
            confidence=confidence,
        )

    def record_event_knowledge(
        self,
        state: MemoryState,
        owner_id: str,
        event: Event,
    ) -> list[KnowledgeFact]:
        """Give direct participants only the facts contained in their experienced event."""
        if owner_id not in event.participants:
            return []
        return [
            self.learn_fact(
                state,
                owner_id,
                fact,
                tick=event.tick,
                source="direct_experience",
                source_event_id=event.id,
                confidence=1.0,
            )
            for fact in event.facts
        ]

    def record_event_belief(
        self,
        state: MemoryState,
        owner_id: str,
        event: Event,
        memory_id: str,
    ) -> Belief:
        action_type = event_action_type(event) or "unknown"
        target_ids = ",".join(event.participants[1:])
        outcome = event.action_result.status if event.action_result else "unknown"
        proposition = f"experience:{action_type}:{target_ids}:{outcome}"
        belief = Belief(
            id=f"belief-{owner_id}-{event.id}",
            owner_id=owner_id,
            proposition=proposition,
            truth_status="true",
            confidence=0.9 if outcome in {"success", "failure"} else 0.75,
            source_memory_ids=[memory_id],
            last_updated_tick=event.tick,
        )
        state.add_belief(belief)
        return belief

    def record_relationship_history(self, state: MemoryState, event: Event) -> list[RelationshipHistoryEntry]:
        """Preserve relationship-changing event history separately from current scores."""
        if event.action_result is None or event.action_result.status not in {"success", "failure"}:
            return []

        action_type = event_action_type(event) or "unknown"
        grouped: dict[str, dict[str, tuple[float, float]]] = {}
        for consequence in event.consequences:
            if consequence.target_type != "relationship":
                continue
            if consequence.field in {"trust", "affection", "loyalty", "fear", "respect", "resentment", "rivalry"}:
                old = float(consequence.old_value)
                new = float(consequence.new_value)
                grouped.setdefault(consequence.target_id, {})[consequence.field] = (old, new)

        entries: list[RelationshipHistoryEntry] = []
        for relationship_id, changes in grouped.items():
            parts = relationship_id.split(":", 1)
            if len(parts) != 2:
                continue
            actor_id, target_id = parts
            entry = RelationshipHistoryEntry(
                id=f"relationship-history-{event.id}-{relationship_id}",
                relationship_id=relationship_id,
                event_id=event.id,
                tick=event.tick,
                actor_id=actor_id,
                target_id=target_id,
                action_type=action_type,
                outcome=event.action_result.status,
                changes=changes,
                summary=event.facts[0] if event.facts else "",
            )
            state.add_relationship_history(entry)
            entries.append(entry)
        return entries

    def revise_memory(
        self,
        state: MemoryState,
        memory_id: str,
        new_interpretation: str,
        tick: int,
        reason: str = "",
        evidence_memory_ids: list[str] | None = None,
        confidence: float | None = None,
    ) -> MemoryRevision:
        """Record a new interpretation without destroying the prior one."""
        memory = state.memories[memory_id]
        previous = memory.interpretation
        revision = MemoryRevision(
            id=f"revision-{memory_id}-{tick}-{len(state.memory_revisions.get(memory_id, [])) + 1}",
            memory_id=memory_id,
            owner_id=memory.owner_id,
            tick=tick,
            previous_interpretation=previous,
            new_interpretation=new_interpretation,
            reason=reason,
            evidence_memory_ids=list(evidence_memory_ids or ()),
            confidence=memory.confidence if confidence is None else max(0.0, min(1.0, confidence)),
        )
        memory.interpretation = new_interpretation
        if confidence is not None:
            memory.confidence = revision.confidence
        state.add_memory_revision(revision)
        return revision

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
