from engine.core.models import CharacterState, Event, WorldState
from engine.narrative.literary import LiteraryExpressionPipeline
from engine.narrative.models import NarrativeScene, NarrativeState, SceneExpressionPlan
from engine.narrative.research import LiteraryResearchRegistry
from engine.narrative.rhythm import SentenceRhythmPlanner


def test_high_pressure_scene_gets_faster_sentence_rhythm():
    plans = SentenceRhythmPlanner().plan([
        SceneExpressionPlan("s1", narrative_distance="close", cadence="tight", omission_strength=0.20)
    ])
    assert plans[0].pace == "fast"
    assert plans[0].sentence_length_mix == "short-medium"
    assert plans[0].variation > 0.70


def test_reflective_scene_gets_longer_and_more_breathing_rhythm():
    plans = SentenceRhythmPlanner().plan([
        SceneExpressionPlan("s1", narrative_distance="moderate", cadence="measured", omission_strength=0.90)
    ])
    assert plans[0].pace == "slow"
    assert plans[0].sentence_length_mix == "medium-long"
    assert plans[0].paragraph_breathing > 0.70


def test_middle_pressure_scene_keeps_mixed_rhythm():
    plans = SentenceRhythmPlanner().plan([
        SceneExpressionPlan("s1", narrative_distance="close", cadence="varied", omission_strength=0.55)
    ])
    assert plans[0].pace == "medium"
    assert plans[0].sentence_length_mix == "short-medium-long"


def test_research_registry_returns_abstract_mechanisms():
    registry = LiteraryResearchRegistry()
    profile = registry.get("causal_foreshadowing")
    assert profile is not None
    assert "payoff through consequence" in profile.mechanisms
    assert "never invent prior evidence" in profile.constraints


def test_jianghu_profile_is_mechanism_based_not_style_imitation():
    profile = LiteraryResearchRegistry().get("jianghu_classic_mechanics")
    assert profile is not None
    assert "no author imitation" in profile.constraints
    assert "loyalty-versus-freedom tension" in profile.mechanisms


def test_literary_pipeline_exposes_rhythm_and_research_profiles():
    state = WorldState(world_id="pipeline")
    state.add_character(CharacterState(id="a", name="A"))
    state.event_log.append(Event("e1", 1, "t1", "town", ["a"], [], ["A waits."]))
    narrative = NarrativeState(
        scenes=[NarrativeScene("s1", ["b1"], ["e1"], ["a"], 1, 1, 0.8)],
        treatments=[],
    )
    result = LiteraryExpressionPipeline().build(state, narrative)
    assert result.rhythm_plans
    assert result.literary_profiles
    assert result.literary_profiles[0].mechanisms


def test_observer_builds_literary_control_layers():
    from engine.narrative.observer import NarrativeObserver
    state = WorldState(world_id="observer-literary")
    state.add_character(CharacterState(id="a", name="A"))
    state.event_log.append(Event("e1", 1, "t1", "town", ["a"], [], ["A waits."]))
    result = NarrativeObserver().observe(state, state.event_log)
    assert result.character_voices
    assert result.rhythm_plans
    assert result.literary_profiles
