from engine.core.demo import build_demo_world, run_demo
from engine.core.models import RelationshipState
from engine.core.human_condition import HumanCondition
from engine.core.simulation import SimulationEngine, event_action_type


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
    world.add_relationship(RelationshipState("lin", "mei", trust=90.0))
    from engine.core.decision import DecisionKernel
    pool = __import__("engine.core.actions", fromlist=["generate_action_pool"]).generate_action_pool(world, "lin")
    contact = next(action for action in pool if action.action_type == "contact_person")
    low_world = build_demo_world()
    low_world.add_relationship(RelationshipState("lin", "mei", trust=10.0))
    low_pool = __import__("engine.core.actions", fromlist=["generate_action_pool"]).generate_action_pool(low_world, "lin")
    low_contact = next(action for action in low_pool if action.action_type == "contact_person")
    high_eval = DecisionKernel(seed=1).evaluate(world, contact)
    low_eval = DecisionKernel(seed=1).evaluate(low_world, low_contact)
    assert high_eval.utility > low_eval.utility


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


def test_blocked_help_requires_same_location() -> None:
    from engine.core.models import ActionCandidate
    world = build_demo_world()
    world.characters["mei"].location = "elsewhere"
    action = ActionCandidate("help", "lin", "help_person", targets=["mei"], confidence=1.0)
    events = SimulationEngine(seed=42).resolve(world, [action])
    assert events[0].action_result is not None
    assert events[0].action_result.status == "blocked"
    assert "same location" in events[0].action_result.reason


def test_emotions_settle_between_ticks() -> None:
    world = build_demo_world()
    world.characters["lin"].emotions["resentment"] = 80.0
    SimulationEngine(seed=1).step(world)
    assert world.characters["lin"].emotions["resentment"] < 80.0


def test_action_resolver_can_fail_and_is_seed_reproducible() -> None:
    from engine.core.models import ActionCandidate
    from engine.core.simulation import ActionResolver
    world = build_demo_world()
    action = ActionCandidate("hard", "mei", "contact_person", targets=["lin"], confidence=0.1, difficulty=0.99)
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


