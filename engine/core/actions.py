"""Action generation for the first character-driven simulation."""

from __future__ import annotations

from .models import ActionCandidate, CharacterState, WorldState


def _has_value(character: CharacterState, value: str) -> bool:
    return value.lower() in {item.lower() for item in character.values}


def generate_action_pool(state: WorldState, character_id: str) -> list[ActionCandidate]:
    """Generate plausible actions without deciding which one must happen."""
    character = state.characters[character_id]
    if character.status != "active":
        return []

    pool: list[ActionCandidate] = []
    goal = max(character.goals, key=lambda item: item.priority) if character.goals else None

    if goal:
        pool.append(
            ActionCandidate(
                id=f"tick-{state.tick}-{character.id}-pursue",
                actor_id=character.id,
                action_type="pursue_goal",
                motivation=goal.description,
                confidence=0.8,
                score=goal.priority,
            )
        )

    if character.relationships:
        target_id, trust = min(character.relationships.items(), key=lambda item: item[1])
        pool.append(
            ActionCandidate(
                id=f"tick-{state.tick}-{character.id}-contact",
                actor_id=character.id,
                action_type="contact_person",
                targets=[target_id],
                motivation="address an important relationship",
                confidence=0.65,
                score=(100.0 - trust) / 100.0,
            )
        )

    if "loyalty" in {value.lower() for value in character.values} and character.relationships:
        target_id = max(character.relationships, key=character.relationships.get)
        pool.append(
            ActionCandidate(
                id=f"tick-{state.tick}-{character.id}-help",
                actor_id=character.id,
                action_type="help_person",
                targets=[target_id],
                motivation="help someone they feel loyal to",
                confidence=0.7,
                score=0.6,
            )
        )

    if "freedom" in {value.lower() for value in character.values} and len(state.locations) > 1:
        destination = next(
            location for location in state.locations if location != character.location
        )
        pool.append(
            ActionCandidate(
                id=f"tick-{state.tick}-{character.id}-travel",
                actor_id=character.id,
                action_type="travel",
                targets=[destination],
                motivation=f"move toward {destination}",
                confidence=0.55,
                score=0.5,
            )
        )

    return pool


def choose_action(pool: list[ActionCandidate]) -> ActionCandidate | None:
    """Choose from the pool; ties preserve deterministic input ordering."""
    if not pool:
        return None
    return max(pool, key=lambda action: action.score);
