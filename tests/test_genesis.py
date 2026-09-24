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
