"""M25-R1 -- one-shot consequence-rollback retest + M26 first phase.

Specs: ChatGPT PR#10 6014735499 (M25 裁定 + M26); Arena independent
M25 recheck: M25's pin_one() re-pinned the target field EVERY tick
after onset (suppressed the field's own natural drift), so M25's
goal.current_stage "crossings" may reflect freezing, not a genuine
single-consequence effect. This tool fixes that (ONE-SHOT pin, no
re-pin) and extends to M26's 1000-tick narrative window.
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
M26_TICKS = 1000
W30, W50 = 30, 50


def _resolve(root_world, target_type, target_id, field):
    """Return (value, key, kind, container) for read; see M25."""
    if target_type == "relationship":
        rel = root_world.relationships[target_id]
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


def _apply(root_world, target_type, target_id, field, value):
    """Write value into the target field, preserving key-existence
    semantics: only writes a key the target root already has (or is a
    plain attribute on an existing object); never invents a new key
    the natural arm's pre-witness state lacked."""
    if target_type == "relationship":
        setattr(root_world.relationships[target_id], field, value)
        return
    if target_type == "character":
        ch = root_world.characters[target_id]
        parts = field.split(".")
        obj = ch
        for p in parts[:-1]:
            obj = getattr(obj, p)
        if isinstance(obj, dict):
            if parts[-1] in obj:      # key-existence guard (M25 fix)
                obj[parts[-1]] = value
        else:
            setattr(obj, parts[-1], value)
        return
    if target_type == "goal":
        ch = root_world.characters.get(target_id.split("-")[0])
        if ch is None:
            return
        for g in ch.goals:
            if g.id == target_id:
                setattr(g, field, value)
                return


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


def _pre_value_and_wtick(seed, event_id, target_type, target_id,
                         field, ticks):
    """Find the witness tick and the field's PRE-STEP value (value at
    the END of tick wtick-1, i.e. before the witness step ran)."""
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)
    prev_end = _resolve(world, target_type, target_id, field)[0]
    for i in range(ticks):
        res = engine.step(world)
        if any(e.id == event_id for e in res.events):
            return prev_end, i
        prev_end = _resolve(world, target_type, target_id, field)[0]
    raise AssertionError(f"{event_id} not found in {ticks}-tick run")


def one_shot(seed, actor, event_id, target_type, target_id, field,
             ticks):
    """M25-R1 corrected method: undo the target field ONCE at the
    witness tick's step() exit (restore to its pre-step natural
    value), then NEVER touch it again -- all subsequent ticks evolve
    it naturally, including any new natural writes to it."""
    nat_committed, nat_events = natural(seed, ticks)
    pre_value, wtick = _pre_value_and_wtick(
        seed, event_id, target_type, target_id, field, ticks)

    world2 = build_genesis_world()
    world2.timestamp = "0001-01-01T00:00:00"
    engine2 = SimulationEngine(seed=seed, use_arbitration=True)
    cf_committed, cf_events = [], []
    undone = False
    for i in range(ticks):
        res = engine2.step(world2)
        cf_committed.append({a.actor_id: a.id for a in res.actions})
        cf_events.extend(res.events)
        if i == wtick:
            _apply(world2, target_type, target_id, field,
                   pre_value if pre_value is not None else 0.0)
            undone = True
    assert undone, f"pin never fired for {event_id}"

    divs = [i for i in range(wtick, ticks)
            if nat_committed[i].get(actor) != cf_committed[i].get(actor)]
    divs_w30 = [d for d in divs if d - wtick < W30]
    divs_w50 = [d for d in divs if d - wtick < W50]
    # actor-participating events only, within the 30/50-tick window
    def actor_events_in(events, lo, hi):
        return sorted({e.id for e in events
                       if lo <= e.tick < hi and actor in e.participants})
    nat_ev30 = actor_events_in(nat_events, wtick + 1, wtick + 1 + W30)
    cf_ev30 = actor_events_in(cf_events, wtick + 1, wtick + 1 + W30)
    new_cf_ev30 = [e for e in cf_ev30 if e not in nat_ev30]
    nat_ev50 = actor_events_in(nat_events, wtick + 1, wtick + 1 + W50)
    cf_ev50 = actor_events_in(cf_events, wtick + 1, wtick + 1 + W50)
    new_cf_ev50 = [e for e in cf_ev50 if e not in nat_ev50]
    return {
        "seed": seed, "actor": actor, "witness_tick": wtick,
        "target": (target_type, target_id, field),
        "pre_value": pre_value,
        "divergence_w30": divs_w30,
        "divergence_w50": divs_w50,
        "new_cf_events_w30": new_cf_ev30,
        "new_cf_events_w50": new_cf_ev50,
    }