def test_successful_goal_action_advances_or_completes_goal():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].goals[0].description = "help a friend"
    world.characters["lin"].goals[0].stages = ["help a friend", "help the friend again"]
    action = ActionCandidate(
        "help", "lin", "help_person", targets=["mei"], confidence=1.0, difficulty=0.1
    )
    events = SimulationEngine(seed=1).resolve(world, [action])
    goal = world.characters["lin"].goals[0]
    assert goal.status == "active"
    assert goal.current_stage == 1
    assert goal.progress == 0.5
    assert any(item.target_type == "goal" and item.field == "current_stage" for item in events[0].consequences)


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
    world.characters["lin"].location = world.characters["mei"].location

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
    import copy
    from engine.core.actions import generate_action_pool
    from engine.core.models import ActionCandidate
    from engine.core.decision import DecisionKernel

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    world.characters["mei"].goals[0].status = "achieved"
    world.add_relationship(RelationshipState("lin", "mei", trust=60.0, affection=50.0, loyalty=50.0))
    world.add_relationship(RelationshipState("mei", "lin", trust=20.0, affection=40.0, loyalty=30.0))
    world.characters["mei"].human_condition.desires["belonging"] = 40.0
    world.characters["lin"].location = world.characters["mei"].location

    before_world = copy.deepcopy(world)
    before = next(
        action for action in generate_action_pool(before_world, "mei")
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

    before_utility = DecisionKernel(seed=1).evaluate(before_world, before).utility
    after_utility = DecisionKernel(seed=1).evaluate(world, after).utility
    # Successful help raises Mei's trust in Lin, so relationship alignment
    # makes subsequent contact more attractive under the current semantics.
    assert after_utility > before_utility


def test_failed_attempt_increases_unresolved_desire_pressure():
    from engine.core.models import ActionCandidate
    from engine.core.simulation import SimulationEngine

    world = build_demo_world()
    world.characters["mei"].goals[0].status = "achieved"
    world.characters["mei"].human_condition.desires["reconciliation"] = 40.0
    action = ActionCandidate(
        "hard-contact",
        "mei",
        "contact_person",
        targets=["lin"],
        confidence=0.1,
        difficulty=0.99,
    )

    events = SimulationEngine(seed=1).resolve(world, [action])

    assert events[0].action_result is not None
    assert events[0].action_result.status == "failure"
    assert world.characters["mei"].human_condition.desires["reconciliation"] == 48.0
    assert any(
        consequence.field == "human_condition.desires.reconciliation"
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
    world.add_relationship(RelationshipState("mei", "lin", trust=50.0))
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
        "hard-help",
        "mei",
        "help_person",
        targets=["lin"],
        confidence=0.1,
        difficulty=0.99,
    )

    events = SimulationEngine(seed=1).resolve(world, [action])

    assert events[0].action_result is not None
    assert events[0].action_result.status == "failure"
    assert world.characters["mei"].habits["help_person"] == -0.1
    assert any(
        consequence.field == "habits.help_person"
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


def test_successful_help_builds_positive_self_concept_evidence():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    action = ActionCandidate(
        "help", "lin", "help_person", targets=["mei"], confidence=1.0, difficulty=0.1
    )

    events = SimulationEngine(seed=1).resolve(world, [action])

    assert events[0].action_result is not None
    assert events[0].action_result.status == "success"
    assert world.characters["lin"].identity_beliefs["compassionate"] == 0.08
    assert world.characters["lin"].identity_beliefs["reliable"] == 0.08
    assert any(
        item.field == "identity_beliefs.reliable"
        for item in events[0].consequences
    )


def test_failed_travel_builds_negative_self_concept_evidence():
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
    assert world.characters["mei"].identity_beliefs["independent"] == -0.08
    assert world.characters["mei"].identity_beliefs["capable"] == -0.08


def test_blocked_action_does_not_create_self_concept_evidence():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    action = ActionCandidate(
        "blocked-travel",
        "mei",
        "travel",
        targets=["missing-place"],
        confidence=1.0,
        difficulty=0.1,
    )

    events = SimulationEngine(seed=1).resolve(world, [action])

    assert events[0].action_result is not None
    assert events[0].action_result.status == "blocked"
    assert world.characters["mei"].identity_beliefs == {}


def test_self_concept_influences_matching_action_utility():
    from engine.core.models import ActionCandidate
    from engine.core.decision import DecisionKernel

    world = build_demo_world()
    world.characters["lin"].goals.clear()
    action = ActionCandidate(
        "help", "lin", "help_person", targets=["mei"], confidence=0.8, difficulty=0.4
    )

    low = DecisionKernel(seed=1).evaluate(world, action)
    world.characters["lin"].identity_beliefs["reliable"] = 1.0
    world.characters["lin"].identity_beliefs["compassionate"] = 1.0
    high = DecisionKernel(seed=1).evaluate(world, action)

    assert high.utility > low.utility
    assert "self-concept alignment" in high.reasons


def test_simulation_gives_event_knowledge_only_to_participants():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    action = ActionCandidate(
        "contact", "lin", "contact_person", targets=["mei"], confidence=1.0, difficulty=0.1
    )

    event = SimulationEngine(seed=1).resolve(world, [action])[0]

    assert world.event_log[-1].id == event.id
    assert event.facts[0] in world.characters["lin"].knowledge
    assert event.facts[0] in world.characters["mei"].knowledge


def test_world_event_history_is_not_enough_for_an_unaware_character_to_pay_repetition_cost():
    from engine.core.models import ActionCandidate, ActionResult, Event
    from engine.core.decision import DecisionKernel

    world = build_demo_world()
    world.characters["lin"].goals.clear()
    action = ActionCandidate(
        "repeat", "lin", "travel", targets=["town"], confidence=0.8, difficulty=0.4
    )
    baseline = DecisionKernel(seed=1).evaluate(world, action)

    hidden_event = Event(
        "unseen-lin-travel",
        0,
        "0001-01-01T00:00:00",
        "town",
        ["lin"],
        ["unrelated-cause"],
        ["Lin traveled long ago."],
        action_result=ActionResult("success"),
    )
    world.event_log.append(hidden_event)
    unaware = DecisionKernel(seed=1).evaluate(world, action)

    assert unaware.utility == baseline.utility
    assert "recently repeated action" not in unaware.reasons


def test_known_past_action_can_still_create_repetition_pressure():
    from engine.core.models import ActionCandidate, ActionResult, Event
    from engine.core.decision import DecisionKernel
    from engine.memory.kernel import MemoryKernel

    world = build_demo_world()
    world.characters["lin"].goals.clear()
    action = ActionCandidate(
        "repeat", "lin", "travel", targets=["town"], confidence=0.8, difficulty=0.4
    )
    baseline = DecisionKernel(seed=1).evaluate(world, action)

    event = Event(
        "known-lin-travel",
        0,
        "0001-01-01T00:00:00",
        "town",
        ["lin"],
        ["tick-0-lin-travel"],
        ["Lin traveled to town."],
        action_result=ActionResult("success"),
    )
    world.event_log.append(event)
    MemoryKernel().remember_event(world.memory_state, "lin", event, "Lin traveled to town.")

    known = DecisionKernel(seed=1).evaluate(world, action)

    assert known.utility < baseline.utility
    assert "recently repeated action" in known.reasons



def test_contact_does_not_complete_help_goal():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].goals[0].description = "help a friend"
    action = ActionCandidate(
        "contact", "lin", "contact_person", targets=["mei"], confidence=1.0, difficulty=0.1
    )

    events = SimulationEngine(seed=1).resolve(world, [action])

    assert world.characters["lin"].goals[0].status == "active"
    assert events[0].action_type == "contact_person"
    assert not any(item.target_type == "goal" for item in events[0].consequences)


def test_event_exposes_structured_action_type():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    action = ActionCandidate(
        "travel", "lin", "travel", targets=["town"], confidence=1.0, difficulty=0.1
    )

    events = SimulationEngine(seed=1).resolve(world, [action])

    assert events[0].action_type == "travel"


def test_repetition_penalty_uses_structured_action_type():
    from engine.core.models import ActionCandidate, ActionResult, Event
    from engine.core.decision import DecisionKernel

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    action = ActionCandidate(
        "retry-contact", "lin", "contact_person", targets=["mei"], confidence=0.8, difficulty=0.4
    )
    world.event_log.extend(
        [
            Event(
                id="contact-1", tick=1, timestamp="0001-01-02T00:00:00", location="town",
                participants=["lin", "mei"], causes=["tick-1-lin-contact"], facts=["contact"],
                action_type="contact_person", action_result=ActionResult("success"),
            ),
            Event(
                id="contact-2", tick=2, timestamp="0001-01-03T00:00:00", location="town",
                participants=["lin", "mei"], causes=["tick-2-lin-contact"], facts=["contact"],
                action_type="contact_person", action_result=ActionResult("success"),
            ),
        ]
    )

    engine = SimulationEngine(seed=1)
    for event in world.event_log:
        engine.memory_kernel.remember_event(world.memory_state, "lin", event, "contact")

    evaluation = DecisionKernel(seed=1).evaluate(world, action)

    assert "recently repeated action" in evaluation.reasons


def test_travel_is_not_suppressed_by_a_cooldown_when_pressure_is_real():
    from engine.core.actions import generate_action_pool
    from engine.core.models import ActionResult, Event

    world = build_demo_world()
    world.locations.add("road")
    world.characters["mei"].goals[0].status = "achieved"
    world.characters["mei"].human_condition.desires["freedom"] = 80.0
    world.event_log.append(
        Event(
            id="travel-1", tick=0, timestamp="0001-01-01T00:00:00", location="town",
            participants=["mei"], causes=["tick-0-mei-travel"], facts=["travel"],
            action_type="travel", action_result=ActionResult("success"),
        )
    )
    world.tick = 1
    world.characters["mei"].human_condition.desires["freedom"] = 55.0

    pool = generate_action_pool(world, "mei")

    assert any(action.action_type == "travel" for action in pool)


def test_goal_alignment_uses_exact_words_not_substrings():
    from engine.core.decision import DecisionKernel
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].goals[0].description = "be a good neighbor"
    action = ActionCandidate(
        "travel", "lin", "travel", targets=["town"], confidence=0.8, difficulty=0.4
    )

    evaluation = DecisionKernel(seed=1).evaluate(world, action)

    assert evaluation.utility < 1.0
    assert "goal alignment" not in evaluation.reasons


