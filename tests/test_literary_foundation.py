from engine.core.models import CharacterState, Event, WorldState
from engine.narrative.literary import LiteraryExpressionPipeline, LiteraryExpressionPlanner
from engine.narrative.models import LiteraryExpressionState, NarrativeImportance, NarrativeScene, NarrativeState, NarrativeTreatment
from engine.narrative.quality import ProseQualityGate


def make_state():
    state = WorldState(world_id="literary")
    state.locations.add("town")
    state.add_character(CharacterState(id="a", name="A", traits=["reserved", "formal"], values=["duty"]))
    state.add_character(CharacterState(id="b", name="B", traits=["blunt", "witty"], values=["freedom"]))
    state.event_log.append(Event("e1", 1, "t1", "town", ["a", "b"], [], ["A waits by the old gate."]))
    state.event_log.append(Event("e2", 2, "t2", "town", ["a", "b"], ["e1"], ["B returns to the old gate."]))
    return state


def test_voice_profiles_reflect_character_traits_and_values():
    profiles = LiteraryExpressionPlanner().build_voice_profiles(make_state())
    a = next(item for item in profiles if item.character_id == "a")
    b = next(item for item in profiles if item.character_id == "b")
    assert a.register == "formal"
    assert a.directness < b.directness
    assert "duty" in a.vocabulary_keys


def test_motifs_only_emerge_from_repeated_existing_material():
    motifs = LiteraryExpressionPlanner().discover_motifs(make_state())
    names = {item.motif for item in motifs}
    assert "gate" in names
    assert any(item.occurrence_count >= 2 for item in motifs if item.motif == "gate")


def test_scene_expression_uses_treatment_and_pressure():
    state = make_state()
    narrative = NarrativeState(
        literary=LiteraryExpressionState(dialogue_density=0.40),
        scenes=[NarrativeScene("s1", ["b1"], ["e1", "e2"], ["a", "b"], 1, 2, 0.80)],
        treatments=[NarrativeTreatment("s1", "slow_down", 0.9)],
        importance=[NarrativeImportance("e1", narrative_score=0.8), NarrativeImportance("e2", narrative_score=0.7)],
    )
    result = LiteraryExpressionPipeline().build(state, narrative)
    plan = result.scene_expression[0]
    assert plan.narrative_distance == "close"
    assert plan.emphasis_mode == "slow_down"
    assert plan.cadence == "tight"
    assert plan.viewpoint_character_id in {"a", "b"}


def test_scene_expression_respects_global_literary_identity():
    state = make_state()
    narrative = NarrativeState(
        literary=LiteraryExpressionState(
            narrative_distance="moderate",
            sentence_cadence="measured",
            sensory_detail=0.80,
            exposition_density=0.70,
        ),
        scenes=[NarrativeScene("s1", ["b1"], ["e1"], ["a", "b"], 1, 1, 0.20)],
    )
    result = LiteraryExpressionPipeline().build(state, narrative)
    plan = result.scene_expression[0]
    assert plan.narrative_distance == "moderate"
    assert plan.cadence == "measured"


def test_quality_gate_rejects_unknown_event_and_character():
    report = ProseQualityGate().validate(make_state(), ["e999"], "missing", ["ghost"])
    assert report.factual_fidelity is False
    assert report.viewpoint_consistency is False
    assert report.participant_consistency is False
    assert report.score < 1.0


def test_quality_gate_accepts_history_grounded_material():
    report = ProseQualityGate().validate(make_state(), ["e1", "e2"], "a", ["a", "b"])
    assert report.factual_fidelity
    assert report.viewpoint_consistency
    assert report.participant_consistency
    assert report.score == 1.0
