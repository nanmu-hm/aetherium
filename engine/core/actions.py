"""Action generation for the character-driven simulation."""

from __future__ import annotations

from .models import ActionCandidate, CharacterState, WorldState
from .action_types import event_action_type, goal_matches_action


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

    return goal_matches_action(goal.description, action_type)


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

    if goal:
        pool.append(ActionCandidate(
            id=f"tick-{state.tick}-{character.id}-pursue", actor_id=character.id,
            action_type="pursue_goal", motivation=goal.description,
            confidence=0.8, difficulty=0.5, score=goal.priority,
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
        contact_pressure = max(0.0, min(100.0, tension + 0.5 * relationship_desire))

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
        if contact_pressure >= 35.0 and not recent_success_cooldown:
            pool.append(ActionCandidate(
                id=f"tick-{state.tick}-{character.id}-contact", actor_id=character.id,
                action_type="contact_person", targets=[target_id],
                motivation="address an important relationship",
                preconditions=["target is at the same location"],
                expected_outcomes=["relationship may change"], confidence=0.65, difficulty=0.35,
                score=(contact_pressure / 100.0),
            ))

    if _has_value(character, "loyalty") and _goal_supports_action(character, "help_person") and _relationship_targets(state, character):
        targets = _relationship_targets(state, character)
        target_id = max(targets, key=lambda item: _trust(state, character, item))
        pool.append(ActionCandidate(
            id=f"tick-{state.tick}-{character.id}-help", actor_id=character.id,
            action_type="help_person", targets=[target_id],
            motivation="help someone they feel loyal to", confidence=0.7, score=0.6,
        ))

    freedom_pressure = character.human_condition.desires.get("freedom", 0.0)
    if _has_value(character, "freedom") and freedom_pressure >= 50.0 and len(state.locations) > 1:
        destination = sorted(location for location in state.locations if location != character.location)[0]
        pool.append(ActionCandidate(
            id=f"tick-{state.tick}-{character.id}-travel", actor_id=character.id,
            action_type="travel", targets=[destination],
            motivation=f"move toward {destination}", confidence=0.55, score=0.5,
        ))

    # Relationship pressure can create a search journey even for a character
    # whose values do not include freedom. The destination comes from the
    # character's own remembered/uncertain model, never from the target's
    # current world-state location.
    relationship_pressure = max(
        character.human_condition.desires.get("reconciliation", 0.0),
        character.human_condition.desires.get("belonging", 0.0),
    )
    if relationship_pressure >= 70.0 and len(state.locations) > 1:
        for target_id in _relationship_targets(state, character):
            target = state.characters[target_id]

            # A character can directly perceive another character at the same
            # location. Searching for someone who is already present would
            # contradict the actor's available information, so contact (or
            # another same-location action) must remain the available path.
            if target.location == character.location:
                continue

            remembered = _remembered_location(state, character, target_id)
            alternatives = sorted(
                location for location in state.locations if location != character.location
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
                score=relationship_pressure / 100.0,
            ))
            break

    return pool


def choose_action(pool: list[ActionCandidate]) -> ActionCandidate | None:
    """Choose from the pool; ties preserve deterministic input ordering."""
    if not pool:
        return None
    return max(pool, key=lambda action: action.score)
