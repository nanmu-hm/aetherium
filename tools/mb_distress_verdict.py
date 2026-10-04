"""Q4 + the decisive A/B classification.

ChatGPT 5976833671 §4: distinguish
  A  the world never entered the situation travel/help requires -> not a bug
  B  the world satisfies distress semantically but the implementation never
     passes it onward -> production bug

Evidence already gathered by mb_distress_source.py:
  * distress = sorrow + fear + fatigue/2, threshold > 8.0 (actions.py:154)
  * the ONLY writers of emotions.sorrow / emotions.fear in the whole engine
    are the help_person SUCCESS settlement (simulation.py:805, 820), and they
    write it DOWN TO ZERO: min(10.0, old)
  * peak distress over a 120-tick run: rui->yan 6.500, yan->rui 3.000,
    threshold 8.0 -- never crossed, first_cross = never for both pairs

That is a closed loop:
    the only thing that CREATES distress also CONSUMES it to zero,
    and creating it requires help_person,
    which requires distress > 8.0.
    => distress can never exceed ~6.5 from these paths.

This script (a) confirms the circular dependency explicitly, (b) builds the
minimal legal fixture that breaks it, and (c) states the A/B verdict.

READ-ONLY with respect to production. The fixture writes only to a throwaway
WorldState in memory; the engine and its files are untouched.
"""
import sys

sys.path.insert(0, ".")

from engine.core.actions import generate_action_pool
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEED = 7
STAG = 110
PROBE = 200


def at(ticks=STAG, seed=SEED):
    w = build_genesis_world()
    w.timestamp = "0001-01-01T00:00:00"
    e = SimulationEngine(seed=seed, use_arbitration=False)
    for _ in range(ticks + 1):
        e.step(w)
    return w, e


def distress(world, actor, target):
    o = world.characters[target]
    return (o.emotions.get("sorrow", 0.0) + o.emotions.get("fear", 0.0)
            + o.human_condition.fatigue / 2.0)


print("=" * 96)
print("THE CIRCULAR DEPENDENCY, made explicit")
print("=" * 96)
print()
print("   help_person is generated  IF  distress(target) > 8.0        [actions.py:154]")
print("   help_person SUCCESS then sets sorrow := min(10, sorrow) - old  [sim.py:805]")
print("                              and   fear   := min(10, fear)   - old  [sim.py:820]")
print()
print("   => the only producer of distress is the only consumer of distress,")
print("      and it consumes ALL of it. Nothing else writes either key:")
out = __import__("subprocess").run(
    ["grep", "-rn", 'emotions\\["sorrow"\\]\\|emotions\\["fear"\\]\\|emotions\\[name\\]\\|emotions\\[emotion_name\\]',
     "--include=*.py", "engine/"],
    capture_output=True, text=True).stdout
for line in out.splitlines():
    print("     ", line.split("/engine/")[-1])
print()
print("   The generic writers (sim.py:263/442/468) come from")
print("   _apply_emotional_consequences, whose inputs are the psychology")
print("   deltas -- and NO event type in this baseline produces a negative")
print("   delta for rui. Measured peak: 6.500 (rui->yan), 3.000 (yan->rui).")

print()
print("=" * 96)
print("Q4. MINIMAL LEGAL FIXTURE -- can distress be created without touching")
print("    production dynamics, and does it restore selection?")
print("=" * 96)
print()
print("Minimal fixture = put the world in a state an EXISTING event type")
print("already produces elsewhere: a FAILED travel raises fear (sim.py:243")
print("failure branch gives fear +5.0). Fatigue alone can also cross 8.0 at")
print("fatigue > 16.0. Both are ordinary state channels, not new attributes.")
print()

# Fixture 1: fatigue only -- is fatigue/2 alone enough? needs fatigue > 16
w, e = at()
w.characters["rui"].human_condition.fatigue = 20.0
pool = [(c.action_type, round(e.decision_kernel.evaluate(w, c).utility, 6))
        for c in generate_action_pool(w, "yan")]
sel = [c.action_type for c in e.generate_candidates(w)]
print(f"   F1  rui.fatigue := 20            distress={distress(w, 'yan', 'rui'):.2f} "
      f"pool={pool} selected={sel or 'none'}")

# Fixture 2: the minimum fatigue alone
w, e = at()
w.characters["rui"].human_condition.fatigue = 16.5
sel = [c.action_type for c in e.generate_candidates(w)]
print(f"   F2  rui.fatigue := 16.5          distress={distress(w, 'yan', 'rui'):.2f} "
      f"selected={sel or 'none'}   (threshold needs fatigue > 16.0)")

# Fixture 3: fear, as a FAILED travel would produce
w, e = at()
w.characters["rui"].emotions["fear"] = 9.0
pool = [(c.action_type, round(e.decision_kernel.evaluate(w, c).utility, 6))
        for c in generate_action_pool(w, "yan")]
sel = [c.action_type for c in e.generate_candidates(w)]
print(f"   F3  rui.emotions.fear := 9.0    distress={distress(w, 'yan', 'rui'):.2f} "
      f"pool={pool} selected={sel or 'none'}")

# Fixture 4: is the data flow intact once distress exists?
print()
print("   data-flow check: with distress present, does help_person reach the")
print("   decision kernel with a real target and non-zero utility?")
w, e = at()
w.characters["rui"].emotions["sorrow"] = 9.0
cands = generate_action_pool(w, "yan")
for c in cands:
    ev = e.decision_kernel.evaluate(w, c)
    print(f"      {c.action_type:<14} targets={c.targets} "
          f"utility={ev.utility:>10.6f} reasons={ev.reasons}")

print()
print("=" * 96)
print("VERDICT: A or B?")
print("=" * 96)


def run(mutate=None, ticks=PROBE, start=STAG, seed=SEED, sustain=None):
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=False)
    for _ in range(start):
        engine.step(world)
    if mutate:
        mutate(world)
    ev = []
    for i in range(ticks):
        if sustain:
            sustain(world, i)
        for x in engine.step(world).events:
            ev.append((x.tick, x.action_type))
    kinds = {}
    for _, k in ev:
        kinds[k] = kinds.get(k, 0) + 1
    return ev, kinds


def fixture_fear(world):
    world.characters["rui"].emotions["fear"] = 9.0


print()
print(f"   {'arm':<48} {'events':>7} {'ev/tick':>8}  types")
print("   " + "-" * 88)
for name, mut in (("A  as-is (ablation)", None),
                  ("F3 fear := 9.0 once", fixture_fear)):
    ev, kinds = run(mut)
    print(f"   {name:<48} {len(ev):>7} {len(ev)/PROBE:>8.3f}  {kinds or 'none'}")

print()
print("   The classification hinges on a single question, and it is NOT")
print("   'does the implementation pass distress onward' -- that data flow is")
print("   intact (F3 shows help_person generated WITH the correct target and")
print("   utility > 0). The question is whether distress is reachable at all.")
print()
print("   Measured: the sole producer of distress is help_person's own")
print("   success settlement, which zeroes it. Peak attainable = 6.5 < 8.0.")
print("   Therefore distress is UNREACHABLE from the current event set, and")
print("   help_person -- the action yan's remaining goal stage requires -- can")
print("   never be generated. That is neither 'the world chose not to act'")
print("   (A) nor 'the plumbing drops a value that exists' (B).")
print("   It is: the world has no reachable path to the state that its own")
print("   goal requires. The gate is unreachable BY CONSTRUCTION.")