from __future__ import annotations

from ..core.models import WorldState
from .models import ConflictFinding, InterventionRequest


class InterventionConflictDetector:
    """Detect conflicts between an intervention and authoritative current state."""

    def detect(self, state: WorldState, request: InterventionRequest) -> list[ConflictFinding]:
        conflicts: list[ConflictFinding] = []
        if request.intervention_type == "historical_rewrite":
            if request.effective_tick is None:
                conflicts.append(ConflictFinding("validation", "Historical rewrites require an effective tick.", 0.95))
            elif request.effective_tick > state.tick:
                conflicts.append(ConflictFinding("chronology", "Historical rewrite starts after the current simulation tick.", 0.80))

        if request.intervention_type == "future_only" and request.effective_tick is not None and request.effective_tick < state.tick:
            conflicts.append(ConflictFinding("chronology", "Future-only intervention cannot begin in the past.", 0.90))

        if request.target_path.startswith("characters."):
            character_id = request.target_path.split(".")[1]
            if character_id not in state.characters:
                conflicts.append(ConflictFinding("missing_target", f"Unknown character: {character_id}", 1.0))
        elif request.target_path.startswith("relationships."):
            relationship_id = request.target_path.split(".")[1]
            if relationship_id not in state.relationships:
                conflicts.append(ConflictFinding("missing_target", f"Unknown relationship: {relationship_id}", 1.0))
        elif request.target_path.startswith("factions."):
            faction_id = request.target_path.split(".")[1]
            if faction_id not in state.factions:
                conflicts.append(ConflictFinding("missing_target", f"Unknown faction: {faction_id}", 1.0))
        elif not request.target_path.startswith("world."):
            conflicts.append(ConflictFinding("validation", f"Unsupported intervention target: {request.target_path}", 0.90))

        return conflicts
