"""Is the blockage the motive KEY, or the carrier LIFECYCLE?

Both arms of the goal-directed experiment came back with zero events. Before
reporting that as "goal-directed pressure does not work", the premise itself
has to be checked, and the two rival explanations separated:

  H1 (motive key)    the world cannot express "travel toward a goal" because
                     travel_pressure reads only freedom/curiosity.
  H2 (lifecycle)     the goal's remaining stage needs help_person /
                     contact_person, those are gated on reconciliation /
                     belonging, and those carriers are CONSUMED -- so the
                     blockage is consumption, not the key mapping.

Decisive test: give the character the motive the goal actually asks for, with
NO lifecycle change. If the world revives, H2 was the binding constraint and
H1 is not the root cause of stagnation.
"""
import sys

sys.path.insert(0, ".")

from engine.core.actions import generate_action_pool
from engine.core.decision import DecisionKernel
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEED = 7
STAG = 110
PROBE = 200
TEXTURE = 0.124


def at_stag(seed=SEED, ticks=STAG):
    w = build_genesis_world()
    w.timestamp = "0001-01-01T00:00:00"
    e = SimulationEngine(seed=seed, use_arbitration=False)
    for _ in range(ticks + 1):
        e.step(w)
    return w, e


print("=" * 96)
print("WHICH IS BINDING: motive key, or carrier lifecycle?")
print("=" * 96)

print()
print("1. what is actually proposed at the stagnation point")
w, e = at_stag()
for cid in sorted(w.characters):
    for cand in generate_action_pool(w, cid):
        ev = e.decision_kernel.evaluate(w, cand)
        print(f"   {cid:<4} {cand.action_type:<12} targets={cand.targets} "
              f"utility={ev.utility:>10.6f}")
print("   -> if ONLY travel is ever proposed, no amount of goal-directed")
print("      pressure on help_person/contact_person can ever fire.")

print()
print("2. yan's goal remaining stage vs. what is proposed")
c = w.characters["yan"]
g = c.goals[0]
stage = g.stage_conditions[g.current_stage]
print(f"   goal={g.description!r} stage {g.current_stage}/{len(g.stage_conditions)}")
print(f"   stage asks: {stage.get('action_types')} target={stage.get('target_id')}")
print(f"   proposed now: {[x.action_type for x in generate_action_pool(w, 'yan')]}")
print("   -> the goal's stage names an action the pool NEVER offers.")

print()
print("3. WHY the pool does not offer it: help_person gate")
from engine.core.actions import _has_value, has_trait
for cid in sorted(w.characters):
    ch = w.characters[cid]
    others = [o for o in w.characters if o != cid]
    distressed = []
    for other in others:
        o = w.characters[other]
        if o.location != ch.location:
            continue
        distress = (o.emotions.get("sorrow", 0.0) + o.emotions.get("fear", 0.0)
                    + o.human_condition.fatigue / 2.0)
        if distress > 8.0:
            distressed.append((other, round(distress, 2)))
    print(f"   {cid}: distressed co-located = {distressed or 'NONE'}")
    print(f"      has loyalty={_has_value(ch, 'loyalty')} "
          f"responsibility={_has_value(ch, 'responsibility')} "
          f"compassionate={has_trait(ch, 'compassionate', 'protective', 'helpful')}")
    print(f"      desires.responsibility={ch.human_condition.desires.get('responsibility', 0.0)}")
    print(f"      co-located: {[o for o in others if w.characters[o].location == ch.location]}")

print()
print("4. rui's condition -- is anyone actually in distress?")
for cid in sorted(w.characters):
    ch = w.characters[cid]
    print(f"   {cid}: emotions={ {k: round(v, 3) for k, v in ch.emotions.items()} }")
    print(f"        fatigue={ch.human_condition.fatigue}  "
          f"mortality={ch.human_condition.mortality_pressure}")

print()
print("5. the decisive counterfactual: revive ONLY the motive the goal asks for")
print("   (help_person needs responsibility>0 per the generation gate)")
for label, mutate in (
    ("desires.responsibility := 60", lambda w: w.characters["yan"].human_condition.desires.__setitem__("responsibility", 60.0)),
    ("rui.emotions.sorrow := 40", lambda w: w.characters["rui"].emotions.__setitem__("sorrow", 40.0)),
    ("BOTH (gate fully satisfied)", lambda w: (w.characters["yan"].human_condition.desires.__setitem__("responsibility", 60.0),
                                               w.characters["rui"].emotions.__setitem__("sorrow", 40.0))),
):
    w2, e2 = at_stag()
    mutate(w2)
    pool = [(c.actor_id, c.action_type) for c in generate_action_pool(w2, "yan")]
    cands = generate_action_pool(w2, "yan")
    utils = [round(e2.decision_kernel.evaluate(w2, c).utility, 6) for c in cands]
    sel = [a.action_type for a in e2.generate_candidates(w2)]
    print(f"   {label:<36} pool={pool} utility={utils} selected={sel or 'none'}")

print()
print("6. and the lifecycle question, isolated: does clearing CONSUMED alone help")
print("   contact_person (whose motive pair is reconciliation/belonging)?")
for label, mutate in (
    ("carriers -> ACTIVE", lambda w: [setattr(v, "lifecycle", "ACTIVE")
                                       for v in w.characters["yan"].desire_carriers.values()]),
    ("carriers ACTIVE + trust := 20", lambda w: ([setattr(v, "lifecycle", "ACTIVE")
                                                  for v in w.characters["yan"].desire_carriers.values()],
                                                 setattr(w.get_relationship("yan", "rui"), "trust", 20.0))),
):
    w2, e2 = at_stag()
    mutate(w2)
    cands = generate_action_pool(w2, "yan")
    info = [(c.action_type, round(e2.decision_kernel.evaluate(w2, c).utility, 6)) for c in cands]
    sel = [a.action_type for a in e2.generate_candidates(w2)]
    print(f"   {label:<36} {info} selected={sel or 'none'}")