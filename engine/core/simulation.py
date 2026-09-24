"""Deterministic character-driven simulation loop with memory integration."""

from __future__ import annotations

from dataclasses import dataclass
import random

from .actions import generate_action_pool
from .decision import DecisionKernel
from .models import ActionCandidate, Consequence, Event, WorldState
from ..memory.kernel import MemoryKernel


@dataclass
class SimulationResult:
    tick: int
    actions: list[ActionCandidate]
    events: list[Event]
    validation_errors: list[str]


class SimulationEngine:
    def __init__(self, seed: int = 0, memory_kernel: MemoryKernel | None = None) -> None:
        self.random = random.Random(seed)
        self.memory_kernel = memory_kernel or MemoryKernel()
        self.decision_kernel = DecisionKernel(seed=seed)

    def generate_candidates(self, state: WorldState) -> list[ActionCandidate]:
        """Generate and select one plausible action per active character."""
        selected: list[ActionCandidate] = []
        for character in state.characters.values():
            pool = generate_action_pool(state, character.id)
            action, _ = self.decision_kernel.choose(state, pool)
            if action is not None:
                selected.append(action)
        return selected

    def _record_memories(self, state: WorldState, event: Event) -> None:
        """Give participants an experience of the event without giving them omniscience."""
        for character_id in event.participants:
            character = state.characters.get(character_id)
            if character is None:
                continue
            summary = event.facts[0] if event.facts else "An event occurred."
            memory = self.memory_kernel.remember_event(
                state.memory_state, character_id, event, summary,
                emotional_salience=0.55 if len(event.participants) > 1 else 0.35,
                personal_importance=0.5,
                relationship_importance=0.5 if len(event.participants) > 1 else 0.0,
                unresolved=bool(event.causes),
            )
            character.memory_ids.append(memory.id)
            # Legacy human-readable memory remains available during migration.
            character.memory.append(summary)

    def resolve(self, state: WorldState, actions: list[ActionCandidate]) -> list[Event]:
        events: list[Event] = []
        for action in actions:
            actor = state.characters[action.actor_id]
            consequences: list[Consequence] = []
            facts: list[str] = []

            if action.action_type == "travel":
                destination = action.targets[0]
                old = actor.location
                actor.location = destination
                consequences.append(Consequence("character", actor.id, "location", old, destination, "travel"))
                facts.append(f"{actor.name} travels from {old} to {destination}.")

            elif action.action_type == "contact_person":
                target = state.characters.get(action.targets[0])
                relationship = state.get_relationship(actor.id, target.id) if target else None
                if target is not None and relationship is not None and target.location == actor.location:
                    old_trust = relationship.trust
                    old_affection = relationship.affection
                    relationship.trust = min(100.0, relationship.trust + 2.0)
                    relationship.affection = min(100.0, relationship.affection + 1.0)
                    facts.append(f"{actor.name} speaks with {target.name} at {actor.location}.")
                    consequences.append(Consequence("relationship", f"{actor.id}:{target.id}", "trust", old_trust, relationship.trust, "successful contact"))
                    consequences.append(Consequence("relationship", f"{actor.id}:{target.id}", "affection", old_affection, relationship.affection, "successful contact"))
                elif target is not None:
                    facts.append(f"{actor.name} cannot meet {target.name}; they are in different locations.")

            elif action.action_type == "help_person":
                target = state.characters.get(action.targets[0])
                if target is not None:
                    facts.append(f"{actor.name} decides to help {target.name}.")

            else:
                facts.append(f"{actor.name} attempts to {action.motivation}.")

            events.append(Event(
                id=f"event-{state.tick}-{actor.id}-{action.action_type}",
                tick=state.tick,
                timestamp=state.timestamp,
                location=actor.location,
                participants=[actor.id, *action.targets],
                causes=[action.id], facts=facts, consequences=consequences,
            ))

        for event in events:
            state.event_log.append(event)
            self._record_memories(state, event)
        return events

    def validate(self, state: WorldState) -> list[str]:
        errors: list[str] = []
        for character in state.characters.values():
            if character.location and character.location not in state.locations:
                errors.append(f"{character.id} is at unknown location {character.location!r}")
        return errors

    def step(self, state: WorldState) -> SimulationResult:
        actions = self.generate_candidates(state)
        events = self.resolve(state, actions)
        self.memory_kernel.decay(state.memory_state, state.tick)
        self.memory_kernel.advance_desires(state.memory_state, state.tick)
        errors = self.validate(state)
        current_tick = state.tick
        state.tick += 1
        return SimulationResult(current_tick, actions, events, errors)
