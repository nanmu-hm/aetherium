from engine.genesis import discover_genesis_stories, run_genesis
from engine.core.action_types import event_action_type
from engine.core.simulation import SimulationEngine


def test_genesis_runs_without_manual_plot_injection():
    world = run_genesis(ticks=12, seed=7)
    assert world.tick == 12
    assert len(world.event_log) > 0
    assert len(world.memory_state.memories) >= len(world.event_log)


def test_genesis_is_reproducible():
    first = run_genesis(ticks=12, seed=7)
    second = run_genesis(ticks=12, seed=7)
    assert [event.facts for event in first.event_log] == [
        event.facts for event in second.event_log
    ]
    assert [
        (event.id, event.action_result.status if event.action_result else None)
        for event in first.event_log
    ] == [
        (event.id, event.action_result.status if event.action_result else None)
        for event in second.event_log
    ]


def test_genesis_can_produce_story_candidates():
    world, candidates = discover_genesis_stories(ticks=12, seed=7)
    assert world.event_log
    assert candidates
    assert candidates[0].event_ids
    assert candidates[0].participants


def test_genesis_allows_goal_and_value_driven_action_change():
    world = run_genesis(ticks=12, seed=7)
    action_types = {
        event_action_type(event)
        for event in world.event_log
        if event.causes
    }
    assert "contact_person" in action_types
    assert "travel" in action_types


def test_genesis_records_completed_goal_consequences():
    world = run_genesis(ticks=12, seed=7)
    assert any(
        consequence.target_type == "goal"
        and consequence.field == "status"
        and consequence.new_value == "achieved"
        for event in world.event_log
        for consequence in event.consequences
    )


def test_genesis_travel_has_a_character_grounded_reason():
    world = run_genesis(ticks=12, seed=7)
    travel_events = [
        event
        for event in world.event_log
        if event_action_type(event) == "travel"
        and event.action_result is not None
        and event.action_result.status == "success"
    ]
    assert travel_events
    assert all(
        event.consequences
        and any(item.field == "location" for item in event.consequences)
        for event in travel_events
    )
    assert all(
        not (
            event.tick > 0
            and event.participants
            and event.participants[0] == "rui"
            and event.location == "river_town"
            and any("goal" in fact.lower() and "leave town" in fact.lower() for fact in event.facts)
        )
        for event in travel_events
    )


def test_genesis_conditioned_goal_does_not_complete_after_returning_to_town():
    from engine.core.models import ActionCandidate
    from engine.core.simulation import SimulationEngine

    world = run_genesis(ticks=1, seed=7)
    # Reopen the goal only for this controlled semantic probe.
    goal = world.characters["rui"].goals[0]
    goal.status = "active"
    goal.current_stage = 1
    world.characters["rui"].location = "old_road"
    action = ActionCandidate(
        "semantic-return",
        "rui",
        "travel",
        targets=["river_town"],
        confidence=1.0,
        difficulty=0.1,
    )

    event = SimulationEngine(seed=7).resolve(world, [action])[0]

    assert event.action_result is not None
    assert event.action_result.status == "success"
    assert world.characters["rui"].goals[0].status == "active"


def test_genesis_conditioned_goals_do_not_generate_generic_pursuit():
    from engine.core.actions import generate_action_pool

    world = run_genesis(ticks=0, seed=7)
    for character in world.characters.values():
        assert not any(action.action_type == "pursue_goal" for action in generate_action_pool(world, character.id))


def test_genesis_clock_advances_with_simulation_ticks():
    world = run_genesis(ticks=12, seed=7)
    assert world.timestamp == "0001-01-13T00:00:00"
    assert len({event.timestamp for event in world.event_log}) > 1


def test_genesis_long_run_is_reproducible_and_valid():
    first = run_genesis(ticks=100, seed=7)
    second = run_genesis(ticks=100, seed=7)

    assert first.tick == 100
    assert first.timestamp == "0001-04-11T00:00:00"
    assert first.event_log
    assert len(first.memory_state.beliefs) > 0
    assert [event.facts for event in first.event_log] == [
        event.facts for event in second.event_log
    ]
    assert all(
        character.location in first.locations
        for character in first.characters.values()
    )


def test_genesis_does_not_immediately_reverse_travel_without_a_new_reason():
    world = run_genesis(ticks=1, seed=7)
    rui = world.characters["rui"]
    assert rui.location == "old_road"
    before = len(world.event_log)
    engine = SimulationEngine(seed=7)
    for _ in range(4):
        engine.step(world)
    new_events = world.event_log[before:]
    rui_travel = [
        event for event in new_events
        if event.participants and event.participants[0] == "rui"
        and event_action_type(event) == "travel"
        and event.action_result is not None
        and event.action_result.status == "success"
    ]
    assert not any(event.location == "river_town" for event in rui_travel)
