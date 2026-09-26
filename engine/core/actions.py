"""Action generation for the character-driven simulation."""

from __future__ import annotations

import re

from .models import ActionCandidate, CharacterState, WorldState


def _goal_words(description: str) -> set[str]:
    return set(re.findall(r"[a-z]+", description.lower()))


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

    words = _goal_words(goal.description)
    keywords = {
        "help_person": {"help", "protect", "support", "save"},
        "contact_person": {"find", "reconcile", "talk", "meet", "contact"},
        "travel": {"leave", "escape", "go", "move", "freedom", "depart"},
    }
    return bool(words & keywords.get(action_type, set()))


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
                if event.action_type == "contact_person":
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
    recent_travel = next(
        (
            event for event in reversed(state.event_log)
            if event.participants
            and event.participants[0] == character.id
            and event.action_type == "travel"
        ),
        None,
    )
    # A two-location world cannot express meaningful destination choice yet.
    # After a successful trip, give the character time to experience the new
    # place before immediately bouncing back and forth.
    travel_cooldown = (
        recent_travel is not None
        and recent_travel.action_result is not None
        and recent_travel.action_result.status == "success"
        and state.tick - recent_travel.tick < 2
    )
    if _has_value(character, "freedom") and freedom_pressure >= 50.0 and len(state.locations) > 1 and not travel_cooldown:
        destination = sorted(location for location in state.locations if location != character.location)[0]
        pool.append(ActionCandidate(
            id=f"tick-{state.tick}-{character.id}-travel", actor_id=character.id,
            action_type="travel", targets=[destination],
            motivation=f"move toward {destination}", confidence=0.55, score=0.5,
        ))

    return pool


def choose_action(pool: list[ActionCandidate]) -> ActionCandidate | None:
    """Choose from the pool; ties preserve deterministic input ordering."""
    if not pool:
        return None
    return max(pool, key=lambda action: action.score)
