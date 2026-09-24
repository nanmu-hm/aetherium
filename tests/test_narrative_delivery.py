from engine.narrative.models import (
    ForeshadowingLink, NarrativeBeat, NarrativeImportance, NarrativeScene, NarrativeSequence, NarrativeThread, NarrativeState, RhythmState, StoryArc,
)
from engine.narrative.allocation import NarrativeResourceAllocator
from engine.narrative.callbacks import CallbackScheduler
from engine.narrative.completion import StoryCompletionDetector
from engine.narrative.interleave import MultiArcInterleaver


def test_resource_allocator_slows_down_high_value_scene():
    scenes=[NarrativeScene("s1",["b1"],["e1"],["a"],1,1,0.8)]
    importance=[NarrativeImportance("e1",0.2,0.9)]
    result=NarrativeResourceAllocator().allocate(scenes,importance,RhythmState(phase="steady"))
    assert result[0].mode=="slow_down"
    assert result[0].attention>0.7


def test_resource_allocator_uses_breathing_for_low_pressure_after_high_pressure():
    scenes=[NarrativeScene("s1",["b1"],["e1"],["a"],4,4,0.2)]
    result=NarrativeResourceAllocator().allocate(scenes,[NarrativeImportance("e1",0.1,0.2)],RhythmState(phase="recovery",breathing_needed=True))
    assert result[0].mode=="interiority"


def test_interleaver_switches_between_arcs_when_possible():
    sequences=[
        NarrativeSequence("s1",["sc1"],["a"],["x"],0.7),
        NarrativeSequence("s2",["sc2"],["b"],["y"],0.6),
        NarrativeSequence("s3",["sc3"],["a"],["x"],0.5),
    ]
    arcs=[
        StoryArc("a","A",["s1","s3"],["a"],["x"],0.7),
        StoryArc("b","B",["s2"],["b"],["y"],0.6),
    ]
    slots=MultiArcInterleaver().plan(arcs,sequences,max_consecutive=1)
    assert [slot.arc_id for slot in slots]==["a","b","a"]


def test_callback_scheduler_keeps_payoff_timing_flexible():
    links=[ForeshadowingLink("e1","e8",["relationship:a:b"],0.9,True)]
    result=CallbackScheduler().schedule(links)
    assert result[0].priority>0.7
    assert result[0].minimum_gap==2
    assert result[0].maximum_gap==12


def test_story_completion_needs_grounded_resolution_and_payoff():
    threads=[NarrativeThread("t1","goal","goal",["a"],["e1"],0.5,"resolved","")]
    sequences=[NarrativeSequence("s1",["sc1"],["t1"],["a"],0.4,"developing",[])]
    arcs=[StoryArc("a","Arc",["s1"],["t1"],["a"],0.4,"development",0.8,[])]
    complete=StoryCompletionDetector().assess(arcs,sequences,threads,{"e8"})
    assert complete[0].status=="complete"


def test_story_completion_stays_open_when_question_remains():
    threads=[NarrativeThread("t1","goal","goal",["a"],["e1"],0.5,"open","What next?")]
    sequences=[NarrativeSequence("s1",["sc1"],["t1"],["a"],0.4,"open",["What next?"])]
    arcs=[StoryArc("a","Arc",["s1"],["t1"],["a"],0.4,"development",0.2,["What next?"])]
    result=StoryCompletionDetector().assess(arcs,sequences,threads,set())
    assert result[0].status=="open"


def test_observer_exposes_resource_interleave_callback_and_completion_layers():
    from engine.core.models import CharacterState, Consequence, Event, WorldState
    from engine.narrative.observer import NarrativeObserver
    state=WorldState(world_id="observer")
    state.add_character(CharacterState(id="a",name="A"))
    state.add_character(CharacterState(id="b",name="B"))
    event=Event("e1",1,"t","town",["a","b"],["choice"],["A meets B."],consequences=[Consequence("relationship","a:b","trust",50,60,"meeting")])
    state.event_log.append(event)
    narrative=NarrativeObserver().observe(state,[event])
    assert narrative.treatments
    assert narrative.completion
    assert isinstance(narrative.interleave_slots,list)

