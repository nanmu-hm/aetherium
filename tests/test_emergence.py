from engine.core.human_condition import HumanCondition
from engine.core.models import CharacterState, Consequence, Event, RelationshipState, WorldState
from engine.narrative import NarrativePressureAnalyzer, StoryArchaeologist


def test_human_condition_is_pressure_not_plot():
    condition = HumanCondition(
        attachments={"family": 90},
        desires={"reconciliation": 80},
        fears={"loss": 70},
        virtues={"loyalty": 95},
    )
    assert 0.0 < condition.pressure() <= 1.0
    assert condition.attachment_strength() == 0.9
    assert condition.virtue_strength() == 0.95


def test_pressure_uses_existing_world_state():
    state = WorldState(world_id="test")
    state.add_character(
        CharacterState(
            id="a",
            name="A",
            human_condition=HumanCondition(
                attachments={"friend": 90},
                desires={"help": 90},
                fears={"loss": 80},
            ),
        )
    )
    state.add_character(CharacterState(id="b", name="B"))
    state.add_relationship(
        RelationshipState(source_id="a", target_id="b", resentment=80, rivalry=50)
    )
    event = Event(
        id="e1",
        tick=1,
        timestamp="0001-01-02T00:00:00",
        location="town",
        participants=["a", "b"],
        causes=["choice:a"],
        facts=["A chose to help B despite their conflict."],
        consequences=[
            Consequence(
                target_type="character",
                target_id="a",
                field="reputation",
                old_value=50,
                new_value=20,
                reason="The choice was publicly condemned.",
            )
        ],
    )
    state.event_log.append(event)

    score = NarrativePressureAnalyzer().score_event(state, event)
    assert score > 0.0


def test_story_archaeologist_discovers_persistent_thread():
    state = WorldState(world_id="test")
    state.add_character(CharacterState(id="a", name="A"))
    state.add_character(CharacterState(id="b", name="B"))
    state.event_log.extend(
        Event(
            id=f"e{i}",
            tick=i,
            timestamp=f"0001-01-0{i + 1}T00:00:00",
            location="town",
            participants=["a", "b"],
            causes=["choice:a"],
            facts=[f"Consequence {i}"],
            consequences=[
                Consequence(
                    target_type="character",
                    target_id="a",
                    field="reputation",
                    old_value=i,
                    new_value=i + 1,
                    reason="Persistent change",
                )
            ],
        )
        for i in range(1, 4)
    )

    candidates = StoryArchaeologist().discover(state, min_score=0.1)
    assert candidates
    assert candidates[0].event_ids
    assert candidates[0].participants == ["a", "b"]
