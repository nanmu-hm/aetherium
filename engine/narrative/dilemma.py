"""Detect character dilemmas from current viable choices without forcing outcomes."""

from __future__ import annotations

from itertools import combinations

from ..core.actions import generate_action_pool
from ..core.decision import DecisionKernel
from ..core.models import ActionCandidate, WorldState
from .models import NarrativeDilemma


class DilemmaDetector:
    """Find close, value-opposed choices already available to a character."""

    ACTION_VALUES = {
        "travel": {"freedom", "courage"},
        "contact_person": {"loyalty", "friendship"},
        "help_person": {"loyalty", "responsibility", "friendship"},
        "pursue_goal": {"responsibility"},
    }

    def __init__(self, utility_gap_limit: float = 0.30, seed: int = 0) -> None:
        self.utility_gap_limit = utility_gap_limit
        self.decision_kernel = DecisionKernel(seed=seed)

    def _values_for_action(self, character, action: ActionCandidate) -> set[str]:
        normalized = {value.lower() for value in character.values}
        afforded = self.ACTION_VALUES.get(action.action_type, set())
        matched = normalized.intersection(afforded)
        if matched:
            return matched

        text = f"{action.action_type} {action.motivation}".lower()
        return {value for value in normalized if value in text}

    def detect(
        self,
        state: WorldState,
        action_pools: dict[str, list[ActionCandidate]] | None = None,
    ) -> list[NarrativeDilemma]:
        dilemmas: list[NarrativeDilemma] = []

        for character in state.characters.values():
            if character.status != "active":
                continue

            pool = (
                action_pools.get(character.id, [])
                if action_pools is not None
                else generate_action_pool(state, character.id)
            )
            if len(pool) < 2:
                continue

            evaluations = {
                evaluation.action_id: evaluation
                for evaluation in (
                    self.decision_kernel.evaluate(state, action) for action in pool
                )
            }

            for left, right in combinations(pool, 2):
                left_values = self._values_for_action(character, left)
                right_values = self._values_for_action(character, right)
                if not left_values or not right_values or left_values == right_values:
                    continue

                competing = sorted(left_values | right_values)
                left_score = evaluations[left.id].utility
                right_score = evaluations[right.id].utility
                gap = abs(left_score - right_score)
                if gap > self.utility_gap_limit:
                    continue

                closeness = 1.0 - min(1.0, gap / max(0.01, self.utility_gap_limit))
                value_conflict = min(1.0, len(set(left_values) | set(right_values)) / 2.0)
                strength = min(1.0, 0.70 * closeness + 0.30 * value_conflict)

                dilemmas.append(
                    NarrativeDilemma(
                        id=f"dilemma-{character.id}-{left.id}-{right.id}",
                        character_id=character.id,
                        action_ids=[left.id, right.id],
                        competing_values=competing,
                        strength=strength,
                        utility_gap=gap,
                        description=(
                            f"{character.name} faces viable choices aligned with "
                            f"competing values: {', '.join(competing)}."
                        ),
                    )
                )

        dilemmas.sort(key=lambda item: (-item.strength, item.id))
        return dilemmas
