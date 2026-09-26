"""Action generation for the character-driven simulation."""

from __future__ import annotations

from .models import ActionCandidate, CharacterState, WorldState
from .action_types import event_action_type, goal_matches_action
from .psychology import has_trait


def _has_value(character: CharacterState, value: str) -> bool:
    return value.lower() in {item.lower() for item in character.values}


def _relationship_targets(state: WorldState, character: CharacterState) -> list[str]:
    """Read relationships from the authoritative world graph, with legacy fallback."""
    targets = [
        rel.target_id
        for rel in state.relationships.values()
        if rel.source_id == character.id and rel.target_id in state.characters
    ]
    if targets:
        return targets
    return [target_id for target_id in character.relationships if target_id in state.characters]


def _trust(state: WorldState, character: CharacterState, target_id: str) -> float:
    relationship = state.get_relationship(character.id, target_id)
    if relationship is not None:
        return relationship.trust
    return character.relationships.get(target_id, 50.0)


def _goal_supports_action(character: CharacterState, action_type: str) -> bool:
    goal = max(
        (g for g in character.goals if g.status == "active"),
        key=lambda item: item.priority,
        default=None,
    )
    if goal is None:
        return False

    if goal.stage_conditions and goal.current_stage < len(goal.stage_conditions):
        condition = goal.stage_conditions[goal.current_stage]
        supported = condition.get("action_types")
        if supported is not None:
            return action_type in supported
        return False

    return goal_matches_action(goal.current_description, action_type)


def _contextual_desire(character: CharacterState, desire_name: str) -> float:
    """Return a desire as experienced in the actor's current place."""
    base = max(0.0, min(100.0, character.human_condition.desires.get(desire_name, 0.0)))
    if desire_name == "freedom":
        return base * character.human_condition.confinement_at(character.location)
    return base


def _remembered_location(state: WorldState, character: CharacterState, target_id: str) -> str | None:
    """Return the latest location the character remembers for a target.

    This reads only the actor's knowledge model. It never consults the target's
    current world-state location, preserving information asymmetry.
    """
    prefix = f"location_seen:{target_id}:"
    facts = [
        fact for fact in state.memory_state.knowledge.get(character.id, {}).values()
        if fact.proposition.startswith(prefix)
    ]
    if not facts:
        return None
    latest = max(facts, key=lambda fact: (fact.last_confirmed_tick, fact.confidence, fact.id))
    return latest.proposition[len(prefix):]


