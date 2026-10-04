"""CORRECTION: failure is not structurally unreachable -- I overstated it.

My previous message claimed world_validated pins EVERY candidate to 1.0 and
therefore the failure branch is unreachable. Measuring the probability per
candidate shows that is wrong:

    251 candidates examined over 120 ticks
    distinct probabilities: [0.632844, 1.0]

`rest` (actions.py:269) is the one generator that does NOT stamp
world_validated, so it goes through the real stochastic path:

    ability      0.5 + 0.35*(0.5 - 0.05)          (no required_ability -> 0.5)
    confidence   0.25 + 0.75*0.95
    = 0.632844

So the failure branch IS live. The accurate statement is narrower and more
interesting:

  * failure can occur, but only for `rest`
  * `rest` is generated for fatigue recovery, and its failure consequence is
    FAILURE_PRESSURE_MAP["rest"] -- which is empty, because a failed rest has
    no interpersonal target and no unresolved-pressure story
  * every action that COULD form distress (contact_person, help_person,
    travel, search_person) is world_validated -> probability 1.0 -> can never
    fail -> _apply_failed_attempt never sees them

So the endogenous failure entry exists for exactly one action, and that one
action is the only action whose failure cannot produce distress.

This script measures both halves of that claim rather than asserting it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.actions import generate_action_pool
from engine.core.simulation import FAILURE_PRESSURE_MAP, SimulationEngine
from engine.genesis import build_genesis_world

print("=" * 96)
print("CORRECTION 1 -- which actions can fail at all?")
print("=" * 96)

w = build_genesis_world()
w.timestamp = "0001-01-01T00:00:00"
e = SimulationEngine(seed=7, use_arbitration=False)
resolver = e.action_resolver

seen = {}
for _ in range(120):
    for cid in sorted(w.characters):
        if w.characters[cid].status != "active":
            continue
        for cand in generate_action_pool(w, cid):
            key = cand.action_type
            prob = resolver.probability(w, cand)
            validated = bool((cand.metadata or {}).get("world_validated"))
            seen.setdefault(key, set()).add((round(prob, 6), validated))
    e.step(w)

print()
print(f"   {'action':<16} {'probability':>12} {'world_validated':>17} {'can fail?':>10}")
print("   " + "-" * 62)
for key in sorted(seen):
    for prob, validated in sorted(seen[key]):
        print(f"   {key:<16} {prob:>12.6f} {str(validated):>17} "
              f"{('YES' if prob < 1.0 else 'NO'):>10}")

print()
print("=" * 96)
print("CORRECTION 2 -- what does a failure of each action DO?")
print("=" * 96)
print()
print("   FAILURE_PRESSURE_MAP (simulation.py):")
for action_type, pressures in sorted(FAILURE_PRESSURE_MAP.items()):
    print(f"      {action_type:<16} -> {pressures}")
print()
print("   Action types that appear in the baseline but NOT in the map:")
for key in sorted(seen):
    if key not in FAILURE_PRESSURE_MAP:
        print(f"      {key:<16} -> NO ENTRY (failure produces no desire pressure)")

print()
print("   The distress-producing consequences in _apply_failed_attempt:")
print("      failed contact_person -> trust down, resentment up")
print("      failed help_person    -> recipient trust -2.0, loyalty -1.0")
print("      failure outcome       -> fear +5.0, regret +2.0 (sim.py:243)")
print("      => ANY failure yields fear +5.0, which is 5.0 of the 8.0")
print("         distress threshold. Two failures would clear it -- but they must")
print("         come from an action that can fail.")

print()
print("=" * 96)
print("THE PRECISE STATEMENT")
print("=" * 96)
print()
print("   Not 'failure is unreachable'.")
print("   Rather: failure is reachable ONLY for rest, and rest is the only")
print("   action with no distress-relevant failure consequence. Every action")
print("   that could form distress is world_validated, so its probability is")
print("   pinned to 1.0 and it can never fail.")
print()
print("   The endogenous failure entry and the distress-producing failures")
print("   are disjoint sets. That is the structural fact.")

print()
print("=" * 96)
print("DOES rest EVER FAIL IN PRACTICE? (seed sweep)")
print("=" * 96)
from collections import Counter
totals = Counter()
for seed in (1, 2, 3, 7, 42):
    w2 = build_genesis_world()
    w2.timestamp = "0001-01-01T00:00:00"
    e2 = SimulationEngine(seed=seed, use_arbitration=False)
    c = Counter()
    for _ in range(400):
        for ev in e2.step(w2).events:
            st = ev.action_result.status if ev.action_result else "none"
            c[(ev.action_type, st)] += 1
            totals[(ev.action_type, st)] += 1
    fails = {k: v for k, v in c.items() if k[1] != "success"}
    print(f"   seed {seed:>2}: {sum(c.values()):>3} events, "
          f"non-success = {sum(fails.values())} {fails if fails else ''}")
print()
print("   all seeds x 400 ticks:")
for (a, s), n in sorted(totals.items()):
    print(f"      {a:<16} {s:<10} {n}")
non_success = sum(n for (a, s), n in totals.items() if s != "success")
print()
print(f"   TOTAL non-success outcomes across 5 seeds x 400 ticks: {non_success}")
print()
if non_success == 0:
    print("   => even rest, the one action that CAN fail, never does in practice.")
    print("      Its probability is 0.632844 per attempt, but it is generated")
    print("      only when fatigue > 0 and resolves to fatigue 0, so the")
    print("      candidate usually disappears before fatigue can build up.")
    print("      Measuring that directly next.")
print()
print("=" * 96)
print("WHY rest NEVER FAILS: is the rest candidate ever selected?")
print("=" * 96)
selected_rest = 0
attempted_rest = 0
for seed in (1, 2, 3, 7, 42):
    w3 = build_genesis_world()
    w3.timestamp = "0001-01-01T00:00:00"
    e3 = SimulationEngine(seed=seed, use_arbitration=False)
    for _ in range(400):
        pool = []
        for cid in sorted(w3.characters):
            if w3.characters[cid].status == "active":
                pool.extend(generate_action_pool(w3, cid))
        if any(c.action_type == "rest" for c in pool):
            attempted_rest += 1
        for ev in e3.step(w3).events:
            if ev.action_type == "rest":
                selected_rest += 1
                if ev.action_result and ev.action_result.status != "success":
                    selected_rest += 1000
print(f"   ticks where a rest candidate EXISTED : {attempted_rest}")
print(f"   rest events actually executed       : {selected_rest}")
print(f"   rest failures                       : {max(0, selected_rest - (selected_rest % 1000))}")
print()
print("   probability of a rest attempt failing ~0.367; over the executed")
print("   rests above, a zero-failure count would be the expected observation")
print("   only if the sample is small. The number above is the sample.")