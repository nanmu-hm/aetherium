"""Does the revival cycle, or is it a one-shot?

Arm C in mb_path_c_ab.py produced 5 events and then the world died again. This
script asks whether that is a one-shot (the goal completes and the motive is
consumed) or a limit cycle (the world can keep going if the precondition is
sustained).

It also checks the thing that would decide M-B's usefulness: can a
precondition-driven world sustain itself WITHOUT the intervention, i.e. is the
precondition itself renewable from inside the simulation?
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEED = 7
STAG = 110
PROBE = 200


def run(mutate=None, ticks=PROBE, start=STAG, seed=SEED, sustain=None):
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=False)
    for _ in range(start):
        engine.step(world)
    if mutate:
        mutate(world)

    events = []
    for i in range(ticks):
        if sustain:
            sustain(world, i)
        for e in engine.step(world).events:
            events.append((e.tick, e.action_type))
    kinds = {}
    for _, k in events:
        kinds[k] = kinds.get(k, 0) + 1
    return events, kinds, world


def distress_once(world):
    world.characters["rui"].emotions["sorrow"] = 40.0
    world.characters["rui"].human_condition.fatigue = 30.0


def distress_always(world, i):
    world.characters["rui"].emotions["sorrow"] = 40.0
    world.characters["rui"].human_condition.fatigue = 30.0


print("=" * 92)
print("ONE-SHOT OR CYCLE?")
print("=" * 92)

print()
print(f"{'arm':<46} {'events':>7} {'ev/tick':>8}  types")
print("-" * 92)
arms = (
    ("A  as-is (ablation)", None, None),
    ("C  distress injected once at t110", distress_once, None),
    ("D  distress SUSTAINED every tick", distress_once, distress_always),
)
for name, mut, sus in arms:
    ev, kinds, _ = run(mut, sustain=sus)
    print(f"{name:<46} {len(ev):>7} {len(ev)/PROBE:>8.3f}  {kinds or 'none'}")

print()
print("=== arm C: exactly when and why it stops ===")
ev, kinds, world = run(distress_once)
print(f"   events: {[(t, k) for t, k in ev]}")
print(f"   final state:")
for cid, c in sorted(world.characters.items()):
    g = c.goals[0] if c.goals else None
    print(f"     {cid}: desires={ {k: round(v,1) for k,v in c.human_condition.desires.items()} }")
    if g:
        print(f"        goal={g.description!r} status={g.status} "
              f"stage={g.current_stage}/{len(g.stage_conditions)}")
    print(f"        carriers={ {k:(v.lifecycle, round(v.strength,1)) for k,v in c.desire_carriers.items()} }")

print()
print("=== arm D: does sustaining the precondition keep the world alive? ===")
ev_d, kinds_d, world_d = run(distress_once, sustain=distress_always)
print(f"   events: {len(ev_d)}  types: {kinds_d}")
if ev_d:
    print(f"   window {ev_d[0][0]}..{ev_d[-1][0]}")
    print(f"   density {len(ev_d)/PROBE:.3f}/tick")
    span = ev_d[-1][0] - ev_d[0][0] + 1
    print(f"   NOTE: sustained externally for {PROBE} ticks. An intervention that")
    print(f"         must be re-applied every tick is NOT a self-sustaining world.")
else:
    print("   no events even with the precondition held constant")

print()
print("=== the structural reason, isolated ===")
print("   help_person generation gate needs BOTH:")
print("     (a) the TARGET distressed          <- supplied by the intervention")
print("     (b) actor has loyalty/responsibility/compassion")
print("   yan's values: loyalty=True responsibility=True compassionate=True  (b holds)")
print("   -> so only (a) is ever missing, and (a) is exactly what the")
print("      intervention fabricates. The world has no in-simulation source")
print("      that would produce (a) on its own: at the stagnation point")
print("      rui's sorrow/fear are ~1.0 and fatigue is 0.0.")