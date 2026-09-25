from __future__ import annotations

from collections import Counter

from .rhythm import SentenceRhythmPlanner
from .research import LiteraryResearchRegistry
from .models import (
    CharacterVoiceProfile,
    LiteraryExpressionState,
    MotifObservation,
    NarrativeImportance,
    NarrativeScene,
    NarrativeState,
    SceneExpressionPlan,
)
from ..core.models import WorldState


class LiteraryExpressionPlanner:
    def build_voice_profiles(self, state: WorldState) -> list[CharacterVoiceProfile]:
        result = []
        for character in sorted(state.characters.values(), key=lambda item: item.id):
            traits = {item.lower() for item in character.traits}
            values = {item.lower() for item in character.values}
            directness = 0.55
            restraint = 0.50
            register = "natural"
            length = "medium"
            if {"reserved", "quiet", "guarded"} & traits:
                directness -= 0.15
                restraint += 0.15
            if {"blunt", "frank", "direct"} & traits:
                directness += 0.20
                restraint -= 0.10
            if {"formal", "disciplined", "traditional"} & traits:
                register = "formal"
                length = "longer"
            if {"playful", "witty", "humorous"} & traits:
                directness += 0.05
            if {"honor", "duty", "loyalty"} & values:
                restraint += 0.05
            if {"curiosity", "freedom"} & values:
                length = "varied"
            result.append(CharacterVoiceProfile(
                character_id=character.id,
                register=register,
                sentence_length=length,
                directness=max(0.0, min(1.0, directness)),
                emotional_restraint=max(0.0, min(1.0, restraint)),
                vocabulary_keys=sorted(traits | values)[:8],
                dialogue_density=0.55 if character.goals else 0.45,
            ))
        return result

    def discover_motifs(self, state: WorldState) -> list[MotifObservation]:
        counts: Counter[str] = Counter()
        event_ids: dict[str, list[str]] = {}
        for event in state.event_log:
            for fact in event.facts:
                words = {word.strip(".,!?;:()[]{}").lower() for word in fact.split()}
                for word in words:
                    if len(word) >= 4:
                        counts[word] += 1
                        event_ids.setdefault(word, []).append(event.id)
        result = []
        for word, count in counts.most_common():
            if count < 2:
                continue
            result.append(MotifObservation(
                motif=word,
                event_ids=event_ids[word],
                occurrence_count=count,
                resonance=min(1.0, 0.20 * count),
            ))
        return result[:20]

    def plan_scenes(
        self,
        state: WorldState,
        narrative: NarrativeState,
        literary: LiteraryExpressionState,
        voices: list[CharacterVoiceProfile],
    ) -> list[SceneExpressionPlan]:
        importance = {item.event_id: item for item in narrative.importance}
        voice_by_id = {item.character_id: item for item in voices}
        result = []
        for scene in narrative.scenes:
            viewpoint = self._choose_viewpoint(scene, importance)
            voice = voice_by_id.get(viewpoint) if viewpoint else None
            treatment = next((item for item in narrative.treatments if item.scene_id == scene.id), None)
            pressure = scene.pressure
            if pressure >= 0.75:
                distance = "close"
                cadence = "tight"
            elif pressure <= 0.25:
                distance = "moderate"
                cadence = literary.sentence_cadence
            else:
                distance = literary.narrative_distance
                cadence = literary.sentence_cadence
            restraint = voice.emotional_restraint if voice else 0.50
            dialogue = literary.dialogue_density + (0.15 if len(scene.participants) >= 2 else 0.0)
            result.append(SceneExpressionPlan(
                scene_id=scene.id,
                viewpoint_character_id=viewpoint,
                narrative_distance=distance,
                dialogue_density=max(0.0, min(1.0, dialogue)),
                emotional_explicitness=max(0.0, min(1.0, literary.emotional_explicitness * (1.0 - restraint * 0.35))),
                sensory_detail=max(0.0, min(1.0, literary.sensory_detail + pressure * 0.15)),
                exposition_density=max(0.0, min(1.0, literary.exposition_density - pressure * 0.15)),
                subtext_strength=max(0.0, min(1.0, 0.40 + restraint * 0.40 + pressure * 0.10)),
                omission_strength=max(0.0, min(1.0, literary.omission_strength + restraint * 0.15)),
                cadence=cadence,
                emphasis_mode=treatment.mode if treatment else "summarize",
                reason="Expression follows observed pressure, treatment, and character voice.",
            ))
        return result

    @staticmethod
    def _choose_viewpoint(scene: NarrativeScene, importance: dict[str, NarrativeImportance]) -> str | None:
        if not scene.participants:
            return None
        scores = {participant: 0.0 for participant in scene.participants}
        for event_id in scene.event_ids:
            item = importance.get(event_id)
            if item:
                for participant in scene.participants:
                    scores[participant] += item.narrative_score
        return max(scene.participants, key=lambda participant: (scores[participant], participant))


class LiteraryExpressionPipeline:
    def __init__(
        self,
        planner: LiteraryExpressionPlanner | None = None,
        rhythm_planner: SentenceRhythmPlanner | None = None,
        research_registry: LiteraryResearchRegistry | None = None,
    ) -> None:
        self.planner = planner or LiteraryExpressionPlanner()
        self.rhythm_planner = rhythm_planner or SentenceRhythmPlanner()
        self.research_registry = research_registry or LiteraryResearchRegistry()

    def build(self, state: WorldState, narrative: NarrativeState) -> NarrativeState:
        voices = self.planner.build_voice_profiles(state)
        motifs = self.planner.discover_motifs(state)
        scene_expression = self.planner.plan_scenes(state, narrative, narrative.literary, voices)
        narrative.character_voices = voices
        narrative.motifs = motifs
        narrative.scene_expression = scene_expression
        narrative.rhythm_plans = self.rhythm_planner.plan(scene_expression)
        narrative.literary_profiles = self.research_registry.list()
        return narrative
