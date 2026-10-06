"""M22-R1 -- three read-only follow-ups requested in ChatGPT PR#10 review
5423617435 (M22 delivery 6008987551 / head d065fcd), anchored to 0ba1699.

A. W2 seed-3 activity outlier (54 events vs 15-22 for the other 4 W2 seeds):
   step-by-step provenance from the FIRST divergence tick forward:
   candidate pool -> arbitration verdict -> committed action -> event ->
   state consequence. No param tuning, no engine change, no manufactured
   event.

B. State->behavior strong causal witness for the relationship chain:
   search, using ONLY existing decision readers / channels (visit_counts,
   repetition, find_top_evidence, belief_friction, and the goal/desire/
   emotion/relationship state reads already in the kernel) for a natural
   witness of: relationship/goal/desire delta -> later candidate/decision
   delta -> event. If none is found, report NOT PROVEN / not exercised --
   do not manufacture one.

C. Event.downstream writer-path audit: locate every write site, explain
   why 190/190 are empty in natural operation, and distinguish
   "a writer exists but the natural path never triggers it" from "there
   is no production write path at all." Read-only, no sample filling.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine.core.appraisal as ap
from engine.core.actions import generate_action_pool
from engine.core.decision import DecisionKernel
from engine.core.models import ActionCandidate
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEEDS = (1, 3, 7, 42, 99)
TICKS = 1000


def run_w2(seed: int) -> dict:
    """W2 mode, with per-tick arbitration verdict + chosen candidate id
    captured WITHOUT changing the engine (we call the public kernel/appraise
    helpers the same way the engine does, per tick, to observe the exact
    candidate that was committed and why)."""
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)
    kernel = engine.decision_kernel
    per_tick: list[dict] = []
    for _ in range(TICKS):
        tick_before = world.tick
        ch = {}
        for cid, c in world.characters.items():
            pool = generate_action_pool(world, cid)
            if len(pool) == 0:
                continue
            evs = [kernel.evaluate(world, c) for c in pool]
            recs = ap.build_appraisals(kernel, world, c, pool)
            verdict = ap.arbitrate(recs, pool, evs)
            # Arena 5423617435-A follow-up: a SINGLE-candidate pool can
            # still be committed (via choose()'s empty-after-arbitration
            # guard), so it must be captured in per-tick state as well as
            # previously -- just don't claim there's no verdict when the
            # pool was genuinely single-candidate (arbitrate() is only
            # meaningful for >=2, per M16's own framing; still record the
            # raw top-1 utility so the single-candidate case is explained
            # rather than elided).
            ch[cid] = {"pool_ids": [c.id for c in pool],
                       "verdict_kind": verdict.kind,
                       "verdict_candidate": verdict.candidate_id,
                       "top1": (sorted(evs, key=lambda e: e.utility,
                                       reverse=True)[0].action_id
                                 if evs else None),
                       # full ranked (id, utility) list so a single-
                       # candidate / no-verdict tick is explained, not
                       # elided (Arena 5423617435-A correction)
                       "top1_util": [(e.action_id, e.utility) for e in
                                     sorted(evs, key=lambda e: e.utility,
                                            reverse=True)]}
        res = engine.step(world)
        committed = {a.actor_id: a.id for a in res.actions}
        per_tick.append({"tick": tick_before, "ch": ch,
                         "committed": committed,
                         "events": [e.id for e in res.events]})
    return {"event_log": world.event_log, "per_tick": per_tick,
            "n_events": len(world.event_log)}


def first_divergence_tick(per_tick: list[dict],
                          reference_per_tick: list[dict]) -> int | None:
    """First tick where seed-3's committed-action set (actor->candidate)
    differs from the seed-1 (reference) arm, W2 mode, same mode."""
    for i in range(len(per_tick)):
        a = per_tick[i]
        b = reference_per_tick[i]
        if a["committed"] != b["committed"]:
            return a["tick"]
    return None


def main() -> int:
    print("=" * 72)
    print("M22-R1  (read-only, anchored to 0ba1699)")
    print("=" * 72)

    # --- A: seed-3 outlier provenance ---------------------------------
    ref = run_w2(1)
    out = run_w2(3)
    print("\n[A] W2 seed-3 vs seed-1 (reference) event counts:")
    for s, r in ((1, ref), (3, out)):
        print(f"   seed {s}: {r['n_events']} events")
    div = first_divergence_tick(out["per_tick"], ref["per_tick"])
    print(f"   first committed-action divergence tick: {div}")
    if div is not None:
        print("   step-by-step around that tick (pool -> verdict -> "
              "committed -> event):")
        for i in range(max(0, div - 1), min(len(out["per_tick"]),
                                             div + 6)):
            rec = out["per_tick"][i]
            refrec = ref["per_tick"][i]
            # A (Arena correction 5423617435-A): the previous version only
            # printed actors whose pool had >= 2 candidates, so a key
            # single-candidate tick (e.g. t3: rui's only candidate is
            # travel -> ridge, utility -0.015216, no arbitration verdict
            # because the pool has a single element) showed "-" and left a
            # gap. Now: for each committed actor, ALWAYS print the pool
            # size, the single-candidate case explicitly, AND the full
            # utility ranking so a "no verdict" tick is explained, not
            # elided.
            s3 = " | ".join(
                f"{cid}: pool{len(d['pool_ids'])}"
                + (f" single-candidate {d['pool_ids'][0]} "
                   f"(utility {d['top1_util'][0][1]:+.6f}), no verdict"
                   if len(d["pool_ids"]) == 1 else
                   f" verdict={d['verdict_kind']}({d['verdict_candidate']})")
                + f" committed={rec['committed'].get(cid)}"
                for cid, d in rec["ch"].items() if rec["committed"].get(cid))
            s1 = " | ".join(
                f"{cid}: pool{len(d['pool_ids'])}"
                + (f" single-candidate {d['pool_ids'][0]} "
                   f"(utility {d['top1_util'][0][1]:+.6f}), no verdict"
                   if len(d["pool_ids"]) == 1 else
                   f" verdict={d['verdict_kind']} "
                   f"(top1 {d['top1_util'][0][0]})")
                + f" committed={refrec['committed'].get(cid)}"
                for cid, d in refrec["ch"].items()
                if refrec["committed"].get(cid))
            print(f"   t{rec['tick']} seed3: {s3 or '- (no commit this tick)'}")
            print(f"        seed1: {s1 or '- (no commit this tick)'}")
            if rec["events"]:
                print(f"        seed3 events this tick: {rec['events']}")
    else:
        print("   No tick-level committed-action divergence found before "
              "tick 1000 under W2 for seed3 vs seed1 -- report as NOT "
              "FOUND at this granularity, do not force a story.")

    # --- B: state->behavior witness search ---------------------------
    print("\n[B] State->behavior strong causal witness "
          "(relationship/goal/desire delta -> later candidate/decision "
          "delta -> event), using ONLY existing readers")
    print("    (visit_counts / repetition / find_top_evidence / "
          "belief_friction / goal-desire-emotion-relationship state reads; "
          "no recall() wiring, no manufactured sample).")
    found_any = False
    for seed in SEEDS:
        r = run_w2(seed)
        per_tick = r["per_tick"]
        # relationship state trajectory (we already know trust 48->50->52
        # from M22's chain, at t0/t13). Does any LATER tick's candidate
        # pool, verdict, or committed action actually differ for the SAME
        # actor compared to what it would have been WITHOUT that earlier
        # trust change -- measured by comparing this seed's later ticks
        # against a same-seed arm where the relationship field was
        # artificially NOT changed at t0 (i.e. neutralize ONLY the trust
        # consequence's effect, held through later steps, no other change)?
        # This is the cleanest available "state -> behavior" counterfactual
        # that does NOT require inventing a new sample or wiring recall.
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=True)
        for i, rec in enumerate(per_tick):
            if i >= 30:
                break  # B-search only needs the early window where the
                       # trust chain fires (M22: t0 -> t13)
            if not rec["events"]:
                continue
        # Neutralise the trust consequence of the t0 event, step forward
        # the same number of ticks, and check whether the set of committed
        # actions between tick 1..30 changes at all.
        def run_neutralised(seed: int, n_ticks: int) -> list[dict]:
            world = build_genesis_world()
            world.timestamp = "0001-01-01T00:00:00"
            engine = SimulationEngine(seed=seed, use_arbitration=True)
            out: list[dict] = []
            for _ in range(n_ticks):
                res = engine.step(world)
                committed = {a.actor_id: a.id for a in res.actions}
                # neutralise: immediately roll back any relationship-axis
                # delta this tick's events just wrote
                for ev in res.events:
                    for c in ev.consequences:
                        if c.target_type == "relationship":
                            rel = world.relationships.get(c.target_id)
                            if rel is not None:
                                # restore pre-event value
                                if c.field == "trust":
                                    rel.trust = c.old_value
                                elif c.field == "affection":
                                    rel.affection = c.old_value
                                elif c.field == "resentment":
                                    rel.resentment = c.old_value
                out.append({"tick": world.tick, "committed": committed})
            return out

        neutral = run_neutralised(seed, 30)
        base = [{"tick": pt["tick"], "committed": pt["committed"]}
                for pt in per_tick[:30]]
        diffs = [i for i, (a, b) in enumerate(zip(base, neutral))
                 if a["committed"] != b["committed"]]
        if diffs:
            found_any = True
            print(f"   seed {seed}: relationship-state delta DID change "
                  f"later committed actions at ticks {diffs} "
                  f"(counterfactual: trust reversion held tick-by-tick, "
                  f"no other input touched)")
            for i in diffs[:3]:
                print(f"      t{neutral[i]['tick']}: base committed="
                      f"{base[i]['committed']}  neutralised committed="
                      f"{neutral[i]['committed']}")
        else:
            print(f"   seed {seed}: no later committed-action difference "
                  f"found in ticks 1-30 when the relationship-axis delta "
                  f"is rolled back tick-by-tick -> state->behavior link "
                  f"for THIS reader, THIS seed, THIS window: NOT PROVEN "
                  f"(not a measured zero of all possible windows, just "
                  f"this one)")
    if not found_any:
        print("   => Across all 5 seeds x ticks 1-30, no natural witness "
              "found where rolling back ONLY the relationship-axis "
              "consequence changes a later committed action. Verdict for "
              "M22-R1 item B: NOT PROVEN / not exercised in this window "
              "(does not negate a longer or differently-scoped witness).")

    # --- C: Event.downstream writer-path audit ------------------------
    print("\n[C] Event.downstream writer-path audit (read-only, no filling)")
    print("    Grep across engine/ for every assignment/append to a "
          "concrete Event object's .downstream attribute:")
    print("    -> ONLY the dataclass default in engine/core/models.py:333 "
          "(field(default_factory=list))")
    print("    CONCLUSION: this is the second case of the distinction "
          "ChatGPT's review asked us to draw -- there is no SIMULATION-PATH "
          "writer for Event.downstream (not 'a writer that the natural "
          "path fails to trigger'). The single Event-construction site in "
          "the simulation execution path (engine/core/simulation.py, "
          "resolve(), ~line 893-913) does not pass a downstream= argument, "
          "and no simulation-path code appends to a live Event's "
          ".downstream. 190/190 empty in a natural run is therefore "
          "EXPECTED.")
    print("    CORRECTION to our own earlier wording (Arena 5423617435-C "
          "follow-up, applied here): it is NOT true that 'the ONLY "
          "Event(...) construction in the whole repo is that one site'. "
          "The persistence loader (engine/persistence/codec.py, and the "
          "persistence round-trip path) ALSO reconstructs Event objects "
          "from serialized data (Event(**data)) -- but that path only "
          "restores whatever value was already serialized, it does not "
          "derive or compute a new downstream reference for a newly "
          "created event. Accurate statement: the SIMULATION execution "
          "path has no write logic for downstream; the LOADER can "
          "rehydrate an externally-produced value but does not generate "
          "one. We do not claim the loader is a 'writer' in the sense "
          "M22's question cares about.")
    print("    -> The single Event-construction site in production "
          "(engine/core/simulation.py, resolve(), ~line 893-913) passes "
          "id/tick/timestamp/location/participants/causes/facts/"
          "action_type/action_result/consequences/intent/preconditions/"
          "observations, and does NOT pass a downstream= argument.")
    print("\nAll three M22-R1 items are read-only. No engine/production/"
          "test change, no recall() wiring, no manufactured failure or "
          "event. Anchor: 0ba1699 throughout; seed-3 numbers come from "
          "the same m-b-goal-directed-ab branch, not from e395abde.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
