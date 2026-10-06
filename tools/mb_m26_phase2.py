"""M26 Phase-2 -- Narrative Emergence audit (read-only, anchored 0ba1699).

Spec: ChatGPT PR#10 6015214047 (M25-R1/M26-Phase-1 裁定 + Phase-2 规格).
Natural long-horizon trajectory as the sole primary sample; per-
trajectory event-level structural annotation:
  goal/desire -> action -> consequence -> state change ->
  subsequent action
Stats per trajectory: chain length, divergence persistence,
repetition/silence ratio, relationship change, goal change, natural
conflict/failure (NOT OBSERVED if 0, never manufactured).

Judgment target (per spec item 4): if long-horizon runs still
primarily show short-chain-then-silence, repeated actions, or
isolated events, the verdict is NARRATIVE-EMERGENCE NOT MET -- do
NOT substitute "4 causal crossings exist" (M25-R1 result) for a
story-quality judgment.

Anchor 0ba1699; read-only; production HELD; recall() HELD; no weight/
production/test change; no manufactured failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEEDS = (3, 42, 1, 7, 99)
TICKS = 1000


def run(seed: int) -> dict:
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)
    per_tick_actions: list[dict] = []
    events = []
    for _ in range(TICKS):
        res = engine.step(world)
        per_tick_actions.append({a.actor_id: a.id for a in res.actions})
        events.extend(res.events)
    return {"actions": per_tick_actions, "events": events,
            "world": world}


def annotate(run_data: dict) -> dict:
    events = run_data["events"]
    actions = run_data["actions"]
    world = run_data["world"]

    total_committed = sum(
        len([a for a in tick.values() if a])
        for tick in actions)
    silent_ticks = sum(
        1 for tick in actions
        if not any(tick.values()))
    total_ticks = len(actions)

    n_fail = sum(1 for e in events
                 if e.action_result and
                 e.action_result.status == "failure")
    n_success = sum(1 for e in events
                    if e.action_result and
                    e.action_result.status == "success")
    n_blocked = sum(1 for e in events
                    if e.action_result and
                    e.action_result.status == "blocked")

    # repetition: most common action type across all committed actions
    from collections import Counter
    type_counts = Counter()
    for tick in actions:
        for aid in tick.values():
            if aid:
                type_counts[aid.rsplit("-", 1)[-1]] += 1
    rep_ratio = (type_counts.most_common(1)[0][1] / total_committed
                 if total_committed else 0.0)

    # chain links: a committed action at tick t, followed by ANOTHER
    # committed action by the SAME actor 2-5 ticks later (distinct
    # from per-tick cadence gap=1)
    per_actor: dict[str, list[int]] = {}
    for i, tick in enumerate(actions):
        for actor, aid in tick.items():
            if aid:
                per_actor.setdefault(actor, []).append(i)
    chain_links = 0
    for actor, ts in per_actor.items():
        for j in range(len(ts) - 1):
            if 2 <= ts[j + 1] - ts[j] <= 5:
                chain_links += 1
    chain_ratio = chain_links / max(total_committed - 1, 1)

    # relationship / goal change over the whole run
    rel_fields_changed = 0
    for key, rel in world.relationships.items():
        for fld in ("trust", "affection", "loyalty"):
            cur = getattr(rel, fld, None)
            if cur is not None and cur not in (0.0, None):
                rel_fields_changed += 1
    goal_stage_changes = 0
    for ch in world.characters.values():
        for g in ch.goals:
            goal_stage_changes += g.current_stage

    return {
        "total_events": len(events),
        "total_committed": total_committed,
        "silent_ticks": silent_ticks,
        "total_ticks": total_ticks,
        "silent_ratio": silent_ticks / total_ticks,
        "n_fail": n_fail,
        "n_success": n_success,
        "n_blocked": n_blocked,
        "repetition_ratio": rep_ratio,
        "chain_links": chain_links,
        "chain_ratio": chain_ratio,
        "rel_fields_changed": rel_fields_changed,
        "goal_stage_changes": goal_stage_changes,
        "per_actor_action_counts": {
            a: len(ts) for a, ts in per_actor.items()},
        "top_action_type": type_counts.most_common(1)[0][0]
                             if type_counts else None,
    }


def main() -> int:
    print("=" * 72)
    print("M26 Phase-2  Narrative Emergence Audit  (read-only, "
          "anchored 0ba1699)")
    print("=" * 72)

    results = {}
    for seed in SEEDS:
        rd = run(seed)
        a = annotate(rd)
        results[seed] = a
        print(f"\n[seed {seed}] {a['total_events']} events / "
              f"{TICKS} ticks, {a['total_committed']} committed "
              f"actions, silent={a['silent_ticks']} ticks "
              f"({a['silent_ratio']:.2f}), "
              f"top action type={a['top_action_type']} "
              f"(repetition ratio={a['repetition_ratio']:.2f})")
        print(f"  success/failure/blocked = "
              f"{a['n_success']}/{a['n_fail']}/{a['n_blocked']}")
        print(f"  causal chain links (2-5 tick re-action gaps) = "
              f"{a['chain_links']} (ratio={a['chain_ratio']:.2f})")
        print(f"  relationship fields in nonzero state: "
              f"{a['rel_fields_changed']}; goal stage progress "
              f"total: {a['goal_stage_changes']}")
        print(f"  per-actor committed action counts: "
              f"{a['per_actor_action_counts']}")

    print("\n[Verdict]")
    # Spec 6015214047 item 4: narrative-emergence NOT MET when the
    # long-horizon run still primarily shows short-chain-then-silence,
    # repeated actions, or isolated events. We operationalize "short
    # chain" as chain_ratio < 0.20 AND high silence (>=0.90) AND no
    # natural failure -- i.e. the run is dominated by isolated,
    # short-lived bursts followed by long quiet, with travel-style
    # repetition. We do NOT claim a precise universal threshold; each
    # seed's raw numbers are above for three-party inspection.
    not_met = []
    open_ = []
    for seed, r in results.items():
        is_not_met = (r["chain_ratio"] < 0.20
                      and r["silent_ratio"] >= 0.90
                      and r["n_fail"] == 0
                      and r["n_blocked"] == 0)
        if is_not_met:
            not_met.append(seed)
        else:
            open_.append(seed)
    for seed in SEEDS:
        r = results[seed]
        tag = ("NOT MET" if seed in not_met else "OPEN (investigate)")
        print(f"  seed {seed}: {tag}  "
              f"(chain_ratio={r['chain_ratio']:.2f}, "
              f"silent_ratio={r['silent_ratio']:.2f}, "
              f"failure={r['n_fail']}, blocked={r['n_blocked']}, "
              f"repetition={r['repetition_ratio']:.2f})")

    print("\n[Strict spec read: does ANY seed reach narrative-emergence "
          "threshold?]")
    if not open_ and not_met:
        print("  NARRATIVE-EMERGENCE NOT MET (all 5 seeds: short-"
              "chain / high-silence / no-natural-failure pattern; no "
              "seed shows continuous causal story structure). M25-R1's "
              "4 causal crossings do NOT substitute for this judgment "
              "(spec item 4).")
    else:
        print(f"  OPEN seeds {open_} exceed the loose screening "
              "cutoffs; requires closer inspection of whether their "
              "chain links form genuine cause->re-action structure "
              "before any PROVEN claim (do not auto-approve on the "
              "ratio alone).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
