"""Reproducible long-run evidence for the autonomous-world loop.

Run:
    python scripts/simulation_metrics.py
"""

from __future__ import annotations

from collections import Counter, defaultdict

from engine.core.actions import generate_action_pool
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world
from engine.persistence.codec import world_from_dict, world_to_dict
from engine.persistence.replay import ReplayVerifier


SEEDS = (1, 2, 3, 7, 42)
TICKS = 100


def run_seed(seed: int, ticks: int = TICKS) -> dict:
    world = build_genesis_world()
    engine = SimulationEngine(seed=seed)
    idle_no_candidates = 0
    chosen_rest = 0
    action_counts = Counter()
    travel_ticks: defaultdict[str, list[int]] = defaultdict(list)
    travel_counts: Counter = Counter()
    travel_reasons: Counter = Counter()
    failed_searches = 0

    for _ in range(ticks):
        pools = {
            character.id: generate_action_pool(world, character.id)
            for character in world.characters.values()
            if character.status == "active"
        }
        idle_no_candidates += sum(1 for pool in pools.values() if not pool)
        result = engine.step(world)
        for action in result.actions:
            action_counts[action.action_type] += 1
            if action.action_type == "rest":
                chosen_rest += 1
        for event in result.events:
            if event.action_type == "travel" and event.action_result:
                actor_id = event.participants[0]
                if event.action_result.status == "success":
                    travel_ticks[actor_id].append(event.tick)
                    if actor_id in world.characters and world.characters[actor_id].values:
                        reason = "search" if any("searches for" in fact for fact in event.facts) else "freedom"
                        travel_counts[actor_id] += 1
                        travel_reasons[reason] += 1
                if any("searches for" in fact and "not there" in fact for fact in event.facts):
                    failed_searches += 1

    intervals = []
    for ticks_for_actor in travel_ticks.values():
        intervals.extend(
            b - a for a, b in zip(ticks_for_actor, ticks_for_actor[1:])
        )

    return {
        "events": len(world.event_log),
        "idle_no_candidates": idle_no_candidates,
        "chosen_rest": chosen_rest,
        "action_counts": dict(sorted(action_counts.items())),
        "travel_intervals": intervals,
        "travel_counts": dict(sorted(travel_counts.items())),
        "travel_reasons": dict(sorted(travel_reasons.items())),
        "failed_searches": failed_searches,
        "final_locations": {
            cid: world.characters[cid].location for cid in sorted(world.characters)
        },
    }


def checkpoint_replay_check() -> bool:
    initial = build_genesis_world()
    continuous = world_from_dict(world_to_dict(initial))
    engine = SimulationEngine(seed=19)
    for _ in range(40):
        engine.step(continuous)

    split = world_from_dict(world_to_dict(initial))
    first = SimulationEngine(seed=19)
    for _ in range(20):
        first.step(split)

    restored = world_from_dict(world_to_dict(split))
    second = SimulationEngine(seed=999)
    for _ in range(20):
        second.step(restored)

    return (
        [ReplayVerifier.event_signature(e) for e in restored.event_log]
        == [ReplayVerifier.event_signature(e) for e in continuous.event_log]
        and world_to_dict(restored) == world_to_dict(continuous)
    )


def three_location_search_probe() -> dict:
    """Exercise search -> miss -> actor-local evidence -> reroute in three places."""
    from engine.core.human_condition import HumanCondition
    from engine.core.models import CharacterState, RelationshipState, WorldState
    from engine.memory.kernel import MemoryKernel

    world = WorldState(world_id="metrics-search", locations={"town", "temple", "harbor"})
    world.add_character(CharacterState(
        id="a", name="A", location="town",
        human_condition=HumanCondition(desires={"reconciliation": 1.0}),
    ))
    world.add_character(CharacterState(id="b", name="B", location="harbor"))
    world.add_relationship(RelationshipState("a", "b", trust=50.0))
    MemoryKernel().learn_fact(
        world.memory_state, "a", "location_seen:b:temple", tick=0, confidence=1.0
    )
    engine = SimulationEngine(seed=1)
    first = next(
        item for item in generate_action_pool(world, "a")
        if item.metadata.get("search_target") == "b"
    )
    first_event = engine.resolve(world, [first])[0]
    second = next(
        item for item in generate_action_pool(world, "a")
        if item.metadata.get("search_target") == "b"
    )
    return {
        "first_destination": first.targets[0],
        "first_found": any("finds B" in fact for fact in first_event.facts),
        "failed_search": any("not there" in fact for fact in first_event.facts),
        "second_destination": second.targets[0],
    }


def main() -> None:
    print(f"seeds={SEEDS} ticks={TICKS}")
    for seed in SEEDS:
        result = run_seed(seed)
        print(
            f"seed={seed} events={result['events']} "
            f"idle_no_candidates={result['idle_no_candidates']} "
            f"chosen_rest={result['chosen_rest']} "
            f"actions={result['action_counts']} "
            f"travel_intervals={result['travel_intervals']} "
            f"final_locations={result['final_locations']}"
        )
    print(f"three_location_search_probe={three_location_search_probe()}")
    print(f"checkpoint_replay={checkpoint_replay_check()}")


if __name__ == "__main__":
    main()
