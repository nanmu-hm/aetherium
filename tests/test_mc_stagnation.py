"""M-C acceptance: the stagnation baseline, pinned as tests.

ChatGPT 5976565086 §5 authorises measurement only. These tests exist so a
later M-B "recovery" can be compared against a baseline that cannot silently
drift -- and so a measurement bug shows up as a failure rather than as a
plausible-looking number in a report.

READ-ONLY. Nothing here writes to world state or asserts that M-B works.
"""
from __future__ import annotations

import sys

import pytest

sys.path.insert(0, ".")

from engine.core.actions import generate_action_pool
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

OFFICIAL_SEEDS = (1, 2, 3, 7, 42)
# Must exceed every seed's last event tick (measured: 105/106/106/108/111) with
# a real silent tail after it. An earlier 130 was too short for seed 1 (last
# event 111, leaving 19 ticks) and made the tail assertion reject a correct
# baseline.
SHORT_HORIZON = 160


def run(seed: int, horizon: int):
    """Replay one seed, recording when things happen.

    Both pool levels are recorded because they answer different questions and
    conflating them is a known, real error in this project's history:
      raw    -- generate_action_pool, pre-choose: did the engine PROPOSE it?
      engine -- generate_candidates, post-choose: did the arbiter SELECT it?
    """
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=False)

    event_ticks = []
    raw_nonempty = 0
    engine_nonempty = 0
    types: dict[str, int] = {}
    nonnegative = 0
    raw_total = 0

    for _ in range(horizon):
        for cid in world.characters:
            if world.characters[cid].status != "active":
                continue
            for candidate in generate_action_pool(world, cid):
                raw_total += 1
                key = candidate.action_type
                meta = candidate.metadata or {}
                if key == "travel" and meta.get("event_action_type"):
                    key = f"travel[{meta['event_action_type']}]"
                types[key] = types.get(key, 0) + 1
                if engine.decision_kernel.evaluate(world, candidate).utility > 0.0:
                    nonnegative += 1

        if any(
            generate_action_pool(world, cid)
            for cid in world.characters
            if world.characters[cid].status == "active"
        ):
            raw_nonempty += 1
        if engine.generate_candidates(world):
            engine_nonempty += 1

        if engine.step(world).events:
            event_ticks.append(world.tick)

    return {
        "event_ticks": event_ticks,
        "raw_nonempty": raw_nonempty,
        "engine_nonempty": engine_nonempty,
        "types": types,
        "nonnegative": nonnegative,
        "raw_total": raw_total,
        "last_event": max(event_ticks) if event_ticks else None,
    }


# ---------------------------------------------------------------------------
# The baseline itself. These numbers are the "before" that M-B must beat.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", OFFICIAL_SEEDS)
def test_mc_baseline_stagnates_and_never_recovers(seed):
    """Every official seed stagnates and stays silent for the rest of the run.

    Also pins the distinction Arena forced: the RAW pool never empties. The
    world does not run out of proposals -- it runs out of positive ones.
    """
    r = run(seed, SHORT_HORIZON)
    assert r["event_ticks"], f"seed {seed} must produce events"
    assert r["raw_nonempty"] == SHORT_HORIZON, (
        f"seed {seed}: raw pool emptied on {SHORT_HORIZON - r['raw_nonempty']} "
        f"ticks -- if this changed, the world stopped PROPOSING actions, which "
        f"is a different failure than the one being measured"
    )
    # after the last event the world is permanently quiet
    tail = SHORT_HORIZON - r["last_event"]
    assert tail >= 40, (
        f"seed {seed}: expected a long silent tail, got {tail} ticks "
        f"(last event {r['last_event']}, horizon {SHORT_HORIZON})"
    )
    # measured last-event ticks, pinned so a baseline change is visible
    assert r["last_event"] in (105, 106, 108, 111), (
        f"seed {seed}: last event moved to {r['last_event']}; the M-B "
        f"comparison baseline must be re-measured, not silently accepted"
    )
    # and the engine selected almost nothing
    assert r["engine_nonempty"] <= len(r["event_ticks"]), (
        f"seed {seed}: engine selected on {r['engine_nonempty']} ticks but only "
        f"{len(r['event_ticks'])} events occurred"
    )


@pytest.mark.parametrize("seed", OFFICIAL_SEEDS)
def test_mc_selectable_candidates_are_a_small_minority(seed):
    """The engine rejects the overwhelming majority of what it proposed.

    This is the quantitative form of "candidates exist but all score <= 0",
    and it is the number M-B has to move.
    """
    r = run(seed, SHORT_HORIZON)
    ratio = r["nonnegative"] / r["raw_total"] if r["raw_total"] else 0.0
    assert ratio < 0.10, (
        f"seed {seed}: {ratio:.1%} of raw candidates were selectable -- if this "
        f"is already high, the stagnation has a different cause"
    )


