"""M22 -- Long-run World Life acceptance (read-only), spec 6008682481.

Runs the REAL SimulationEngine.step() 5 seeds x 1000 ticks on
m-b-goal-directed-ab@0ba1699 and reports the four acceptance layers
(L1 life activity / L2 trajectory divergence / L3 relationship+goal
evolution / L4 natural failure), one auditable long-range causal chain
per seed, checkpoint summaries, and a separately-booked narrative
projection. No engine/production/test modification, no recall()
wiring, no manufactured failure. All figures are anchored to 0ba1699.

The engine has two real step modes. The W2 production semantics
(m-b line commit 8c8e53a) run under use_arbitration=True; default
(False) is the pre-W2 path. This tool runs BOTH modes, each
5 seeds x 1000 ticks, and reports them as two separate labeled layers.
They are never mixed into one denominator.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEEDS = (1, 3, 7, 42, 99)
TICKS = 1000
CHECKPOINTS = (0, 100, 250, 500, 750, 1000)


def rel_sig(rels) -> list[str]:
    out = []
    for key in sorted(rels):
        r = rels[key]
        out.append(f"{key}:T{round(r.trust,1)}/A{round(r.affection,1)}"
                   f"/R{round(r.resentment,1)}")
    return out


def snap(world) -> dict:
    s: dict = {"tick": world.tick, "locations": {}, "emotions": {},
               "habits": {}, "identity_beliefs": {}, "goals": {}}
    for cid, ch in sorted(world.characters.items()):
        s["locations"][cid] = ch.location
        s["emotions"][cid] = {k: round(v, 2)
                              for k, v in sorted(ch.emotions.items())}
        s["habits"][cid] = {k: round(v, 2)
                            for k, v in sorted(ch.habits.items())}
        s["identity_beliefs"][cid] = {k: round(v, 2)
                                      for k, v in
                                      sorted(ch.identity_beliefs.items())}
        s["goals"][cid] = [
            {"id": g.id, "status": g.status,
             "stage": f"{g.current_stage}/{len(g.stages)}"}
            for g in ch.goals]
    s["relationship_axes"] = rel_sig(world.relationships)
    s["belief_rows"] = len(world.memory_state.beliefs)
    return s


def run_one(seed: int) -> dict:
    per_mode: dict = {}
    for arb in (False, True):
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=arb)
        per_tick_actions: list = []
        events_by_tick: dict[int, list] = {}
        checkpoints: dict[int, dict] = {}
        for _ in range(TICKS):
            res = engine.step(world)
            for a in res.actions:
                per_tick_actions.append((world.tick, a.actor_id,
                                         a.action_type,
                                         ",".join(a.targets)))
            for ev in res.events:
                events_by_tick.setdefault(ev.tick, []).append(ev)
            if world.tick in CHECKPOINTS:
                checkpoints[world.tick] = snap(world)
        per_mode[arb] = {
            "per_tick_actions": per_tick_actions,
            "events_by_tick": events_by_tick,
            "checkpoints": checkpoints,
            "event_log": [
                {"id": e.id, "tick": e.tick, "type": e.action_type,
                 "participants": list(e.participants),
                 "outcome": (e.action_result.status
                              if e.action_result else "no-result"),
                 "consequences": [c.__dict__ for c in e.consequences],
                 "causes": list(e.causes),
                 "downstream": list(getattr(e, "downstream", []))}
                for e in world.event_log
            ],
        }
    return {"seed": seed, "modes": per_mode}


def _longest_quiet(events_by_tick, ticks: int) -> tuple:
    ev_set = set(events_by_tick)
    longest = 0
    run_start = best_start = best_end = 0
    for t in range(ticks + 1):
        if t == ticks or t in ev_set:
            run = t - run_start
            if run > longest:
                longest = run
                best_start, best_end = run_start, t
            run_start = t + 1
    return (best_start, best_end, longest) if longest else (0, 0, 0)


def layer_report(mode_name: str, arb: bool, runs: list[dict]) -> None:
    print(f"\n{'='*72}\nLAYER: {mode_name} (use_arbitration={arb})\n{'='*72}")
    print(f"\n--- OVERVIEW: L1 + L4 ---")
    print(f"{'seed':>4} {'actions':>7} {'events':>6} {'eventless':>9} "
          f"{'longest-quiet':>16} {'outcomes':>24}")
    total_outcomes: dict[str, int] = {}
    for r in runs:
        m = r["modes"][arb]
        l1_actions = len(m["per_tick_actions"])
        l1_events = len(m["event_log"])
        quiet = _longest_quiet(m["events_by_tick"], TICKS)
        out_counts: dict[str, int] = {}
        for ev in m["event_log"]:
            out_counts[ev["outcome"]] = out_counts.get(ev["outcome"], 0) + 1
            total_outcomes[ev["outcome"]] = total_outcomes.get(
                ev["outcome"], 0) + 1
        qs = f"{quiet[0]}-{quiet[1]}({quiet[2]})" if quiet[2] else "-"
        out = ",".join(f"{k}:{v}" for k, v in sorted(out_counts.items()))
        print(f"{r['seed']:>4} {l1_actions:>7} {l1_events:>6} "
              f"{TICKS - len(m['events_by_tick']):>9} {qs:>16} {out:>24}")

    print("\n--- L2: CROSS-SEED DIVERGENCE (checkpoint signatures) ---")
    for ck in CHECKPOINTS:
        sigs = []
        for r in runs:
            s = r["modes"][arb]["checkpoints"].get(ck)
            if s is None:
                continue
            sig = json.dumps({"loc": s["locations"],
                              "goals": s["goals"],
                              "rels": s["relationship_axes"],
                              "habits": s["habits"],
                              "identity": s["identity_beliefs"]},
                             sort_keys=True)
            sigs.append(sig)
        distinct = len(set(sigs))
        print(f"  t{ck:>4d}: {distinct}/5 distinct signatures")

    print("\n--- L3: ONE AUDITABLE CHAIN PER SEED "
          "(downstream-ref or same target/field; no proximity inference) ---")
    for r in runs:
        chain = _find_chain(r["modes"][arb]["event_log"])
        if chain:
            cf = chain["consequence_a"]
            print(f"  seed {r['seed']}: {chain['event_a']} (t"
                  f"{chain['event_a_tick']}) --[{chain['link']}]--> "
                  f"{chain['event_b']} (t{chain['event_b_tick']})")
            print(f"    A consequence: {cf.get('target_type')}/"
                  f"{cf.get('target_id')}.{cf.get('field')}  "
                  f"{cf.get('old_value')} -> {cf.get('new_value')}")
            bc = chain.get("consequence_b")
            if bc:
                print(f"    B consequence: {bc.get('target_type')}/"
                      f"{bc.get('target_id')}.{bc.get('field')}  "
                      f"{bc.get('old_value')} -> {bc.get('new_value')}")
        else:
            print(f"  seed {r['seed']}: NO auditable chain under the two "
                  f"rules -> NOT EXERCISED in this layer")

    print("\n--- L4: NATURAL FAILURE (this layer only) ---")
    print(f"  aggregate outcomes ({len(runs)} seeds x {TICKS} ticks): "
          f"{total_outcomes}")
    if total_outcomes.get("failure", 0) == 0:
        print("  FAILURE PATH = UNKNOWN / not exercised under this "
              "regime + this step mode (reported as such, not as a "
              "pass gate, not as 'the system has no failure').")

    print("\n--- NARRATIVE PROJECTION (separate book, NOT an engine-"
          "correctness gate) ---")
    for r in runs:
        lines = [f"t{e['tick']:4d}  {e['type']:24s} "
                 f"{'/'.join(e['participants']):20s} -> {e['outcome']}"
                 for e in r["modes"][arb]["event_log"]]
        print(f"  seed {r['seed']}: {len(lines)} event-lines; head/tail:")
        for l in lines[:2]:
            print("   ", l)
        print("    ...")
        for l in lines[-2:]:
            print("   ", l)


def _find_chain(events: list[dict]) -> dict | None:
    for i, a in enumerate(events):
        if not a["consequences"]:
            continue
        target = a["consequences"][0]
        for b in events[i + 1:]:
            if not (set(a["participants"]) & set(b["participants"])):
                continue
            if a["id"] in b["downstream"]:
                return {"event_a": a["id"], "event_a_tick": a["tick"],
                        "event_b": b["id"], "event_b_tick": b["tick"],
                        "link": "downstream-ref",
                        "consequence_a": target,
                        "consequence_b": (b["consequences"][0]
                                          if b["consequences"] else None)}
            if b["consequences"]:
                t2 = b["consequences"][0]
                if (t2.get("target_id") == target.get("target_id")
                        and t2.get("field") == target.get("field")):
                    return {"event_a": a["id"], "event_a_tick": a["tick"],
                            "event_b": b["id"], "event_b_tick": b["tick"],
                            "link": "same target/field re-touched",
                            "consequence_a": target,
                            "consequence_b": t2}
    return None


def main() -> int:
    print("=" * 72)
    print("M22  LONG-RUN WORLD LIFE ACCEPTANCE (read-only, 0ba1699)")
    print("=" * 72)
    print(f"\nSeeds {SEEDS} x {TICKS} ticks, real engine.step(), "
          f"TWO labeled layers (pre-W2 / W2). No production/test change.")

    runs = [run_one(s) for s in SEEDS]

    out_dir = Path(__file__).parent / "m22_runs"
    out_dir.mkdir(exist_ok=True)
    for r in runs:
        slim = {"seed": r["seed"]}
        for arb, m in r["modes"].items():
            slim[f"mode_arb_{int(arb)}"] = {
                k: v for k, v in m.items() if k != "event_log"}
            with open(out_dir /
                      f"seed{r['seed']}_arb{int(arb)}_events.json",
                      "w") as fh:
                json.dump(m["event_log"], fh, indent=2, default=str)
        with open(out_dir / f"seed{r['seed']}_summary.json", "w") as fh:
            json.dump(slim, fh, indent=2, default=str)

    layer_report("PRE-W2 (default engine.step(), use_arbitration=False)",
                 False, runs)
    layer_report("W2 PRODUCTION SEMANTICS "
                 "(use_arbitration=True, m-b line 8c8e53a)",
                 True, runs)

    print("\n--- TOOL SELF-CHECK ---")
    for r in runs:
        for arb in (False, True):
            m = r["modes"][arb]
            print(f"  seed {r['seed']} arb={arb}: "
                  f"final events={len(m['event_log'])} "
                  f"ticks covered={len(m['events_by_tick'])} "
                  f"of {TICKS} (rest eventless)")
    print("\nAll numbers anchored to 0ba1699. No data mixed from "
          "e395abde. Two layers kept separate: they are not "
          "sub-addable. No engine/production/test change was made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
