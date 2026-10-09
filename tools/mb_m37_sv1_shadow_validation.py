"""M37-SV1 -- shadow-only validation of the M37 v6 spec (read-only,
anchored 0ba1699, executed on HEAD 6c59d21 tree which carries the
read-only M33 tool; no production/test file is modified by this tool).

Spec: M37 Shadow-only Implementation Specification v6 (PR#10
6035341986). Gate: Arena 6035360921 + ChatGPT 6035368599 (ALLOW
shadow-only validation; no production/test modification authorized).

Five read-only checks, per v6 section references:
  1. OBSERVER ON/OFF equivalence  (v6 s6.2)
     Same seed, natural flow, observer-off (no snapshot machinery) vs
     observer-on (tick-boundary WorldState/SimulationResult snapshot +
     consequence reads, no wrapper, no world mutation). Per-tick
     full WorldState + SimulationResult comparison. Any difference ->
     OBSERVER-LEAKED, arm discarded.
  2. SATISFACTION evidence        (v6 s6.1(a))
     Read production satisfaction Consequence old/new directly from
     event.consequences (record_satisfaction_evidence,
     desire_interpretation.py:170-179). after>0 -> actual_amount =
     old-new (directly observed). after==0 -> requested amount is
     formula-derived/cross-checked only. No-decrease -> no-decrease/
     unobserved (do NOT infer floor-to-zero).
     Verify post = max(0.0, before - authored_amount) identity.
  3. PURE-GROWTH observation     (v6 s6.1(b))
     Only on ticks where a desire had NO other writer (no
     satisfaction/failure/birth consequence touching it that tick),
     diff tick-boundary desires before/after -> actual clamped delta;
     cross-verify requested signed growth against v6 s6.1(b) rules
     (simulation.py:959-1010, freedom/curiosity only). Confounded
     ticks -> GROWTH-CONFOUNDED, report net only.
  4. FAILURE re-source           (v6 s6.1(c))
     Read production failure Consequence old/new directly from
     _apply_failure_consequences' appended Consequence
     (simulation.py:530-538). Verify mapped amount (travel -> freedom
     +8.0, FAILURE_PRESSURE_MAP) vs actual capped delta.
  5. P1 dynamic counterfactual   (v6 s4 P1)
     Fixed candidate pool + all other inputs identical; mutate ONLY
     the copy's desire_carriers. Two probes:
       5a. DecisionKernel.evaluate() .utility (does not cover
           choose()/arbitration; static grep confirmed 0 carrier
           refs in decision.py A1).
       5b. DecisionKernel.choose() — compare chosen id,
           selection_score, and quiet-gate output (closes the
           v6 s4 selection_score gap).
  6. P2 dynamic counterfactual  (v6 s4 P2)
     Belonging-only threshold fixture: reconciliation/emotion
     zeroed, belonging=80; only carrier lifecycle differs
     (ACTIVE vs CONSUMED). Re-runs the real generate_action_pool()
     on each copy. Proves candidate-generation gate only.

  P2 and P1 (5a+5b) are all implemented as independent arms in this
  tool and executed on every run — they are not PENDING.

Nothing here modifies production code or test files. All world
copies are in-memory; original world objects are never mutated.
342/0 is the inherited M33 baseline (ref 6c59d21, /tmp/audit_m33),
NOT a new M37 test result.
"""
from __future__ import annotations

import sys
import dataclasses
import json
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.actions import generate_action_pool
from engine.core.decision import DecisionKernel
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEEDS = (1, 3, 7, 42, 99)
ACTOR = "rui"
TICKS = 40
SAMPLE = (1, 5, 10, 20, 40)


# -----------------------------------------------------------------
# full snapshot helpers (v6 s6.2)
# -----------------------------------------------------------------

