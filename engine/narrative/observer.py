"""Narrative observation for the first autonomous-fiction prototype."""

from __future__ import annotations

from .arcs import CharacterArcDetector
from .dilemma import DilemmaDetector
from .information import KnowledgeAsymmetryAnalyzer, RevelationDetector
from .convergence import ThreadConvergenceDetector
from .foreshadowing import ForeshadowingTracker
from .importance import NarrativeImportanceAnalyzer
from .threads import CausalThreadEngine
from .models import NarrativeBeat, NarrativeSignal, NarrativeState
from .structure import NarrativeStructureBuilder
from .rhythm import NarrativeRhythmAnalyzer
from ..core.models import Event, WorldState


class NarrativeObserver:
    """Detect tension and story-bearing changes without forcing a plot."""

    def __init__(
        self,
        dilemma_detector: DilemmaDetector | None = None,
        rhythm_analyzer: NarrativeRhythmAnalyzer | None = None,
        thread_engine: CausalThreadEngine | None = None,
        arc_detector: CharacterArcDetector | None = None,
        knowledge_analyzer: KnowledgeAsymmetryAnalyzer | None = None,
        revelation_detector: RevelationDetector | None = None,
        importance_analyzer: NarrativeImportanceAnalyzer | None = None,
        convergence_detector: ThreadConvergenceDetector | None = None,
        foreshadowing_tracker: ForeshadowingTracker | None = None,
        structure_builder: NarrativeStructureBuilder | None = None,
    ) -> None:
        self.dilemma_detector = dilemma_detector or DilemmaDetector()
        self.rhythm_analyzer = rhythm_analyzer or NarrativeRhythmAnalyzer()
        self.thread_engine = thread_engine or CausalThreadEngine()
        self.arc_detector = arc_detector or CharacterArcDetector()
        self.knowledge_analyzer = knowledge_analyzer or KnowledgeAsymmetryAnalyzer()
        self.revelation_detector = revelation_detector or RevelationDetector()
        self.importance_analyzer = importance_analyzer or NarrativeImportanceAnalyzer()
        self.convergence_detector = convergence_detector or ThreadConvergenceDetector()
        self.foreshadowing_tracker = foreshadowing_tracker or ForeshadowingTracker()
        self.structure_builder = structure_builder or NarrativeStructureBuilder()

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
        threads = self.thread_engine.discover(state, events)
        arcs = self.arc_detector.detect(state, events)
        information_gaps = self.knowledge_analyzer.analyze(state)
        revelations = self.revelation_detector.detect(state, information_gaps)
        importance = self.importance_analyzer.score(state, events)
        event_ticks = {event.id: event.tick for event in state.event_log}
        event_ticks.update({event.id: event.tick for event in events})
        convergences = self.convergence_detector.detect(threads, event_ticks)
        foreshadowing = self.foreshadowing_tracker.detect(state)

        narrative_state = NarrativeState(
            pressure=pressure,
            recent_climax_tick=climax_tick,
            signals=signals,
            beats=beats,
            dilemmas=dilemmas,
            rhythm=rhythm,
            threads=threads,
            arcs=arcs,
            information_gaps=information_gaps,
            revelations=revelations,
            unresolved_threads=[thread for thread in threads if thread.status == "open"],
            importance=importance,
            convergences=convergences,
            foreshadowing=foreshadowing,
        )

        scenes, sequences, story_arcs = self.structure_builder.build(narrative_state)
        narrative_state.scenes = scenes
        narrative_state.sequences = sequences
        narrative_state.story_arcs = story_arcs
        return narrative_state