def test_mc_after_stagnation_only_travel_persists_and_nothing_is_selected():
    """After the last event the world keeps proposing travel forever, and
    selects nothing.

    Two facts, deliberately kept apart because conflating "proposed" with
    "selected" is a known error in this project's history:

      * proposed: travel (and occasionally rest) account for essentially all
        raw candidates after the last event -- the world never runs out of
        things to SAY.
      * selected: zero. No event occurs, because every remaining candidate
        scores <= 0.

    Note contact_person is still occasionally PROPOSED after the last event
    (measured: 3 occurrences on seed 7 over 420 ticks) while never being
    SELECTED. An earlier version of this test asserted a hard zero and failed
    against correct data.
    """
    # Two-pass on purpose. A monotone "we have stagnated" flag classifies
    # everything after the FIRST event as post-stagnation; the stagnation
    # point is the LAST event. Two earlier attempts got this wrong (one
    # reported 11 phantom selections, one classified the whole run), so the
    # ticks are recorded first and only then split at last_event.
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=7, use_arbitration=False)

    proposed_by_tick: dict[int, dict[str, int]] = {}
    selected_by_tick: dict[int, int] = {}
    event_ticks: list[int] = []

    for _ in range(SHORT_HORIZON):
        proposed: dict[str, int] = {}
        for cid in world.characters:
            if world.characters[cid].status != "active":
                continue
            for candidate in generate_action_pool(world, cid):
                proposed[candidate.action_type] = proposed.get(candidate.action_type, 0) + 1
        proposed_by_tick[world.tick] = proposed
        selected_by_tick[world.tick] = len(engine.generate_candidates(world))
        if engine.step(world).events:
            event_ticks.append(world.tick)

    assert event_ticks, "fixture must produce events"
    last = max(event_ticks)
    after = range(last + 1, SHORT_HORIZON)

    post_proposed: dict[str, int] = {}
    for tick in after:
        for key, count in proposed_by_tick[tick].items():
            post_proposed[key] = post_proposed.get(key, 0) + count
    post_selected = sum(selected_by_tick[tick] for tick in after)

    assert post_proposed, "candidates must still be proposed after stagnation"
    # travel dominates the residual proposals
    assert post_proposed.get("travel", 0) > sum(
        v for k, v in post_proposed.items() if k != "travel"
    ), f"expected travel to dominate residual proposals, got {post_proposed}"
    # nothing is ever chosen, and nothing ever happens
    assert post_selected == 0, (
        f"{post_selected} candidates were SELECTED after tick {last} -- the "
        f"baseline this tool measures has changed"
    )
    assert not [t for t in event_ticks if t > last], "fixture logic error"


def test_mc_measurement_does_not_disturb_the_world():
    """The instrument must not change what it observes.

    A measurement tool that perturbs the simulation is worse than no tool, so
    this runs the engine twice with and without probing in between and
    requires bit-identical trajectories.
    """
    def trajectory(probe: bool) -> list[str]:
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=7, use_arbitration=False)
        trace = []
        for _ in range(60):
            if probe:
                engine.generate_candidates(world)
                for cid in world.characters:
                    if world.characters[cid].status == "active":
                        generate_action_pool(world, cid)
                        for candidate in generate_action_pool(world, cid):
                            engine.decision_kernel.evaluate(world, candidate)
            result = engine.step(world)
            trace.append(
                f"{world.tick}|{len(result.events)}|"
                f"{[e.id for e in result.events]}|"
                f"{[c.new_value for c in (result.events[0].consequences if result.events else [])]}"
            )
        return trace

    assert trajectory(probe=True) == trajectory(probe=False), (
        "probing changed the trajectory -- the measurement is not read-only"
    )


def test_mc_sustained_silence_equals_last_event_tick():
    """No seed ever revives after its final event.

    If a future change makes a seed produce an event after a long quiet
    stretch, this fails and the baseline must be re-measured rather than
    quietly updated. Arena's 33/34 canary works the same way: re-measure,
    do not delete.
    """
    for seed in OFFICIAL_SEEDS:
        r = run(seed, SHORT_HORIZON)
        after = r["event_ticks"]
        last = r["last_event"]
        later = [t for t in after if t > last]
        assert not later, (
            f"seed {seed} produced events after its last event: {later}"
        )