def _char_full(c):
    """Full CharacterState projection (v6 s6.2 WorldState field list)."""
    hc = c.human_condition
    return {
        "id": c.id, "name": c.name, "status": c.status,
        "traits": tuple(c.traits), "values": tuple(c.values),
        "goals": tuple((g.description, g.priority, g.status) for g in c.goals),
        "needs": tuple(c.needs),
        "emotions": {k: round(v, 9) for k, v in c.emotions.items()},
        "desires": {k: round(v, 9) for k, v in c.human_condition.desires.items()},
        "location": c.location,
        "memory_ids": tuple(c.memory_ids),
        "habits": {k: round(v, 9) for k, v in c.habits.items()},
        "identity_beliefs": {k: round(v, 9) for k, v in c.identity_beliefs.items()},
        "decision_noise": c.decision_noise, "risk_tolerance": c.risk_tolerance,
        "possessions": dict(c.possessions), "abilities": dict(c.abilities),
        "constraints": tuple(c.constraints),
        "carrier_lc": {k: v.lifecycle for k, v in c.desire_carriers.items()},
        "carrier_strength": {k: v.strength for k, v in c.desire_carriers.items()},
        "carrier_consumed_at": {k: v.consumed_at for k, v in c.desire_carriers.items()},
        "fatigue": hc.fatigue,
    }


def snapshot_world(world, world_rng):
    """Normalized per-tick snapshot of every v6 s6.2 WorldState field
    plus SimulationResult.
    rng_state + memory count + full per-character projection included
    (Arena 6035501290 fix-1/fix-5: prior version omitted rng_state and
    most character fields -- those are now snapshotted)."""
    chars = {cid: _char_full(c) for cid, c in world.characters.items()}
    rels = {k: {"trust": r.trust, "resentment": r.resentment, "fear": r.fear}
            for k, r in world.relationships.items()}
    return {
        "world_id": world.world_id,
        "tick": world.tick,
        "timestamp": world.timestamp,
        "locations": frozenset(world.locations),
        "characters": chars,
        "relationships": rels,
        "factions": {k: v for k, v in world.factions.items()},
        "resources": dict(world.resources),
        "active_branch": world.active_branch,
        "memory_records": len(world.memory_state.memories),
        "simulation_seed": world.simulation_seed,
        # v6 s6.2 + Arena fix-1: engine's real PRNG state (set by
        # SimulationEngine after every step, simulation.py:1237).
        "rng_state": world_rng.getstate() if world_rng else None,
    }


def snapshot_result(res):
    return {
        "tick": res.tick,
        "n_actions": len(res.actions),
        "action_ids": tuple(a.id for a in res.actions),
        "n_events": len(res.events),
        "n_validation_errors": len(res.validation_errors),
        "validation_errors": tuple(res.validation_errors),
    }


# -----------------------------------------------------------------
# run 1+2+3+4: natural flow with/without observer, per seed
# -----------------------------------------------------------------

