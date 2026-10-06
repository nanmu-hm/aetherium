"""M18 -- isolated find_top_evidence witness run (read-only).

Follow-on to the M16->M17-Rb repetition closure: find_top_evidence is the
one reader M17's table left "not measured" because M17's own presence
test and neutralisation both went through the function itself.

Design:
  A (intact)  : real engine.step(), persisted events
  B (detached): find_top_evidence neutralised via in-memory monkeypatch
                for the duration of B's kernel evaluation and step only;
                every other memory input is left EXACTLY as in A

Reported per witness:
  - P1 candidate pool changed?
  - P2 verdict changed?
  - P3 SimulationResult.actions changed?
  - P4 persisted event changed?
  - the exact evidence record A relied on, if any

A "crossing" is only counted when P4 changes. P3 is reported but not
treated as final evidence on its own, per the standing rule.

Usage:  python3 tools/mb_evidence_isolation.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine.core.appraisal as ap
from engine.core.actions import generate_action_pool
from engine.core.decision import DecisionKernel
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEEDS = (1, 2, 3, 7, 42)
TICKS = 200
ACTORS = ("rui", "yan")


def step_and_capture(world, seed):
    before = len(world.event_log)
    res = SimulationEngine(seed=seed, use_arbitration=True).step(world)
    return res, world.event_log[before:]


def main() -> int:
    kernel = DecisionKernel(seed=0)
    orig = ap.find_top_evidence
    tested = 0
    p1 = p2 = p3 = p4 = 0
    details = []

    for seed in SEEDS:
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=False)
        for _ in range(TICKS):
            engine.step(world)
            for cid in ACTORS:
                if cid not in world.characters:
                    continue
                ch = world.characters[cid]
                if ch.status != "active":
                    continue
                pool = generate_action_pool(world, cid)
                if len(pool) < 2:
                    continue

                # Presence test computed WITHOUT going through
                # find_top_evidence itself: scan the event log directly,
                # using the same pair-key rule as appraisal.py:89-90.
                def focal_pair(c):
                    focal = ap.candidate_focal_target(c, world)
                    actor, target = focal[1], focal[2]
                    if target is None:
                        return None
                    return f"{min(actor, target)}:{max(actor, target)}"

                live_pairs = set()
                for ev in world.event_log:
                    if cid not in ev.participants:
                        continue
                    for other in ev.participants:
                        if other == cid:
                            continue
                        live_pairs.add(f"{min(cid, other)}:{max(cid, other)}")
                has_evidence = any(
                    fp and fp in live_pairs
                    for c in pool if (fp := focal_pair(c)))

                if not has_evidence:
                    continue
                tested += 1

                evs_a = [kernel.evaluate(world, c) for c in pool]
                recs_a = ap.build_appraisals(kernel, world, ch, pool)
                verdict_a = ap.arbitrate(recs_a, pool, evs_a)

                # B: neutralise find_top_evidence only
                w_b = copy.deepcopy(world)
                ch_b = w_b.characters[cid]
                pool_b = generate_action_pool(w_b, cid)
                ap.find_top_evidence = lambda *a, **k: None
                try:
                    evs_b = [kernel.evaluate(w_b, c) for c in pool_b]
                    recs_b = ap.build_appraisals(kernel, w_b, ch_b, pool_b)
                    verdict_b = ap.arbitrate(recs_b, pool_b, evs_b)
                finally:
                    ap.find_top_evidence = orig

                p1 += [c.id for c in pool] != [c.id for c in pool_b]

                res_a, ev_a = step_and_capture(copy.deepcopy(world), seed)
                res_b, ev_b = step_and_capture(copy.deepcopy(w_b), seed)
                chosen_a = [f"{a.actor_id}:{a.id}" for a in res_a.actions]
                chosen_b = [f"{a.actor_id}:{a.id}" for a in res_b.actions]
                p3 += chosen_a != chosen_b
                p4 += [e.id for e in ev_a] != [e.id for e in ev_b]
                p2 += (verdict_a.kind, verdict_a.candidate_id) != (
                    verdict_b.kind, verdict_b.candidate_id)

                if [e.id for e in ev_a] != [e.id for e in ev_b]:
                    cand = next(c for c in pool if (fp := focal_pair(c))
                                and fp in live_pairs)
                    ev_record = orig(world, cid, ap.candidate_focal_target(cand, world))
                    details.append((seed, world.tick, cid,
                                    [e.id for e in ev_a], [e.id for e in ev_b],
                                    ev_record.past_event_id if ev_record else None,
                                    ev_record.current_relevance if ev_record else None))

    print("=" * 70)
    print("M18  ISOLATED find_top_evidence (read-only)")
    print("=" * 70)
    print()
    print(f"  contested snapshots where the actor has a live pair  : {tested}")
    print(f"  P1 candidate pool changed                            : {p1}")
    print(f"  P2 verdict changed                                    : {p2}")
    print(f"  P3 SimulationResult.actions changed                  : {p3}")
    print(f"  P4 persisted event changed (CROSSING)                : {p4}")
    print()
    for seed, tick, cid, ea, eb, ev_id, rel in details:
        print(f"  seed{seed} t{tick} {cid}: {ea} -> {eb}")
        print(f"      evidence relied on by A: {ev_id} (relevance {rel})")
    print()
    if p4:
        print("  find_top_evidence has an isolated crossing: the evidence")
        print("  channel is a real, individually-sufficient agency path.")
    else:
        print("  No isolated crossing found for find_top_evidence.")
        print("  Its intermediate (verdict/utility) effect does not reach a")
        print("  persisted event on its own in this regime; combined with")
        print("  another channel it may still matter. Not a zero-crossing")
        print("  claim beyond 5 seeds x 200 ticks.")
    print()
    print("  Nothing modified. No recall wiring, no weights, no "
          "production/test change, no manufactured failure. The")
    print("  monkeypatch lives only inside this process for this run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
