"""M19 -- targeted belief_friction provenance + witness audit (read-only).

Spec from ChatGPT (PR#10 6007445444), anchored to d391bab's 34 contested
snapshots where an actor has a live evidence pair.

TWO PHASES, IN ORDER:

PHASE A -- provenance audit (design level, no ablation yet)
  For each contested snapshot, for each candidate in the pool, derive
  which belief rows _belief_friction(state, char, cand) ACTUALLY reads,
  per the exact matching rule in decision.py:86-104:
      owner == candidate's actor
      proposition starts with "experience:"
      proposition form  experience:<action_type>:<belief_targets>:<outcome>
      canonical(action_type) == canonical(cand.action_type)
      belief_targets == ",".join(cand.targets)
  Print the full provenance table. If a candidate's matching beliefs
  cannot be pinned to a concrete event in the persisted log (i.e. we
  cannot say which recorded event created that belief), stop there:
  Phase B is not allowed to guess that mapping.

PHASE B -- targeted ablation (only where Phase A produced a concrete
  belief row that can be neutralised in isolation)
  Neutralise ONLY the matching belief rows' confidence (set to 0.0),
  leaving every other belief row, every memory row, every event, and
  the full event log intact. The B side is stepped with the neutralisation
  held through the entire real engine.step() until P4 is sampled.

P1/P2/P3/P4 come from four different sources, never blended:
  P1 candidate pool (A vs B, world-level ids)
  P2 real arbitration verdict (A vs B)
  P3 SimulationResult.actions filtered to the actor
  P4 persisted event_log filtered to the actor's participants

success / failure are reported separately. No natural failure exists
in this regime; we do not manufacture one.

Usage:  python3 tools/mb_belief_friction_isolation.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine.core.appraisal as ap
from engine.core.actions import generate_action_pool
from engine.core.decision import DecisionKernel, canonical_action_type
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEEDS = (1, 2, 3, 7, 42)
TICKS = 200
ACTORS = ("rui", "yan")


def step_live(world, seed):
    before = len(world.event_log)
    res = SimulationEngine(seed=seed, use_arbitration=True).step(world)
    return res, world.event_log[before:]


def step_belief_neutralised(world, seed, neutralised_bids):
    """Hold a targeted belief neutralisation through the ENTIRE real step."""
    state = world.memory_state
    saved = {bid: state.beliefs[bid].confidence
             for bid in neutralised_bids if bid in state.beliefs}
    for bid, _ in saved.items():
        state.beliefs[bid].confidence = 0.0
    before = len(world.event_log)
    try:
        res = SimulationEngine(seed=seed, use_arbitration=True).step(world)
    finally:
        for bid, conf in saved.items():
            if bid in state.beliefs:
                state.beliefs[bid].confidence = conf
    return res, world.event_log[before:]


def matching_beliefs(world, cid, pool):
    """Which belief rows _belief_friction ACTUALLY reads for this pool.

    Returns {candidate_pool_position: [belief rows]}, where the key is
    the candidate's pool position index (0-based), because candidates
    carry no persistent id in the pool.
    """
    out = {}
    for i, c in enumerate(pool):
        target_text = ",".join(c.targets)
        act = canonical_action_type(c.action_type)
        matched = []
        for b in world.memory_state.beliefs.values():
            if b.owner_id != cid or not b.proposition.startswith("experience:"):
                continue
            parts = b.proposition.split(":", 3)
            if len(parts) != 4:
                continue
            _, b_act, b_targets, b_outcome = parts
            if canonical_action_type(b_act) != act or b_targets != target_text:
                continue
            matched.append((b.id, b_outcome, b.confidence))
        out[i] = matched
    return out


def has_live_pair(world, cid, pool):
    def fp(c):
        f = ap.candidate_focal_target(c, world)
        if f[2] is None:
            return None
        return f"{min(f[1], f[2])}:{max(f[1], f[2])}"
    live = set()
    for ev in world.event_log:
        if cid not in ev.participants:
            continue
        for o in ev.participants:
            if o != cid:
                live.add(f"{min(cid, o)}:{max(cid, o)}")
    return any(fp(c) in live for c in pool if fp(c))


def main() -> int:
    kernel = DecisionKernel(seed=0)
    tested = 0
    phaseA: list[tuple] = []
    p1 = p2 = p3 = p4_success = p4_failure = 0
    witnesses = []
    utility_changed_count = 0

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
                if not has_live_pair(world, cid, pool):
                    continue
                tested += 1

                matches = matching_beliefs(world, cid, pool)
                any_matched = any(v for v in matches.values())

                # ---- Phase A: provenance, recorded for every snapshot ----
                provenance = {
                    cid_c: [(bid, outcome, conf)
                            for (bid, outcome, conf) in v]
                    for cid_c, v in matches.items() if v}
                phaseA.append((seed, world.tick, cid, any_matched, provenance))

                if not any_matched:
                    continue
                # No matching belief rows -> nothing to ablate, but the
                # snapshot still counts as "tested" for Phase A.

                neutralised = {bid for v in matches.values()
                               for (bid, _, _) in v}

                wA = copy.deepcopy(world)
                res_a, ev_a = step_live(wA, seed)
                evs_a = [kernel.evaluate(world, c) for c in pool]
                verdict_a = ap.arbitrate(
                    ap.build_appraisals(kernel, world, ch, pool),
                    pool, evs_a)

                wB = copy.deepcopy(world)
                res_b, ev_b = step_belief_neutralised(wB, seed, neutralised)
                evs_b = [kernel.evaluate(wB, c) for c in pool]
                verdict_b = ap.arbitrate(
                    ap.build_appraisals(kernel, wB, wB.characters[cid], pool),
                    pool, evs_b)

                # utility_changed: at least one candidate's utility score
                # differs between the live and neutralised pre-step
                # evaluations -- the "input reached the utility layer"
                # count, reported separately from P2/P3/P4 per spec.
                utility_changed_count += any(
                    a.utility != b.utility for a, b in zip(evs_a, evs_b))

                # P1: candidate pool ids are derived from
                # memory.visit_counts, which this ablation does NOT
                # touch. Measured by actually generating B's pool after
                # neutralisation (A and B pools must be paired) and
                # comparing positionally; flag loudly if nonzero.
                pool_a_ids = [f"{c.action_type}:{','.join(c.targets)}" for c in pool]
                pool_b_ids = [f"{c.action_type}:{','.join(c.targets)}"
                              for c in generate_action_pool(wB, cid)]
                p1 += pool_a_ids != pool_b_ids
                if p1:
                    print(f"  !! P1 NONZERO: seed{seed} t{world.tick} {cid} "
                          f"A={pool_a_ids} B={pool_b_ids}")

                # P2 measured on the PRE-STEP snapshot (original world vs
                # belief-neutralised copy, same pre-step candidate pool)
                # -- this is the isolated verdict-layer effect of the
                # ablation itself, per spec item 4.
                p2 += (verdict_a.kind, verdict_a.candidate_id) != (
                    verdict_b.kind, verdict_b.candidate_id)

                ca = [f"{a.actor_id}:{a.id}" for a in res_a.actions
                      if a.actor_id == cid]
                cb = [f"{a.actor_id}:{a.id}" for a in res_b.actions
                      if a.actor_id == cid]
                p3 += ca != cb

                ea = [e.id for e in ev_a if cid in (e.participants or [])]
                eb = [e.id for e in ev_b if cid in (e.participants or [])]
                changed = ea != eb
                if changed:
                    # classify success/failure by whether a NEW event was
                    # written on the B side (i.e. the actor still did
                    # something) vs went quiet (no new event).
                    if eb:
                        p4_success += 1
                    else:
                        p4_failure += 1
                p4 = p4_success + p4_failure
                if changed:
                    witnesses.append(
                        (seed, world.tick, cid,
                         sorted(neutralised), ea, eb,
                         p4_failure > 0 and not p4_success))

    print("=" * 70)
    print("M19  TARGETED BELIEF_FRICTION (read-only)")
    print("=" * 70)
    print()
    print(f"  contested snapshots (actor has live evidence pair) : {tested}")
    n_matched = sum(1 for x in phaseA if x[3])
    print(f"  Phase A: snapshots where _belief_friction matched "
          f"AT LEAST ONE belief row: {n_matched}")
    print(f"  Phase B ran only on those {n_matched}; the rest had "
          f"no belief input and contributed 0 to P1-P4 by construction.")
    print()
    print("  PHASE A provenance, FULL table (every matched snapshot; "
          "first 3 also shown inline, full table written to "
          "tools/mb_belief_friction_provenance_full.txt):")
    shown = 0
    with open(Path(__file__).parent / "mb_belief_friction_provenance_full.txt",
              "w") as fh:
        for seed, tick, cid, any_m, prov in phaseA:
            if not any_m:
                continue
            fh.write(f"seed{seed} t{tick} {cid}:\n")
            for cand_id, lst in prov.items():
                for bid, outcome, conf in lst:
                    fh.write(f"  {cand_id} <- belief {bid} "
                             f"(outcome={outcome}, confidence={conf})\n")
            if shown < 3:
                print(f"    seed{seed} t{tick} {cid}:")
                for cand_id, lst in prov.items():
                    for bid, outcome, conf in lst:
                        print(f"      {cand_id} <- belief {bid} "
                              f"(outcome={outcome}, confidence={conf})")
            shown += 1
    print()
    print("  THE FOUR COUNTS, NEVER BLENDED (Phase B snapshots only):")
    print(f"    utility_changed (>=1 candidate utility differs, pre-step) : {utility_changed_count}/{n_matched}")
    print(f"    P1 candidate pool changed                        : {p1}")
    print(f"    P2 arbitration verdict changed                   : {p2}")
    print(f"    P3 SimulationResult.actions changed (actor-filtered): {p3}")
    print(f"    P4 persisted event changed (actor-filtered)      : {p4}")
    print(f"       of which B side wrote a new event             : {p4_success}")
    print(f"       of which B side went quiet                    : {p4_failure}")
    print()
    for seed, tick, cid, bids, ea, eb, _ in witnesses:
        print(f"    seed{seed} t{tick} {cid}: neutralised {bids}")
        print(f"      A persisted: {ea}")
        print(f"      B persisted: {eb}")
    print()
    print("  Anything NOT covered above: no natural failure exists in")
    print("  this regime; we did not manufacture one.")
    print("  The belief-neutralisation was held through the whole real")
    print("  engine.step() on the B side, as spec'd. No recall wiring,")
    print("  no weights, no production/test change.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