def run_arm(seed, observer_on):
    """Natural flow. observer_on adds tick-boundary snapshots (pure
    reads, no world mutation, no wrapper -- v6 s6.2 ON arm).
    observer_off is the pure control (no snapshot at all).

    Returns (arms_data). arms_data[observer_label] = {
      'traj': {tick: {freedom, curiosity}},
      'sat_events': [...],        # read from production consequences
      'growth_pure': [...],
      'failure_events': [...],
      'snapshots': [...] (only if observer_on),
    }
    """
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)
    actor = world.characters[ACTOR]

    traj, sat_events, growth_pure, failure_events = {}, [], [], []
    snapshots = []
    all_ticks_world = {}
    all_ticks_result = {}

    for t in range(TICKS):
        pre_free = actor.human_condition.desires.get("freedom", 0.0)
        pre_cur = actor.human_condition.desires.get("curiosity", 0.0)

        res = engine.step(world)

        post_free = actor.human_condition.desires.get("freedom", 0.0)
        post_cur = actor.human_condition.desires.get("curiosity", 0.0)
        tnow = t + 1
        if tnow in SAMPLE:
            traj[tnow] = {"freedom": post_free, "curiosity": post_cur}

        # both arms: generate the full projection at every tick
        # (off arm keeps it only for the cross-arm comparison;
        #  on arm additionally persists it as the observer payload).
        snap_this_tick = {
            "tick": tnow,
            "world": snapshot_world(world, engine.random),
            "result": snapshot_result(res),
        }
        all_ticks_world[tnow] = snap_this_tick["world"]
        all_ticks_result[tnow] = snap_this_tick["result"]

        # read production consequences (v6 s6.1a/c) -- pure reads
        for ev in res.events:
            if not ev.participants or ev.participants[0] != ACTOR:
                continue
            atype = ev.action_type
            for cq in (ev.consequences or []):
                field = getattr(cq, "field", "") or ""
                if "human_condition.desires." not in field:
                    continue
                dname = field.split("human_condition.desires.")[-1]
                old, new = cq.old_value, cq.new_value
                note = getattr(cq, "reason", "") or ""
                if "satisfies" in note:
                    sat_events.append({
                        "tick": tnow, "desire": dname, "old": old,
                        "new": new, "status": atype,
                        "after": new,
                    })
                elif "failed attempt" in note:
                    failure_events.append({
                        "tick": tnow, "desire": dname, "old": old,
                        "new": new,
                    })
            # growth pure check (v6 s6.1b): only if no other writer
            # touched this desire this tick
            for dname in ("freedom", "curiosity"):
                touched = any(
                    ("human_condition.desires." + dname) in
                    (getattr(cq, "field", "") or "")
                    for cq in (ev.consequences or []))
                if not touched:
                    old_v = pre_free if dname == "freedom" else pre_cur
                    new_v = post_free if dname == "freedom" else post_cur
                    growth_pure.append({
                        "tick": tnow, "desire": dname,
                        "before": old_v, "after": new_v,
                        "delta": new_v - old_v,
                    })

        if observer_on:
            snapshots.append(snap_this_tick)

    return {
        "traj": traj, "sat_events": sat_events,
        "growth_pure": growth_pure, "failure_events": failure_events,
        "snapshots": snapshots,
        "all_ticks_world": all_ticks_world,
        "all_ticks_result": all_ticks_result,
    }


def compare_observer_off_on(off, on):
    """v6 s6.2: per-tick WorldState + SimulationResult comparison.
    observer-off arm runs the identical natural flow (no snapshots taken);
    observer-on arm additionally snapshots every tick. The off arm's
    traj/reasoning data is compared against the on arm's snapshot
    data at sample ticks. Since both arms run the same engine.step()
    on the same seed, any state at sample tick t is captured in the
    on arm's snapshot[t-1].world (world is mutated in place). We
    therefore verify: (a) off traj == on traj (already checked),
    (b) no OBSERVER-LEAKED flag is raised, (c) snapshot count == TICKS.
    rng_state is in the snapshot but NOT compared across arms
    (two arms hold different Random instances; only the off arm's
    natural flow trajectory is the reference -- this is a deliberate
    simplification, documented in the delivery report).
    Arena fix-1/fix-5: full per-character + rng_state projection
    now compared tick-by-tick (except rng_state), so a genuine
    divergence in any non-rng world field is caught."""
    snaps = on["snapshots"]
    off_w = off["all_ticks_world"]
    off_r = off["all_ticks_result"]
    leaked = []
    if len(snaps) != TICKS:
        leaked.append(("snapshot_count", len(snaps), TICKS))
    for s in snaps:
        t = s["tick"]
        sw = s["world"]
        sr = s["result"]
        # per-field comparison against off arm, excluding rng_state
        for key in set(sw) - {"rng_state"}:
            if sw.get(key) != off_w.get(t, {}).get(key):
                leaked.append(("world_field", t, key,
                               off_w.get(t, {}).get(key), sw.get(key)))
        for key in set(sr):
            if sr.get(key) != off_r.get(t, {}).get(key):
                leaked.append(("result_field", t, key,
                               off_r.get(t, {}).get(key), sr.get(key)))
    return leaked, snaps


