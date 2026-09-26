"""Canonical action-type names used across simulation, memory, and decisions."""

from __future__ import annotations

import re

_ALIASES = {
    "contact": "contact_person",
    "contact_person": "contact_person",
    "help": "help_person",
    "help_person": "help_person",
    "travel": "travel",
    "search_person": "search_person",
    "search": "search_person",
    "pursue": "pursue_goal",
    "pursue_goal": "pursue_goal",
}


def canonical_action_type(action_type: str) -> str:
    return _ALIASES.get(action_type, action_type)


GOAL_ACTION_KEYWORDS = {
    "help_person": frozenset({"help", "protect", "support", "save"}),
    "contact_person": frozenset({"find", "reconcile", "talk", "meet", "contact"}),
    "search_person": frozenset({"find", "search", "seek", "look"}),
    "travel": frozenset({"leave", "escape", "go", "move", "freedom", "depart"}),
}


def goal_tokens(goal_description: str) -> set[str]:
    return set(re.findall(r"[a-z]+", goal_description.lower()))


def goal_matches_action(goal_description: str, action_type: str) -> bool:
    return bool(goal_tokens(goal_description) & GOAL_ACTION_KEYWORDS.get(canonical_action_type(action_type), frozenset()))


def event_action_type(event) -> str:
    """Return the semantic event type while preserving legacy travel events."""
    explicit = getattr(event, "action_type", "")
    if explicit:
        if canonical_action_type(explicit) == "travel" and event.causes:
            cause = event.causes[0]
            if "-search-" in cause:
                return "search_person"
        return canonical_action_type(explicit)
    if event.causes:
        cause = event.causes[0]
        if "-search-" in cause:
            return "search_person"
        return canonical_action_type(cause.rsplit("-", 1)[-1])
    return ""
