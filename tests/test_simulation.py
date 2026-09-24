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
    result = SimulationEngine(seed=1).step(world)
    contact = next(event for event in result.events if event.causes[0].endswith("contact"))
    assert contact.facts[0] == "Lin speaks with Mei at town."
    assert "Lin achieves the goal: find a missing friend." in contact.facts
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


def test_action_resolver_can_fail_and_is_seed_reproducible() -> None:
    from engine.core.models import ActionCandidate
    from engine.core.simulation import ActionResolver
    world = build_demo_world()
    action = ActionCandidate("hard", "mei", "travel", targets=["town"], confidence=0.1, difficulty=0.99)
    first = ActionResolver(__import__("random").Random(1)).resolve_outcome(world, action)
    second = ActionResolver(__import__("random").Random(1)).resolve_outcome(world, action)
    assert first.status == second.status
    assert first.probability == second.probability
    assert first.status == "failure"



def test_precondition_blocks_without_roll() -> None:
    from engine.core.models import ActionCandidate
    from engine.core.preconditions import PreconditionEngine
    world = build_demo_world()
    action = ActionCandidate("bad", "mei", "travel", targets=["missing-place"])
    result = PreconditionEngine().check(world, action)
    assert result.satisfied is False
    assert "does not exist" in result.reasons[0]


def test_successful_goal_action_marks_goal_achieved():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].goals[0].description = "help a friend"
    action = ActionCandidate(
        "help", "lin", "help_person", targets=["mei"], confidence=1.0, difficulty=0.1
    )
    events = SimulationEngine(seed=1).resolve(world, [action])
    assert world.characters["lin"].goals[0].status == "achieved"
    assert any(item.target_type == "goal" for item in events[0].consequences)


def test_achieved_goal_no_longer_generates_matching_help_action():
    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    pool = __import__("engine.core.actions", fromlist=["generate_action_pool"]).generate_action_pool(
        world, "lin"
    )
    assert not any(action.action_type == "help_person" for action in pool)


def test_repeated_successful_contact_gets_a_temporary_social_cooldown():
    from engine.core.actions import generate_action_pool
    from engine.core.models import Event, ActionResult

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    world.add_relationship(RelationshipState("lin", "mei", trust=60.0))

    world.event_log.extend(
        [
            Event(
                id="contact-1",
                tick=1,
                timestamp="0001-01-02T00:00:00",
                location="town",
                participants=["lin", "mei"],
                causes=["tick-1-lin-contact"],
                facts=["contact"],
                action_result=ActionResult("success"),
            ),
            Event(
                id="contact-2",
                tick=2,
                timestamp="0001-01-03T00:00:00",
                location="town",
                participants=["lin", "mei"],
                causes=["tick-2-lin-contact"],
                facts=["contact"],
                action_result=ActionResult("success"),
            ),
        ]
    )

    pool = generate_action_pool(world, "lin")
    assert not any(action.action_type == "contact_person" for action in pool)

def test_successful_contact_reduces_reconciliation_pressure():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    world.characters["lin"].human_condition.desires["reconciliation"] = 70.0
    world.add_relationship(RelationshipState("lin", "mei", trust=40.0))
    action = ActionCandidate(
        "contact", "lin", "contact_person", targets=["mei"], confidence=1.0, difficulty=0.1
    )

    engine = SimulationEngine(seed=1)
    events = engine.resolve(world, [action])
    engine._advance_human_pressures(world, events)
    assert world.characters["lin"].human_condition.desires["reconciliation"] < 70.0


def test_simulation_advances_world_clock_and_preserves_event_timestamp():
    world = build_demo_world()
    world.timestamp = "0001-01-01T00:00:00"
    result = SimulationEngine(seed=42).step(world)

    assert result.events
    assert all(event.timestamp == "0001-01-01T00:00:00" for event in result.events)
    assert world.timestamp == "0001-01-02T00:00:00"


def test_simulation_supports_custom_tick_duration():
    world = build_demo_world()
    world.timestamp = "0001-01-01T00:00:00"
    SimulationEngine(seed=42, tick_duration_hours=6).step(world)
    assert world.timestamp == "0001-01-01T06:00:00"


def test_remembered_failure_reduces_repeat_action_utility():
    from engine.core.actions import ActionCandidate
    from engine.core.models import ActionResult, Event
    from engine.core.decision import DecisionKernel

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    action = ActionCandidate(
        "retry", "lin", "travel", targets=["town"], confidence=0.8, difficulty=0.4, score=0.5
    )
    plain = DecisionKernel(seed=1).evaluate(world, action)

    event = Event(
        "past-failure",
        0,
        "0001-01-01T00:00:00",
        "town",
        ["lin", "town"],
        ["tick-0-lin-travel"],
        ["Lin failed to travel to town."],
        action_result=ActionResult("failure"),
    )
    memory = SimulationEngine(seed=1).memory_kernel.remember_event(
        world.memory_state, "lin", event, "failed travel"
    )
    SimulationEngine(seed=1).memory_kernel.record_event_belief(
        world.memory_state, "lin", event, memory.id
    )
    remembered = DecisionKernel(seed=1).evaluate(world, action)

    assert remembered.utility < plain.utility


def test_remembered_contact_failure_reduces_contact_utility():
    from engine.core.actions import ActionCandidate
    from engine.core.models import ActionResult, Event
    from engine.core.decision import DecisionKernel

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    world.add_relationship(RelationshipState("lin", "mei", trust=40.0))
    action = ActionCandidate(
        "retry-contact",
        "lin",
        "contact_person",
        targets=["mei"],
        confidence=0.8,
        difficulty=0.4,
    )
    plain = DecisionKernel(seed=1).evaluate(world, action)

    event = Event(
        "past-contact-failure",
        0,
        "0001-01-01T00:00:00",
        "town",
        ["lin", "mei"],
        ["tick-0-lin-contact"],
        ["Lin's conversation with Mei failed."],
        action_result=ActionResult("failure"),
    )
    memory = SimulationEngine(seed=1).memory_kernel.remember_event(
        world.memory_state, "lin", event, "failed conversation"
    )
    SimulationEngine(seed=1).memory_kernel.record_event_belief(
        world.memory_state, "lin", event, memory.id
    )
    remembered = DecisionKernel(seed=1).evaluate(world, action)

    assert remembered.utility < plain.utility
