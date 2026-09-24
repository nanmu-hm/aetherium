"""Deterministic first-pass simulation loop.

This module deliberately contains no LLM calls. It establishes the
authoritative state-transition boundary before model integration.
"""

from __future__ import annotations

from dataclasses import dataclass
import random

from .models import ActionCandidate, Event, WorldState


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
        candidates: list[ActionCandidate] = []
        for character in state.characters.values():
            if character.status != "active":
                continue
            if not character.goals:
                continue
            goal = max(character.goals, key=lambda item: item.priority)
            action_id = f"tick-{state.tick}-{character.id}-pursue"
            candidates.append(
                ActionCandidate(
                    id=action_id,
                    actor_id=character.id,
                    action_type="pursue_goal",
                    motivation=goal.description,
                    confidence=0.8,
                    score=goal.priority,
                )
            )
        return candidates

    def resolve(self, state: WorldState, actions: list[ActionCandidate]) -> list[Event]:
        events: list[Event] = []
        for action in actions:
            actor = state.characters[action.actor_id]
            goal_text = action.motivation or "pursue a goal"
            fact = f"{actor.name} attempts to {goal_text}."
            event = Event(
                id=f"event-{state.tick}-{action.actor_id}",
                tick=state.tick,
                timestamp=state.timestamp,
                location=actor.location,
                participants=[actor.id],
                causes=[action.id],
                facts=[fact],
            )
            actor.memory.append(fact)
            events.append(event)
        return events

    def validate(self, state: WorldState) -> list[str]:
        errors: list[str] = []
        for character in state.characters.values():
            if character.location and character.location not in state.locations:
                errors.append(
                    f"{character.id} is at unknown location {character.location!r}"
                )
        return errors

    def step(self, state: WorldState) -> SimulationResult:
        actions = self.generate_candidates(state)
        events = self.resolve(state, actions)
        state.event_log.extend(events)
        errors = self.validate(state)
        state.tick += 1
        return SimulationResult(
            tick=state.tick - 1,
            actions=actions,
            events=events,
            validation_errors=errors,
        )
