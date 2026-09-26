"""Action generation for the character-driven simulation."""

from __future__ import annotations

from .models import ActionCandidate, CharacterState, WorldState
from .action_types import event_action_type, goal_matches_action
from .psychology import has_trait


def _has_value(character: CharacterState, value: str) -> bool:
    return value.lower() in {item.lower() for item in character.values}


def _relationship_targets(state: WorldState, character: CharacterState) -> list[str]:
    targets = [rel.target_id for rel in state.relationships.values() if rel.source_id == character.id and rel.target_id in state.characters]
    if targets:
        return targets
    return [target_id for target_id in character.relationships if target_id in state.characters]


def _trust(state: WorldState, character: CharacterState, target_id: str) -> float:
    relationship = state.get_relationship(character.id, target_id)
    if relationship is not None:
        return relationship.trust
    return character.relationships.get(target_id, 50.0)


def _goal_supports_action(character: CharacterState, action_type: str) -> bool:
    goal = max((g for g in character.goals if g.status == "active"), key=lambda item: item.priority, default=None)
    if goal is None:
        return False
    if goal.stage_conditions and goal.current_stage < len(goal.stage_conditions):
        supported = goal.stage_conditions[goal.current_stage].get("action_types")
        if supported is not None:
            return action_type in supported
        return False
    return goal_matches_action(goal.current_description, action_type)


def _contextual_desire(character: CharacterState, desire_name: str) -> float:
    base = max(0.0, min(100.0, character.human_condition.desires.get(desire_name, 0.0)))
    if desire_name == "freedom":
        return base * character.human_condition.confinement_at(character.location)
    return base


def _remembered_location(state: WorldState, character: CharacterState, target_id: str) -> str | None:
    prefix = f"location_seen:{target_id}:"
    facts = [fact for fact in state.memory_state.knowledge.get(character.id, {}).values() if fact.proposition.startswith(prefix)]
    if not facts:
        return None
    latest = max(facts, key=lambda fact: (fact.last_confirmed_tick, fact.confidence, fact.id))
    return latest.proposition[len(prefix):]


