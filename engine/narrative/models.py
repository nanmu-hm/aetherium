"""Narrative-layer data models.

The narrative layer observes simulation history. It does not mutate world state.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NarrativeSignal:
    """A detected condition that may matter to a future story."""

    signal_type: str
    strength: float
    participants: list[str] = field(default_factory=list)
    source_event_ids: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class NarrativeThread:
    """A persistent thread tracked across otherwise independent events."""

    id: str
    thread_type: str
    title: str
    participants: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    tension: float = 0.0
    status: str = "open"
    unresolved_question: str = ""


@dataclass
class InformationGap:
    """A proposition known by some characters but not others."""

    id: str
    proposition: str
    source_event_ids: list[str] = field(default_factory=list)
    known_by: list[str] = field(default_factory=list)
    unknown_by: list[str] = field(default_factory=list)
    confidence_range: tuple[float, float] = (0.0, 0.0)
    strength: float = 0.0
    description: str = ""


@dataclass
class RevelationCandidate:
    """A causally grounded opportunity for one character to learn an asymmetric fact."""

    id: str
    proposition: str
    source_character_id: str
    target_character_id: str
    source_event_id: str | None = None
    confidence: float = 0.0
    strength: float = 0.0
    reason: str = ""


@dataclass
class CharacterArc:
    """A derived trajectory from persistent character changes."""

    id: str
    character_id: str
    event_ids: list[str] = field(default_factory=list)
    identity_changes: list[str] = field(default_factory=list)
    emotional_changes: list[str] = field(default_factory=list)
    goal_changes: list[str] = field(default_factory=list)
    relationship_changes: list[str] = field(default_factory=list)
    change_score: float = 0.0
    phase: str = "stable"
    description: str = ""


@dataclass
class NarrativeImportance:
    """Derived importance of an event to an emerging story."""

    event_id: str
    historical_size: float = 0.0
    narrative_score: float = 0.0
    pressure_factor: float = 0.0
    relationship_factor: float = 0.0
    character_change_factor: float = 0.0
    information_factor: float = 0.0
    causal_reach_factor: float = 0.0
    description: str = ""


@dataclass
class ThreadConvergence:
    """A derived point where previously separate threads begin to interact."""

    id: str
    thread_ids: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    strength: float = 0.0
    description: str = ""


@dataclass
class ForeshadowingLink:
    """A candidate setup/callback relation discovered after both events exist."""

    setup_event_id: str
    payoff_event_id: str
    shared_keys: list[str] = field(default_factory=list)
    confidence: float = 0.0
    causal: bool = False
    description: str = ""


@dataclass
class NarrativeDilemma:
    """A derived conflict between viable actions aligned with different values."""

    id: str
    character_id: str
    action_ids: list[str] = field(default_factory=list)
    competing_values: list[str] = field(default_factory=list)
    strength: float = 0.0
    utility_gap: float = 0.0
    description: str = ""


@dataclass
class RhythmState:
    """Derived narrative rhythm; it never changes authoritative world state."""

    phase: str = "calm"
    pressure: float = 0.0
    previous_pressure: float = 0.0
    trend: str = "flat"
    breathing_needed: bool = False
    high_pressure_streak: int = 0


@dataclass
class NarrativeBeat:
    """A compact story unit selected from simulation history."""

    id: str
    tick: int
    beat_type: str
    event_ids: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    pressure: float = 0.0
    description: str = ""


@dataclass
class NarrativeScene:
    """A contiguous group of beats that can be staged as one scene."""

    id: str
    beat_ids: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    start_tick: int = 0
    end_tick: int = 0
    pressure: float = 0.0
    dominant_beat_type: str = "event"


@dataclass
class NarrativeSequence:
    """A connected run of scenes sharing a causal or relational concern."""

    id: str
    scene_ids: list[str] = field(default_factory=list)
    thread_ids: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    tension: float = 0.0
    status: str = "open"
    unresolved_questions: list[str] = field(default_factory=list)


@dataclass
class StoryArc:
    """A discovered story-scale arc derived from sequences and threads."""

    id: str
    title: str
    sequence_ids: list[str] = field(default_factory=list)
    thread_ids: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    tension: float = 0.0
    phase: str = "emerging"
    completion_signal: float = 0.0
    unresolved_questions: list[str] = field(default_factory=list)


@dataclass
class NarrativeTreatment:
    """How much narrative attention a scene should receive."""

    scene_id: str
    mode: str = "summarize"
    attention: float = 0.0
    reason: str = ""


@dataclass
class CallbackSchedule:
    """A delayed callback candidate grounded in an existing setup/payoff link."""

    setup_event_id: str
    payoff_event_id: str
    priority: float = 0.0
    minimum_gap: int = 0
    maximum_gap: int = 0
    status: str = "eligible"
    reason: str = ""


@dataclass
class ArcInterleaveSlot:
    """One planned narrative slot in a multi-arc reading order."""

    arc_id: str
    sequence_id: str
    rank: int = 0
    reason: str = ""


@dataclass
class StoryCompletionAssessment:
    """Evidence-based assessment of whether an observed arc has ended."""

    arc_id: str
    status: str = "open"
    confidence: float = 0.0
    resolved_thread_count: int = 0
    unresolved_question_count: int = 0
    payoff_count: int = 0
    reason: str = ""

@dataclass
class LiteraryExpressionState:
    register: str = "natural"
    cultural_texture: str = "grounded"
    narrative_distance: str = "close"
    default_viewpoint: str = "limited"
    sentence_cadence: str = "varied"
    dialogue_density: float = 0.45
    emotional_explicitness: float = 0.45
    sensory_detail: float = 0.50
    exposition_density: float = 0.40
    omission_strength: float = 0.45
    humor_level: float = 0.10


@dataclass
class CharacterVoiceProfile:
    character_id: str
    register: str = "natural"
    sentence_length: str = "medium"
    directness: float = 0.50
    emotional_restraint: float = 0.50
    vocabulary_keys: list[str] = field(default_factory=list)
    habitual_phrases: list[str] = field(default_factory=list)
    dialogue_density: float = 0.50


@dataclass
class MotifObservation:
    motif: str
    event_ids: list[str] = field(default_factory=list)
    occurrence_count: int = 0
    contexts: list[str] = field(default_factory=list)
    resonance: float = 0.0


@dataclass
class SceneExpressionPlan:
    scene_id: str
    viewpoint_character_id: str | None = None
    narrative_distance: str = "close"
    dialogue_density: float = 0.45
    emotional_explicitness: float = 0.45
    sensory_detail: float = 0.50
    exposition_density: float = 0.40
    subtext_strength: float = 0.45
    omission_strength: float = 0.45
    cadence: str = "varied"
    motif_ids: list[str] = field(default_factory=list)
    emphasis_mode: str = "summarize"
    reason: str = ""


@dataclass
class ProseQualityReport:
    factual_fidelity: bool = True
    viewpoint_consistency: bool = True
    temporal_consistency: bool = True
    spatial_consistency: bool = True
    participant_consistency: bool = True
    knowledge_consistency: bool = True
    score: float = 1.0
    failures: list[str] = field(default_factory=list)


@dataclass
class NarrativeState:
    """Derived narrative observations; safe to recompute from the event log."""

    pressure: float = 0.0
    recent_climax_tick: int | None = None
    unresolved_threads: list[NarrativeThread] = field(default_factory=list)
    signals: list[NarrativeSignal] = field(default_factory=list)
    beats: list[NarrativeBeat] = field(default_factory=list)
    dilemmas: list[NarrativeDilemma] = field(default_factory=list)
    rhythm: RhythmState = field(default_factory=RhythmState)
    threads: list[NarrativeThread] = field(default_factory=list)
    arcs: list[CharacterArc] = field(default_factory=list)
    information_gaps: list[InformationGap] = field(default_factory=list)
    revelations: list[RevelationCandidate] = field(default_factory=list)
    importance: list[NarrativeImportance] = field(default_factory=list)
    convergences: list[ThreadConvergence] = field(default_factory=list)
    foreshadowing: list[ForeshadowingLink] = field(default_factory=list)
    scenes: list[NarrativeScene] = field(default_factory=list)
    sequences: list[NarrativeSequence] = field(default_factory=list)
    story_arcs: list[StoryArc] = field(default_factory=list)
    treatments: list[NarrativeTreatment] = field(default_factory=list)
    callback_schedules: list[CallbackSchedule] = field(default_factory=list)
    interleave_slots: list[ArcInterleaveSlot] = field(default_factory=list)
    completion: list[StoryCompletionAssessment] = field(default_factory=list)
    literary: LiteraryExpressionState = field(default_factory=LiteraryExpressionState)
    character_voices: list[CharacterVoiceProfile] = field(default_factory=list)
    motifs: list[MotifObservation] = field(default_factory=list)
    scene_expression: list[SceneExpressionPlan] = field(default_factory=list)
    story_boundaries: list[StoryBoundaryCandidate] = field(default_factory=list)
    story_discoveries: list[StoryDiscoveryCandidate] = field(default_factory=list)
    reader_knowledge: list[ReaderKnowledgePlan] = field(default_factory=list)
    rhythm_plans: list[SentenceRhythmPlan] = field(default_factory=list)
    literary_profiles: list[LiteraryMechanismProfile] = field(default_factory=list)


@dataclass
class StoryBoundaryCandidate:
    start_event_id: str
    end_event_id: str
    confidence: float = 0.0
    reason: str = ""


@dataclass
class StoryDiscoveryCandidate:
    event_ids: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    score: float = 0.0
    title: str = ""
    reason: str = ""


@dataclass
class ReaderKnowledgePlan:
    scene_id: str
    reveal_event_ids: list[str] = field(default_factory=list)
    withheld_propositions: list[str] = field(default_factory=list)
    dramatic_irony: list[str] = field(default_factory=list)
    mode: str = "discover"
    reason: str = ""


@dataclass
class SentenceRhythmPlan:
    scene_id: str
    pace: str = "medium"
    sentence_length_mix: str = "medium"
    variation: float = 0.50
    punctuation_density: float = 0.45
    pause_strength: float = 0.45
    paragraph_breathing: float = 0.50
    reason: str = ""


@dataclass
class LiteraryMechanismProfile:
    id: str
    title: str
    mechanisms: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    intended_effects: list[str] = field(default_factory=list)
    compatible_dimensions: list[str] = field(default_factory=list)
