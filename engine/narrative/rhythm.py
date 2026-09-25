from __future__ import annotations

from .models import SceneExpressionPlan, SentenceRhythmPlan


class SentenceRhythmPlanner:
    def plan(self, scenes: list[SceneExpressionPlan]) -> list[SentenceRhythmPlan]:
        result = []
        for scene in scenes:
            pressure = 1.0 - scene.omission_strength
            if scene.cadence == "tight" or pressure >= 0.70:
                pace = "fast"
                mix = "short-medium"
                variation = 0.72
                punctuation = 0.65
                pause = 0.25
                breathing = 0.30
            elif scene.narrative_distance == "moderate" and pressure <= 0.35:
                pace = "slow"
                mix = "medium-long"
                variation = 0.55
                punctuation = 0.35
                pause = 0.72
                breathing = 0.80
            else:
                pace = "medium"
                mix = "short-medium-long"
                variation = 0.65
                punctuation = 0.48
                pause = 0.48
                breathing = 0.55
            result.append(SentenceRhythmPlan(
                scene_id=scene.scene_id,
                pace=pace,
                sentence_length_mix=mix,
                variation=variation,
                punctuation_density=punctuation,
                pause_strength=pause,
                paragraph_breathing=breathing,
                reason="Sentence rhythm follows scene expression controls rather than maximizing intensity.",
            ))
        return result
