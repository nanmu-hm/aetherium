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