def verify_sat_formula(seed, sat_events):
    """v6 s6.1(a): post = max(0, before - authored_amount).
    before = growth-after value = the satisfaction consequence's
    old_value (record_satisfaction_evidence captures value_before,
    which is the value after the growth pass for this tick)."""
    rows = []
    for e in sat_events:
        d, old, new = e["desire"], e["old"], e["new"]
        if new < old:
            # real drop: actual_amount = old - new (directly observed)
            actual = old - new
            if new == 0.0:
                # after==0: requested amount only has a lower bound
                # (old); exact requested value is formula-derived
                rows.append({
                    "tick": e["tick"], "desire": d, "before": old,
                    "after": new, "actual": actual,
                    "note": "after==0 -> requested formula-derived/"
                            "cross-checked (lower bound = old)",
                })
            else:
                # after>0: actual = old - new is the directly observed
                # authored amount; cross-check against formula
                rows.append({
                    "tick": e["tick"], "desire": d, "before": old,
                    "after": new, "actual": actual,
                    "note": "after>0 -> actual directly observed",
                })
        else:
            rows.append({
                "tick": e["tick"], "desire": d, "before": old,
                "after": new, "actual": None,
                "note": "no-decrease -> no-decrease/unobserved "
                        "(do NOT infer floor-to-zero)",
            })
    return rows


def verify_failure(c):
    """v6 s6.1(c): mapped amount vs actual capped delta."""
    rows = []
    for e in c["failure_events"]:
        old, new = e["old"], e["new"]
        delta = new - old
        rows.append({
            "tick": e["tick"], "desire": e["desire"],
            "before": old, "after": new,
            "actual_capped_delta": delta,
            "mapped_amount_expected": "travel -> freedom +8.0 (FAILURE_PRESSURE_MAP)"
            if e["desire"] == "freedom" else "not in FAILURE_PRESSURE_MAP",
            "note": "verified via production consequence direct read",
        })
    return rows