def generate_action_pool(state: WorldState, character_id: str) -> list[ActionCandidate]:
    character = state.characters[character_id]
    if character.status != "active":
        return []

    pool: list[ActionCandidate] = []
    goal = max((g for g in character.goals if g.status == "active"), key=lambda item: item.priority, default=None)
    if goal and not goal.stage_conditions:
        pool.append(ActionCandidate(id=f"tick-{state.tick}-{character.id}-pursue", actor_id=character.id, action_type="pursue_goal", motivation=goal.current_description, confidence=0.8, difficulty=0.5, score=0.10))

    nearby = [target_id for target_id in _relationship_targets(state, character) if state.characters[target_id].location == character.location]
    if nearby:
        target_id = min(nearby, key=lambda item: _trust(state, character, item))
        trust = _trust(state, character, target_id)
        recent_contacts: list = []
        for event in reversed(state.event_log):
            if event.participants and event.participants[0] == character.id:
                if event_action_type(event) == "contact_person":
                    recent_contacts.append(event)
                    if len(recent_contacts) >= 3:
                        break
                elif recent_contacts:
                    break
        reconciliation = character.human_condition.desires.get("reconciliation", 0.0)
        belonging = character.human_condition.desires.get("belonging", 0.0)
        relationship = state.get_relationship(character.id, target_id)
        tension = max(0.0, min(100.0, max(100.0 - trust, relationship.resentment if relationship else 0.0, relationship.fear if relationship else 0.0)))
        emotional_pressure = max(character.emotions.get("anger", 0.0), character.emotions.get("longing", 0.0), character.emotions.get("resentment", 0.0), character.emotions.get("love", 0.0))
        reconciliation_motive = reconciliation * (tension / 100.0) ** 2
        relationship_motive = max(reconciliation_motive, belonging * 0.50, emotional_pressure)
        goal_motive = 100.0 * goal.priority if goal and _goal_supports_action(character, "contact_person") else 0.0
        contact_pressure = max(max(0.0, min(100.0, relationship_motive)), goal_motive)
        # A successful contact should satisfy part of the current social pressure.
        # Do not impose a time-based cooldown: the relationship state itself must
        # determine whether another contact is meaningful.
        if contact_pressure >= 20.0:
            pool.append(
                ActionCandidate(
                    id=f"tick-{state.tick}-{character.id}-contact",
                    actor_id=character.id,
                    action_type="contact_person",
                    targets=[target_id],
                    motivation="address an important relationship",
                    preconditions=["target is at the same location"],
                    expected_outcomes=["relationship may change"],
                    confidence=1.0,
                    difficulty=0.0,
                    score=0.15,
                    metadata={"world_validated": True},
                )
            )

    targets = _relationship_targets(state, character)
    distressed = [target_id for target_id in targets if state.characters[target_id].location == character.location and state.characters[target_id].emotions.get("sorrow", 0.0) + state.characters[target_id].emotions.get("fear", 0.0) + state.characters[target_id].human_condition.fatigue / 2.0 > 8.0]
    if distressed and (_has_value(character, "loyalty") or _has_value(character, "responsibility") or has_trait(character, "compassionate", "protective", "helpful") or character.human_condition.desires.get("responsibility", 0.0) > 20.0):
        target_id = max(distressed, key=lambda item: (state.characters[item].emotions.get("sorrow", 0.0) + state.characters[item].emotions.get("fear", 0.0), -_trust(state, character, item)))
        pool.append(ActionCandidate(id=f"tick-{state.tick}-{character.id}-help", actor_id=character.id, action_type="help_person", targets=[target_id], motivation=f"help {state.characters[target_id].name} because their condition looks difficult", preconditions=["target is at the same location"], confidence=1.0, difficulty=0.0, score=0.20, metadata={"world_validated": True}))

    freedom_pressure = _contextual_desire(character, "freedom")
    curiosity_pressure = _contextual_desire(character, "curiosity")
    travel_pressure = max(freedom_pressure, curiosity_pressure)
    adventurous = has_trait(character, "adventurous", "curious", "restless", "explorer")
    cautious = has_trait(character, "cautious", "fearful")
    if len(state.locations) > 1:
        visit_counts = {location: 0 for location in state.locations}
        for memory in state.memory_state.memories.values():
            if memory.owner_id == character.id and memory.location in visit_counts:
                visit_counts[memory.location] += 1
        alternatives = [location for location in state.locations if location != character.location]
        recent_travel_locations: list[str] = []
        for event in reversed(state.event_log):
            if event.participants and event.participants[0] == character.id and event_action_type(event) == "travel" and event.action_result is not None and event.action_result.status == "success" and event.location in state.locations:
                recent_travel_locations.append(event.location)
                if len(recent_travel_locations) >= 3:
                    break
        if recent_travel_locations:
            last_destination = recent_travel_locations[0]
            non_reversal = [location for location in alternatives if location != last_destination]
            if non_reversal:
                alternatives = non_reversal
        fresh = [location for location in alternatives if visit_counts[location] == 0]
        if fresh:
            alternatives = fresh
        def destination_score(location: str) -> float:
            confinement = character.human_condition.confinement_at(location)
            fear = character.human_condition.fears.get("confinement", 0.0) * confinement / 100.0
            recent_experience = sum(0.5 ** index for index, recent_location in enumerate(recent_travel_locations) if recent_location == location)
            familiarity = min(1.0, visit_counts[location] / 3.0 + recent_experience / 2.0)
            novelty = 1.0 - familiarity
            adventurous_bonus = 0.15 if adventurous else 0.0
            cautious_penalty = 0.15 * confinement if cautious else 0.0
            return 0.50 * (1.0 - confinement) + 0.25 * novelty + 0.15 * max(0.0, 1.0 - fear) + adventurous_bonus - cautious_penalty
        destination = max(alternatives, key=lambda location: (destination_score(location), location))
        # Travel is a continuous affordance. Pressure and decision utility
        # determine whether it is chosen; generation does not hide it behind
        # an arbitrary threshold.
        pool.append(
            ActionCandidate(
                id=f"tick-{state.tick}-{character.id}-travel",
                actor_id=character.id,
                action_type="travel",
                targets=[destination],
                motivation=f"explore beyond the familiar: {destination}",
                preconditions=["destination is a place the actor can reach"],
                expected_outcomes=["experience a different place"],
                confidence=1.0,
                difficulty=0.5,
                # Destination affordance selects where to go; it must not create
                # motivation to travel in the first place.
                score=0.0,
                metadata={
                    "travel_reason": "freedom_exploration",
                    "destination_affordance": destination_score(destination),
                    "destination_confinement": character.human_condition.confinement_at(destination),
                    "travel_pressure": travel_pressure,
                    "world_validated": True,
                },
            )
        )

    relationship_pressure = max(character.human_condition.desires.get("reconciliation", 0.0), character.human_condition.desires.get("belonging", 0.0))
    if relationship_pressure > 0.0 and len(state.locations) > 1:
        for target_id in _relationship_targets(state, character):
            target = state.characters[target_id]
            if target.location == character.location:
                continue
            remembered = _remembered_location(state, character, target_id)
            absent_prefix = f"location_absent:{target_id}:"
            absent = {fact.proposition[len(absent_prefix):] for fact in state.memory_state.knowledge.get(character.id, {}).values() if fact.proposition.startswith(absent_prefix)}
            alternatives = sorted(location for location in state.locations if location != character.location and location not in absent)
            destination = remembered if remembered in alternatives else (alternatives[0] if alternatives else None)
            if destination is None:
                continue
            # Search remains a travel action in the world, but carries an explicit
            # semantic event type so decision and history layers can distinguish it.
            pool.append(
                ActionCandidate(
                    id=f"tick-{state.tick}-{character.id}-search-{target_id}",
                    actor_id=character.id,
                    action_type="travel",
                    targets=[destination],
                    motivation=(
                        f"search for {target.name} after losing contact"
                        if remembered is None
                        else f"search for {target.name}; last remembered location was {remembered}"
                    ),
                    preconditions=[
                        f"search is based on {target.name}'s remembered or uncertain location"
                    ],
                    expected_outcomes=["may reunite with the person", "may discover they are elsewhere"],
                    confidence=0.45 if remembered is None else 0.65,
                    difficulty=0.5,
                    score=0.20,
                    metadata={
                        "search_target": target_id,
                        "search_basis": "remembered_location" if remembered else "uncertain_location",
                        "search_destination": destination,
                        "event_action_type": "search_person",
                        "world_validated": True,
                    },
                )
            )
            break

    fatigue = max(0.0, min(100.0, character.human_condition.fatigue))
    stress = max(0.0, character.emotions.get("stress", 0.0))
    sorrow = max(0.0, character.emotions.get("sorrow", 0.0))
    if fatigue >= 10.0 or stress >= 20.0 or sorrow >= 35.0:
        pool.append(ActionCandidate(id=f"tick-{state.tick}-{character.id}-rest", actor_id=character.id, action_type="rest", motivation="rest and recover from current pressures", preconditions=["current location permits rest"], expected_outcomes=["recover and continue later"], confidence=0.95, difficulty=0.05, score=0.05, metadata={"rest_reason": "fatigue_recovery"}))
    return pool


def choose_action(pool: list[ActionCandidate]) -> ActionCandidate | None:
    """Choose from the pool; ties preserve deterministic input ordering."""
    if not pool:
        return None
    return max(pool, key=lambda action: action.score)
