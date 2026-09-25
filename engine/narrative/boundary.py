from __future__ import annotations

from .models import NarrativeState, StoryBoundaryCandidate
from ..core.models import Event, WorldState


class StoryBoundaryDetector:
    def detect(self, state: WorldState, narrative: NarrativeState, max_gap: int = 8) -> list[StoryBoundaryCandidate]:
        events = sorted(state.event_log, key=lambda item: (item.tick, item.id))
        if len(events) < 2:
            return []
        pressures = {item.event_id: item.narrative_score for item in narrative.importance}
        sequence_by_event = {
            event_id: sequence.id
            for sequence in narrative.sequences
            for scene_id in sequence.scene_ids
            for scene in narrative.scenes
            if scene.id == scene_id
            for event_id in scene.event_ids
        }
        result = []
        for previous, current in zip(events, events[1:]):
            gap = current.tick - previous.tick
            shared = bool(set(previous.participants).intersection(current.participants))
            pressure_drop = pressures.get(previous.id, 0.0) - pressures.get(current.id, 0.0)
            sequence_break = (
                sequence_by_event.get(previous.id) is not None
                and sequence_by_event.get(current.id) is not None
                and sequence_by_event.get(previous.id) != sequence_by_event.get(current.id)
            )
            confidence = 0.0
            reasons = []
            if gap > max_gap:
                confidence += 0.45
                reasons.append("large temporal gap")
            if not shared:
                confidence += 0.20
                reasons.append("participant discontinuity")
            if pressure_drop >= 0.35:
                confidence += 0.20
                reasons.append("narrative pressure release")
            if sequence_break:
                confidence += 0.15
                reasons.append("sequence transition")
            if confidence >= 0.50:
                result.append(StoryBoundaryCandidate(
                    start_event_id=previous.id,
                    end_event_id=current.id,
                    confidence=min(1.0, confidence),
                    reason=", ".join(reasons),
                ))
        return result


class StoryWindowDetector:
    def windows(self, state: WorldState, window_size: int = 32, overlap: int = 8) -> list[list[Event]]:
        events = sorted(state.event_log, key=lambda item: (item.tick, item.id))
        if not events:
            return []
        step = max(1, window_size - overlap)
        return [events[start:start + window_size] for start in range(0, len(events), step) if events[start:start + window_size]]
