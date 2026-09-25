"""Build story structure from observed beats, threads, and history."""

from __future__ import annotations

from collections import defaultdict

from .models import NarrativeBeat, NarrativeScene, NarrativeSequence, NarrativeState, StoryArc


class NarrativeStructureBuilder:
    """Organize observed history into scenes, sequences, and discovered arcs."""

    def __init__(self, scene_gap: int = 1, sequence_gap: int = 3) -> None:
        self.scene_gap = max(0, scene_gap)
        self.sequence_gap = max(self.scene_gap, sequence_gap)

    @staticmethod
    def _ordered_beats(narrative: NarrativeState) -> list[NarrativeBeat]:
        return sorted(narrative.beats, key=lambda beat: (beat.tick, beat.id))

    @staticmethod
    def _participants(beat_ids: list[str], beats: dict[str, NarrativeBeat]) -> set[str]:
        return {participant for beat_id in beat_ids for participant in beats[beat_id].participants}

    def build_scenes(self, narrative: NarrativeState) -> list[NarrativeScene]:
        ordered = self._ordered_beats(narrative)
        if not ordered:
            return []
        scenes: list[list[NarrativeBeat]] = [[ordered[0]]]
        for beat in ordered[1:]:
            current = scenes[-1]
            previous = current[-1]
            shared = bool(set(beat.participants).intersection(previous.participants))
            close = beat.tick - previous.tick <= self.scene_gap
            if close and shared:
                current.append(beat)
            else:
                scenes.append([beat])

        result: list[NarrativeScene] = []
        for index, group in enumerate(scenes, start=1):
            counts=defaultdict(int)
            for beat in group:
                counts[beat.beat_type]+=1
            dominant=max(counts, key=counts.get)
            pressure=sum(beat.pressure for beat in group)/len(group)
            event_ids=[event_id for beat in group for event_id in beat.event_ids]
            result.append(NarrativeScene(
                id=f"scene-{index}-{group[0].id}",
                beat_ids=[beat.id for beat in group],
                event_ids=event_ids,
                participants=sorted({p for beat in group for p in beat.participants}),
                start_tick=group[0].tick,
                end_tick=group[-1].tick,
                pressure=pressure,
                dominant_beat_type=dominant,
            ))
        return result

    def build_sequences(self, narrative: NarrativeState, scenes: list[NarrativeScene]) -> list[NarrativeSequence]:
        if not scenes:
            return []
        thread_by_event={event_id:thread.id for thread in narrative.threads for event_id in thread.event_ids}
        groups=[[scenes[0]]]
        for scene in scenes[1:]:
            current=groups[-1]
            previous=current[-1]
            shared=bool(set(scene.participants).intersection(previous.participants))
            thread_overlap=bool(
                set(thread_by_event.get(event_id) for event_id in scene.event_ids if event_id in thread_by_event).intersection(
                    thread_by_event.get(event_id) for event_id in previous.event_ids if event_id in thread_by_event
                )
            )
            close=scene.start_tick-previous.end_tick <= self.sequence_gap
            if close and (shared or thread_overlap):
                current.append(scene)
            else:
                groups.append([scene])

        result=[]
        for index, group in enumerate(groups, start=1):
            thread_ids=sorted({thread_by_event[event_id] for scene in group for event_id in scene.event_ids if event_id in thread_by_event})
            questions=[]
            for thread_id in thread_ids:
                thread=next((item for item in narrative.threads if item.id==thread_id),None)
                if thread and thread.unresolved_question:
                    questions.append(thread.unresolved_question)
            result.append(NarrativeSequence(
                id=f"sequence-{index}-{group[0].id}",
                scene_ids=[scene.id for scene in group],
                thread_ids=thread_ids,
                participants=sorted({p for scene in group for p in scene.participants}),
                tension=sum(scene.pressure for scene in group)/len(group),
                status="open" if questions else "developing",
                unresolved_questions=sorted(set(questions)),
            ))
        return result

    def build_story_arcs(self, narrative: NarrativeState, sequences: list[NarrativeSequence]) -> list[StoryArc]:
        if not sequences:
            return []
        arcs: list[StoryArc]=[]
        for index, sequence in enumerate(sequences, start=1):
            matching=[thread for thread in narrative.threads if set(sequence.thread_ids).intersection({thread.id})]
            questions=sorted({q for thread in matching for q in [thread.unresolved_question] if q})
            if sequence.tension >= 0.70:
                phase="climax_candidate"
            elif sequence.tension >= 0.35:
                phase="development"
            else:
                phase="emerging"
            completion_signal=0.75 if sequence.status != "open" and not questions else max(0.0, min(1.0, 1.0-sequence.tension))
            title=(matching[0].title if matching else f"Emerging arc {index}")
            arcs.append(StoryArc(
                id=f"arc-{index}-{sequence.id}",
                title=title,
                sequence_ids=[sequence.id],
                thread_ids=list(sequence.thread_ids),
                participants=list(sequence.participants),
                tension=sequence.tension,
                phase=phase,
                completion_signal=completion_signal,
                unresolved_questions=questions,
            ))
        return arcs

    def build(self, narrative: NarrativeState) -> tuple[list[NarrativeScene], list[NarrativeSequence], list[StoryArc]]:
        scenes=self.build_scenes(narrative)
        sequences=self.build_sequences(narrative,scenes)
        arcs=self.build_story_arcs(narrative,sequences)
        return scenes,sequences,arcs
