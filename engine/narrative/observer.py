"""Narrative observation for the first autonomous-fiction prototype."""

from __future__ import annotations

from .dilemma import DilemmaDetector
from .models import NarrativeBeat, NarrativeSignal, NarrativeState
from .rhythm import NarrativeRhythmAnalyzer
from ..core.models import Event, WorldState


class NarrativeObserver:
    """Detect tension and story-bearing changes without forcing a plot."""

    def __init__(
        self,
        dilemma_detector: DilemmaDetector | None = None,
        rhythm_analyzer: NarrativeRhythmAnalyzer | None = None,
    ) -> None:
        self.dilemma_detector = dilemma_detector or DilemmaDetector()
        self.rhythm_analyzer = rhythm_analyzer or NarrativeRhythmAnalyzer()

    def observe(self, state: WorldState, events: list[Event]) -> NarrativeState:
        signals: list[NarrativeSignal] = []
        beats: list[NarrativeBeat] = []

        for event in events:
            consequence_count = len(event.consequences)
            participant_count = len(set(event.participants))
            strength = min(1.0, 0.25 * consequence_count + 0.15 * max(0, participant_count - 1))

            if consequence_count:
                signals.append(
                    NarrativeSignal(
                        signal_type="state_change",
                        strength=strength,
                        participants=event.participants,
                        source_event_ids=[event.id],
                        description="The event changed persistent world or relationship state.",
                    )
                )

            if participant_count >= 2:
                signals.append(
                    NarrativeSignal(
                        signal_type="relationship_or_conflict",
                        strength=min(1.0, 0.35 + 0.1 * participant_count),
                        participants=event.participants,
                        source_event_ids=[event.id],
                        description="Multiple actors were involved in one event.",
                    )
                )

            if event.facts:
                beats.append(
                    NarrativeBeat(
                        id=f"beat-{event.id}",
                        tick=event.tick,
                        beat_type="event",
                        event_ids=[event.id],
                        participants=event.participants,
                        pressure=strength,
                        description=event.facts[0],
                    )
                )

        recent = [beat.pressure for beat in beats[-5:]]
        pressure = min(1.0, (sum(recent) / len(recent)) if recent else 0.0)
        climax_tick = None
        if beats:
            strongest = max(beats, key=lambda beat: beat.pressure)
            if strongest.pressure >= 0.7:
                climax_tick = strongest.tick

        dilemmas = self.dilemma_detector.detect(state)
        rhythm = self.rhythm_analyzer.analyze(state, events)

        return NarrativeState(
            pressure=pressure,
            recent_climax_tick=climax_tick,
            signals=signals,
            beats=beats,
            dilemmas=dilemmas,
            rhythm=rhythm,
        )
