"""Deterministic character-driven simulation loop with memory integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import random

from .actions import generate_action_pool
from .action_types import canonical_action_type, event_action_type
from .decision import DecisionKernel
from .models import ActionCandidate, ActionResult, Consequence, Event, WorldState
from .preconditions import PreconditionEngine
from ..memory.kernel import MemoryKernel


@dataclass
class SimulationResult:
    tick: int
    actions: list[ActionCandidate]
    events: list[Event]
    validation_errors: list[str]


class SimulationEngine:
    def __init__(
        self,
        seed: int = 0,
        memory_kernel: MemoryKernel | None = None,
        tick_duration_hours: int = 24,
    ) -> None:
        if tick_duration_hours <= 0:
            raise ValueError("tick_duration_hours must be positive")
        self.random = random.Random(seed)
        self.tick_duration = timedelta(hours=tick_duration_hours)
        self.memory_kernel = memory_kernel or MemoryKernel()
        self.decision_kernel = DecisionKernel(seed=seed)
        self.action_resolver = ActionResolver(self.random)
        self.precondition_engine = PreconditionEngine()

    def _restore_rng_state(self, state: WorldState) -> None:
        if state.simulation_seed is None:
            state.simulation_seed = self.decision_kernel.seed
        else:
            # Checkpoint state is authoritative even if the new engine uses another seed.
            self.decision_kernel.seed = state.simulation_seed
        if state.rng_state is not None:
            self.random.setstate(state.rng_state)

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
                state.memory_state,
                character_id,
                event,
                summary,
                emotional_salience=0.55 if len(event.participants) > 1 else 0.35,
                personal_importance=0.5,
                relationship_importance=0.5 if len(event.participants) > 1 else 0.0,
                unresolved=bool(event.causes),
            )
            character.memory_ids.append(memory.id)
            character.memory.append(summary)
            self.memory_kernel.record_event_belief(
                state.memory_state,
                character_id,
                event,
                memory.id,
            )
            learned = self.memory_kernel.record_event_knowledge(
                state.memory_state,
                character_id,
                event,
            )
            # A participant remembers where the other participants were seen.
            # This is actor-local knowledge, not a read of their current state.
            for other_id in event.participants:
                if other_id == character_id or other_id not in state.characters:
                    continue
                learned.append(
                    self.memory_kernel.learn_fact(
                        state.memory_state,
                        character_id,
                        f"location_seen:{other_id}:{event.location}",
                        tick=event.tick,
                        source="direct_experience",
                        source_event_id=event.id,
                        confidence=1.0,
                    )
                )
            character.knowledge.update(item.proposition for item in learned)
        self.memory_kernel.record_relationship_history(state.memory_state, event)

    @staticmethod
    def _goal_condition_met(state: WorldState, actor, goal, action: ActionCandidate, outcome: ActionResult) -> bool:
        """Evaluate goal progress from observed world state and concrete outcomes."""
        if outcome.status != "success":
            return False
        if not goal.stage_conditions or goal.current_stage >= len(goal.stage_conditions):
            return False

        condition = goal.stage_conditions[goal.current_stage]
        kind = condition.get("type")

        if kind == "not_at_location":
            return actor.location != condition.get("location")

        if kind == "at_same_location":
            target_id = condition.get("target_id")
            target = state.characters.get(target_id)
            return target is not None and actor.location == target.location

        if kind == "desire_at_most":
            desire = str(condition.get("desire", ""))
            limit = float(condition.get("value", 0.0))
            return actor.human_condition.effective_desire(desire, actor.location) <= limit

        if kind == "successful_action":
            expected = canonical_action_type(str(condition.get("action_type", "")))
            return canonical_action_type(action.action_type) == expected

        return False

    def _apply_goal_progress(
        self,
        state: WorldState,
        actor,
        action: ActionCandidate,
        outcome: ActionResult,
        consequences: list[Consequence],
    ) -> str | None:
        goal = max(
            (item for item in actor.goals if item.status == "active"),
            key=lambda item: item.priority,
            default=None,
        )
        if goal is None or not self._goal_condition_met(state, actor, goal, action, outcome):
            return None

        old_stage = goal.current_stage
        goal.current_stage += 1
        consequences.append(
            Consequence(
                "goal",
                goal.id,
                "current_stage",
                old_stage,
                goal.current_stage,
                "goal stage condition became true",
            )
        )

        if goal.current_stage < len(goal.stages):
            return (
                f"{actor.name} advances the goal '{goal.description}' "
                f"to stage {goal.current_stage + 1}/{len(goal.stages)}: "
                f"{goal.current_description}."
            )

        old_status = goal.status
        goal.status = "achieved"
        consequences.append(
            Consequence(
                "goal",
                goal.id,
                "status",
                old_status,
                goal.status,
                "goal completion condition became true",
            )
        )
        return f"{actor.name} achieves the goal: {goal.description}."

    @staticmethod
    def _apply_emotional_consequences(
        state: WorldState,
        actor,
        action: ActionCandidate,
        outcome: ActionResult,
        consequences: list[Consequence],
    ) -> None:
        """Update experienced characters' current emotions from the outcome."""
        if outcome.status not in {"success", "failure"}:
            return

        action_type = canonical_action_type(action.action_type)
        effects = {
            "travel": (
                {"joy": 3.0, "hope": 3.0, "fear": -2.0} if outcome.status == "success"
                else {"fear": 5.0, "regret": 2.0, "hope": -2.0}
            ),
            "contact_person": (
                {"joy": 3.0, "love": 2.0, "longing": -3.0, "resentment": -2.0}
                if outcome.status == "success"
                else {"sorrow": 3.0, "anger": 2.0, "resentment": 3.0, "hope": -2.0}
            ),
            "help_person": (
                {"joy": 3.0, "love": 1.0, "hope": 2.0}
                if outcome.status == "success"
                else {"sorrow": 3.0, "regret": 2.0, "hope": -1.0}
            ),
        }.get(action_type, {})

        def apply(character, changes: dict[str, float], reason: str) -> None:
            for emotion_name, delta in changes.items():
                old_value = character.emotions.get(emotion_name, 0.0)
                new_value = max(0.0, min(100.0, old_value + delta))
                if new_value == old_value:
                    continue
                character.emotions[emotion_name] = new_value
                consequences.append(
                    Consequence(
                        "character",
                        character.id,
                        f"emotions.{emotion_name}",
                        old_value,
                        new_value,
                        reason,
                    )
                )

        apply(actor, effects, f"emotional response to {outcome.status}")

        if not action.targets:
            return
        target = state.characters.get(action.targets[0])
        if target is None:
            return

        if action_type == "contact_person":
            target_effects = (
                {"joy": 2.0, "hope": 1.0}
                if outcome.status == "success"
                else {"sorrow": 2.0, "resentment": 2.0}
            )
            apply(target, target_effects, f"emotional response to contact {outcome.status}")
        elif action_type == "help_person":
            target_effects = (
                {"joy": 4.0, "hope": 2.0}
                if outcome.status == "success"
                else {"sorrow": 4.0, "resentment": 2.0}
            )
            apply(target, target_effects, f"emotional response to help {outcome.status}")

    @staticmethod
    def _update_identity_beliefs(
        actor,
        action: ActionCandidate,
        outcome: ActionResult,
        consequences: list[Consequence],
    ) -> None:
        """Update self-concept gradually from lived success or failure."""
        if outcome.status not in {"success", "failure"}:
            return

        affordances = {
            "travel": ("independent", "capable"),
            "contact_person": ("loyal", "reliable"),
            "help_person": ("compassionate", "reliable"),
        }
        action_type = canonical_action_type(action.action_type)
        dimensions = affordances.get(action_type, ())
        if not dimensions:
            return

        direction = 1.0 if outcome.status == "success" else -1.0
        learning_rate = 0.08
        for dimension in dimensions:
            old_value = actor.identity_beliefs.get(dimension, 0.0)
            target = 1.0 if direction > 0 else -1.0
            new_value = old_value + learning_rate * (target - old_value)
            new_value = max(-1.0, min(1.0, new_value))
            actor.identity_beliefs[dimension] = new_value
            consequences.append(
                Consequence(
                    "character",
                    actor.id,
                    f"identity_beliefs.{dimension}",
                    old_value,
                    new_value,
                    f"self-concept updated by {outcome.status} {action_type}",
                )
            )

    @staticmethod
    def _update_procedural_habit(
        actor,
        action: ActionCandidate,
        outcome: ActionResult,
        consequences: list[Consequence],
    ) -> None:
        """Learn a small action preference from an experienced outcome."""
        if outcome.status not in {"success", "failure"}:
            return

        action_type = canonical_action_type(action.action_type)
        old_value = actor.habits.get(action_type, 0.0)
        if outcome.status == "success":
            new_value = old_value + 0.10 * (1.0 - old_value)
        else:
            new_value = old_value - 0.10 * (old_value + 1.0)

        new_value = max(-1.0, min(1.0, new_value))
        actor.habits[action_type] = new_value
        consequences.append(
            Consequence(
                "character",
                actor.id,
                f"habits.{action_type}",
                old_value,
                new_value,
                f"procedural learning from {outcome.status}",
            )
        )

    def _apply_failure_consequences(
        self,
        state: WorldState,
        actor,
        action: ActionCandidate,
        outcome: ActionResult,
        consequences: list[Consequence],
    ) -> None:
        """Turn a failed attempt into persistent state pressure when the model supports it."""
        if outcome.status != "failure":
            return

        pressure_map = {
            "travel": (("freedom", 8.0),),
            "contact_person": (("reconciliation", 8.0), ("belonging", 4.0)),
            "help_person": (("responsibility", 8.0),),
        }
        for desire_name, amount in pressure_map.get(canonical_action_type(action.action_type), ()):
            if desire_name not in actor.human_condition.desires:
                continue
            old_value = actor.human_condition.desires[desire_name]
            new_value = min(100.0, old_value + amount)
            actor.human_condition.desires[desire_name] = new_value
            consequences.append(
                Consequence(
                    "character",
                    actor.id,
                    f"human_condition.desires.{desire_name}",
                    old_value,
                    new_value,
                    "failed attempt increases unresolved pressure",
                )
            )

        if not action.targets:
            return
        target = state.characters.get(action.targets[0])
        if target is None:
            return

        relationship = state.get_relationship(actor.id, target.id)
        reciprocal = state.get_relationship(target.id, actor.id)
        if canonical_action_type(action.action_type) == "contact_person" and relationship is not None:
            old_trust = relationship.trust
            old_resentment = relationship.resentment
            relationship.trust = max(0.0, relationship.trust - 1.0)
            relationship.resentment = min(100.0, relationship.resentment + 1.0)
            consequences.extend(
                [
                    Consequence(
                        "relationship",
                        f"{actor.id}:{target.id}",
                        "trust",
                        old_trust,
                        relationship.trust,
                        "failed contact creates relational friction",
                    ),
                    Consequence(
                        "relationship",
                        f"{actor.id}:{target.id}",
                        "resentment",
                        old_resentment,
                        relationship.resentment,
                        "failed contact creates unresolved friction",
                    ),
                ]
            )
        elif canonical_action_type(action.action_type) == "help_person" and reciprocal is not None:
            old_trust = reciprocal.trust
            old_loyalty = reciprocal.loyalty
            reciprocal.trust = max(0.0, reciprocal.trust - 2.0)
            reciprocal.loyalty = max(0.0, reciprocal.loyalty - 1.0)
            consequences.extend(
                [
                    Consequence(
                        "relationship",
                        f"{target.id}:{actor.id}",
                        "trust",
                        old_trust,
                        reciprocal.trust,
                        "failed help weakens confidence",
                    ),
                    Consequence(
                        "relationship",
                        f"{target.id}:{actor.id}",
                        "loyalty",
                        old_loyalty,
                        reciprocal.loyalty,
                        "failed help disappoints the recipient",
                    ),
                ]
            )

    def resolve(self, state: WorldState, actions: list[ActionCandidate]) -> list[Event]:
        events: list[Event] = []
        for action in actions:
            actor = state.characters[action.actor_id]
            consequences: list[Consequence] = []
            facts: list[str] = []
            participants = [actor.id, *action.targets]

            precondition = self.precondition_engine.check(state, action)
            if not precondition.satisfied:
                outcome = ActionResult("blocked", "; ".join(precondition.reasons))
                facts.append(
                    f"{actor.name} cannot attempt {action.action_type}: {outcome.reason}."
                )
            else:
                outcome = self.action_resolver.resolve_outcome(state, action)

                if action.action_type == "travel":
                    destination = action.targets[0]
                    if outcome.status == "success":
                        old = actor.location
                        actor.location = destination
                        consequences.append(
                            Consequence(
                                "character", actor.id, "location", old, destination, "travel"
                            )
                        )
                        facts.append(f"{actor.name} travels from {old} to {destination}.")

                        search_target_id = action.metadata.get("search_target")
                        if search_target_id and search_target_id in state.characters:
                            target = state.characters[search_target_id]
                            if target.location == destination:
                                participants.append(search_target_id)
                                self.memory_kernel.learn_fact(
                                    state.memory_state,
                                    actor.id,
                                    f"location_seen:{search_target_id}:{destination}",
                                    tick=state.tick,
                                    source="direct_experience",
                                    confidence=1.0,
                                )
                                facts.append(
                                    f"{actor.name} finds {target.name} at {destination}."
                                )
                            else:
                                absent_fact = self.memory_kernel.learn_fact(
                                    state.memory_state,
                                    actor.id,
                                    f"location_absent:{search_target_id}:{destination}",
                                    tick=state.tick,
                                    source="direct_experience",
                                    confidence=1.0,
                                )
                                actor.knowledge.add(absent_fact.proposition)
                                facts.append(
                                    f"{actor.name} searches for {target.name} at {destination}, "
                                    f"but {target.name} is not there."
                                )
                    else:
                        facts.append(
                            f"{actor.name} attempts to travel to {destination}, but fails."
                        )

                elif action.action_type == "contact_person":
                    target = state.characters[action.targets[0]]
                    relationship = state.get_relationship(actor.id, target.id)
                    if outcome.status == "success" and relationship is not None:
                        old_trust = relationship.trust
                        old_affection = relationship.affection
                        relationship.trust = min(100.0, relationship.trust + 2.0)
                        relationship.affection = min(100.0, relationship.affection + 1.0)
                        facts.append(
                            f"{actor.name} speaks with {target.name} at {actor.location}."
                        )
                        consequences.append(
                            Consequence(
                                "relationship",
                                f"{actor.id}:{target.id}",
                                "trust",
                                old_trust,
                                relationship.trust,
                                "successful contact",
                            )
                        )
                        consequences.append(
                            Consequence(
                                "relationship",
                                f"{actor.id}:{target.id}",
                                "affection",
                                old_affection,
                                relationship.affection,
                                "successful contact",
                            )
                        )
                    else:
                        facts.append(
                            f"{actor.name} speaks with {target.name}, "
                            "but the interaction does not go as intended."
                        )

                elif action.action_type == "help_person":
                    target = state.characters[action.targets[0]]
                    if outcome.status == "success":
                        facts.append(f"{actor.name} successfully helps {target.name}.")
                        reciprocal = state.get_relationship(target.id, actor.id)
                        if reciprocal is not None:
                            old_trust = reciprocal.trust
                            old_affection = reciprocal.affection
                            old_loyalty = reciprocal.loyalty
                            reciprocal.trust = min(100.0, reciprocal.trust + 5.0)
                            reciprocal.affection = min(100.0, reciprocal.affection + 2.0)
                            reciprocal.loyalty = min(100.0, reciprocal.loyalty + 3.0)
                            relationship_id = f"{target.id}:{actor.id}"
                            consequences.extend(
                                [
                                    Consequence(
                                        "relationship",
                                        relationship_id,
                                        "trust",
                                        old_trust,
                                        reciprocal.trust,
                                        "successful help received",
                                    ),
                                    Consequence(
                                        "relationship",
                                        relationship_id,
                                        "affection",
                                        old_affection,
                                        reciprocal.affection,
                                        "successful help received",
                                    ),
                                    Consequence(
                                        "relationship",
                                        relationship_id,
                                        "loyalty",
                                        old_loyalty,
                                        reciprocal.loyalty,
                                        "successful help received",
                                    ),
                                ]
                            )
                    else:
                        facts.append(f"{actor.name} tries to help {target.name}, but fails.")

                elif action.action_type == "rest":
                    if outcome.status == "success":
                        facts.append(f"{actor.name} rests at {actor.location}.")
                    else:
                        facts.append(f"{actor.name} tries to rest at {actor.location}, but fails.")
                else:
                    facts.append(
                        f"{actor.name} attempts to {action.motivation} and {outcome.status}."
                    )

            self._apply_emotional_consequences(state, actor, action, outcome, consequences)
            self._update_procedural_habit(actor, action, outcome, consequences)
            self._update_identity_beliefs(actor, action, outcome, consequences)
            self._apply_failure_consequences(state, actor, action, outcome, consequences)

            goal_fact = self._apply_goal_progress(state, actor, action, outcome, consequences)
            if goal_fact:
                facts.append(goal_fact)

            events.append(
                Event(
                    id=f"event-{state.tick}-{actor.id}-{action.action_type}",
                    tick=state.tick,
                    timestamp=state.timestamp,
                    location=actor.location,
                    participants=participants,
                    causes=[action.id],
                    facts=facts,
                    action_type=canonical_action_type(action.action_type),
                    action_result=outcome,
                    consequences=consequences,
                )
            )

        for event in events:
            state.event_log.append(event)
            self._record_memories(state, event)
        return events

    def validate(self, state: WorldState) -> list[str]:
        errors: list[str] = []
        for character in state.characters.values():
            if character.location and character.location not in state.locations:
                errors.append(
                    f"{character.id} is at unknown location {character.location!r}"
                )
        return errors

    @staticmethod
    def _advance_human_pressures(state: WorldState, events: list[Event]) -> None:
        acted = {
            event.participants[0]
            for event in events
            if event.participants
        }

        # Desires are pressures, not permanent flags. Successful satisfaction
        # lowers a pressure; time without satisfaction lets it recover slowly.
        for character in state.characters.values():
            desires = character.human_condition.desires
            if not desires:
                continue

            for desire_name, value in list(desires.items()):
                modifiers = character.human_condition.location_desire_modifiers
                if desire_name in modifiers.get(character.location, {}):
                    delta = modifiers[character.location][desire_name]
                    desires[desire_name] = max(0.0, min(100.0, value + delta))
                elif desire_name != "freedom":
                    desires[desire_name] = min(100.0, value + 3.0)

            for event in events:
                if not event.participants or event.participants[0] not in acted:
                    continue
                actor = event.participants[0]
                if actor != character.id or event.action_result is None:
                    continue
                if event.action_result.status != "success":
                    continue

                action_type = event_action_type(event)
                satisfaction = {
                    "contact_person": {"reconciliation": 20.0, "belonging": 10.0},
                    "help_person": {"responsibility": 20.0},
                }
                for desire_name, amount in satisfaction.get(action_type, {}).items():
                    if desire_name not in desires:
                        continue
                    old_value = desires[desire_name]
                    desires[desire_name] = max(0.0, old_value - amount)

    def _advance_clock(self, state: WorldState) -> None:
        current = datetime.fromisoformat(state.timestamp)
        state.timestamp = (current + self.tick_duration).isoformat()

    def step(self, state: WorldState) -> SimulationResult:
        self._restore_rng_state(state)
        actions = self.generate_candidates(state)
        events = self.resolve(state, actions)
        self.memory_kernel.decay(state.memory_state, state.tick)
        self.memory_kernel.advance_desires(state.memory_state, state.tick)
        self._advance_human_pressures(state, events)
        errors = self.validate(state)
        current_tick = state.tick
        self._advance_clock(state)
        state.tick += 1
        state.rng_state = self.random.getstate()
        state.simulation_seed = self.decision_kernel.seed
        return SimulationResult(current_tick, actions, events, errors)


class ActionResolver:
    """Resolve probabilistic outcomes from current state with a seeded RNG."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def probability(self, state: WorldState, action: ActionCandidate) -> float:
        actor = state.characters[action.actor_id]
        ability = (
            actor.abilities.get(action.required_ability, 0.5)
            if action.required_ability
            else 0.5
        )
        base = 0.5 + 0.35 * (ability - action.difficulty)
        # Confidence should materially affect willingness to take an uncertain
        # action: low confidence must not turn a very difficult action into a
        # near-even roll.
        confidence_factor = 0.25 + 0.75 * action.confidence
        return max(0.05, min(0.95, base * confidence_factor))

    def resolve_outcome(
        self, state: WorldState, action: ActionCandidate
    ) -> ActionResult:
        probability = self.probability(state, action)
        if self.rng.random() <= probability:
            return ActionResult("success", "action succeeded", probability)
        return ActionResult(
            "failure", "action failed despite being attempted", probability
        )
