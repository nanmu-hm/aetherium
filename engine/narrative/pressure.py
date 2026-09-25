"""Narrative pressure extraction.

The pressure layer does not invent events. It measures why existing world
conditions are difficult for the involved characters and therefore useful for
story discovery.
"""

from __future__ import annotations

from ..core.models import Event, WorldState


class NarrativePressureAnalyzer:
    """Estimate conflict pressure from simulation state and event consequences."""

    def score_event(self, state: WorldState, event: Event) -> float:
        participant_pressure = 0.0
        seen = 0
        for character_id in event.participants:
            character = state.characters.get(character_id)
            if not character:
                continue
            participant_pressure += character.human_condition.pressure()
            participant_pressure += character.human_condition.attachment_strength() * 0.25
            seen += 1

        human_pressure = participant_pressure / seen if seen else 0.0
        consequence_pressure = min(1.0, len(event.consequences) * 0.2)
        relationship_pressure = 0.0
        for source_id in event.participants:
            for target_id in event.participants:
                if source_id == target_id:
                    continue
                relationship = state.get_relationship(source_id, target_id)
                if relationship:
                    relationship_pressure = max(
                        relationship_pressure,
                        min(
                            1.0,
                            (
                                relationship.resentment
                                + relationship.fear
                                + relationship.rivalry
                            )
                            / 150.0,
                        ),
                    )

        # Pressure is deliberately additive but capped: one dramatic signal
        # should not overwhelm all other evidence.
        return min(
            1.0,
            0.35 * human_pressure
            + 0.35 * consequence_pressure
            + 0.30 * relationship_pressure,
        )

    def score_events(self, state: WorldState, events: list[Event]) -> dict[str, float]:
        return {event.id: self.score_event(state, event) for event in events}
