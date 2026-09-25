from __future__ import annotations

from ..core.models import WorldState
from .models import ImpactItem, ImpactReport, InterventionRequest


class InterventionImpactAnalyzer:
    """Trace likely downstream material without mutating the world."""

    def analyze(self, state: WorldState, request: InterventionRequest) -> ImpactReport:
        items: list[ImpactItem] = []
        prefix = request.target_path.split(".", 1)[0]
        target_id = self._target_id(request.target_path)

        for event in state.event_log:
            participant_hit = target_id in event.participants if target_id else False
            consequence_hit = any(
                target_id
                and (
                    consequence.target_id == target_id
                    or consequence.field.startswith(request.target_path)
                    or request.target_path.startswith(consequence.field)
                )
                for consequence in event.consequences
            )
            if participant_hit or consequence_hit:
                items.append(
                    ImpactItem(
                        "event",
                        event.id,
                        "Historical event depends on or involves the requested target.",
                        0.75 if consequence_hit else 0.55,
                    )
                )

        if prefix == "characters" and target_id in state.characters:
            character = state.characters[target_id]
            items.append(ImpactItem("character", target_id, f"Character field {request.target_path} changes future behavior.", 0.85))
            for goal in character.goals:
                items.append(ImpactItem("goal", goal.id, "Character model changes can alter goal pursuit.", 0.65))
        elif prefix == "relationships":
            items.extend(
                ImpactItem("relationship", key, "Relationship changes can alter later decisions and narrative threads.", 0.80)
                for key in state.relationships
                if not target_id or key == target_id
            )
        elif prefix == "factions":
            items.extend(
                ImpactItem("faction", key, "Faction state can propagate into collective actions and events.", 0.80)
                for key in state.factions
                if not target_id or key == target_id
            )
        elif prefix == "world":
            items.append(ImpactItem("world", state.world_id, "World-rule changes may affect future simulation outcomes.", 0.95))

        return ImpactReport(request.id, items)

    @staticmethod
    def _target_id(path: str) -> str | None:
        parts = path.split(".")
        if len(parts) >= 2 and parts[0] in {"characters", "relationships", "factions"}:
            return parts[1]
        return None