def test_repetition_penalty_covers_help_and_pursue_goal():
    from engine.core.models import ActionCandidate, ActionResult, Event
    from engine.core.decision import DecisionKernel
    from engine.memory.kernel import MemoryKernel

    for action_type, event_action in (("help_person", "help_person"), ("pursue_goal", "pursue_goal")):
        world = build_demo_world()
        world.characters["lin"].goals.clear()
        action = ActionCandidate(
            f"repeat-{action_type}", "lin", action_type, targets=["mei"], confidence=0.8, difficulty=0.4
        )
        event = Event(
            f"known-{action_type}", 1, "0001-01-02T00:00:00", "town",
            ["lin", "mei"], [f"tick-1-lin-{action_type}"], ["known action"],
            action_type=event_action, action_result=ActionResult("success"),
        )
        world.event_log.append(event)
        MemoryKernel().remember_event(world.memory_state, "lin", event, "known action")

        evaluation = DecisionKernel(seed=1).evaluate(world, action)

        assert "recently repeated action" in evaluation.reasons


def test_successful_travel_satisfies_freedom_pressure_from_place_context():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.locations.add("road")
    world.characters["mei"].goals[0].status = "achieved"
    world.characters["mei"].human_condition.desires["freedom"] = 80.0
    world.characters["mei"].human_condition.location_pressures["town"] = {"confinement": 0.75}
    action = ActionCandidate(
        "travel", "mei", "travel", targets=["road"], confidence=1.0, difficulty=0.1,
        metadata={"travel_reason": "freedom_exploration"},
    )

    event = SimulationEngine(seed=1).resolve(world, [action])[0]

    assert event.action_result is not None
    assert event.action_result.status == "success"
    assert world.characters["mei"].human_condition.desires["freedom"] == 80.0

    SimulationEngine._advance_human_pressures(world, [event])
    assert world.characters["mei"].human_condition.desires["freedom"] < 21.0
    assert world.characters["mei"].human_condition.desires["freedom"] == 6.5


