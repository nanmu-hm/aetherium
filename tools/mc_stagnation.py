"""M-C: stagnation measurement. READ-ONLY -- observes, never writes.

ChatGPT 5976565086 §5 authorises exactly this and nothing more:
measure the world's death point so a later M-B "recovery" has a comparable
before/after baseline. No dynamics change, no new world semantics.

Two levels are measured SEPARATELY, because conflating them is exactly the
error Arena caught in my first inventory post (5976589602 §2):

  raw pool    = generate_action_pool(state, cid)      per character, pre-choose
  engine pool = engine.generate_candidates(state)    post-choose, the arbiter's
                                                    actual output

"World is still" can mean either "no candidate was generated" (raw pool
empty) or "candidates were generated but none scored > 0" (engine pool
empty). Those point at different fixes, so the report must distinguish them.

Definitions used throughout, stated so they are checkable:
  silence_tick        : a tick that produced no Event
  sustained_silence   : the first tick t such that EVERY tick from t to the
                        horizon produced no Event. This is the stagnation
                        point. (Not "first gap" -- one quiet tick is normal.)
  silent_tail_length  : horizon - last_event_tick
  nonnegative_ratio   : of all raw candidates over the run, the fraction with
                        utility > 0 (i.e. selectable)
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")

from engine.core.actions import generate_action_pool
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

OFFICIAL_SEEDS = (1, 2, 3, 7, 42)
HORIZON = 420
SILENCE_WINDOW = 8


def measure(seed: int, horizon: int = HORIZON) -> dict:
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=False)

    event_ticks: list[int] = []
    raw_counts: list[int] = []
    engine_counts: list[int] = []
    nonnegative = 0
    raw_total = 0
    action_types: dict[str, int] = {}
    utilities: list[float] = []

    for _ in range(horizon):
        # measure BEFORE stepping, so tick N's pools describe the state the
        # step for tick N actually acts on
        for character_id in world.characters:
            if world.characters[character_id].status != "active":
                continue
            for candidate in generate_action_pool(world, character_id):
                raw_total += 1
                action_types[candidate.action_type] = (
                    action_types.get(candidate.action_type, 0) + 1
                )
                evaluation = engine.decision_kernel.evaluate(world, candidate)
                utilities.append(evaluation.utility)
                if evaluation.utility > 0.0:
                    nonnegative += 1

        raw_counts.append(sum(
            len(generate_action_pool(world, cid))
            for cid in world.characters
            if world.characters[cid].status == "active"
        ))
        engine_counts.append(len(engine.generate_candidates(world)))

        result = engine.step(world)
        if result.events:
            event_ticks.append(world.tick)

    # sustained silence: first tick after which no event ever appears again
    sustained = None
    for t in range(horizon):
        if not any(et > t for et in event_ticks):
            sustained = t
            break

    last_event = max(event_ticks) if event_ticks else None

    # raw-pool emptiness is a different fact from engine-pool emptiness
    raw_empty_after = None
    for t in range(horizon):
        if all(c == 0 for c in raw_counts[t:]):
            raw_empty_after = t
            break

    return {
        "seed": seed,
        "horizon": horizon,
        "events": len(event_ticks),
        "first_event_tick": event_ticks[0] if event_ticks else None,
        "last_event_tick": last_event,
        "sustained_silence_tick": sustained,
        "silent_tail_length": (horizon - last_event) if last_event is not None else None,
        "raw_pool_total": raw_total,
        "raw_pool_empty_from": raw_empty_after,
        "engine_pool_nonempty_ticks": sum(1 for c in engine_counts if c > 0),
        "nonnegative_candidates": nonnegative,
        "nonnegative_ratio": (nonnegative / raw_total) if raw_total else None,
        "action_type_counts": action_types,
        "utility_min": min(utilities) if utilities else None,
        "utility_max": max(utilities) if utilities else None,
        "utility_mean": (sum(utilities) / len(utilities)) if utilities else None,
        "event_ticks": event_ticks,
        "raw_pool_series": raw_counts,
        "engine_pool_series": engine_counts,
    }


def main() -> None:
    horizon = int(sys.argv[1]) if len(sys.argv) > 1 else HORIZON
    results = [measure(seed, horizon) for seed in OFFICIAL_SEEDS]

    print(f"M-C stagnation measurement, horizon={horizon}, seeds={list(OFFICIAL_SEEDS)}")
    print()
    header = (
        f"{'seed':>4} {'events':>6} {'1st':>5} {'last':>5} {'sustain':>7} "
        f"{'tail':>5} {'rawEmpty':>8} {'engNonEmpty':>11} {'nonneg':>7} {'nonneg%':>7}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        pct = (r["nonnegative_ratio"] * 100) if r["nonnegative_ratio"] is not None else 0.0
        print(
            f"{r['seed']:>4} {r['events']:>6} "
            f"{str(r['first_event_tick']):>5} {str(r['last_event_tick']):>5} "
            f"{str(r['sustained_silence_tick']):>7} {str(r['silent_tail_length']):>5} "
            f"{str(r['raw_pool_empty_from']):>8} "
            f"{r['engine_pool_nonempty_ticks']:>11} "
            f"{r['nonnegative_candidates']:>7} {pct:>6.2f}%"
        )

    print()
    print("action types actually generated (seed 7 detail in the JSON dump):")
    all_types: dict[str, int] = {}
    for r in results:
        for k, v in r["action_type_counts"].items():
            all_types[k] = all_types.get(k, 0) + v
    for k, v in sorted(all_types.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<16} {v}")

    print()
    print("utility range over all raw candidates:")
    for r in results:
        print(
            f"  seed {r['seed']:>2}: min={r['utility_min']} max={r['utility_max']} "
            f"mean={r['utility_mean']:.4f}"
        )

    with open("/home/ming/.hermes/cache/scratch/mc_results.json", "w") as handle:
        json.dump(results, handle, indent=1)
    print()
    print("full series written to /home/ming/.hermes/cache/scratch/mc_results.json")


if __name__ == "__main__":
    main()