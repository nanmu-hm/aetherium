"""Distress prerequisite: where does it come from, and is its absence a bug?

ChatGPT ruling 5976833671 supersedes the Path-C hypothesis and asks four
questions, all read-only:

  1. what state/events produce `distress` in the current world
  2. why yan lacks it at the stagnation point
  3. which existing event/state transition SHOULD have produced it, or whether
     it legitimately only exists in specific circumstances
  4. whether a minimal legal fixture can create it WITHOUT touching production
     dynamics, and prove it restores travel selection

And the decisive classification:
  A  the world simply never entered the situation travel requires -> not a bug
  B  the world satisfies distress semantically but the implementation never
     passes it to candidate/decision -> production bug

READ-ONLY. Nothing here writes to world state; the engine is never edited.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.actions import generate_action_pool
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEED = 7
STAG = 110


def at(ticks=STAG, seed=SEED):
    w = build_genesis_world()
    w.timestamp = "0001-01-01T00:00:00"
    e = SimulationEngine(seed=seed, use_arbitration=False)
    for _ in range(ticks + 1):
        e.step(w)
    return w, e


print("=" * 96)
print("Q1. WHERE DOES `distress` COME FROM?")
print("=" * 96)

print()
print("1a. every place the distress term is computed (grep)")
out = subprocess.run(
    ["grep", "-rn", "distress", "--include=*.py", "engine/"],
    capture_output=True, text=True).stdout
for line in out.splitlines():
    print("   ", line.split("/engine/")[-1])

print()
print("1b. the exact expression used by the action pool")
out2 = subprocess.run(
    ["grep", "-n", "distressed", "-A", "4", "engine/core/actions.py"],
    capture_output=True, text=True).stdout
print(out2)

print()
print("1c. every writer of the emotion keys that feed it")
for key in ("sorrow", "fear"):
    out3 = subprocess.run(
        ["grep", "-rn", f'"{key}"', "--include=*.py", "engine/"],
        capture_output=True, text=True).stdout
    print(f"   --- {key} ---")
    for line in out3.splitlines():
        print("   ", line.split("/engine/")[-1])

print()
print("=" * 96)
print("Q2. WHY DOES YAN LACK IT AT THE STAGNATION POINT?")
print("=" * 96)
w, e = at()
print()
print("   distress(a -> b) = sorrow + fear + fatigue/2, threshold > 8.0")
print()
print(f"   {'who':<5} {'sorrow':>8} {'fear':>8} {'fatigue':>8} {'score':>8} {'>8?':>5} {'same loc':>9}")
for cid in sorted(w.characters):
    c = w.characters[cid]
    others = [o for o in w.characters if o != cid]
    coloc = [o for o in others if w.characters[o].location == c.location]
    for other in (coloc or [None]):
        if other is None:
            continue
        o = w.characters[other]
        score = (o.emotions.get("sorrow", 0.0) + o.emotions.get("fear", 0.0)
                 + o.human_condition.fatigue / 2.0)
        print(f"   {cid:<5} (as actor, target={other})")
        print(f"        target sorrow={o.emotions.get('sorrow', 0.0):.3f} "
              f"fear={o.emotions.get('fear', 0.0):.3f} "
              f"fatigue={o.human_condition.fatigue:.3f} -> "
              f"score={score:.3f}  >8? {score > 8.0}")

print()
print("   full emotional state at stagnation:")
for cid in sorted(w.characters):
    c = w.characters[cid]
    print(f"     {cid}: { {k: round(v, 4) for k, v in c.emotions.items()} }")
    print(f"        fatigue={c.human_condition.fatigue} "
          f"mortality={c.human_condition.mortality_pressure}")

print()
print("=" * 96)
print("Q3. WHICH TRANSITION SHOULD HAVE PRODUCED IT?")
print("=" * 96)
print()
print("3a. the whole-run history of the distress score for both characters")
w2 = build_genesis_world()
w2.timestamp = "0001-01-01T00:00:00"
e2 = SimulationEngine(seed=SEED, use_arbitration=False)
peak = {}
first_cross = {}
for _ in range(120):
    for cid in w2.characters:
        c = w2.characters[cid]
        others = [o for o in w2.characters if o != cid]
        for other in others:
            if w2.characters[other].location != c.location:
                continue
            o = w2.characters[other]
            score = (o.emotions.get("sorrow", 0.0) + o.emotions.get("fear", 0.0)
                     + o.human_condition.fatigue / 2.0)
            key = f"{cid}->{other}"
            peak[key] = max(peak.get(key, 0.0), score)
            if score > 8.0 and key not in first_cross:
                first_cross[key] = w2.tick
    e2.step(w2)

print(f"   {'pair':<12} {'peak score':>11} {'first tick >8':>15}")
for key in sorted(peak):
    print(f"   {key:<12} {peak[key]:>11.3f} {str(first_cross.get(key, 'never')):>15}")
print()
print(f"   => peak distress over the whole run never exceeds "
      f"{max(peak.values()):.3f}; the gate threshold is 8.0")
print()
print("3b. so what DO the existing event types actually write?")
seen = {}
for ev in w2.event_log:
    seen.setdefault(ev.action_type, ev)
for kind, ev in sorted(seen.items()):
    print(f"   {kind}: {ev.id}")
    for c in ev.consequences[:6]:
        print(f"      {c.kind:<18} {c.target_id:<10} {c.field} "
              f"{c.old_value} -> {c.new_value}")
print()
print("   NOTE: no consequence anywhere targets emotions.sorrow or")
print("         emotions.fear. Check the belief/memory writers too:")
out4 = subprocess.run(
    ["grep", "-rn", "emotions\\[", "--include=*.py", "engine/"],
    capture_output=True, text=True).stdout
for line in out4.splitlines():
    print("   ", line.split("/engine/")[-1])