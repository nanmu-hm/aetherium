from engine.core.models import CharacterState, Event, WorldState
from engine.narrative.boundary import StoryBoundaryDetector
from engine.narrative.discovery import LongHistoryStoryDiscovery
from engine.narrative.models import NarrativeImportance, NarrativeScene, NarrativeState, NarrativeSequence, InformationGap
from engine.narrative.reader import ReaderKnowledgePlanner


def state_with_events():
    state = WorldState(world_id="discover")
    state.locations.update({"town", "road"})
    state.add_character(CharacterState(id="a", name="A"))
    state.add_character(CharacterState(id="b", name="B"))
    state.event_log.extend([
        Event("e1", 1, "t1", "town", ["a"], [], ["A waits."]),
        Event("e2", 2, "t2", "town", ["a"], ["e1"], ["A decides."]),
        Event("e3", 12, "t12", "road", ["b"], [], ["B travels."]),
    ])
    return state


def test_story_boundary_detects_temporal_and_participant_break():
    state = state_with_events()
    narrative = NarrativeState(
        importance=[
            NarrativeImportance("e2", narrative_score=0.8),
            NarrativeImportance("e3", narrative_score=0.2),
        ],
    )
    boundaries = StoryBoundaryDetector().detect(state, narrative)
    assert boundaries
    assert boundaries[-1].start_event_id == "e2"
    assert boundaries[-1].end_event_id == "e3"
    assert boundaries[-1].confidence >= 0.5


def test_long_history_discovery_returns_nonduplicate_candidates():
    state = WorldState(world_id="long")
    state.locations.add("town")
    state.add_character(CharacterState(id="a", name="A"))
    for tick in range(1, 45):
        state.event_log.append(Event(f"e{tick}", tick, f"t{tick}", "town", ["a"], [], [f"A acts {tick}."]))
    found = LongHistoryStoryDiscovery(window_size=16, overlap=4).discover(state, min_score=0.25)
    assert found
    ids = [tuple(item.event_ids) for item in found]
    assert len(ids) == len(set(ids))


def test_reader_knowledge_planner_marks_grounded_reveal():
    narrative = NarrativeState(
        scenes=[NarrativeScene("s1", ["b1"], ["e1"], ["a"], 1, 1, 0.5)],
        information_gaps=[InformationGap("g1", "A knows the gate is closed", ["e1"], ["a"], ["b"], (1.0, 1.0), 0.8)],
    )
    plans = ReaderKnowledgePlanner().plan(narrative)
    assert plans[0].mode == "reveal"
    assert plans[0].reveal_event_ids == ["e1"]


def test_reader_knowledge_planner_can_mark_dramatic_irony():
    narrative = NarrativeState(
        scenes=[NarrativeScene("s1", ["b1"], ["e2"], ["a"], 1, 1, 0.5)],
        information_gaps=[InformationGap("g1", "A knows the truth", ["e1"], ["a"], ["b"], (1.0, 1.0), 0.8)],
    )
    plans = ReaderKnowledgePlanner().plan(narrative)
    assert plans[0].mode == "discover"
    narrative.scenes.append(NarrativeScene("s2", ["b2"], ["e1"], ["a"], 2, 2, 0.5))
    plans = ReaderKnowledgePlanner().plan(narrative)
    assert any(item.mode in {"reveal", "dramatic_irony"} for item in plans)
