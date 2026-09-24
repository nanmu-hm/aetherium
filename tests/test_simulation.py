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


def test_human_condition_desire_changes_action_utility():
    from engine.core.models import ActionCandidate
    from engine.core.decision import DecisionKernel

    world = build_demo_world()
    world.characters["lin"].goals.clear()
    travel = ActionCandidate(
        "travel", "lin", "travel", targets=["town"], confidence=0.8, difficulty=0.4
    )
    rest = ActionCandidate(
        "rest", "lin", "rest", confidence=0.8, difficulty=0.2
    )

    world.characters["lin"].human_condition.desires["freedom"] = 0.0
    low = DecisionKernel(seed=1).evaluate(world, travel)
    rest_low = DecisionKernel(seed=1).evaluate(world, rest)

    world.characters["lin"].human_condition.desires["freedom"] = 100.0
    high = DecisionKernel(seed=1).evaluate(world, travel)

    assert high.utility > low.utility
    assert rest_low.utility < high.utility
    assert "time pressure" in high.reasons


def test_successful_help_changes_reciprocal_relationship_state():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    world.characters["lin"].values = ["loyalty"]
    world.add_relationship(RelationshipState("lin", "mei", trust=60.0, affection=50.0, loyalty=50.0))
    world.add_relationship(RelationshipState("mei", "lin", trust=20.0, affection=40.0, loyalty=30.0))

    action = ActionCandidate(
        "help", "lin", "help_person", targets=["mei"], confidence=1.0, difficulty=0.1
    )
    events = SimulationEngine(seed=1).resolve(world, [action])

    assert events[0].action_result is not None
    assert events[0].action_result.status == "success"
    reciprocal = world.relationships["mei:lin"]
    assert reciprocal.trust == 25.0
    assert reciprocal.affection == 42.0
    assert reciprocal.loyalty == 33.0
    assert any(
        item.target_type == "relationship"
        and item.target_id == "mei:lin"
        and item.field == "trust"
        for item in events[0].consequences
    )


def test_relationship_consequence_is_visible_to_later_action_generation():
    from engine.core.actions import generate_action_pool
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    world.characters["mei"].goals[0].status = "achieved"
    world.add_relationship(RelationshipState("lin", "mei", trust=60.0, affection=50.0, loyalty=50.0))
    world.add_relationship(RelationshipState("mei", "lin", trust=20.0, affection=40.0, loyalty=30.0))
    world.characters["mei"].human_condition.desires["belonging"] = 40.0

    before = next(
        action for action in generate_action_pool(world, "mei")
        if action.action_type == "contact_person"
    )

    help_action = ActionCandidate(
        "help", "lin", "help_person", targets=["mei"], confidence=1.0, difficulty=0.1
    )
    SimulationEngine(seed=1).resolve(world, [help_action])

    after = next(
        action for action in generate_action_pool(world, "mei")
        if action.action_type == "contact_person"
    )

    assert after.score < before.score


def test_failed_attempt_increases_unresolved_desire_pressure():
    from engine.core.models import ActionCandidate
    from engine.core.simulation import SimulationEngine

    world = build_demo_world()
    world.characters["mei"].goals[0].status = "achieved"
    world.characters["mei"].human_condition.desires["freedom"] = 40.0
    action = ActionCandidate(
        "hard-travel",
        "mei",
        "travel",
        targets=["town"],
        confidence=0.1,
        difficulty=0.99,
    )

    events = SimulationEngine(seed=1).resolve(world, [action])

    assert events[0].action_result is not None
    assert events[0].action_result.status == "failure"
    assert world.characters["mei"].human_condition.desires["freedom"] == 48.0
    assert any(
        consequence.field == "human_condition.desires.freedom"
        for consequence in events[0].consequences
    )


def test_failed_contact_creates_persistent_relational_friction():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    world.add_relationship(RelationshipState("lin", "mei", trust=40.0, resentment=5.0))
    action = ActionCandidate(
        "failed-contact",
        "lin",
        "contact_person",
        targets=["mei"],
        confidence=0.1,
        difficulty=0.99,
    )

    events = SimulationEngine(seed=1).resolve(world, [action])

    relationship = world.relationships["lin:mei"]
    assert events[0].action_result is not None
    assert events[0].action_result.status == "failure"
    assert relationship.trust == 39.0
    assert relationship.resentment == 6.0
    assert any(
        consequence.field == "resentment"
        and consequence.target_id == "lin:mei"
        for consequence in events[0].consequences
    )


def test_failed_help_disappoints_the_recipient():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    world.add_relationship(RelationshipState("lin", "mei", trust=50.0, loyalty=40.0))
    world.add_relationship(RelationshipState("mei", "lin", trust=35.0, loyalty=25.0))
    action = ActionCandidate(
        "failed-help",
        "lin",
        "help_person",
        targets=["mei"],
        confidence=0.1,
        difficulty=0.99,
    )

    events = SimulationEngine(seed=1).resolve(world, [action])

    relationship = world.relationships["mei:lin"]
    assert events[0].action_result is not None
    assert events[0].action_result.status == "failure"
    assert relationship.trust == 33.0
    assert relationship.loyalty == 24.0


