from __future__ import annotations

from .conflict import InterventionConflictDetector
from .impact import InterventionImpactAnalyzer
from .models import InterventionPlan, InterventionRequest


class InterventionPlanner:
    def __init__(
        self,
        impact_analyzer: InterventionImpactAnalyzer | None = None,
        conflict_detector: InterventionConflictDetector | None = None,
    ) -> None:
        self.impact_analyzer = impact_analyzer or InterventionImpactAnalyzer()
        self.conflict_detector = conflict_detector or InterventionConflictDetector()

    def plan(self, state, request: InterventionRequest) -> InterventionPlan:
        impact = self.impact_analyzer.analyze(state, request)
        conflicts = self.conflict_detector.detect(state, request)

        if conflicts:
            action = "reject"
            reason = "Conflicts must be resolved before any authoritative mutation."
        elif request.intervention_type == "historical_rewrite" or request.intervention_type == "world_rule":
            action = "fork"
            reason = "Historical or world-rule changes must preserve the existing history."
        elif request.intervention_type in {"future_only", "character_model"}:
            action = "apply"
            reason = "The change can begin from the current or requested future tick without rewriting past events."
        elif request.intervention_type == "narrative_only":
            action = "apply"
            reason = "Narrative-only changes do not mutate authoritative world state."
        else:
            action = "reject"
            reason = "Unknown intervention type."

        return InterventionPlan(request.id, action, reason, impact, conflicts)
