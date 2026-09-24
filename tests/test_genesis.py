from engine.genesis import discover_genesis_stories, run_genesis


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
        event.causes[0].rsplit("-", 1)[-1]
        for event in world.event_log
        if event.causes
    }
    assert "contact" in action_types
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


def test_genesis_has_recovery_between_repeated_travel_actions():
    world = run_genesis(ticks=12, seed=7)
    travel_ticks = [
        event.tick
        for event in world.event_log
        if event.causes and event.causes[0].endswith("travel")
        and event.action_result is not None
        and event.action_result.status == "success"
    ]
    assert travel_ticks
    assert all(
        second > first + 1
        for first, second in zip(travel_ticks, travel_ticks[1:])
    )


def test_genesis_clock_advances_with_simulation_ticks():
    world = run_genesis(ticks=12, seed=7)
    assert world.timestamp == "0001-01-13T00:00:00"
    assert len({event.timestamp for event in world.event_log}) > 1
