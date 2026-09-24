from engine.core.demo import build_demo_world
from engine.core.models import Consequence, Event
from engine.narrative.observer import NarrativeObserver


def test_narrative_observer_detects_state_change() -> None:
    world = build_demo_world()
    event = Event(
        id="e1",
        tick=0,
        timestamp=world.timestamp,
        location="town",
        participants=["lin", "mei"],
        causes=["a1"],
        facts=["Lin speaks with Mei at town."],
        consequences=[
            Consequence("relationship", "lin:mei", "trust", 40.0, 42.0, "contact"),
            Consequence("relationship", "lin:mei", "affection", 50.0, 51.0, "contact"),
        ],
    )

    narrative = NarrativeObserver().observe(world, [event])

    assert narrative.signals[0].signal_type == "state_change"
    assert narrative.beats[0].description == "Lin speaks with Mei at town."
    assert narrative.pressure > 0
