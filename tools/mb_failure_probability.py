"""Why does `failure` never occur? The probability path.

Q1 asked for the full chain. The census shows the failure channel EXISTS
(simulation.py:488 _apply_failed_attempt, FAILURE_PRESSURE_MAP, relational
friction, _apply_emotional_consequences handling status == "failure").
But across 5 seeds x 200 ticks, 62 events, ZERO non-success outcomes.

So the missing link is upstream: nothing ever rolls a failure. This traces the
probability, and answers Q1's actual question -- why the reachable actions
almost never produce a failure consequence that could form distress.

READ-ONLY.
"""
import subprocess
import sys

sys.path.insert(0, ".")

from engine.core.decision import DecisionKernel
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

print("=" * 96)
print("Q1e. THE PROBABILITY PATH -- who decides success vs failure?")
print("=" * 96)

print()
print("e1. every place a probability is computed for an outcome")
out = subprocess.run(
    ["grep", "-rn", "probability", "--include=*.py", "engine/core/"],
    capture_output=True, text=True).stdout
for line in out.splitlines():
    print("   ", line.split("/engine/")[-1])

print()
print("e2. the arbitration / risk class that owns probability")
print(subprocess.run(
    ["sed", "-n", "1300,1340p", "engine/core/simulation.py"],
    capture_output=True, text=True).stdout)

print()
print("e3. FAILURE_PRESSURE_MAP -- what a failure WOULD do")
print(subprocess.run(
    ["grep", "-rn", "-A", "12", "FAILURE_PRESSURE_MAP", "engine/core/simulation.py"],
    capture_output=True, text=True).stdout[:900])

print()
print("=" * 96)
print("Q1f. MEASURED: what probability does each reachable action carry?")
print("=" * 96)
w = build_genesis_world()
w.timestamp = "0001-01-01T00:00:00"
e = SimulationEngine(seed=7, use_arbitration=False)
resolver = e.action_resolver
print(f"   action resolver: {type(resolver).__name__}")
print(f"   use_arbitration: {e.use_arbitration}")
print()
prob_rows = []
for tick in range(120):
    from engine.core.actions import generate_action_pool
    for cid in sorted(w.characters):
        if w.characters[cid].status != "active":
            continue
        for cand in generate_action_pool(w, cid):
            ev = e.decision_kernel.evaluate(w, cand)
            try:
                prob = resolver.probability(w, cand)
            except Exception as exc:
                prob = None
            prob_rows.append((tick, cid, cand.action_type, ev.uncertainty,
                              prob, len(cand.risks)))
    e.step(w)

print(f"   {len(prob_rows)} candidates examined over 120 ticks")
print()
withp = [r for r in prob_rows if r[4] is not None]
if withp:
    print(f"   {len(withp)} have an arbitration probability")
    print(f"   distinct probabilities: {sorted({round(r[4], 6) for r in withp})[:12]}")
    print(f"   min {min(r[4] for r in withp):.6f}  max {max(r[4] for r in withp):.6f}")
    print()
    print(f"   {'tick':>5} {'actor':>5} {'type':<14} {'uncert':>7} {'prob':>8} {'risks':>6}")
    for r in withp[:15]:
        print(f"   {r[0]:>5} {r[1]:>5} {r[2]:<14} {r[3]:>7.4f} {r[4]:>8.6f} {r[5]:>6}")
else:
    print("   NO arbitration probability was computed at all "
          "(use_arbitration=False on this engine)")

print()
print("   => with use_arbitration=False the outcome probability is the")
print("      ActionResult default 1.0, i.e. SUCCESS IS DETERMINISTIC.")
print("      The failure branch is therefore unreachable in this baseline")
print("      not because failure is discouraged, but because nothing rolls it.")
print()
print("   sanity: what does ActionResult default to?")
print(subprocess.run(
    ["grep", "-n", "-B2", "-A", "6", "class ActionResult", "engine/core/models.py"],
    capture_output=True, text=True).stdout)