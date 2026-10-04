"""WHY arm B produced zero events -- and what the correct experiment is.

Finding: yan's goal 'help an old friend' has two stages and both name
action_types ['contact_person'] and ['help_person']. Neither names travel.
goal_matches_action(goal.description, 'travel') is False for every action
type. So a goal-directed term added to TRAVEL is semantically wrong by
construction: travel is not a means toward yan's goal.

ChatGPT's premise was "travel 可能只是为了达到人物目标而移动". For THIS seed
that premise is false: yan's goal has no travel leg at all. So arm B measured
the wrong thing.

Correct experiment: apply the goal-directed pressure to the actions the goal
actually names, and separately measure whether travel EVER has goal-directed
motive available in this baseline.
"""
import sys

sys.path.insert(0, ".")

from engine.core.action_types import canonical_action_type
from engine.core.actions import generate_action_pool, goal_matches_action
from engine.core.decision import DecisionKernel
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEED = 7
STAG = 110
PROBE = 200


def goal_pressure(character, action) -> float:
    action_type = (
        "search_person" if action.metadata.get("search_target")
        else canonical_action_type(action.action_type)
    )
    goal = max((g for g in character.goals if g.status == "active"),
               key=lambda g: g.priority, default=None)
    if goal is None:
        return 0.0
    p = 0.0
    if goal_matches_action(goal.description, action_type):
        p = max(p, goal.priority)
    if goal.stage_conditions and goal.current_stage < len(goal.stage_conditions):
        stage = goal.stage_conditions[goal.current_stage]
        acts = stage.get("action_types") or ()
        if acts and action_type in acts:
            p = max(p, goal.priority)
        tid = stage.get("target_id")
        if tid and action.targets and tid in action.targets:
            p = max(p, goal.priority)
    return min(1.0, p)


class SelectiveGoalKernel(DecisionKernel):
    """Goal-directed pressure, but ONLY where the goal actually points."""

    @staticmethod
    def _human_condition_urgency(character, action) -> float:
        base = DecisionKernel._human_condition_urgency(character, action)
        return min(1.0, base + goal_pressure(character, action))


def run(kernel_cls, seed=SEED, ticks=PROBE, start=STAG):
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=False)
    if kernel_cls is not DecisionKernel:
        engine.decision_kernel = kernel_cls(seed=seed)
    for _ in range(start):
        engine.step(world)
    ev = []
    for _ in range(ticks):
        for e in engine.step(world).events:
            ev.append((e.tick, e.action_type))
    kinds = {}
    for _, k in ev:
        kinds[k] = kinds.get(k, 0) + 1
    return ev, kinds


print("=" * 92)
print("WHY ARM B WAS ZERO, and the corrected experiment")
print("=" * 92)

w = build_genesis_world(); w.timestamp = "0001-01-01T00:00:00"
e = SimulationEngine(seed=SEED, use_arbitration=False)
for _ in range(STAG + 1):
    e.step(w)

print()
print("1. yan's goal at the stagnation point")
c = w.characters["yan"]
for g in c.goals:
    print(f"   {g.id} status={g.status} priority={g.priority} stage={g.current_stage}/{len(g.stage_conditions)}")
    print(f"     description={g.description!r}")
    for i, sc in enumerate(g.stage_conditions):
        print(f"     stage[{i}] action_types={sc.get('action_types')} target={sc.get('target_id')}")

print()
print("2. goal_matches_action against EVERY action type")
for at in ("travel", "pursue_goal", "contact_person", "help_person",
           "search_person", "rest"):
    print(f"   {at:<15} = {goal_matches_action(c.goals[0].description, at)}")

print()
print("3. goal-directed pressure per candidate actually proposed at this tick")
for cand in generate_action_pool(w, "yan"):
    p = goal_pressure(c, cand)
    ev = e.decision_kernel.evaluate(w, cand)
    print(f"   {cand.action_type:<14} goalPressure={p:.4f}  "
          f"utility={ev.utility:>10.6f}  reasons={ev.reasons}")

print()
print("4. corrected arms over", PROBE, "ticks from tick", STAG)
print(f"   {'arm':<44} {'events':>7} {'ev/tick':>8}  types")
print("   " + "-" * 88)
ev_a, k_a = run(DecisionKernel)
print(f"   {'A  as-is':<44} {len(ev_a):>7} {len(ev_a)/PROBE:>8.3f}  {k_a or 'none'}")

ev_c, k_c = run(SelectiveGoalKernel)
print(f"   {'C  goal-directed where the goal points':<44} {len(ev_c):>7} {len(ev_c)/PROBE:>8.3f}  {k_c or 'none'}")

print()
print("5. arm C event trace (first 30)")
for tick, kind in ev_c[:30]:
    print(f"   {tick:>4}  {kind}")

print()
if ev_c:
    span = ev_c[-1][0] - ev_c[0][0] + 1
    print(f"   C: {len(ev_c)} events over span {span} ticks, "
          f"{len(k_c)} distinct type(s), "
          f"dominant {max(k_c.values())/len(ev_c):.1%}")
    if len(k_c) == 1:
        print("   => single action type: that is grinding, not story")
else:
    print("   C produced no events either -- see the note below")

print()
print("NOTE: if C is also zero, the goal-directed premise fails for a second,")
print("      different reason: not that the goal lacks a travel leg, but that")
print("      the goal's remaining stage requires successful_help / contact_person,")
print("      and those actions are gated on the OTHER motive pair")
print("      (reconciliation/belonging), whose carriers are CONSUMED.")
print("      That would mean the blockage is the LIFECYCLE, not the motive key --")
print("      which is Arena's third suspicion, and it is testable separately.")