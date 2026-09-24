from engine.narrative.models import NarrativeBeat, NarrativeState, NarrativeThread
from engine.narrative.structure import NarrativeStructureBuilder


def make_state():
    return NarrativeState(
        beats=[
            NarrativeBeat("b1",1,"event",["e1"],["a","b"],0.2,"one"),
            NarrativeBeat("b2",2,"event",["e2"],["a","b"],0.5,"two"),
            NarrativeBeat("b3",5,"event",["e3"],["a","b"],0.7,"three"),
        ],
        threads=[
            NarrativeThread("t1","relationship","relationship",["a","b"],["e1","e2","e3"],0.5,"open","what next?"),
        ],
    )


def test_structure_builder_groups_close_shared_beats_into_scene():
    scenes= NarrativeStructureBuilder().build_scenes(make_state())
    assert len(scenes)==2
    assert scenes[0].beat_ids==["b1","b2"]
    assert scenes[0].start_tick==1 and scenes[0].end_tick==2


def test_structure_builder_splits_scene_without_actor_continuity():
    state=NarrativeState(beats=[
        NarrativeBeat("b1",1,"event",["e1"],["a"],0.2),
        NarrativeBeat("b2",2,"event",["e2"],["b"],0.5),
    ])
    scenes=NarrativeStructureBuilder().build_scenes(state)
    assert len(scenes)==2


def test_structure_builder_merges_scenes_into_sequence_by_thread():
    state=make_state()
    scenes=NarrativeStructureBuilder().build_scenes(state)
    sequences=NarrativeStructureBuilder().build_sequences(state,scenes)
    assert len(sequences)==1
    assert sequences[0].thread_ids==["t1"]
    assert sequences[0].unresolved_questions==["what next?"]


def test_structure_builder_keeps_distant_unrelated_sequences_separate():
    state=NarrativeState(
        beats=[
            NarrativeBeat("b1",1,"event",["e1"],["a"],0.2),
            NarrativeBeat("b2",10,"event",["e2"],["c"],0.2),
        ]
    )
    scenes=NarrativeStructureBuilder().build_scenes(state)
    sequences=NarrativeStructureBuilder().build_sequences(state,scenes)
    assert len(sequences)==2


def test_structure_builder_derives_story_arc_from_sequence():
    state=make_state()
    builder=NarrativeStructureBuilder()
    scenes=builder.build_scenes(state)
    sequences=builder.build_sequences(state,scenes)
    arcs=builder.build_story_arcs(state,sequences)
    assert len(arcs)==1
    assert arcs[0].thread_ids==["t1"]
    assert arcs[0].phase=="development"
    assert arcs[0].unresolved_questions==["what next?"]


def test_observer_now_exposes_story_structure():
    from engine.core.models import CharacterState, Consequence, Event, WorldState
    from engine.narrative.observer import NarrativeObserver
    state=WorldState(world_id="structure")
    state.add_character(CharacterState(id="a",name="A"))
    state.add_character(CharacterState(id="b",name="B"))
    event=Event("e1",1,"t","town",["a","b"],["choice"],["A meets B."],consequences=[Consequence("relationship","a:b","trust",50,60,"meeting")])
    state.event_log.append(event)
    narrative=NarrativeObserver().observe(state,[event])
    assert narrative.scenes
    assert narrative.sequences
    assert narrative.story_arcs
