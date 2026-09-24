from engine.core.demo import build_demo_world, run_demo
from engine.core.models import RelationshipState
from engine.core.simulation import SimulationEngine


def test_demo_world_produces_history() -> None:
    world = run_demo(3)
    assert world.tick == 3
    assert len(world.event_log) == 6
    assert world.event_log[0].participants == ["lin"]


def test_same_location_contact_changes_relationship() -> None:
    world = build_demo_world()
    world.characters["lin"].relationships["mei"] = 40.0
    world.characters["mei"].relationships["lin"] = 50.0
    world.characters["lin"].goals[0].priority = 0.2
    world.characters["mei"].goals[0].priority = 0.2
    world.add_relationship(RelationshipState("lin", "mei", trust=40.0))
    result = SimulationEngine(seed=42).step(world)
    contact = next(event for event in result.events if event.causes[0].endswith("contact"))
    assert contact.facts == ["Lin speaks with Mei at town."]
    assert world.relationships["lin:mei"].trust == 42.0
    assert world.relationships["lin:mei"].affection == 51.0
    assert any(item.field == "trust" for item in contact.consequences)
