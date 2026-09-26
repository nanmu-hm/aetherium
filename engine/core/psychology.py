"""Deterministic character interpretation and social reaction rules.

This module keeps personality causal without asking the narrative layer to invent
behavior. The same event can therefore produce different internal changes for
different characters.
"""

from __future__ import annotations

from .models import ActionCandidate, CharacterState


def _tags(character: CharacterState) -> set[str]:
    return {item.strip().lower().replace("-", "_") for item in [*character.traits, *character.values] if item}


def has_trait(character: CharacterState, *names: str) -> bool:
    tags = _tags(character)
    return any(name.lower().replace("-", "_") in tags for name in names)


def social_reaction(
    character: CharacterState,
    action: ActionCandidate,
    outcome_status: str,
    *,
    is_target: bool,
) -> dict[str, float]:
    """Return emotion changes caused by another character's action.

    Personality changes interpretation rather than merely adding a utility bonus.
    The returned deltas are intentionally small and deterministic; repeated
    experiences accumulate through the existing state and memory systems.
    """
    action_type = action.action_type
    if action_type not in {"contact_person", "help_person"}:
        return {}

    if outcome_status == "success":
        if action_type == "contact_person":
            if has_trait(character, "distrustful", "suspicious", "proud"):
                return {"hope": 1.0, "resentment": 1.5}
            if has_trait(character, "warm", "forgiving", "loyal", "compassionate"):
                return {"joy": 3.0, "hope": 2.0, "longing": -2.0}
            return {"joy": 2.0, "hope": 1.0}
        if has_trait(character, "proud", "independent"):
            return {"respect": 1.0, "resentment": 1.0}
        if has_trait(character, "grateful", "loyal", "compassionate"):
            return {"joy": 3.0, "love": 2.0, "hope": 2.0}
        return {"joy": 2.0, "hope": 1.0}

    if outcome_status == "failure":
        if has_trait(character, "proud", "hot_tempered", "impulsive"):
            return {"anger": 4.0, "resentment": 3.0, "hope": -1.0}
        if has_trait(character, "cautious", "fearful", "distrustful"):
            return {"fear": 3.0, "sorrow": 2.0, "hope": -2.0}
        if has_trait(character, "loyal", "forgiving", "compassionate"):
            return {"sorrow": 2.0, "longing": 2.0}
        return {"sorrow": 2.0, "resentment": 2.0}

    return {}


def witness_reaction(
    character: CharacterState,
    action: ActionCandidate,
    outcome_status: str,
) -> dict[str, float]:
    """Return how a bystander interprets an observed event."""
    if outcome_status not in {"success", "failure"}:
        return {}

    if action.action_type == "contact_person":
        if has_trait(character, "curious"):
            return {"curiosity": 2.0}
        if has_trait(character, "suspicious", "distrustful"):
            return {"fear": 1.5, "curiosity": 1.5}
        if has_trait(character, "compassionate", "loyal"):
            return {"hope": 1.0}
        return {}

    if action.action_type == "help_person":
        if outcome_status == "success" and has_trait(character, "compassionate", "loyal"):
            return {"joy": 2.0, "hope": 1.0}
        if outcome_status == "failure" and has_trait(character, "protective", "responsible"):
            return {"concern": 2.0, "anger": 1.0}
        if has_trait(character, "suspicious"):
            return {"curiosity": 2.0}
        return {}

    if action.action_type == "travel" and has_trait(character, "curious", "adventurous"):
        return {"curiosity": 2.0}

    return {}
