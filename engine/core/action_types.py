"""Canonical action-type names used across simulation, memory, and decisions."""

from __future__ import annotations

_ALIASES = {
    "contact": "contact_person",
    "contact_person": "contact_person",
    "help": "help_person",
    "help_person": "help_person",
    "travel": "travel",
    "pursue": "pursue_goal",
    "pursue_goal": "pursue_goal",
}


def canonical_action_type(action_type: str) -> str:
    """Return the canonical internal action name for an event or action."""
    return _ALIASES.get(action_type, action_type)


def event_action_type(event) -> str:
    """Return an event's canonical action type, with legacy-cause fallback."""
    explicit = getattr(event, "action_type", "")
    if explicit:
        return canonical_action_type(explicit)
    if event.causes:
        return canonical_action_type(event.causes[0].rsplit("-", 1)[-1])
    return ""
