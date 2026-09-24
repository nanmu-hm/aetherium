"""Story archaeology: discover candidate story threads from world history."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.models import Event, WorldState
from .pressure import NarrativePressureAnalyzer


@dataclass
class StoryCandidate:
    """A historical thread that may deserve novel-level treatment."""

    event_ids: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    pressure: float = 0.0
    persistence: float = 0.0
    consequence_density: float = 0.0
    unresolved: bool = False
    score: float = 0.0
    reason: str = ""


class StoryArchaeologist:
    """Find story-bearing chains without rewriting simulation history."""

    def __init__(self, pressure: NarrativePressureAnalyzer | None = None) -> None:
        self.pressure = pressure or NarrativePressureAnalyzer()

    def discover(self, state: WorldState, min_score: float = 0.35) -> list[StoryCandidate]:
        if not state.event_log:
            return []

        scores = self.pressure.score_events(state, state.event_log)
        candidates: list[StoryCandidate] = []
        for index, event in enumerate(state.event_log):
            event_score = scores[event.id]
            if event_score < min_score:
                continue

            chain = [event]
            # Nearby events involving overlapping participants form a provisional
            # historical thread. We never reorder or mutate the source history.
            participant_set = set(event.participants)
            for previous in reversed(state.event_log[max(0, index - 6):index]):
                if participant_set.intersection(previous.participants):
                    chain.insert(0, previous)
                    participant_set.update(previous.participants)

            chain_scores = [scores[item.id] for item in chain]
            persistence = min(1.0, len(chain) / 5.0)
            consequence_density = min(
                1.0,
                sum(bool(item.consequences) for item in chain) / max(1, len(chain)),
            )
            unresolved = any(
                state.characters.get(character_id)
                and state.characters[character_id].status == "active"
                for character_id in participant_set
            )
            pressure = sum(chain_scores) / len(chain_scores)
            score = min(
                1.0,
                0.45 * pressure
                + 0.25 * persistence
                + 0.20 * consequence_density
                + 0.10 * float(unresolved),
            )
            if score < min_score:
                continue

            candidates.append(
                StoryCandidate(
                    event_ids=[item.id for item in chain],
                    participants=sorted(participant_set),
                    pressure=pressure,
                    persistence=persistence,
                    consequence_density=consequence_density,
                    unresolved=unresolved,
                    score=score,
                    reason="A persistent chain combines human pressure with consequential change.",
                )
            )

        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        return candidates
