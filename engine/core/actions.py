"""Action generation for the character-driven simulation."""

from __future__ import annotations

from .models import ActionCandidate, CharacterState, WorldState


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

    text = goal.description.lower()
    keywords = {
        "help_person": ("help", "protect", "support", "save"),
        "contact_person": ("find", "reconcile", "talk", "meet", "contact", "friend"),
        "travel": ("leave", "escape", "go", "move", "freedom", "depart"),
    }
    return any(word in text for word in keywords.get(action_type, ()))


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
        pool.append(ActionCandidate(
            id=f"tick-{state.tick}-{character.id}-contact", actor_id=character.id,
            action_type="contact_person", targets=[target_id],
            motivation="address an important relationship",
            preconditions=["target is at the same location"],
            expected_outcomes=["relationship may change"], confidence=0.65, difficulty=0.35,
            score=(100.0 - trust) / 100.0,
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

    return pool


def choose_action(pool: list[ActionCandidate]) -> ActionCandidate | None:
    """Choose from the pool; ties preserve deterministic input ordering."""
    if not pool:
        return None
    return max(pool, key=lambda action: action.score)
