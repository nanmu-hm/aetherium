""""Character decision kernel: evaluate choices from internal state without knowing the future."""

from __future__ import annotations

from dataclasses import dataclass
import random
import zlib

from .models import ActionCandidate, CharacterState, WorldState
from .action_types import canonical_action_type, event_action_type, goal_matches_action
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
    identity: float = 0.15


@dataclass(frozen=True)
class DecisionEvaluation:
    action_id: str
    utility: float
    reasons: tuple[str, ...] = ()
    uncertainty: float = 0.0
    selection_score: float | None = None


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
        pressure_by_action = {
            "travel": max(
                character.human_condition.desires.get("freedom", 0.0),
                character.human_condition.desires.get("curiosity", 0.0),
            ),
            "contact_person": max(
                character.human_condition.desires.get("reconciliation", 0.0),
                character.human_condition.desires.get("belonging", 0.0),
            ),
            "help_person": character.human_condition.desires.get("responsibility", 0.0),
        }

        matches = 0.0
        for value in character.values:
            normalized = value.lower()
            if normalized in text:
                matches += 1.0
            elif action.action_type in affordances.get(normalized, set()):
                matches += 1.0

        alignment = min(1.0, matches / len(character.values))
        pressure = max(0.0, min(100.0, pressure_by_action.get(action.action_type, 100.0))) / 100.0
        return alignment * pressure

    @staticmethod
    def _relationship_alignment(state: WorldState, character: CharacterState, action: ActionCandidate) -> float:
        if not action.targets:
            return 0.0
        scores: list[float] = []
        for target_id in action.targets:
            rel = state.get_relationship(character.id, target_id)
            if rel is not None:
                scores.append(
                    (
                        rel.trust
                        + rel.loyalty
                        + rel.affection
                        + rel.respect
                        - rel.resentment
                        - rel.fear
                    ) / 500.0
                )
        return sum(scores) / len(scores) if scores else 0.0

    @staticmethod
    def _repetition_penalty(state: WorldState, character: CharacterState, action: ActionCandidate) -> float:
        known_event_ids = {
            memory.event_id
            for memory in state.memory_state.memories.values()
            if memory.owner_id == character.id
        }
        recent = [
            event
            for event in reversed(state.event_log)
            if event.id in known_event_ids
            and event.participants
            and event.participants[0] == character.id
        ][:3]
        if not recent:
            return 0.0

        repeated = sum(
            1
            for event in recent
            if event_action_type(event) == canonical_action_type(action.action_type)
        )
        return min(1.0, repeated / 3.0)

    @staticmethod
    def _belief_friction(state: WorldState, character: CharacterState, action: ActionCandidate) -> float:
        target_text = ",".join(action.targets)
        penalties: list[float] = []
        for belief in state.memory_state.beliefs.values():
            if belief.owner_id != character.id:
                continue
            proposition = belief.proposition
            if not proposition.startswith("experience:"):
                continue
            parts = proposition.split(":", 3)
            if len(parts) != 4:
                continue
            _, action_type, belief_targets, outcome = parts
            if canonical_action_type(action_type) != canonical_action_type(action.action_type):
                continue
            if belief_targets != target_text:
                continue
            if outcome == "failure":
                penalties.append(belief.confidence)
            elif outcome == "success":
                penalties.append(-0.5 * belief.confidence)

        if not penalties:
            return 0.0
        return max(-0.5, min(1.0, sum(penalties) / min(3, len(penalties))))

    @staticmethod
    def _habit_alignment(character: CharacterState, action: ActionCandidate) -> float:
        action_type = canonical_action_type(action.action_type)
        return max(-1.0, min(1.0, character.habits.get(action_type, 0.0)))

    @staticmethod
    def _identity_alignment(character: CharacterState, action: ActionCandidate) -> float:
        """Measure compatibility with the character's current self-concept."""
        action_type = canonical_action_type(action.action_type)
        affordances = {
            "travel": ("independent", "capable"),
            "contact_person": ("loyal", "reliable"),
            "help_person": ("compassionate", "reliable"),
        }
        dimensions = affordances.get(action_type, ())
        if not dimensions:
            return 0.0
        values = [
            max(-1.0, min(1.0, character.identity_beliefs.get(name, 0.0)))
            for name in dimensions
        ]
        return sum(values) / len(values)

    @staticmethod
    def _emotion_alignment(character: CharacterState, action: ActionCandidate) -> float:
        """Translate current emotions into action-specific pressure."""
        emotions = character.emotions
        action_type = canonical_action_type(action.action_type)
        mappings = {
            "travel": {
                "hope": 1.0,
                "longing": 0.5,
                "fear": -1.0,
                "regret": 0.25,
            },
            "contact_person": {
                "love": 1.0,
                "longing": 1.0,
                "hope": 0.5,
                "fear": -0.5,
                "resentment": -0.8,
            },
            "help_person": {
                "love": 0.7,
                "hope": 0.5,
                "joy": 0.2,
                "fear": -0.4,
                "resentment": -0.5,
                "regret": 0.3,
            },
        }
        weights = mappings.get(action_type, {})
        if not weights:
            return 0.0

        total_weight = sum(abs(value) for value in weights.values())
        if total_weight == 0:
            return 0.0
        pressure = sum(
            max(-100.0, min(100.0, emotions.get(name, 0.0))) * weight
            for name, weight in weights.items()
        )
        return max(-1.0, min(1.0, pressure / (100.0 * total_weight) * 2.0))

    @staticmethod
    def _goal_alignment(state: WorldState, character: CharacterState, action: ActionCandidate) -> float:
        goal = max((g for g in character.goals if g.status == "active"), key=lambda g: g.priority, default=None)
        if goal is None:
            return 0.0
        if action.action_type == "pursue_goal":
            return goal.priority

        if goal_matches_action(goal.description, action.action_type):
            alignment = goal.priority
        else:
            alignment = 0.0

        if goal.stage_conditions and goal.current_stage < len(goal.stage_conditions):
            condition = goal.stage_conditions[goal.current_stage]
            if condition.get("type") == "location_not_and_action":
                pressure = max(
                    character.human_condition.desires.get("freedom", 0.0),
                    character.human_condition.desires.get("curiosity", 0.0),
                ) / 100.0
                alignment *= max(0.0, min(1.0, pressure))

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

    @staticmethod
    def _human_condition_urgency(character: CharacterState, action: ActionCandidate) -> float:
        """Translate intrinsic human-condition pressure into action-specific urgency.

        Human-condition desires live on a character because they are continuous
        pressures, not just scheduled goals. They therefore influence both action
        generation and the final decision instead of acting as mere availability flags.
        """
        desires = character.human_condition.desires
        if canonical_action_type(action.action_type) == "rest":
            return max(0.0, min(100.0, character.human_condition.fatigue)) / 100.0

        if canonical_action_type(action.action_type) == "travel" and action.metadata.get("search_target"):
            return max(
                character.human_condition.desires.get("reconciliation", 0.0),
                character.human_condition.desires.get("belonging", 0.0),
            ) / 100.0

        mapping = {
            "travel": ("freedom", "curiosity"),
            "contact_person": ("reconciliation", "belonging"),
            "help_person": ("responsibility",),
        }
        relevant = mapping.get(canonical_action_type(action.action_type), ())
        if not relevant:
            return 0.0
        return max((max(0.0, min(100.0, desires.get(name, 0.0))) / 100.0 for name in relevant), default=0.0)

    def evaluate(self, state: WorldState, action: ActionCandidate) -> DecisionEvaluation:
        character = state.characters[action.actor_id]
        goal = self._goal_alignment(state, character, action)
        values = self._value_alignment(character, action)
        emotion = self._emotion_alignment(character, action)
        relationship = self._relationship_alignment(state, character, action)
        memory_urgency = max((d.urgency * d.priority for d in state.memory_state.desires.values()
                              if d.owner_id == character.id and d.status == "active"), default=0.0)
        human_condition_urgency = self._human_condition_urgency(character, action)
        urgency = max(memory_urgency, human_condition_urgency)
        risk = min(1.0, len(action.risks) / 3.0)
        risk_tolerance = max(0.0, min(1.0, character.risk_tolerance))
        perceived_risk = risk * (1.0 - 0.75 * risk_tolerance)
        cost = min(1.0, sum(1.0 for _ in action.risks) * 0.25)
        uncertainty = max(0.0, min(1.0, 1.0 - action.confidence))
        repetition = self._repetition_penalty(state, character, action)
        belief_friction = self._belief_friction(state, character, action)
        habit = self._habit_alignment(character, action)
        identity = self._identity_alignment(character, action)
        fatigue = max(0.0, min(100.0, character.human_condition.fatigue)) / 100.0
        fatigue_cost = {
            "travel": 0.45,
            "help_person": 0.20,
            "contact_person": 0.10,
        }.get(canonical_action_type(action.action_type), 0.0)
        fatigue_bonus = 0.10 if canonical_action_type(action.action_type) == "rest" else 0.0

        score = (
            self.weights.goal * goal
            + self.weights.values * values
            + self.weights.emotion * emotion
            + self.weights.relationship * relationship
            + self.weights.urgency * urgency
            - self.weights.risk * perceived_risk
            - self.weights.cost * cost
            - self.weights.uncertainty * uncertainty
            + self.weights.habit * habit
            - self.weights.habit * repetition
            + self.weights.identity * identity
            - fatigue_cost * fatigue
            + fatigue_bonus * fatigue
            - self.weights.uncertainty * max(0.0, belief_friction)
            + self.weights.uncertainty * min(0.0, belief_friction)
        )
        reasons = []
        if goal > 0: reasons.append("goal alignment")
        if values > 0: reasons.append("value alignment")
        if emotion > 0: reasons.append("emotional pull")
        if emotion < 0: reasons.append("emotional resistance")
        if relationship > 0: reasons.append("relationship pull")
        if urgency > 0: reasons.append("time pressure")
        if perceived_risk > 0: reasons.append("perceived risk")
        if habit > 0: reasons.append("learned preference")
        if habit < 0: reasons.append("learned avoidance")
        if identity > 0: reasons.append("self-concept alignment")
        if identity < 0: reasons.append("self-concept resistance")
        if repetition > 0: reasons.append("recently repeated action")
        if belief_friction > 0: reasons.append("past failure remembered")
        if belief_friction < 0: reasons.append("past success remembered")
        return DecisionEvaluation(action.id, score, tuple(reasons), uncertainty)

    def _choice_noise(self, state: WorldState, character: CharacterState, action: ActionCandidate) -> float:
        """Return reproducible bounded perturbation; restored state overrides constructor seed."""
        noise_level = max(0.0, min(1.0, character.decision_noise))
        if noise_level <= 0.0:
            return 0.0
        stable_seed = (
            (state.simulation_seed if state.simulation_seed is not None else self.seed)
            + state.tick * 1009
            + zlib.crc32(f"{character.id}:{action.id}".encode("utf-8"))
        )
        rng = random.Random(stable_seed)
        return (rng.random() * 2.0 - 1.0) * noise_level

    def choose(self, state: WorldState, pool: list[ActionCandidate]) -> tuple[ActionCandidate | None, list[DecisionEvaluation]]:
        evaluations = [self.evaluate(state, action) for action in pool]
        if not evaluations:
            return None, []

        selected: list[DecisionEvaluation] = []
        for evaluation in evaluations:
            action = next(item for item in pool if item.id == evaluation.action_id)
            character = state.characters[action.actor_id]
            noise = self._choice_noise(state, character, action)
            selected.append(
                DecisionEvaluation(
                    action_id=evaluation.action_id,
                    utility=evaluation.utility,
                    reasons=evaluation.reasons,
                    uncertainty=evaluation.uncertainty,
                    selection_score=evaluation.utility + max(-1.0, min(1.0, action.score)) + noise,
                )
            )

        # Stable tie-breaking keeps simulations reproducible; no narrative knowledge is used.
        best = max(
            selected,
            key=lambda item: (
                item.selection_score if item.selection_score is not None else item.utility,
                -item.uncertainty,
                item.action_id,
            ),
        )
        return next(action for action in pool if action.id == best.action_id), selected
