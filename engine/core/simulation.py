"""Deterministic first-pass simulation loop."""

from __future__ import annotations

from dataclasses import dataclass
import random

from .actions import choose_action, generate_action_pool
from .models import ActionCandidate, Consequence, Event, WorldState


@dataclass
class SimulationResult:
    tick: int
    actions: list[ActionCandidate]
    events: list[Event]
    validation_errors: list[str]


class SimulationEngine:
    def __init__(self, seed: int = 0) -> None:
        self.random = random.Random(seed)

    def generate_candidates(self, state: WorldState) -> list[ActionCandidate]:
        """Generate and select one action per active character."""
        selected: list[ActionCandidate] = []
        for character in state.characters.values():
            action = choose_action(generate_action_pool(state, character.id))
            if action is not None:
                selected.append(action)
        return selected

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
                    actor.relationships[target.id] = relationship.trust
                    facts.append(f"{actor.name} speaks with {target.name} at {actor.location}.")
                    actor.memory.append(f"Spoke with {target.name}.")
                    target.memory.append(f"Spoke with {actor.name}.")
                    consequences.append(Consequence("relationship", f"{actor.id}:{target.id}", "trust", old_trust, relationship.trust, "successful contact"))
                    consequences.append(Consequence("relationship", f"{actor.id}:{target.id}", "affection", old_affection, relationship.affection, "successful contact"))
                elif target is not None:
                    facts.append(f"{actor.name} cannot meet {target.name}; they are in different locations.")

            elif action.action_type == "help_person":
                target = state.characters.get(action.targets[0])
                if target is not None:
                    facts.append(f"{actor.name} decides to help {target.name}.")
                    actor.memory.append(f"Helped {target.name}.")

            else:
                facts.append(f"{actor.name} attempts to {action.motivation}.")
                actor.memory.append(facts[0])

            events.append(Event(
                id=f"event-{state.tick}-{actor.id}-{action.action_type}",
                tick=state.tick,
                timestamp=state.timestamp,
                location=actor.location,
                participants=[actor.id, *action.targets],
                causes=[action.id],
                facts=facts,
                consequences=consequences,
            ))
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
        state.event_log.extend(events)
        errors = self.validate(state)
        state.tick += 1
        return SimulationResult(state.tick - 1, actions, events, errors)
