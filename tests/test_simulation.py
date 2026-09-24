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


def test_simulation_records_structured_memories_for_participants() -> None:
    world = build_demo_world()
    world.characters["lin"].relationships["mei"] = 40.0
    world.characters["mei"].relationships["lin"] = 50.0
    world.characters["lin"].goals[0].priority = 0.2
    world.characters["mei"].goals[0].priority = 0.2
    world.add_relationship(RelationshipState("lin", "mei", trust=40.0))
    result = SimulationEngine(seed=42).step(world)
    assert result.events
    assert world.memory_state.memories
    assert world.characters["lin"].memory_ids
    memory = world.memory_state.memories[world.characters["lin"].memory_ids[0]]
    assert memory.owner_id == "lin"
    assert memory.event_id == result.events[0].id


def test_authoritative_relationship_is_used_for_action_scoring() -> None:
    world = build_demo_world()
    world.characters["lin"].relationships["mei"] = 99.0
    world.add_relationship(RelationshipState("lin", "mei", trust=10.0))
    pool = __import__("engine.core.actions", fromlist=["generate_action_pool"]).generate_action_pool(world, "lin")
    contact = next(action for action in pool if action.action_type == "contact_person")
    assert contact.score == 0.9


def test_decision_kernel_uses_character_state_not_narrative_outcomes() -> None:
    from engine.core.actions import ActionCandidate
    from engine.core.decision import DecisionKernel
    world = build_demo_world()
    world.characters["lin"].goals[0].priority = 0.1
    pool = [
        ActionCandidate("a", "lin", "pursue_goal", motivation="find a missing friend", confidence=0.8),
        ActionCandidate("b", "lin", "rest", motivation="rest", confidence=0.8),
    ]
    chosen, evaluations = DecisionKernel(seed=42).choose(world, pool)
    assert chosen is not None
    assert {item.action_id for item in evaluations} == {"a", "b"}


def test_blocked_travel_does_not_change_character_location() -> None:
    from engine.core.models import ActionCandidate
    world = build_demo_world()
    actor = world.characters["mei"]
    action = ActionCandidate("bad-travel", actor.id, "travel", targets=["unknown-place"], confidence=1.0)
    events = SimulationEngine(seed=42).resolve(world, [action])
    assert actor.location == "town"
    assert events[0].action_result is not None
    assert events[0].action_result.status == "blocked"
    assert events[0].consequences == []


def test_blocked_contact_is_explicit() -> None:
    from engine.core.models import ActionCandidate
    world = build_demo_world()
    world.characters["mei"].location = "elsewhere"
    action = ActionCandidate("contact", "lin", "contact_person", targets=["mei"], confidence=1.0)
    events = SimulationEngine(seed=42).resolve(world, [action])
    assert events[0].action_result is not None
    assert events[0].action_result.status == "blocked"
    assert events[0].consequences == []
