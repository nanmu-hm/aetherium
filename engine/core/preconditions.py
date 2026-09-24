"""Structured action precondition checks.

Preconditions answer whether an action can be attempted; they never decide its outcome.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import ActionCandidate, WorldState


@dataclass(frozen=True)
class PreconditionResult:
    satisfied: bool
    reasons: tuple[str, ...] = ()


class PreconditionEngine:
    def check(self, state: WorldState, action: ActionCandidate) -> PreconditionResult:
        actor = state.characters.get(action.actor_id)
        if actor is None:
            return PreconditionResult(False, ("actor does not exist",))
        if actor.status != "active":
            return PreconditionResult(False, ("actor is not active",))

        reasons: list[str] = []
        for target_id in action.targets:
            if target_id not in state.characters and target_id not in state.locations:
                reasons.append(f"target does not exist: {target_id}")

        if action.action_type == "contact_person" and action.targets:
            target = state.characters.get(action.targets[0])
            if target is None:
                reasons.append("contact target does not exist")
            elif target.location != actor.location:
                reasons.append("target is not at the same location")

        if action.action_type == "travel" and action.targets:
            if action.targets[0] not in state.locations:
                reasons.append("destination does not exist")

        return PreconditionResult(not reasons, tuple(reasons))
