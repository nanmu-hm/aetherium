"""Character decision kernel: evaluate choices from internal state without knowing the future."""

from __future__ import annotations

from dataclasses import dataclass

from .models import ActionCandidate, CharacterState, WorldState
from ..memory.kernel import MemoryKernel


@dataclass(frozen=True)
class DecisionWeights:
    goal: float = 1.0
    values: float = 0.45
    emotion: float = 0.25
    relationship: float = 0.30
    urgency: float = 0.35
    risk: float = 0.45
    cost: float = 0.35
    uncertainty: float = 0.20
    habit: float = 0.35


@dataclass(frozen=True)
class DecisionEvaluation:
    action_id: str
    utility: float
    reasons: tuple[str, ...] = ()
    uncertainty: float = 0.0


class DecisionKernel:
    """Bounded, deterministic decision-making for fictional characters.

    The kernel only sees the character's current model of the world. It does not
    inspect future events or narrative signals, so story outcomes cannot leak
    backward into character choice.
    """

    def __init__(self, seed: int = 0, weights: DecisionWeights | None = None) -> None:
        self.seed = seed
        self.weights = weights or DecisionWeights()

    @staticmethod
    def _value_alignment(character: CharacterState, action: ActionCandidate) -> float:
        text = f"{action.action_type} {action.motivation}".lower()
        if not character.values:
            return 0.0

        # Values affect choices through semantic affordances rather than
        # requiring the exact value word to appear in an action description.
        affordances = {
            "freedom": {"travel"},
            "loyalty": {"help_person", "contact_person"},
            "responsibility": {"help_person", "pursue_goal"},
            "friendship": {"contact_person", "help_person"},
            "courage": {"travel", "help_person"},
        }

        matches = 0.0
        for value in character.values:
            normalized = value.lower()
            if normalized in text:
                matches += 1.0
            elif action.action_type in affordances.get(normalized, set()):
                matches += 1.0

        return min(1.0, matches / len(character.values))

    @staticmethod
    def _relationship_alignment(state: WorldState, character: CharacterState, action: ActionCandidate) -> float:
        if not action.targets:
            return 0.0
        scores: list[float] = []
        for target_id in action.targets:
            rel = state.get_relationship(character.id, target_id)
            if rel is not None:
                scores.append((rel.loyalty + rel.affection + rel.respect - rel.resentment - rel.fear) / 300.0)
        return sum(scores) / len(scores) if scores else 0.0

    @staticmethod
    def _repetition_penalty(state: WorldState, character: CharacterState, action: ActionCandidate) -> float:
        recent = [
            event
            for event in reversed(state.event_log)
            if event.participants and event.participants[0] == character.id
        ][:3]
        if not recent:
            return 0.0

        repeated = sum(
            1
            for event in recent
            if event.causes and action.action_type in event.causes[0]
        )
        return min(1.0, repeated / 3.0)

    @staticmethod
    def _goal_alignment(state: WorldState, character: CharacterState, action: ActionCandidate) -> float:
        goal = max((g for g in character.goals if g.status == "active"), key=lambda g: g.priority, default=None)
        if goal is None:
            return 0.0
        if action.action_type == "pursue_goal":
            return goal.priority

        alignment = min(1.0, goal.priority * action.confidence)

        # Relationship-seeking actions become more compelling when the
        # relationship itself carries unresolved tension. This keeps the
        # decision grounded in the character's present situation rather than
        # letting a generic "help" action dominate every tick.
        if action.action_type == "contact_person" and action.targets:
            relationship = state.get_relationship(character.id, action.targets[0])
            if relationship is not None:
                tension = max(
                    relationship.resentment,
                    relationship.fear,
                    100.0 - relationship.trust,
                ) / 100.0
                alignment = min(1.0, alignment + 0.5 * tension)

        return alignment

    def evaluate(self, state: WorldState, action: ActionCandidate) -> DecisionEvaluation:
        character = state.characters[action.actor_id]
        goal = self._goal_alignment(state, character, action)
        values = self._value_alignment(character, action)
        relationship = self._relationship_alignment(state, character, action)
        urgency = max((d.urgency * d.priority for d in state.memory_state.desires.values()
                       if d.owner_id == character.id and d.status == "active"), default=0.0)
        risk = min(1.0, len(action.risks) / 3.0)
        cost = min(1.0, sum(1.0 for _ in action.risks) * 0.25)
        uncertainty = max(0.0, min(1.0, 1.0 - action.confidence))
        repetition = self._repetition_penalty(state, character, action)
        score = (
            self.weights.goal * goal
            + self.weights.values * values
            + self.weights.emotion * sum(character.emotions.values()) / max(1, len(character.emotions))
            + self.weights.relationship * relationship
            + self.weights.urgency * urgency
            - self.weights.risk * risk
            - self.weights.cost * cost
            - self.weights.uncertainty * uncertainty
            - self.weights.habit * repetition
        )
        reasons = []
        if goal > 0: reasons.append("goal alignment")
        if values > 0: reasons.append("value alignment")
        if relationship > 0: reasons.append("relationship pull")
        if urgency > 0: reasons.append("time pressure")
        if risk > 0: reasons.append("perceived risk")
        if repetition > 0: reasons.append("recently repeated action")
        return DecisionEvaluation(action.id, score, tuple(reasons), uncertainty)

    def choose(self, state: WorldState, pool: list[ActionCandidate]) -> tuple[ActionCandidate | None, list[DecisionEvaluation]]:
        evaluations = [self.evaluate(state, action) for action in pool]
        if not evaluations:
            return None, []
        # Stable tie-breaking keeps simulations reproducible; no narrative knowledge is used.
        best = max(evaluations, key=lambda item: (item.utility, -item.uncertainty, item.action_id))
        return next(action for action in pool if action.id == best.action_id), evaluations