def test_freedom_pressure_does_not_recover_away_from_confining_context():
    from engine.core.models import CharacterState, WorldState

    world = WorldState(world_id="freedom-context", locations={"town", "road"})
    world.add_character(
        CharacterState(
            id="r",
            name="R",
            location="road",
            values=["freedom"],
            human_condition=HumanCondition(
                desires={"freedom": 20.0},
                location_pressures={"road": {"confinement": 0.0}},
            ),
        )
    )
    SimulationEngine._advance_human_pressures(world, [])
    assert world.characters["r"].human_condition.desires["freedom"] == 20.0


def test_rest_requires_a_real_recovery_need():
    from engine.core.actions import generate_action_pool

    world = build_demo_world()
    world.characters["lin"].human_condition.fatigue = 0.0
    pool = generate_action_pool(world, "lin")
    assert not any(action.action_type == "rest" for action in pool)

    world.characters["lin"].human_condition.fatigue = 40.0
    pool = generate_action_pool(world, "lin")
    assert any(action.action_type == "rest" for action in pool)


def test_location_seen_evidence_retracts_stale_absence_fact():
    from engine.memory.kernel import MemoryKernel

    world = build_demo_world()
    kernel = MemoryKernel()
    kernel.learn_fact(world.memory_state, "lin", "location_absent:mei:road", tick=1)
    assert world.memory_state.get_knowledge("lin", "location_absent:mei:road") is not None

    kernel.learn_fact(world.memory_state, "lin", "location_seen:mei:road", tick=2)
    assert world.memory_state.get_knowledge("lin", "location_absent:mei:road") is None


