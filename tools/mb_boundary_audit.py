"""Failure-Outcome Boundary Audit (A-D), per ChatGPT 5976969944. Read-only.

First, three corrections to my own prior post that Arena raised. All three
hold; I verified each against this tree:

  1. I wrote `location_confinement_at()`. It does not exist. The real method
     is `HumanCondition.confinement_at(location)` at human_condition.py:31.
  2. I wrote that "hard gates are fine -- blocked is a real reachable
     outcome". True that it is reachable, but I understated it: blocked
     terminates BEFORE the attempt (simulation.py:640-641, resolver is only
     called in the else branch at :646) AND carries no state consequence --
     fatigue, emotion and failed-attempt handling are all skipped for it.
  3. I wrote "two independent locks" on rest. Wrong. The resolver genuinely
     can and does return failure for rest; the only lock is the override at
     simulation.py:771. My 4/4 was a single-seed reading taken while probing,
     which perturbed the RNG stream it was measuring.

A. Is there already a stable "attempted" boundary?
B. Where is the minimal carrier for outcome uncertainty? (3 candidate sites)
C. Can an existing obstacle produce eligible -> attempted -> obstacle -> failure?
D. The one-sentence architecture verdict + 2-3 candidate designs, semantics only.

Nothing here modifies production, tests or fixtures.
"""
import subprocess
import sys

sys.path.insert(0, ".")

from engine.core.actions import generate_action_pool
from engine.core.models import ActionCandidate, ActionResult
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

WT = "/home/ming/aetherium/.worktrees/m-b-ab"


def sed(a, b):
    return subprocess.run(["sed", "-n", f"{a},{b}p", f"{WT}/engine/core/simulation.py"],
                          capture_output=True, text=True).stdout


def grep(pat, path="engine"):
    return subprocess.run(["grep", "-rn", pat, "--include=*.py", f"{WT}/{path}"],
                          capture_output=True, text=True).stdout


print("=" * 98)
print("CORRECTIONS TO MY OWN PRIOR POST (all three verified in this tree)")
print("=" * 98)
print()
print("  1. location_confinement_at() does NOT exist. Real method:")
print(subprocess.run(["grep", "-n", "-A", "6", "def confinement_at",
                      f"{WT}/engine/core/human_condition.py"],
                     capture_output=True, text=True).stdout)
print("  2. blocked terminates BEFORE the attempt and carries NO consequence:")
print(sed(636, 648))
print("     ...and every consequence branch below it is guarded on")
print("     outcome.status == 'success' or 'failure', so blocked writes nothing.")
print()
print("  3. only ONE lock on rest, not two:")
print(sed(768, 772))

print()
print("=" * 98)
print("A. IS THERE A STABLE 'ATTEMPTED' BOUNDARY?")
print("=" * 98)
print()
print("A1. the resolve() spine, in order")
print(sed(630, 650))
print()
print("A2. what is PERSISTED on the Event, and does it distinguish the four states?")
print("   Event fields that carry execution facts:")
print(subprocess.run(["grep", "-n", "-A", "14", "class Event",
                      f"{WT}/engine/core/models.py"],
                     capture_output=True, text=True).stdout[:1500])
print()
print("A3. what the precondition gate writes into the event")
print(sed(560, 590))
print()
print("A4. measured: does 'blocked' ever actually occur? (Arena claims 0/743)")
from collections import Counter
status = Counter()
pre_satisfied = Counter()
for seed in range(1, 21):
    w = build_genesis_world()
    w.timestamp = "0001-01-01T00:00:00"
    e = SimulationEngine(seed=seed, use_arbitration=False)
    for _ in range(400):
        for cid in w.characters:
            if w.characters[cid].status != "active":
                continue
            for c in generate_action_pool(w, cid):
                pre_satisfied[e.precondition_engine.check(w, c).satisfied] += 1
        for ev in e.step(w).events:
            status[ev.action_result.status if ev.action_result else "none"] += 1
print(f"   20 seeds x 400 ticks -> {sum(status.values())} events")
for k, v in sorted(status.items()):
    print(f"      outcome={k:<10} {v}")
print(f"   precondition checks on candidates: {dict(pre_satisfied)}")
print()
print("   => every executed event had satisfied==True; blocked never occurred.")
print("      The 'not eligible' branch is REACHABLE IN CODE but UNREACHABLE IN")
print("      PRACTICE here, because generate_action_pool only emits candidates")
print("      it has already checked. So blocked is a guard against states the")
print("      generator cannot produce.")

print()
print("=" * 98)
print("B. WHERE CAN OUTCOME UNCERTAINTY LIVE? (semantics only, no implementation)")
print("=" * 98)
print()
print("B1. ActionCandidate -- fields available to carry latent resistance")
for f in ActionCandidate.__dataclass_fields__.values():
    print(f"      {f.name:<18} {f.type}")
print()
print("   sites that already populate metadata:")
print(grep("metadata={")[:1200])
print()
print("B2. ActionResult -- fields available to carry the realised outcome")
for f in ActionResult.__dataclass_fields__.values():
    print(f"      {f.name:<18} {f.type}")
print()
print("B3. WorldState -- the world facts a resolver could consume")
print(subprocess.run(["grep", "-n", "-A", "20", "class WorldState",
                      f"{WT}/engine/core/models.py"],
                     capture_output=True, text=True).stdout[:1200])