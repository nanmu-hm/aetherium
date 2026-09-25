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
        threads: list[list[Event]] = []

        # Build connected historical threads first. An event joins an existing
        # thread when it shares participants with recent history in that thread.
        # This produces one candidate for an underlying chain instead of one
        # candidate for every event inside the same chain.
        for event in state.event_log:
            event_participants = set(event.participants)
            selected_thread: list[Event] | None = None
            selected_distance = 7
            for thread in reversed(threads):
                if not thread:
                    continue
                distance = event.tick - thread[-1].tick
                if distance > 6:
                    break
                thread_participants = {
                    participant
                    for item in thread
                    for participant in item.participants
                }
                if event_participants.intersection(thread_participants):
                    if distance < selected_distance:
                        selected_thread = thread
                        selected_distance = distance
            if selected_thread is None:
                threads.append([event])
            else:
                selected_thread.append(event)

        candidates: list[StoryCandidate] = []
        for chain in threads:
            chain_scores = [scores[item.id] for item in chain]
            participant_set = {
                participant
                for item in chain
                for participant in item.participants
            }
            pressure = sum(chain_scores) / len(chain_scores)
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
                    reason=(
                        "A connected historical thread combines human pressure "
                        "with consequential change."
                    ),
                )
            )

        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        return candidates