def test_unannotated_places_use_neutral_confinement_and_do_not_lock_freedom():
    from engine.core.actions import generate_action_pool
    from engine.core.models import CharacterState, WorldState

    world = WorldState(world_id="neutral-place", locations={"a", "b", "c"})
    world.add_character(
        CharacterState(
            id="wanderer",
            name="Wanderer",
            location="a",
            values=["freedom"],
            human_condition=HumanCondition(desires={"freedom": 100.0}),
        )
    )
    character = world.characters["wanderer"]
    assert character.human_condition.confinement_at("a") == 0.5

    engine = SimulationEngine(seed=4)
    travel_destinations = []
    for _ in range(20):
        result = engine.step(world)
        for action in result.actions:
            if action.actor_id == "wanderer" and action.action_type == "travel":
                travel_destinations.append((action.targets[0], world.tick))

    assert travel_destinations
    assert character.human_condition.desires["freedom"] < 100.0

    locations = [character.location]
    for event in world.event_log:
        if event.participants and event.participants[0] == "wanderer" and event_action_type(event) == "travel":
            if event.action_result and event.action_result.status == "success":
                locations.append(event.location)

    reversals = sum(
        1 for a, b, c in zip(locations, locations[1:], locations[2:]) if a == c and a != b
    )
    assert reversals <= max(1, len(locations) // 4)


def test_same_event_can_produce_different_personality_reactions():
    from engine.core.models import ActionCandidate, CharacterState, RelationshipState, WorldState
    from engine.core.human_condition import HumanCondition

    def run_target(traits):
        world = WorldState(world_id="personality-reaction", locations={"town"})
        world.add_character(CharacterState(
            id="actor", name="Actor", location="town", values=["loyalty"],
            human_condition=HumanCondition(),
        ))
        world.add_character(CharacterState(
            id="target", name="Target", location="town", traits=traits,
            human_condition=HumanCondition(),
        ))
        world.add_relationship(RelationshipState("actor", "target", trust=50))
        action = ActionCandidate(
            "contact", "actor", "contact_person", targets=["target"], confidence=1.0, difficulty=0.0,
        )
        event = SimulationEngine(seed=1).resolve(world, [action])[0]
        return world, event

    proud_world, proud_event = run_target(["proud", "independent"])
    warm_world, warm_event = run_target(["warm", "forgiving"])

    assert proud_world.characters["target"].emotions["resentment"] > 0.0
    assert warm_world.characters["target"].emotions["joy"] > 0.0
    assert any(item.target_id == "target" and item.field == "emotions.resentment" for item in proud_event.consequences)
    assert any(item.target_id == "target" and item.field == "emotions.joy" for item in warm_event.consequences)


def test_rest_does_not_reinforce_when_actor_is_already_rested():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].human_condition.fatigue = 0.0
    action = ActionCandidate("rest", "lin", "rest", confidence=1.0, difficulty=0.0)

    event = SimulationEngine(seed=1).resolve(world, [action])[0]

    assert event.action_result is not None
    assert event.action_result.status == "success"
    assert world.characters["lin"].human_condition.fatigue == 0.0
    assert "rest" not in world.characters["lin"].habits


def test_rest_reduces_fatigue_and_can_be_reinforced_by_recovery():
    from engine.core.models import ActionCandidate

    world = build_demo_world()
    world.characters["lin"].human_condition.fatigue = 80.0
    action = ActionCandidate("rest", "lin", "rest", confidence=1.0, difficulty=0.0)

    event = SimulationEngine(seed=1).resolve(world, [action])[0]

    assert event.action_result is not None
    assert event.action_result.status == "success"
    assert world.characters["lin"].human_condition.fatigue < 80.0
    assert world.characters["lin"].habits["rest"] == 0.1


def test_candidate_score_participates_in_final_selection():
    from engine.core.models import ActionCandidate
    from engine.core.decision import DecisionKernel

    world = build_demo_world()
    world.characters["lin"].goals.clear()
    low = ActionCandidate("low", "lin", "travel", targets=["town"], score=0.0, confidence=1.0)
    high = ActionCandidate("high", "lin", "travel", targets=["town"], score=0.9, confidence=1.0)

    chosen, evaluations = DecisionKernel(seed=1).choose(world, [low, high])

    assert chosen is high
    assert all(item.selection_score is not None for item in evaluations)


def test_low_freedom_pressure_keeps_travel_as_an_affordance():
    from engine.core.actions import generate_action_pool
    from engine.core.models import CharacterState, WorldState

    world = WorldState(world_id="low-pressure-travel", locations={"town", "road"})
    world.add_character(
        CharacterState(
            id="r",
            name="R",
            location="town",
            values=["freedom"],
            human_condition=HumanCondition(
                desires={"freedom": 1.0, "curiosity": 0.0},
                location_pressures={"town": {"confinement": 1.0}, "road": {"confinement": 0.0}},
            ),
        )
    )
    pool = generate_action_pool(world, "r")
    assert any(action.action_type == "travel" for action in pool)


def test_high_fatigue_makes_recovery_more_valuable_than_unmotivated_travel():
    from engine.core.actions import generate_action_pool
    from engine.core.decision import DecisionKernel

    world = build_demo_world()
    world.locations.add("road")
    character = world.characters["lin"]
    character.goals.clear()
    character.human_condition.fatigue = 90.0
    character.human_condition.desires["freedom"] = 0.0
    character.human_condition.desires["curiosity"] = 0.0

    pool = generate_action_pool(world, "lin")
    travel = next(action for action in pool if action.action_type == "travel")
    rest = next(action for action in pool if action.action_type == "rest")
    kernel = DecisionKernel(seed=1)
    travel_eval = kernel.evaluate(world, travel)
    rest_eval = kernel.evaluate(world, rest)

    assert rest_eval.utility > travel_eval.utility
    chosen, _ = kernel.choose(world, [travel, rest])
    assert chosen is rest