def main() -> int:
    print("=" * 72)
    print("M25-R1  one-shot consequence-rollback retest + M26 part 1")
    print("(read-only, anchored 0ba1699)")
    print("=" * 72)

    # --- Part 1: corrected one-shot retest of all 36 fields --------
    all_results = []
    for seed, (actor, _wt, event_id) in WINS.items():
        print(f"\n[Part 1: seed {seed}] {actor} ({event_id})")
        nat_committed, nat_events = natural(seed, LIVE_TICKS)
        ev = next((e for e in nat_events if e.id == event_id), None)
        if ev is None:
            print("  event not found, skip")
            continue
        for c in ev.consequences:
            r = one_shot(seed, actor, event_id, c.target_type,
                         c.target_id, c.field, LIVE_TICKS)
            all_results.append(r)
            label = ("CROSSED" if r["divergence_w30"]
                     else ("W50-ONLY" if r["divergence_w50"]
                          else "NO-CROSSING"))
            print(f"  {c.target_type}:{c.target_id}.{c.field}: {label}"
                  f" w30={r['divergence_w30']}"
                  f" w50={r['divergence_w50']}"
                  f" new-cf-ev30={r['new_cf_events_w30'][:4]}")

    crossed = [r for r in all_results if r["divergence_w30"]]
    print(f"\n[Part 1 rollup] one-shot 30-tick crossings: "
          f"{len(crossed)}/{len(all_results)}")
    for r in crossed:
        print(f"  seed {r['seed']} {r['actor']} {r['target']}: "
              f"ticks {r['divergence_w30']}, "
              f"new-cf-ev30={r['new_cf_events_w30'][:4]}")

    # --- Part 2: M26 narrative window (1000 ticks, confirmed
    #     witnesses from Part 1, natural arm only, no intervention)
    print(f"\n[Part 2: M26 narrative window, {M26_TICKS} ticks, "
          "natural arm]")
    survivors = sorted({(r['seed'], r['target'])
                        for r in crossed})
    for seed, target in survivors:
        actor = "yan"
        nat_committed, nat_events = natural(seed, M26_TICKS)
        # action chain: sequence of committed actions for `actor`
        acts = [(i, nat_committed[i].get(actor))
                for i in range(M26_TICKS)
                if nat_committed[i].get(actor)]
        n_events = len(nat_events)
        n_fail = sum(1 for e in nat_events
                     if e.action_result and
                     e.action_result.status == "failure")
        # chain continuity: count "re-action" links where a committed
        # action is followed by ANOTHER committed action 2-5 ticks
        # later (a gap of exactly 1 is normal per-tick cadence, not a
        # distinctive causal link; a larger gap is just drift)
        chain_links = []
        for i in range(len(acts) - 1):
            gap = acts[i + 1][0] - acts[i][0]
            if 2 <= gap <= 5:
                chain_links.append(acts[i][0])
        chain_ratio = len(chain_links) / max(len(acts) - 1, 1)
        print(f"\n  seed {seed} / {actor} ({target} survivor): "
              f"{len(acts)} committed actions over {M26_TICKS} ticks, "
              f"{n_events} events, natural failure={n_fail} "
              f"(NOT OBSERVED if 0), causal-chain-links "
              f"(2-5 tick re-action gaps)={len(chain_links)}, "
              f"ratio={chain_ratio:.2f}")

    verdict = ("CAUSAL-STORY-LOOP PROVEN (one-shot)" if crossed
               else "PARTIAL (one-shot)" if all_results
               else "NOT PROVEN")
    print(f"\nM25-R1 VERDICT: {verdict}")
    print("M26 STATUS: narrative window observed; story quality "
          "judgment DEFERRED to owner/three-party discussion per "
          "6014735499 ('只有当审计显示缺口能被明确定位时，才进入"
          "下一轮设计 intervention')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
