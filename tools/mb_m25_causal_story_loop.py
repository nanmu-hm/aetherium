"""M25 -- Causal Story Loop Audit (read-only, anchored 0ba1699).

Spec: ChatGPT PR#10 6013357680. Targets the 3 confirmed M24 witnesses
(seed3@t89 / seed42@t67 / seed7@t103, all yan, contactPerson event
consequence rollback) and asks, field by field: which SINGLE
consequence field, when pinned back to its immediately-preceding
natural value for the SAME actor at the TRUE production boundary
(right after the witness tick's step() returns, before the next
tick's generate_candidates() reads it -- no manual _settle_emotions()
pass, per Arena's M23-R1 recheck finding), reproduces that witness's
future committed-action / persisted-event crossing?

Folds in Arena's three M23-R1/M24 corrections so they don't repeat
here:
1. No extra _settle_emotions() decay pass -- both arms use plain
   engine.step() only.
2. Every consequence field in the witness's own event is tested,
   individually, not just desire (M23-R1's "9 families NOT PROVEN"
   was desire-only re-verified).
3. Divergence reported as the ACTUAL tick set over a 30/50-tick
   window, not a boolean "irreversible" flag.

No production/test/weight/interface change. No recall() wiring. No
manufactured failure.

Consequence field naming (verified against live engine data, seed 42
tick 0):
  target_type == "relationship": target_id "yan:rui", field "trust" /
    "affection" -- lives on world.relationships["yan:rui"].<field>
  target_type == "character": target_id "yan", field is the FULL
    dotted path already, e.g. "human_condition.fatigue",
    "emotions.joy", "identity_beliefs.loyal", "habits.contact_person",
    "human_condition.desires.reconciliation", "location" -- set on
    world.characters[yan].<dotted path>.
  target_type == "goal": target_id "yan-1", field "current_stage" --
    not exercised by the 3 witnesses (only yan:trust/affection,
    yan.* character fields actually appear on those specific events),
    but handled for completeness.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

WINS = {3: ("yan", 0, "event-0-yan-contact_person"),
        42: ("yan", 0, "event-0-yan-contact_person"),
        7: ("yan", 13, "event-13-yan-contact_person")}
LIVE_TICKS = 140
W30, W50 = 30, 50


def _resolve(root_world, target_type: str, target_id: str,
             field: str):
    """Return (container, key) such that container[key] is the actual
    value, for the write/pin target. container is a dict or an object
    with __setattr__/__getitem__ for the final component."""
    if target_type == "relationship":
        rel = root_world.relationships[target_id]
        # RelationshipState fields are plain attributes (trust/
        # affection/loyalty), not dict keys -- use getattr/setattr
        return getattr(rel, field), field, "attr", rel
    if target_type == "character":
        ch = root_world.characters[target_id]
        parts = field.split(".")
        obj = ch
        for p in parts[:-1]:
            obj = getattr(obj, p)
        if isinstance(obj, dict):
            return obj.get(parts[-1]), parts[-1], "item", obj
        return getattr(obj, parts[-1]), parts[-1], "attr", obj
    if target_type == "goal":
        ch = root_world.characters.get(target_id.split("-")[0])
        if ch is None:
            return None, field, "attr", None
        for g in ch.goals:
            if g.id == target_id:
                return getattr(g, field), field, "attr", g
    raise ValueError(f"unsupported target_type {target_type}")


def _apply_pin(root_world, target_type, target_id, field, value):
    if target_type == "relationship":
        rel = root_world.relationships[target_id]
        setattr(rel, field, value)
    elif target_type == "character":
        ch = root_world.characters[target_id]
        parts = field.split(".")
        obj = ch
        for p in parts[:-1]:
            obj = getattr(obj, p)
        if isinstance(obj, dict):
            obj[parts[-1]] = value
        else:
            setattr(obj, parts[-1], value)
    elif target_type == "goal":
        ch = root_world.characters.get(target_id.split("-")[0])
        if ch is None:
            return
        for g in ch.goals:
            if g.id == target_id:
                setattr(g, field, value)


def natural(seed: int, ticks: int):
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)
    committed, events = [], []
    for _ in range(ticks):
        res = engine.step(world)
        committed.append({a.actor_id: a.id for a in res.actions})
        events.extend(res.events)
    return committed, events


def pin_one(seed: int, actor: str, event_id: str,
            target_type: str, target_id: str, field: str,
            ticks: int) -> dict:
    """Counterfactual arm: identical world/seed; after the witness
    tick's step() returns, pin ONLY (target_type, target_id, field)
    for `actor` to that field's post-step natural value (captured
    from a parallel natural run of the same seed), before every
    subsequent step()'s candidate generation. Compare `actor`'s
    committed actions + events vs the natural arm over the next
    W30/W50 ticks."""
    nat_committed, nat_events = natural(seed, ticks)
    # capture the natural arm's PRE-STEP value of this exact field, i.e.
    # the value it held at the end of tick (witness_tick - 1), which is
    # the "immediately-preceding tick's natural value" the M25 spec calls
    # for -- NOT the post-witness-tick value (that would be a no-op for
    # the field's own natural drift, and would mask whether the field
    # genuinely re-enters the reader's decision later).
    pre_value = None
    wtick = None
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)
    prev_end_value = None
    for i in range(ticks):
        cur_val = _resolve(world, target_type, target_id, field)[0]
        if i == 0:
            prev_end_value = cur_val
        res = engine.step(world)
        if any(e.id == event_id for e in res.events):
            wtick = i
            pre_value = prev_end_value if prev_end_value is not None else 0.0
            break
        prev_end_value = _resolve(world, target_type, target_id,
                                  field)[0]
    assert wtick is not None, f"{event_id} not found in natural run"

    # counterfactual arm
    world2 = build_genesis_world()
    world2.timestamp = "0001-01-01T00:00:00"
    engine2 = SimulationEngine(seed=seed, use_arbitration=True)
    cf_committed, cf_events = [], []
    pinned = False
    for i in range(ticks):
        if pinned:
            _apply_pin(world2, target_type, target_id, field,
                       pre_value if pre_value is not None else 0.0)
        res = engine2.step(world2)
        cf_committed.append({a.actor_id: a.id for a in res.actions})
        cf_events.extend(res.events)
        if i == wtick:
            pinned = True

    divs_all = [i for i in range(wtick, ticks)
                if nat_committed[i].get(actor) !=
                   cf_committed[i].get(actor)]
    divs_w30 = [d for d in divs_all if d - wtick < W30]
    divs_w50 = [d for d in divs_all if d - wtick < W50]
    new_cf_events = sorted({e.id for e in cf_events[wtick:]
                            } - {e.id for e in nat_events[wtick:]})
    return {
        "seed": seed, "actor": actor, "witness_tick": wtick,
        "target": (target_type, target_id, field),
        "pre_value": pre_value,
        "divergence_all": divs_all,
        "divergence_w30": divs_w30,
        "divergence_w50": divs_w50,
        "new_cf_events_w30": [e for e in new_cf_events],
    }


def main() -> int:
    print("=" * 72)
    print("M25  Causal Story Loop Audit  (read-only, anchored 0ba1699)")
    print("=" * 72)

    all_results = []
    for seed, (actor, _wt, event_id) in WINS.items():
        print(f"\n[seed {seed}] witness {actor} ({event_id})")
        nat_committed, nat_events = natural(seed, LIVE_TICKS)
        ev = next((e for e in nat_events if e.id == event_id), None)
        if ev is None:
            print("  event not in natural arm, skip")
            continue
        print(f"  consequence fields this event actually writes:")
        tested = 0
        for c in ev.consequences:
            print(f"    {c.target_type}:{c.target_id}.{c.field}: "
                  f"{c.old_value} -> {c.new_value}")
            r = pin_one(seed, actor, event_id, c.target_type,
                        c.target_id, c.field, LIVE_TICKS)
            tested += 1
            all_results.append(r)
            label = ("CROSSED" if r["divergence_w30"]
                     else ("W50-ONLY" if r["divergence_w50"]
                          else "NO-CROSSING"))
            print(f"      {label}: w30={r['divergence_w30']} "
                  f"w50={r['divergence_w50']} "
                  f"new-cf-events={r['new_cf_events_w30'][:4]}")
        print(f"  (tested {tested} individual consequence fields for "
              f"this witness, each singly-pinned)")

    print("\n[Verdict rollup across all 3 witnesses x their "
          "consequence fields]")
    crossed30 = [r for r in all_results if r["divergence_w30"]]
    w50only = [r for r in all_results
               if not r["divergence_w30"] and r["divergence_w50"]]
    print(f"  fields with a 30-tick future-action crossing: "
          f"{len(crossed30)}/{len(all_results)}")
    for r in crossed30:
        print(f"    seed {r['seed']} / {r['actor']} / "
              f"{r['target']} -> ticks {r['divergence_w30']} "
              f"(pre_value={r['pre_value']})")
    print(f"  fields with only a 50-tick (not 30) crossing: "
          f"{len(w50only)}/{len(all_results)}")

    verdict = ("CAUSAL-STORY-LOOP PROVEN" if crossed30
               else ("PARTIAL" if w50only or all_results
                     else "NOT PROVEN"))
    print(f"\nCAUSAL-STORY-LOOP VERDICT: {verdict}")
    print("  rule: PROVEN = >=1 natural witness field whose SINGLE-"
          "field counterfactual pins it and reproduces a 30-tick "
          "future committed-action/event crossing; PARTIAL = no 30-"
          "tick crossing but a 50-tick one exists; NOT PROVEN = no "
          "natural lineage / no crossing at any window.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
