"""ChatGPT's minimal A/B for path (C): goal-directed action pressure.

ChatGPT (platform ruling; note the referenced comment id 5976753821 never
landed on GitHub -- the ruling text was delivered in the platform
conversation):

  A  keep as-is:   travel_pressure = f(freedom, curiosity)   -> expect stagnation
  B  add ONE semantically legitimate alternative driver:
        travel_pressure = existing freedom/curiosity pressure
                        + goal-directed pressure
     where the goal-directed term must come from EXISTING character
     goal/relationship state -- no invented attributes.

No production file is edited. The variant subclasses DecisionKernel and
overrides ONLY the travel pressure term; the engine's own decision_kernel
attribute is then swapped for the run, so the whole
candidate -> utility -> eligibility -> target -> decision -> Event pipeline
runs unchanged.

The question is NOT "can we make events happen". It is whether a goal-directed
motive revives the world SUSTAINABLY or merely trades one fixed point for
another.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.action_types import canonical_action_type
from engine.core.actions import goal_matches_action
from engine.core.decision import DecisionKernel
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEED = 7
STAGNATION_TICK = 110
PROBE_TICKS = 200
BASELINE_TEXTURE = 0.124          # events/tick over t1..105, for reference


class GoalDirectedKernel(DecisionKernel):
    """Variant B: travel pressure = existing + goal-directed."""

    @staticmethod
    def _human_condition_urgency(character, action) -> float:
        base = DecisionKernel._human_condition_urgency(character, action)
        action_type = (
            "search_person" if action.metadata.get("search_target")
            else canonical_action_type(action.action_type)
        )
        if action_type != "travel":
            return base
        # This hook receives only (character, action) -- no state. That is
        # enough: every goal term used here lives on the character itself.
        extra = _goal_pressure_from_character(character, action)
        return min(1.0, base + extra)


def _goal_pressure_from_character(character, action) -> float:
    action_type = (
        "search_person" if action.metadata.get("search_target")
        else canonical_action_type(action.action_type)
    )
    goal = max(
        (g for g in character.goals if g.status == "active"),
        key=lambda g: g.priority,
        default=None,
    )
    if goal is None:
        return 0.0
    pressure = 0.0
    if goal_matches_action(goal.description, action_type):
        pressure = max(pressure, goal.priority)
    if goal.stage_conditions and goal.current_stage < len(goal.stage_conditions):
        stage = goal.stage_conditions[goal.current_stage]
        stage_actions = stage.get("action_types") or ()
        if stage_actions and action_type in stage_actions:
            pressure = max(pressure, goal.priority)
        target_id = stage.get("target_id")
        if target_id and action.targets and target_id in action.targets:
            pressure = max(pressure, goal.priority)
    return min(1.0, pressure)


def run(kernel_cls, seed=SEED, ticks=PROBE_TICKS, start=STAGNATION_TICK):
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=False)
    if kernel_cls is not DecisionKernel:
        engine.decision_kernel = kernel_cls(seed=seed)
    for _ in range(start):
        engine.step(world)

    events = []
    for _ in range(ticks):
        for event in engine.step(world).events:
            events.append((event.tick, event.action_type))

    kinds: dict[str, int] = {}
    for _, kind in events:
        kinds[kind] = kinds.get(kind, 0) + 1
    dominant = max(kinds.values()) / len(events) if events else 0.0
    return {
        "events": len(events),
        "per_tick": len(events) / ticks,
        "kinds": kinds,
        "distinct_kinds": len(kinds),
        "dominant_share": dominant,
        "first_tick": events[0][0] if events else None,
        "last_tick": events[-1][0] if events else None,
        "trace": events,
        "world": world,
    }


def main():
    print("=" * 94)
    print("CHATGPT PATH-C MINIMAL A/B -- goal-directed action pressure")
    print(f"  seed {SEED}, intervene at tick {STAGNATION_TICK}, run {PROBE_TICKS} ticks")
    print(f"  baseline texture for reference: {BASELINE_TEXTURE:.3f} events/tick")
    print("=" * 94)

    a = run(DecisionKernel)
    b = run(GoalDirectedKernel)

    print()
    print(f"{'arm':<28} {'events':>7} {'ev/tick':>8} {'kinds':>6} "
          f"{'dominant':>9} {'window':>14}")
    print("-" * 94)
    for name, r in (("A  as-is (no motive)", a), ("B  + goal-directed", b)):
        window = f"{r['first_tick']}..{r['last_tick']}" if r["events"] else "—"
        print(f"{name:<28} {r['events']:>7} {r['per_tick']:>8.3f} "
              f"{r['distinct_kinds']:>6} {r['dominant_share']:>8.1%} {window:>14}")
    print(f"{'(reference) baseline texture':<28} {'':>7} {BASELINE_TEXTURE:>8.3f}")

    print()
    print("A event types:", a["kinds"] or "none -- world stayed dead")
    print("B event types:", b["kinds"] or "none")

    print()
    print("B first 24 events:")
    for tick, kind in b["trace"][:24]:
        print(f"   {tick:>4}  {kind}")

    print()
    print("--- sustainability ---")
    if b["events"]:
        span = b["trace"][-1][0] - b["trace"][0][0] + 1
        print(f"   B: {len(b['events'])} events over span {span} ticks")
        print(f"   B density {b['per_tick']:.3f}/tick = "
              f"{b['per_tick'] / BASELINE_TEXTURE:.1f}x the natural rhythm")
        if len(b["kinds"]) == 1:
            print(f"   WARNING single type {list(b['kinds'])[0]!r} = grinding")
        else:
            print(f"   type mix: {b['kinds']} "
                  f"(dominant share {b['dominant_share']:.1%})")

    print()
    print("--- did the event change state / produce new candidates? ---")
    w = b["world"]
    for cid, c in sorted(w.characters.items()):
        print(f"   {cid}: loc={c.location} fatigue={c.human_condition.fatigue}")
        print(f"      desires: "
              f"{ {k: round(v, 2) for k, v in c.human_condition.desires.items()} }")
        print(f"      carriers: "
              f"{ {k: (v.lifecycle, round(v.strength, 1)) for k, v in c.desire_carriers.items()} }")
    print()
    print("--- ablation: arm A IS the ablation (same seed, same start, no goal term)")
    print(f"   A events {a['events']}  vs  B events {b['events']}")


if __name__ == "__main__":
    main()