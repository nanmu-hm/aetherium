from __future__ import annotations

from .models import NarrativeState, ReaderKnowledgePlan


class ReaderKnowledgePlanner:
    def plan(self, narrative: NarrativeState) -> list[ReaderKnowledgePlan]:
        plans = []
        reader_known: set[str] = set()
        for scene in sorted(narrative.scenes, key=lambda item: (item.start_tick, item.id)):
            reveal = []
            withheld = []
            irony = []
            scene_events = set(scene.event_ids)
            for gap in narrative.information_gaps:
                source_events = set(gap.source_event_ids)
                if not source_events.intersection(scene_events):
                    continue
                if gap.proposition in reader_known:
                    continue
                if gap.unknown_by and gap.known_by:
                    irony.append(gap.proposition)
                reveal.append(next(iter(source_events.intersection(scene_events))))
            for revelation in narrative.revelations:
                if revelation.source_event_id in scene_events and revelation.proposition not in reader_known:
                    withheld.append(revelation.proposition)
            if reveal:
                mode = "reveal"
                reason = "The scene contains a grounded information source that can update reader knowledge."
                reader_known.update(gap.proposition for gap in narrative.information_gaps if set(gap.source_event_ids).intersection(scene_events))
            elif irony:
                mode = "dramatic_irony"
                reason = "A known fact remains asymmetric between reader and characters."
            elif withheld:
                mode = "withhold"
                reason = "A grounded proposition exists but need not be exposed immediately."
            else:
                mode = "discover"
                reason = "No information intervention is required."
            plans.append(ReaderKnowledgePlan(
                scene_id=scene.id,
                reveal_event_ids=sorted(set(reveal)),
                withheld_propositions=sorted(set(withheld)),
                dramatic_irony=sorted(set(irony)),
                mode=mode,
                reason=reason,
            ))
        return plans
