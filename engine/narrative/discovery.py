from __future__ import annotations

from .archaeologist import StoryArchaeologist
from .models import StoryDiscoveryCandidate
from ..core.models import Event, WorldState


class LongHistoryStoryDiscovery:
    def __init__(self, archaeologist: StoryArchaeologist | None = None, window_size: int = 32, overlap: int = 8) -> None:
        self.archaeologist = archaeologist or StoryArchaeologist()
        self.window_size = window_size
        self.overlap = overlap

    @staticmethod
    def _overlap(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left.intersection(right)) / len(left.union(right))

    def discover(self, state: WorldState, min_score: float = 0.35) -> list[StoryDiscoveryCandidate]:
        candidates: list[StoryDiscoveryCandidate] = []
        windows = []
        events = sorted(state.event_log, key=lambda item: (item.tick, item.id))
        for start in range(0, len(events), max(1, self.window_size - self.overlap)):
            window = events[start:start + self.window_size]
            if not window:
                continue
            windows.append(window)
        for window in windows:
            window_ids = {event.id for event in window}
            scoped = WorldState(world_id=state.world_id, tick=state.tick, timestamp=state.timestamp)
            scoped.characters = state.characters
            scoped.relationships = state.relationships
            scoped.factions = state.factions
            scoped.locations = state.locations
            scoped.event_log = window
            found = self.archaeologist.discover(scoped, min_score=min_score)
            for item in found:
                event_ids = [event_id for event_id in item.event_ids if event_id in window_ids]
                candidate = StoryDiscoveryCandidate(
                    event_ids=event_ids,
                    participants=item.participants,
                    score=item.score,
                    title=(item.event_ids[0] if item.event_ids else "emerging-story"),
                    reason=item.reason + " Discovered within a long-history window.",
                )
                if candidate.event_ids:
                    candidates.append(candidate)
        candidates.sort(key=lambda item: (-item.score, -len(item.event_ids), item.event_ids[0]))
        result = []
        for candidate in candidates:
            if any(self._overlap(set(candidate.event_ids), set(existing.event_ids)) >= 0.80 for existing in result):
                continue
            result.append(candidate)
        return result
