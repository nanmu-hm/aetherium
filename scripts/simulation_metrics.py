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
    travel_reasons: Counter[tuple[str, str]] = Counter()
    location_absent = 0

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
        actions_by_id = {action.id: action for action in result.actions}
        for event in result.events:
            action = actions_by_id.get(event.causes[0]) if event.causes else None
            if event.action_type == "travel" and event.action_result and event.action_result.status == "success":
                actor_id = event.participants[0]
                travel_ticks[actor_id].append(event.tick)
                reason = "search" if action and action.metadata.get("search_target") else "freedom"
                travel_reasons[(actor_id, reason)] += 1
            if action and action.metadata.get("search_target") and any(
                fact.endswith("is not there.") for fact in event.facts
            ):
                location_absent += 1

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
        "travel_reasons": {f"{actor}:{reason}": count for (actor, reason), count in sorted(travel_reasons.items())},
        "location_absent": location_absent,
        "final_locations": {
            cid: world.characters[cid].location for cid in sorted(world.characters)
        },
    }


def search_reroute_probe() -> list[str]:
    """Three-location probe showing actor-local failed search changing later destinations."""
    world = build_genesis_world()
    world.locations.add("temple")
    world.characters["yan"].location = "river_town"
    world.characters["rui"].location = "old_road"
    SimulationEngine(seed=31).memory_kernel.learn_fact(
        world.memory_state,
        "yan",
        "location_seen:rui:temple",
        tick=0,
        source="prior_observation",
        confidence=0.8,
    )
    events: list[str] = []
    engine = SimulationEngine(seed=31)
    for _ in range(3):
        result = engine.step(world)
        actions_by_id = {action.id: action for action in result.actions}
        for event in result.events:
            action = actions_by_id.get(event.causes[0]) if event.causes else None
            if action and action.metadata.get("search_target"):
                events.extend(event.facts)
    return events


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
            f"travel_reasons={result['travel_reasons']} "
            f"location_absent={result['location_absent']} "
            f"final_locations={result['final_locations']}"
        )
    print(f"checkpoint_replay={checkpoint_replay_check()}")
    print("search_reroute_probe:")
    for fact in search_reroute_probe():
        print(f"  {fact}")


if __name__ == "__main__":
    main()
