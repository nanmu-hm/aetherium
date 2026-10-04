"""ChatGPT's path-C A/B, corrected after the first design failed.

The first attempt added goal-directed pressure to TRAVEL and got zero events.
The reason was a design error on my side, and finding it produced the real
result:

  * yan's goal stage 1 asks for help_person; the pool only ever offers travel
  * help_person's generation gate requires the TARGET to be distressed
  * at the stagnation point rui is not distressed at all
    (emotions ~1.0, fatigue 0.0)

So the goal names an action whose PRECONDITION is absent from the world. That
is exactly the "goal exists, precondition long-term missing" shape ChatGPT
described -- but the blocking gate is `distressed`, not the motive key.

This script runs the honest version:

  A  as-is                                   expect 0 events (stagnation)
  B  goal-directed pressure on travel         expect 0 -- travel has no goal leg
  C  precondition-driven: make the goal's own
     required precondition present            does the world revive, and is
                                             the revival SUSTAINABLE?

Arm C is applied the way the world would have to actually do it -- by giving
rui the distress the goal asks for -- not by inventing a new attribute.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.action_types import canonical_action_type
from engine.core.actions import generate_action_pool, goal_matches_action
from engine.core.decision import DecisionKernel
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEED = 7
STAG = 110
PROBE = 200
TEXTURE = 0.124


def goal_pressure(character, action) -> float:
    action_type = ("search_person" if action.metadata.get("search_target")
                   else canonical_action_type(action.action_type))
    goal = max((g for g in character.goals if g.status == "active"),
               key=lambda g: g.priority, default=None)
    if goal is None:
        return 0.0
    p = 0.0
    if goal_matches_action(goal.description, action_type):
        p = max(p, goal.priority)
    if goal.stage_conditions and goal.current_stage < len(goal.stage_conditions):
        s = goal.stage_conditions[goal.current_stage]
        acts = s.get("action_types") or ()
        if acts and action_type in acts:
            p = max(p, goal.priority)
        tid = s.get("target_id")
        if tid and action.targets and tid in action.targets:
            p = max(p, goal.priority)
    return min(1.0, p)


class GoalDirectedTravelKernel(DecisionKernel):
    """Arm B: goal-directed pressure on travel only."""

    @staticmethod
    def _human_condition_urgency(character, action) -> float:
        base = DecisionKernel._human_condition_urgency(character, action)
        at = ("search_person" if action.metadata.get("search_target")
              else canonical_action_type(action.action_type))
        if at != "travel":
            return base
        return min(1.0, base + goal_pressure(character, action))


def run(kernel_cls, mutate=None, seed=SEED, ticks=PROBE, start=STAG):
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=False)
    if kernel_cls is not DecisionKernel:
        engine.decision_kernel = kernel_cls(seed=seed)
    for _ in range(start):
        engine.step(world)
    if mutate:
        mutate(world)
    events = []
    for _ in range(ticks):
        for e in engine.step(world).events:
            events.append((e.tick, e.action_type, tuple(e.participants)))
    kinds = {}
    for _, k, _ in events:
        kinds[k] = kinds.get(k, 0) + 1
    return events, kinds, world


def give_distress(world):
    """Supply the precondition the goal already names: rui in need.

    Only existing state channels are used -- emotions.sorrow and fatigue --
    because those are precisely what the help_person gate reads.
    """
    world.characters["rui"].emotions["sorrow"] = 40.0
    world.characters["rui"].human_condition.fatigue = 30.0


print("=" * 98)
print("CHATGPT PATH-C A/B -- corrected design")
print(f"  seed {SEED}, intervene at tick {STAG}, run {PROBE} ticks")
print(f"  natural texture for reference: {TEXTURE:.3f} events/tick")
print("=" * 98)

arms = (
    ("A  as-is", DecisionKernel, None),
    ("B  + goal-directed pressure on travel", GoalDirectedTravelKernel, None),
    ("C  + goal's own precondition present", DecisionKernel, give_distress),
)

results = {}
print()
print(f"{'arm':<40} {'events':>7} {'ev/tick':>8} {'kinds':>6} {'dominant':>9} {'window':>13}")
print("-" * 98)
for name, kern, mut in arms:
    ev, kinds, world = run(kern, mut)
    results[name] = (ev, kinds, world)
    dom = max(kinds.values()) / len(ev) if ev else 0.0
    win = f"{ev[0][0]}..{ev[-1][0]}" if ev else "—"
    print(f"{name:<40} {len(ev):>7} {len(ev)/PROBE:>8.3f} {len(kinds):>6} "
          f"{dom:>8.1%} {win:>13}")

print()
print("event type mix")
for name, (ev, kinds, _) in results.items():
    print(f"   {name:<40} {kinds or 'none'}")

print()
print("arm C full trace (first 40)")
ev_c, kinds_c, world_c = results["C  + goal's own precondition present"]
for tick, kind, who in ev_c[:40]:
    print(f"   {tick:>4}  {kind:<14} {who}")
if len(ev_c) > 40:
    print(f"   ... {len(ev_c) - 40} more")

print()
print("--- SUSTAINABILITY of C ---")
if ev_c:
    span = ev_c[-1][0] - ev_c[0][0] + 1
    ticks_with = len({t for t, _, _ in ev_c})
    print(f"   events {len(ev_c)} over span {span} ticks, "
          f"{ticks_with} distinct ticks")
    print(f"   density {len(ev_c)/PROBE:.3f}/tick = "
          f"{len(ev_c)/PROBE/TEXTURE:.1f}x the natural texture")
    print(f"   distinct action types: {len(kinds_c)} -> {kinds_c}")
    if len(kinds_c) == 1:
        print("   VERDICT: single type = grinding (Arena 5976763935 §5 warned of this)")
    else:
        print("   VERDICT: multiple types = more story-like")
else:
    print("   no events")

print()
print("--- did C change state / produce new candidates? ---")
for cid, c in sorted(world_c.characters.items()):
    print(f"   {cid}: loc={c.location} fatigue={c.human_condition.fatigue}")
    print(f"      desires: { {k: round(v,2) for k,v in c.human_condition.desires.items()} }")
    print(f"      emotions: { {k: round(v,2) for k,v in c.emotions.items()} }")
    print(f"      carriers: { {k:(v.lifecycle, round(v.strength,1)) for k,v in c.desire_carriers.items()} }")
    g = c.goals[0] if c.goals else None
    if g:
        print(f"      goal={g.description!r} status={g.status} "
              f"stage={g.current_stage}/{len(g.stage_conditions)}")

print()
print("--- ABLATION ---")
print("   A is the exact ablation of C (same seed, same tick, no precondition).")
print(f"   A events {len(results['A  as-is'][0])} vs C events {len(ev_c)}")