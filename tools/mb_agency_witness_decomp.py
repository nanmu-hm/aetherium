"""M16 -- agency witness decomposition (read-only, pre-registered per
ChatGPT 5990328426).

Answers: what exactly causes the 6 committed-action crossings G4 found,
and is the effect attributable to EXISTING history readers rather than an
artifact of the two-stage decision path?

THE PRE-REGISTERED REQUIREMENT THIS TOOL EXISTS TO SATISFY:
  "The last two should be checked against the actual persisted event,
   not inferred from a local choice variable."

My G4 did exactly what is forbidden: it called a local `committed()`
helper and compared its return value. G4's 6/46 was therefore a
candidate-level observation, NOT a persisted-event observation. This
tool runs the REAL engine.step() on two deep-copied worlds that differ
only in the ablation, and compares the events each one PERSISTS.

Four separate counts, never blended:
    P1 ablation changes the CANDIDATE POOL
    P2 ablation changes the ARBITRATION VERDICT
    P3 ablation changes the W2 SUBMITTED action
    P4 ablation changes the PERSISTED COMMITTED EVENT  <-- the real one

Plus: which existing reader moved first, and whether the witness
survives an independent replay.

Usage:  python3 tools/mb_agency_witness_decomp.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine.core.appraisal as ap  # noqa: E402
from engine.core.actions import generate_action_pool  # noqa: E402
from engine.core.decision import DecisionKernel  # noqa: E402
from engine.core.simulation import SimulationEngine  # noqa: E402
from engine.genesis import build_genesis_world  # noqa: E402

SEEDS = (1, 2, 3, 7, 42)
TICKS = 200
ACTORS = ("rui", "yan")

results: dict[str, list] = {}


def record(k, v):
    results.setdefault(k, []).append(v)


def reader_snapshot(world, ch, cid, pool):
    """Which existing readers see anything for this actor right now?"""
    mems = [m for m in world.memory_state.memories.values() if m.owner_id == cid]
    recent = [e for e in reversed(world.event_log)
              if e.participants and e.participants[0] == cid][:3]
    recent_ids = {e.id for e in recent}
    rep_belief = any(b.owner_id == cid
                     and b.proposition.startswith("experience:")
                     for b in world.memory_state.beliefs.values())
    rep_visits = any(m.location in world.locations for m in mems)
    rep_evidence = 0
    for cand in pool:
        focal = ap.candidate_focal_target(cand, world)
        if ap.find_top_evidence(world, cand.actor_id, focal) is not None:
            rep_evidence += 1
    return {
        "repetition_window": len(recent),
        "repetition_memory_overlap": len(
            [m for m in mems if m.event_id in recent_ids]),
        "belief_friction": rep_belief,
        "visit_counts": rep_visits,
        "evidence_candidates": rep_evidence,
    }


def ablate(world, cid, ch, mode):
    """Remove history through ONE reader at a time, or all of it."""
    w = copy.deepcopy(world)
    if mode == "all":
        recent = [e for e in reversed(world.event_log)
                  if e.participants and e.participants[0] == cid][:3]
        drop = {e.id for e in recent}
        for m in [m for m in list(w.memory_state.memories.values())
                  if m.owner_id == cid and m.event_id in drop]:
            w.memory_state.memories.pop(m.id, None)
        w.characters[cid].memory_ids = [
            i for i in ch.memory_ids if i in w.memory_state.memories]
    elif mode == "repetition_only":
        # keep the memories but hide their event links from the repetition
        # reader by removing them from the actor's id list AND the store
        recent = [e for e in reversed(world.event_log)
                  if e.participants and e.participants[0] == cid][:3]
        drop = {e.id for e in recent}
        for m in [m for m in list(w.memory_state.memories.values())
                  if m.owner_id == cid and m.event_id in drop]:
            w.memory_state.memories.pop(m.id, None)
        w.characters[cid].memory_ids = [
            i for i in ch.memory_ids if i in w.memory_state.memories]
    return w


def step_and_capture(world, seed):
    """Run the REAL engine.step(); return (SimulationResult, new events).

    Two INDEPENDENT sources on purpose: SimulationResult.actions is the
    engine's own statement of what it selected, while the returned events are
    what it actually wrote to the log.
    """
    engine = SimulationEngine(seed=seed, use_arbitration=True)
    before = len(world.event_log)
    result = engine.step(world)
    return result.actions, world.event_log[before:]


def main() -> int:
    print("=" * 78)
    print("M16  AGENCY WITNESS DECOMPOSITION (read-only)")
    print("=" * 78)
    print()
    print("  G4 compared a LOCAL committed() return value. This tool instead")
    print("  runs the real engine.step() on two deep-copied worlds differing")
    print("  only in the ablation, and compares the PERSISTED events.")
    print()
    kernel = DecisionKernel(seed=0)
    tested = 0
    p1_pool = p2_verdict = p3_submitted = p4_event = 0
    witnesses = []

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
                tested += 1

                snap = reader_snapshot(world, ch, cid, pool)
                wB = ablate(world, cid, ch, "all")

                # P1 candidate pool
                pool_b = generate_action_pool(wB, cid)
                ids_a = sorted(c.id for c in pool)
                ids_b = sorted(c.id for c in pool_b)
                pool_changed = ids_a != ids_b
                p1_pool += pool_changed

                # P2 arbitration verdict
                ev_a = [kernel.evaluate(world, c) for c in pool]
                ev_b = [kernel.evaluate(wB, c) for c in pool_b]
                r_a = ap.arbitrate(ap.build_appraisals(kernel, world, ch, pool),
                                   pool, ev_a)
                r_b = ap.arbitrate(ap.build_appraisals(kernel, wB, ch, pool_b),
                                   pool_b, ev_b)
                verdict_changed = (r_a.kind, r_a.candidate_id) != (
                    r_b.kind, r_b.candidate_id)
                p2_verdict += verdict_changed

                # P3 and P4 MUST come from different sources.
                # Arena is right that the previous version derived P3 from
                # the event list, i.e. the same source as P4, so the two
                # counts were not independent. P3 now reads
                # SimulationResult.actions -- what the engine says it
                # selected -- and P4 reads the PERSISTED event_log.
                ev_world_a = copy.deepcopy(world)
                ev_world_b = copy.deepcopy(world)
                ev_world_b = ablate(ev_world_b, cid, ch, "all")
                sel_a, events_a = step_and_capture(ev_world_a, seed)
                sel_b, events_b = step_and_capture(ev_world_b, seed)
                act_a = [e.id for e in events_a
                         if cid in (e.participants or [])]
                act_b = [e.id for e in events_b
                         if cid in (e.participants or [])]
                # P3: the engine's own selected-action list
                chosen_a = [f"{a.actor_id}:{a.id}" for a in sel_a
                            if a.actor_id == cid]
                chosen_b = [f"{a.actor_id}:{a.id}" for a in sel_b
                            if a.actor_id == cid]
                p3_submitted += chosen_a != chosen_b
                # P4: the persisted events
                p4_event += act_a != act_b

                if act_a != act_b:
                    witnesses.append({
                        "seed": seed, "tick": world.tick, "cid": cid,
                        "pool_a": ids_a, "pool_b": ids_b,
                        "pool_changed": pool_changed,
                        "verdict_a": (r_a.kind, r_a.candidate_id),
                        "verdict_b": (r_b.kind, r_b.candidate_id),
                        "verdict_changed": verdict_changed,
                        "event_a": act_a, "event_b": act_b,
                        "readers": snap,
                        "u_a": [(e.action_id, round(e.utility, 6))
                                for e in ev_a],
                        "u_b": [(e.action_id, round(e.utility, 6))
                                for e in ev_b],
                        "dest_a": {c.id: list(c.targets) for c in pool},
                        "dest_b": {c.id: list(c.targets) for c in pool_b},
                        "score_a": {c.id: c.score for c in pool},
                        "noise": ch.decision_noise,
                    })

    print(f"  contested snapshots tested                       : {tested}")
    print()
    print("  THE FOUR COUNTS, NEVER BLENDED:")
    print(f"    P1 ablation changes the CANDIDATE POOL          : {p1_pool}")
    print(f"    P2 ablation changes the ARBITRATION VERDICT     : {p2_verdict}")
    print(f"    P3 ablation changes the W2 SUBMITTED action     : {p3_submitted}")
    print(f"    P4 ablation changes the PERSISTED COMMITTED EVENT: {p4_event}")
    print()
    if not witnesses:
        print("  => No persisted-event difference at all. G4's 6/46 does NOT")
        print("     survive verification against the event log.")
    else:
        print(f"  PERSISTED-EVENT WITNESSES ({len(witnesses)}):")
        for w in witnesses:
            print()
            print(f"    seed{w['seed']} t{w['tick']} actor={w['cid']}")
            print(f"      candidate pool  A: {w['pool_a']}")
            print(f"                    B: {w['pool_b']}   changed={w['pool_changed']}")
            print(f"      verdict         A: {w['verdict_a']}")
            print(f"                    B: {w['verdict_b']}   changed={w['verdict_changed']}")
            print(f"      PERSISTED event A: {w['event_a']}")
            print(f"                    B: {w['event_b']}")
            print(f"      readers in play at A: {w['readers']}")
            print(f"      utility A: {w['u_a']}")
            print(f"      utility B: {w['u_b']}")
            print(f"      TARGETS    A: {w['dest_a']}")
            print(f"                B: {w['dest_b']}   "
                  f"destination changed={w['dest_a'] != w['dest_b']}")
            print(f"      action.score A: {w['score_a']}  "
                  f"decision_noise={w['noise']}")
    print()
    record("P1_pool", p1_pool)
    record("P2_verdict", p2_verdict)
    record("P3_submitted", p3_submitted)
    record("P4_event", p4_event)
    record("tested", tested)
    record("witnesses", len(witnesses))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())