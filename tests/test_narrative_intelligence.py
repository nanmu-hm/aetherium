from engine.core.actions import ActionCandidate
from engine.core.human_condition import HumanCondition
from engine.core.models import CharacterState, Consequence, Event, RelationshipState, WorldState
from engine.narrative.dilemma import DilemmaDetector
from engine.narrative.observer import NarrativeObserver
from engine.narrative.rhythm import NarrativeRhythmAnalyzer


def test_dilemma_detector_finds_competing_value_choices():
    state = WorldState(world_id="dilemma", locations={"town", "road"})
    state.add_character(
        CharacterState(
            id="lin",
            name="Lin",
            location="town",
            values=["freedom", "loyalty"],
        )
    )
    state.add_character(CharacterState(id="mei", name="Mei", location="town"))
    state.add_relationship(RelationshipState("lin", "mei", trust=50.0))

    actions = [
        ActionCandidate("travel", "lin", "travel", targets=["road"], confidence=0.8),
        ActionCandidate(
            "contact",
            "lin",
            "contact_person",
            targets=["mei"],
            confidence=0.8,
        ),
    ]

    dilemmas = DilemmaDetector().detect(state, {"lin": actions})

    assert len(dilemmas) == 1
    assert dilemmas[0].action_ids == ["travel", "contact"]
    assert dilemmas[0].competing_values == ["freedom", "loyalty"]
    assert dilemmas[0].strength > 0.0
    assert dilemmas[0].utility_gap <= 0.30


def test_dilemma_detector_ignores_far_apart_choices():
    state = WorldState(world_id="dilemma", locations={"town", "road"})
    state.add_character(
        CharacterState(
            id="lin",
            name="Lin",
            location="town",
            values=["freedom", "loyalty"],
            emotions={"fear": 100.0},
        )
    )
    actions = [
        ActionCandidate("travel", "lin", "travel", targets=["road"], confidence=0.8),
        ActionCandidate("contact", "lin", "contact_person", targets=["ghost"], confidence=0.1),
    ]

    dilemmas = DilemmaDetector().detect(state, {"lin": actions})

    assert dilemmas == []


def test_rhythm_analyzer_detects_rising_pressure_and_peak():
    state = WorldState(world_id="rhythm")
    state.add_character(CharacterState(id="a", name="A"))
    state.add_character(CharacterState(id="b", name="B"))

    for tick, trust in [(1, 45), (2, 20), (3, 0)]:
        state.event_log.append(
            Event(
                id=f"e{tick}",
                tick=tick,
                timestamp=f"0001-01-0{tick + 1}T00:00:00",
                location="town",
                participants=["a", "b"],
                causes=[f"choice-{tick}"],
                facts=[f"pressure event {tick}"],
                consequences=[
                    Consequence(
                        "relationship",
                        "a:b",
                        "resentment",
                        0,
                        100 - trust,
                        "rising conflict",
                    )
                ],
            )
        )

    rhythm = NarrativeRhythmAnalyzer().analyze(state, [])
    assert rhythm.trend == "rising"
    assert rhythm.phase == "peak"
    assert rhythm.pressure >= 0.70


def test_rhythm_requests_breathing_after_sustained_pressure():
    state = WorldState(world_id="rhythm")
    state.add_character(
        CharacterState(
            id="a",
            name="A",
            human_condition=HumanCondition(desires={"responsibility": 100}),
        )
    )

    for tick in range(1, 4):
        state.event_log.append(
            Event(
                id=f"e{tick}",
                tick=tick,
                timestamp=f"0001-01-0{tick + 1}T00:00:00",
                location="town",
                participants=["a"],
                causes=[f"choice-{tick}"],
                facts=["pressure"],
                consequences=[
                    Consequence("character", "a", "reputation", 50, 20, "cost"),
                    Consequence("character", "a", "fear", 0, 20, "pressure"),
                ],
            )
        )

    rhythm = NarrativeRhythmAnalyzer().analyze(state, [])
    assert rhythm.high_pressure_streak == 3
    assert rhythm.breathing_needed


def test_observer_exposes_dilemmas_and_rhythm_without_mutating_world():
    state = WorldState(world_id="observer")
    state.add_character(CharacterState(id="a", name="A"))
    event = Event(
        id="e1",
        tick=1,
        timestamp="0001-01-02T00:00:00",
        location="town",
        participants=["a"],
        causes=["choice:a"],
        facts=["A chooses."],
        consequences=[
            Consequence("character", "a", "reputation", 50, 40, "cost"),
        ],
    )

    before_tick = state.tick
    narrative = NarrativeObserver().observe(state, [event])

    assert narrative.rhythm.phase in {"calm", "steady", "build", "peak", "release", "recovery"}
    assert state.tick == before_tick
