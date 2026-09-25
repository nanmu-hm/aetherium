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

        if action.required_ability:
            ability = actor.abilities.get(action.required_ability, 0.0)
            if ability <= 0.0:
                reasons.append(f"required ability unavailable: {action.required_ability}")

        if action.action_type == "contact_person" and action.targets:
            target = state.characters.get(action.targets[0])
            if target is None:
                reasons.append("contact target does not exist")
            elif target.status != "active":
                reasons.append("contact target is not active")
            elif target.location != actor.location:
                reasons.append("target is not at the same location")

        if action.action_type == "help_person" and action.targets:
            target = state.characters.get(action.targets[0])
            if target is None:
                reasons.append("help target does not exist")
            elif target.status != "active":
                reasons.append("help target is not active")

        if action.action_type == "travel" and action.targets:
            destination = action.targets[0]
            if destination not in state.locations:
                reasons.append("destination does not exist")

        for declared in action.preconditions:
            rule = declared.strip().lower()
            if rule in {"actor_active"} and actor.status != "active":
                reasons.append("actor is not active")
            elif rule in {"same_location", "target_at_actor_location"} and action.targets:
                target = state.characters.get(action.targets[0])
                if target is not None and target.location != actor.location:
                    reasons.append("declared precondition failed: same location required")
            elif rule == "target_active" and action.targets:
                target = state.characters.get(action.targets[0])
                if target is not None and target.status != "active":
                    reasons.append("declared precondition failed: target must be active")
            elif rule == "destination_exists" and action.targets and action.targets[0] not in state.locations:
                reasons.append("declared precondition failed: destination does not exist")
            elif rule == "destination_differs" and action.targets and action.targets[0] == actor.location:
                reasons.append("declared precondition failed: destination must differ from current location")
            elif rule.startswith("requires_ability:"):
                ability_name = rule.split(":", 1)[1].strip()
                if actor.abilities.get(ability_name, 0.0) <= 0.0:
                    reasons.append(f"declared precondition failed: ability unavailable: {ability_name}")
            elif rule.startswith("requires_possession:"):
                parts = rule.split(":")
                possession_name = parts[1].strip() if len(parts) > 1 else ""
                required_count = int(parts[2]) if len(parts) > 2 and parts[2].strip().isdigit() else 1
                if actor.possessions.get(possession_name, 0) < required_count:
                    reasons.append(
                        f"declared precondition failed: possession required: {possession_name} x{required_count}"
                    )

        return PreconditionResult(not reasons, tuple(dict.fromkeys(reasons)))