def test_successful_experience_builds_a_behavioral_habit():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    action = ActionCandidate(
        "help",
        "lin",
        "help_person",
        targets=["mei"],
        confidence=1.0,
        difficulty=0.1,
    )

    events = SimulationEngine(seed=1).resolve(world, [action])

    assert events[0].action_result is not None
    assert events[0].action_result.status == "success"
    assert world.characters["lin"].habits["help_person"] == 0.1
    assert any(
        consequence.field == "habits.help_person"
        and consequence.new_value == 0.1
        for consequence in events[0].consequences
    )


def test_failed_experience_builds_a_behavioral_avoidance():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["mei"].goals[0].status = "achieved"
    action = ActionCandidate(
        "hard-travel",
        "mei",
        "travel",
        targets=["town"],
        confidence=0.1,
        difficulty=0.99,
    )

    events = SimulationEngine(seed=1).resolve(world, [action])

    assert events[0].action_result is not None
    assert events[0].action_result.status == "failure"
    assert world.characters["mei"].habits["travel"] == -0.1
    assert any(
        consequence.field == "habits.travel"
        and consequence.new_value == -0.1
        for consequence in events[0].consequences
    )


def test_learned_habit_changes_later_action_utility():
    from engine.core.models import ActionCandidate
    from engine.core.decision import DecisionKernel

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    action = ActionCandidate(
        "help",
        "lin",
        "help_person",
        targets=["mei"],
        confidence=0.8,
        difficulty=0.4,
    )

    neutral = DecisionKernel(seed=1).evaluate(world, action)
    world.characters["lin"].habits["help_person"] = 0.8
    preferred = DecisionKernel(seed=1).evaluate(world, action)
    world.characters["lin"].habits["help_person"] = -0.8
    avoidant = DecisionKernel(seed=1).evaluate(world, action)

    assert preferred.utility > neutral.utility > avoidant.utility
    assert "learned preference" in preferred.reasons
    assert "learned avoidance" in avoidant.reasons


def test_blocked_action_does_not_create_a_behavioral_habit():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    action = ActionCandidate(
        "blocked",
        "mei",
        "travel",
        targets=["missing-place"],
        confidence=1.0,
    )

    events = SimulationEngine(seed=1).resolve(world, [action])

    assert events[0].action_result is not None
    assert events[0].action_result.status == "blocked"
    assert "travel" not in world.characters["mei"].habits


def test_successful_contact_creates_actor_and_recipient_emotional_change():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    world.add_relationship(RelationshipState("lin", "mei", trust=40.0))
    action = ActionCandidate(
        "contact",
        "lin",
        "contact_person",
        targets=["mei"],
        confidence=1.0,
        difficulty=0.1,
    )

    events = SimulationEngine(seed=1).resolve(world, [action])

    assert events[0].action_result is not None
    assert events[0].action_result.status == "success"
    assert world.characters["lin"].emotions["joy"] == 3.0
    assert world.characters["lin"].emotions.get("longing", 0.0) == 0.0
    assert world.characters["mei"].emotions["joy"] == 2.0
    assert any(
        consequence.field == "emotions.joy"
        and consequence.target_id == "lin"
        for consequence in events[0].consequences
    )


def test_failed_travel_creates_fear_and_can_resist_later_travel():
    from engine.core.models import ActionCandidate
    from engine.core.decision import DecisionKernel

    world = build_demo_world()
    world.characters["mei"].goals[0].status = "achieved"
    action = ActionCandidate(
        "hard-travel",
        "mei",
        "travel",
        targets=["town"],
        confidence=0.1,
        difficulty=0.99,
    )

    events = SimulationEngine(seed=1).resolve(world, [action])

    assert events[0].action_result is not None
    assert events[0].action_result.status == "failure"
    assert world.characters["mei"].emotions["fear"] == 5.0

    retry = ActionCandidate(
        "retry-travel",
        "mei",
        "travel",
        targets=["town"],
        confidence=0.8,
        difficulty=0.4,
    )
    evaluation = DecisionKernel(seed=1).evaluate(world, retry)

    baseline = build_demo_world()
    baseline.characters["mei"].goals[0].status = "achieved"
    baseline_evaluation = DecisionKernel(seed=1).evaluate(baseline, retry)

    assert evaluation.utility < baseline_evaluation.utility
    assert "emotional resistance" in evaluation.reasons


def test_positive_emotion_does_not_automatically_increase_every_action():
    from engine.core.models import ActionCandidate
    from engine.core.decision import DecisionKernel

    world = build_demo_world()
    world.characters["mei"].goals[0].status = "achieved"
    travel = ActionCandidate("travel", "mei", "travel", targets=["town"], confidence=0.8, difficulty=0.4)
    contact = ActionCandidate("contact", "mei", "contact_person", targets=["lin"], confidence=0.8, difficulty=0.4)
    world.add_relationship(RelationshipState("mei", "lin", trust=50.0))

    neutral_travel = DecisionKernel(seed=1).evaluate(world, travel)
    neutral_contact = DecisionKernel(seed=1).evaluate(world, contact)

    world.characters["mei"].emotions["joy"] = 100.0
    joyful_travel = DecisionKernel(seed=1).evaluate(world, travel)
    joyful_contact = DecisionKernel(seed=1).evaluate(world, contact)

    assert joyful_travel.utility == neutral_travel.utility
    assert joyful_contact.utility == neutral_contact.utility