def generate_action_pool(state: WorldState, character_id: str) -> list[ActionCandidate]:
    """Generate plausible actions without deciding which one must happen."""
    character = state.characters[character_id]
    if character.status != "active":
        return []

    pool: list[ActionCandidate] = []
    goal = max((g for g in character.goals if g.status == "active"), key=lambda item: item.priority, default=None)

    if goal and not goal.stage_conditions:
        pool.append(ActionCandidate(
            id=f"tick-{state.tick}-{character.id}-pursue", actor_id=character.id,
            action_type="pursue_goal", motivation=goal.current_description,
            confidence=0.8, difficulty=0.5, score=0.10,
        ))

    nearby = [
        target_id for target_id in _relationship_targets(state, character)
        if state.characters[target_id].location == character.location
    ]
    if nearby:
        target_id = min(nearby, key=lambda item: _trust(state, character, item))
        trust = _trust(state, character, target_id)

        recent_contacts: list = []
        for event in reversed(state.event_log):
            if event.participants and event.participants[0] == character.id:
                if event_action_type(event) == "contact_person":
                    recent_contacts.append(event)
                    if len(recent_contacts) >= 2:
                        break
                elif recent_contacts:
                    break

        relationship_desire = max(
            character.human_condition.desires.get("reconciliation", 0.0),
            character.human_condition.desires.get("belonging", 0.0),
        )
        tension = 100.0 - trust
        emotional_pressure = max(
            character.emotions.get("anger", 0.0),
            character.emotions.get("longing", 0.0),
            character.emotions.get("resentment", 0.0),
            character.emotions.get("love", 0.0),
        )
        # Relationship tension matters only when there is an actual social
        # motive. A strained relationship by itself is not a command to make
        # contact; otherwise every character with a relationship would keep
        # contacting people forever. The motive is strengthened or weakened by
        # the current relationship state.
        social_motive = max(relationship_desire, emotional_pressure)
        relationship_factor = 0.5 + 0.5 * max(0.0, min(1.0, tension / 100.0))
        contact_pressure = max(
            0.0,
            min(100.0, social_motive * relationship_factor),
        )

        last_contact_succeeded = bool(
            recent_contacts
            and recent_contacts[0].action_result is not None
            and recent_contacts[0].action_result.status == "success"
        )
        severe_pressure = contact_pressure >= 85.0
        recent_success_cooldown = len(recent_contacts) >= 2 and last_contact_succeeded and not severe_pressure

        # Contact is an available life option, not a mandatory tick action.
        # A successful recent conversation creates a stronger cooldown; repeated
        # attempts are still possible when unresolved pressure is genuinely high.
        if contact_pressure > 0.0 and not recent_success_cooldown:
            pool.append(ActionCandidate(
                id=f"tick-{state.tick}-{character.id}-contact", actor_id=character.id,
                action_type="contact_person", targets=[target_id],
                motivation="address an important relationship",
                preconditions=["target is at the same location"],
                expected_outcomes=["relationship may change"], confidence=1.0, difficulty=0.0,
                # The target is co-located and the current world models no
                # separate social obstacle. Do not invent a random failure;
                # personality-shaped consequences are applied after contact.
                score=0.15,
                metadata={"world_validated": True},
            ))

    if _relationship_targets(state, character):
        targets = _relationship_targets(state, character)
        distressed = [
            target_id for target_id in targets
            if state.characters[target_id].location == character.location
            and (
                state.characters[target_id].emotions.get("sorrow", 0.0)
                + state.characters[target_id].emotions.get("fear", 0.0)
                + state.characters[target_id].human_condition.fatigue / 2.0
                > 8.0
            )
        ]
        if distressed and (
            _has_value(character, "loyalty")
            or _has_value(character, "responsibility")
            or has_trait(character, "compassionate", "protective", "helpful")
            or character.human_condition.desires.get("responsibility", 0.0) > 20.0
        ):
            target_id = max(
                distressed,
                key=lambda item: (
                    state.characters[item].emotions.get("sorrow", 0.0)
                    + state.characters[item].emotions.get("fear", 0.0),
                    -_trust(state, character, item),
                ),
            )
            pool.append(ActionCandidate(
                id=f"tick-{state.tick}-{character.id}-help", actor_id=character.id,
                action_type="help_person", targets=[target_id],
                motivation=f"help {state.characters[target_id].name} because their condition looks difficult",
                preconditions=["target is at the same location"],
                confidence=1.0, difficulty=0.0,
                # The current world models co-location as sufficient to attempt
                # help; do not inject an unexplained random failure.
                score=0.20,
                metadata={"world_validated": True},
            ))

    freedom_pressure = _contextual_desire(character, "freedom")
    curiosity_pressure = _contextual_desire(character, "curiosity")
    if len(state.locations) > 1:
        # Travel is a continuous affordance. Pressure and decision utility
        # determine whether it is chosen; generation does not hide it behind
        # an arbitrary threshold.
        visit_counts = {location: 0 for location in state.locations}
        for memory in state.memory_state.memories.values():
            if memory.owner_id == character.id and memory.location in visit_counts:
                visit_counts[memory.location] += 1

        alternatives = [location for location in state.locations if location != character.location]
        recent_travel_locations: list[str] = []
        for event in reversed(state.event_log):
            if (
                event.participants
                and event.participants[0] == character.id
                and event_action_type(event) == "travel"
                and event.action_result is not None
                and event.action_result.status == "success"
                and event.location in state.locations
            ):
                recent_travel_locations.append(event.location)
                if len(recent_travel_locations) >= 3:
                    break

        # New places satisfy curiosity more strongly. Once everything is
        # familiar, destination meaning matters: confinement and fear reduce
        # the attraction of a place for this particular character. Recent
        # experience also increases effective familiarity: this is a memory-
        # grounded novelty effect, not a hard travel cooldown.
        fresh = [location for location in alternatives if visit_counts[location] == 0]
        if fresh:
            alternatives = fresh
        def destination_score(location: str) -> float:
            confinement = character.human_condition.confinement_at(location)
            fear = character.human_condition.fears.get("confinement", 0.0) * confinement / 100.0
            recent_experience = sum(
                0.5 ** index
                for index, recent_location in enumerate(recent_travel_locations)
                if recent_location == location
            )
            familiarity = min(1.0, visit_counts[location] / 3.0 + recent_experience / 2.0)
            return (
                0.55 * (1.0 - confinement)
                + 0.25 * (1.0 - familiarity)
                + 0.20 * max(0.0, 1.0 - fear)
            )

        destination = max(alternatives, key=lambda location: (destination_score(location), location))
        destination_affordance = destination_score(destination)
        pool.append(ActionCandidate(
            id=f"tick-{state.tick}-{character.id}-travel", actor_id=character.id,
            action_type="travel", targets=[destination],
            motivation=f"explore beyond the familiar: {destination}",
            preconditions=["destination is a place the actor can reach"],
            expected_outcomes=["experience a different place"],
            confidence=1.0, difficulty=0.5,
            # Destination affordance selects where to go; it must not create
            # motivation to travel in the first place.
            score=0.0,
            metadata={
                "travel_reason": "freedom_exploration",
                "destination_affordance": destination_affordance,
                "destination_confinement": character.human_condition.confinement_at(destination),
                "world_validated": True,
            },
        ))

    # Relationship pressure can create a search journey even for a character
    # whose values do not include freedom. The destination comes from the
    # character's own remembered/uncertain model, never from the target's
    # current world-state location.
    relationship_pressure = max(
        character.human_condition.desires.get("reconciliation", 0.0),
        character.human_condition.desires.get("belonging", 0.0),
    )
    if relationship_pressure > 0.0 and len(state.locations) > 1:
        for target_id in _relationship_targets(state, character):
            target = state.characters[target_id]

            # A character can directly perceive another character at the same
            # location. Searching for someone who is already present would
            # contradict the actor's available information, so contact (or
            # another same-location action) must remain the available path.
            if target.location == character.location:
                continue

            remembered = _remembered_location(state, character, target_id)
            absent_prefix = f"location_absent:{target_id}:"
            absent = {
                fact.proposition[len(absent_prefix):]
                for fact in state.memory_state.knowledge.get(character.id, {}).values()
                if fact.proposition.startswith(absent_prefix)
            }
            alternatives = sorted(
                location
                for location in state.locations
                if location != character.location and location not in absent
            )
            destination = remembered if remembered in alternatives else (alternatives[0] if alternatives else None)
            if destination is None:
                continue
            pool.append(ActionCandidate(
                id=f"tick-{state.tick}-{character.id}-search-{target_id}",
                actor_id=character.id,
                action_type="travel",
                targets=[destination],
                motivation=(
                    f"search for {target.name} after losing contact"
                    if remembered is None
                    else f"search for {target.name}; last remembered location was {remembered}"
                ),
                preconditions=[f"search is based on {target.name}'s remembered or uncertain location"],
                expected_outcomes=["may reunite with the person", "may discover they are elsewhere"],
                confidence=0.45 if remembered is None else 0.65,
                difficulty=0.5,
                score=0.20,
                metadata={
                    "search_target": target_id,
                    "search_basis": "remembered_location" if remembered else "uncertain_location",
                    "search_destination": destination,
                    "world_validated": True,
                },
            ))
            break

    # Rest is a real biological affordance, not a substitute for an empty action
    # pool. When there is no meaningful recovery need, the character is allowed
    # to be idle instead of repeatedly "resting" without changing state.
    fatigue = max(0.0, min(100.0, character.human_condition.fatigue))
    stress = max(0.0, character.emotions.get("stress", 0.0))
    sorrow = max(0.0, character.emotions.get("sorrow", 0.0))
    if fatigue >= 10.0 or stress >= 20.0 or sorrow >= 35.0:
        rest_score = min(1.0, 0.10 + 0.70 * (fatigue / 100.0))
        pool.append(ActionCandidate(
            id=f"tick-{state.tick}-{character.id}-rest",
            actor_id=character.id,
            action_type="rest",
            motivation="rest and recover from current pressures",
            preconditions=["current location permits rest"],
            expected_outcomes=["recover and continue later"],
            confidence=0.95,
            difficulty=0.05,
            # Recovery need is already represented by fatigue/stress urgency;
            # this prior only says rest is physically easy to perform.
            score=0.05,
            metadata={"rest_reason": "fatigue_recovery"},
        ))
    return pool


def choose_action(pool: list[ActionCandidate]) -> ActionCandidate | None:
    """Choose from the pool; ties preserve deterministic input ordering."""
    if not pool:
        return None
    return max(pool, key=lambda action: action.score)
