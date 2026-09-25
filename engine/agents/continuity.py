from __future__ import annotations

from collections import Counter

from ..persistence.codec import world_from_dict
from .contracts import standard_contracts
from .models import AgentContext, AgentResult, AgentStatus


class ContinuityAgent:
    """Read-only continuity validator over an authoritative snapshot."""

    def __init__(self) -> None:
        self.contract = standard_contracts()[self._role()]

    @staticmethod
    def _role():
        from .models import AgentRole
        return AgentRole.CONTINUITY

    def inspect(self, context: AgentContext) -> AgentResult:
        state = world_from_dict(context.world_snapshot)
        diagnostics: list[str] = []

        character_ids = set(state.characters)
        for character in state.characters.values():
            if character.location and character.location not in state.locations:
                diagnostics.append(
                    f"Character {character.id} references unknown location {character.location}."
                )

        for key, relationship in state.relationships.items():
            if relationship.source_id not in character_ids or relationship.target_id not in character_ids:
                diagnostics.append(
                    f"Relationship {key} references a missing character endpoint."
                )

        event_ids = [event.id for event in state.event_log]
        for event_id, count in Counter(event_ids).items():
            if count > 1:
                diagnostics.append(f"Duplicate event id: {event_id}.")

        previous_tick = -1
        for event in state.event_log:
            if event.tick < previous_tick:
                diagnostics.append(
                    f"Event history is out of order near event {event.id}: tick {event.tick} follows {previous_tick}."
                )
            previous_tick = max(previous_tick, event.tick)

            if event.tick > state.tick:
                diagnostics.append(
                    f"Event {event.id} is ahead of world tick {state.tick}."
                )

            if event.location and event.location not in state.locations:
                diagnostics.append(
                    f"Event {event.id} references unknown location {event.location}."
                )

            missing = [item for item in event.participants if item not in character_ids]
            if missing:
                diagnostics.append(
                    f"Event {event.id} references missing participant(s): {', '.join(missing)}."
                )

        if diagnostics:
            return AgentResult(
                status=AgentStatus.BLOCKED,
                response=f"Continuity check found {len(diagnostics)} issue(s).",
                diagnostics=diagnostics,
            )

        return AgentResult(
            status=AgentStatus.OK,
            response="Continuity check found no structural chronology, location, relationship, or participant violations.",
        )

    def respond(self, context: AgentContext, message: str) -> AgentResult:
        result = self.inspect(context)
        result.response = f"{result.response} User question: {message}"
        return result
