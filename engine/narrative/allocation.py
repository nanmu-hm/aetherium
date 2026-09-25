"""Allocate narrative attention without rewriting world events."""

from __future__ import annotations

from .models import NarrativeImportance, NarrativeScene, NarrativeTreatment, RhythmState


class NarrativeResourceAllocator:
    """Choose summarize/dramatize/slow_down/interiority emphasis for scenes."""

    def allocate(self, scenes:list[NarrativeScene], importance:list[NarrativeImportance], rhythm:RhythmState) -> list[NarrativeTreatment]:
        importance_by_event={item.event_id:item for item in importance}
        result=[]
        for scene in scenes:
            scores=[importance_by_event[event_id].narrative_score for event_id in scene.event_ids if event_id in importance_by_event]
            score=sum(scores)/len(scores) if scores else 0.0
            if rhythm.breathing_needed and scene.pressure < 0.45:
                mode="interiority"
            elif score >= 0.72 or scene.pressure >= 0.75:
                mode="slow_down"
            elif score >= 0.45 or scene.pressure >= 0.45:
                mode="dramatize"
            else:
                mode="summarize"
            attention=min(1.0,0.55*score+0.45*scene.pressure)
            reason=(f"importance={score:.2f}, pressure={scene.pressure:.2f}, rhythm={rhythm.phase}")
            result.append(NarrativeTreatment(scene.id,mode,attention,reason))
        result.sort(key=lambda item:(-item.attention,item.scene_id))
        return result
