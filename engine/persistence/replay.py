from __future__ import annotations

from copy import deepcopy

from ..core.models import WorldState
from ..core.simulation import SimulationEngine


class ReplayVerifier:
    """Re-run a deterministic world and compare authoritative event history."""

    @staticmethod
    def event_signature(event) -> tuple:
        return (
            event.id,
            event.tick,
            event.timestamp,
            event.location,
            tuple(event.participants),
            tuple(event.causes),
            tuple(event.facts),
            event.action_result.status if event.action_result else None,
            tuple(
                (item.target_type, item.target_id, item.field, item.old_value, item.new_value)
                for item in event.consequences
            ),
        )

    def verify(self, initial_state: WorldState, expected_events: list, seed: int, steps: int) -> bool:
        state = deepcopy(initial_state)
        engine = SimulationEngine(seed=seed)
        produced = []
        for _ in range(steps):
            result = engine.step(state)
            produced.extend(result.events)
        return [self.event_signature(event) for event in produced] == [
            self.event_signature(event) for event in expected_events
        ]
