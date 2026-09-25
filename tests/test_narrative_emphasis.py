from engine.core.models import CharacterState, Consequence, Event, RelationshipState, WorldState
from engine.memory.kernel import MemoryKernel
from engine.narrative.convergence import ThreadConvergenceDetector
from engine.narrative.foreshadowing import ForeshadowingTracker
from engine.narrative.importance import NarrativeImportanceAnalyzer
from engine.narrative.models import NarrativeThread


def _event(event_id,tick,participants=("a","b"),field="trust"):
    return Event(event_id,tick,f"t{tick}","town",list(participants),[f"choice-{tick}"],["event"],consequences=[Consequence("relationship","a:b",field,50,60,"change")])


def test_narrative_importance_can_diverge_from_historical_size():
    state=WorldState(world_id="importance")
    state.add_character(CharacterState(id="a",name="A"))
    state.add_character(CharacterState(id="b",name="B"))
    e1=_event("e1",1)
    e2=_event("e2",2,participants=("a",),field="identity_beliefs.reliable")
    state.event_log.extend([e1,e2,_event("e3",3)])
    scores={item.event_id:item for item in NarrativeImportanceAnalyzer().score(state)}
    assert scores["e2"].narrative_score != scores["e2"].historical_size
    assert scores["e2"].description


def test_thread_convergence_detects_shared_participant():
    threads=[
        NarrativeThread("t1","relationship","one",["a","b"],["e1"],0.5),
        NarrativeThread("t2","goal","two",["a","c"],["e2"],0.4),
    ]
    result=ThreadConvergenceDetector().detect(threads,{"e1":1,"e2":3})
    assert len(result)==1
    assert "a" in result[0].participants
    assert result[0].strength>0.5


def test_thread_convergence_allows_close_timing_without_shared_actor():
    threads=[
        NarrativeThread("t1","relationship","one",["a"],["e1"],0.5),
        NarrativeThread("t2","goal","two",["b"],["e2"],0.4),
    ]
    result=ThreadConvergenceDetector().detect(threads,{"e1":10,"e2":15})
    assert result


def test_foreshadowing_tracker_links_reused_causal_state_keys():
    state=WorldState(world_id="foreshadow")
    state.add_character(CharacterState(id="a",name="A"))
    state.add_character(CharacterState(id="b",name="B"))
    state.event_log.extend([_event("e1",1,field="trust"),_event("e2",4,field="trust")])
    links=ForeshadowingTracker().detect(state)
    assert links
    assert links[0].setup_event_id=="e1"
    assert links[0].payoff_event_id=="e2"
    assert links[0].confidence>0


def test_foreshadowing_does_not_claim_intent():
    state=WorldState(world_id="foreshadow")
    state.add_character(CharacterState(id="a",name="A"))
    state.add_character(CharacterState(id="b",name="B"))
    state.event_log.extend([_event("e1",1),_event("e2",30)])
    assert ForeshadowingTracker().detect(state)==[]