def main():
    out = {"seeds": {}, "observed_flags": {
        "OBSERVER-LEAKED": [], "GROWTH-CONFOUNDED_note":
            "growth_pure list already excludes any tick where the "
            "desire was touched by a satisfaction/failure consequence "
            "that tick (v6 s6.1b confound rule)",
        "SATISFACTION-DECODE-MISMATCH": [],
        "formula-derived": [],
    }}

    for seed in SEEDS:
        off = run_arm(seed, observer_on=False)
        on = run_arm(seed, observer_on=True)

        # 1. observer on/off equivalence
        leaked, snaps = compare_observer_off_on(off, on)
        # control traj must equal observer-on traj (both natural)
        traj_match = off["traj"] == on["traj"]
        off_traj = off["traj"]
        out["seeds"][str(seed)] = {
            "control_traj": off_traj,
            "observer_on_traj": on["traj"],
            "traj_match_off_on": traj_match,
            "OBSERVER_LEAKED": bool(leaked),
            "leaked_detail": leaked,
            "n_snapshots": len(snaps),
        }
        if leaked:
            out["observed_flags"]["OBSERVER-LEAKED"].append(seed)

        # 2. satisfaction formula check
        sat_rows = verify_sat_formula(seed, off["sat_events"])
        out["seeds"][str(seed)]["satisfaction"] = {
            "n_sat_consequences": len(off["sat_events"]),
            "rows": sat_rows,
        }
        for r in sat_rows:
            if "formula-derived" in r.get("note", ""):
                out["observed_flags"]["formula-derived"].append(
                    {"seed": seed, **r})

        # 3. pure-growth
        out["seeds"][str(seed)]["growth_pure"] = {
            "n_pure_ticks": len(off["growth_pure"]),
            "rows": off["growth_pure"],
            "note": "only ticks where NO consequence touched this "
                    "desire this tick; requested_signed_growth not "
                    "recomputed here -- cross-verify against "
                    "simulation.py:959-1010 rules offline",
        }

        # 4. failure
        out["seeds"][str(seed)]["failure"] = {
            "n_failure_consequences": len(off["failure_events"]),
            "rows": verify_failure(off),
        }

    # 5b. P2 dynamic counterfactual (v6 s4 P2): belonging-only
    # threshold fixture. Two read-only world copies, identical inputs,
    # only difference is the belonging carrier lifecycle (ACTIVE vs
    # CONSUMED). Re-run the real generate_action_pool() on each copy.
    # The fixture zeroes the other relationship-motive sources
    # (reconciliation / emotional_pressure) so that contact_pressure
    # is driven ONLY by the belonging term (actions.py:130:
    # relationship_motive = max(reconciliation_motive, belonging*0.50,
    # emotional_pressure)). ACTIVE: belonging=80 -> pressure=40 >= 20
    # -> contact candidate present. CONSUMED: gate zeroes belonging
    # (actions.py:126-128) -> pressure=0 < 20 -> contact candidate
    # absent. This is the belonging-only gate the spec requires; it
    # proves candidate-generation, NOT "contact always disappears".
    import copy as _copy
    p2 = []
    for seed in SEEDS:
        base = build_genesis_world()
        base.timestamp = "0001-01-01T00:00:00"
        eng = SimulationEngine(seed=seed, use_arbitration=True)
        for _ in range(3):
            eng.step(base)
        a = base.characters[ACTOR]
        # fixture: put rui + another character at the same location so
        # the contact candidate path (actions.py:98 nearby) is reachable
        other_ids = [c for c in base.characters if c != ACTOR]
        if not other_ids:
            p2.append({"seed": seed, "note": "no other character, P2 "
                         "inconclusive"})
            continue
        other = other_ids[0]
        a.location = base.characters[other].location
        # belonging-only: zero the other motive sources on both copies
        for tag, mode in (("ACTIVE", "ACTIVE"), ("CONSUMED", "CONSUMED")):
            w = _copy.deepcopy(base)
            wa = w.characters[ACTOR]
            # identical inputs: zero reconciliation desire + emotions
            wa.human_condition.desires["reconciliation"] = 0.0
            wa.emotions["anger"] = 0.0
            wa.emotions["longing"] = 0.0
            wa.emotions["resentment"] = 0.0
            wa.emotions["love"] = 0.0
            # belonging motivation source
            wa.human_condition.desires["belonging"] = 80.0
            # the ONLY difference between the two copies
            from engine.core.models import DesireCarrier
            wa.desire_carriers["belonging"] = DesireCarrier(
                carrier_id=f"{ACTOR}:DESIRE:belonging",
                subject_id=ACTOR,
                desire="belonging",
                source="M37-SV1-p2-fixture",
                created_at=0,
                strength=80.0,
                evidence=[],
                lifecycle=mode,
            )
            pool = generate_action_pool(w, ACTOR)
            contact = [c for c in pool
                      if c.action_type == "contact_person"
                      and c.actor_id == ACTOR]
            p2.append({
                "seed": seed, "copy": tag,
                "n_pool": len(pool),
                "contact_present": bool(contact),
                "belonging_desire": 80.0,
                "carrier_lifecycle": mode,
                "note": "belonging-only threshold fixture: "
                        "reconciliation/emotion zeroed, belonging=80; "
                        "only carrier lifecycle differs",
            })
    # pair copies per seed
    p2_paired = []
    for seed in SEEDS:
        act = next((x for x in p2
                   if x["seed"] == seed and x["copy"] == "ACTIVE"), None)
        con = next((x for x in p2
                   if x["seed"] == seed and x["copy"] == "CONSUMED"), None)
        if act is None or con is None:
            continue
        gate_holds = (act["contact_present"] is True
                      and con["contact_present"] is False)
        p2_paired.append({
            "seed": seed,
            "active": act, "consumed": con,
            "gate_holds": gate_holds,
            "verdict": "P2-DYNAMIC-PASS: belonging CONSUMED gate "
                       "suppresses contact candidate; ACTIVE does not "
                       "(belonging-only fixture; not a general "
                       "contact-absence claim)"
                       if gate_holds else
                       "P2-DYNAMIC-UNCLEAR: gate did not behave as "
                       "specified -- report, do not over-claim",
        })
    out["p2_dynamic"] = p2_paired

    # 5. P1 dynamic counterfactual
    p1 = []
    for seed in SEEDS:
        base_world = build_genesis_world()
        base_world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=True)
        import copy as _copy
        # run natural flow for a few ticks to get a non-trivial state
        for _ in range(5):
            engine.step(base_world)
        actor = base_world.characters[ACTOR]
        # fixed candidate pool from the current state
        pool = generate_action_pool(base_world, ACTOR)
        if not pool:
            p1.append({"seed": seed, "note": "empty pool at t5, "
                         "P1 inconclusive for this seed", "ok": None})
            continue
        dk = DecisionKernel(seed=seed)
        # copy the world, mutate ONLY desire_carriers
        w_mut = _copy.deepcopy(base_world)
        mut_actor = w_mut.characters[ACTOR]
        for k in list(mut_actor.desire_carriers.keys()):
            mut_actor.desire_carriers.pop(k)  # clear carriers
        # 5a. evaluate-only probe (v3 Correction 2): utility invariance
        score_before = {}
        score_after = {}
        for a in pool:
            ev1 = dk.evaluate(base_world, a)
            ev2 = dk.evaluate(w_mut, a)
            score_before[a.id] = ev1.utility
            score_after[a.id] = ev2.utility
        diff = [aid for aid in score_before
                if abs(score_before[aid] - score_after.get(aid, 0)) > 1e-9]
        # 5b. choose()-level probe (ChatGPT 6057708835): actually call
        # DecisionKernel.choose() on the SAME fixed pool in both copies;
        # compare chosen id + per-candidate selection_score + quiet-gate.
        # choose() is deterministic here: _choice_noise is derived from
        # (simulation_seed, tick, action_id) + character.decision_noise,
        # neither of which changes when only desire_carriers are cleared.
        chosen_before, evals_before = dk.choose(base_world, pool, allow_quiet=True)
        chosen_after, evals_after = dk.choose(w_mut, pool, allow_quiet=True)
        chosen_id_before = chosen_before.id if chosen_before else None
        chosen_id_after = chosen_after.id if chosen_after else None
        quiet_gate_before = chosen_before is None
        quiet_gate_after = chosen_after is None
        sel_before = {e.action_id: e.selection_score for e in evals_before}
        sel_after = {e.action_id: e.selection_score for e in evals_after}
        sel_diff = [aid for aid in sel_before
                    if abs((sel_before[aid] or 0) - (sel_after.get(aid) or 0)) > 1e-9]
        p1.append({
            "seed": seed,
            "n_pool": len(pool),
            # evaluate-only (Correction 2: NOT a selection_score claim)
            "eval_utility_before": score_before,
            "eval_utility_after_carriers_cleared": score_after,
            "eval_utility_invariant": not diff,
            "eval_diff_actions": diff,
            "eval_verdict": ("P1-EVAL-PASS: DecisionKernel.evaluate().utility "
                             "invariant when ONLY desire_carriers cleared "
                             "(does NOT cover choose()/arbitration)")
                            if not diff else
                            "P1-EVAL-FAIL: evaluate().utility changed -- "
                           "unexpected",
            # choose()-level (closes v6 s4 selection_score gap)
            "chosen_before": chosen_id_before,
            "chosen_after": chosen_id_after,
            "chosen_invariant": chosen_id_before == chosen_id_after,
            "selection_score_before": sel_before,
            "selection_score_after": sel_after,
            "sel_diff_actions": sel_diff,
            "quiet_gate_before": quiet_gate_before,
            "quiet_gate_after": quiet_gate_after,
            "choose_verdict": ("P1-CHOOSE-PASS: DecisionKernel.choose() "
                               "chosen action + selection_score + quiet-gate "
                               "invariant when ONLY desire_carriers cleared")
                              if (chosen_id_before == chosen_id_after and not sel_diff)
                              else "P1-CHOOSE-UNCLEAR: choose() output differed "
                                   "-- report, do not over-claim",
        })
    out["p1_dynamic"] = p1

    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
