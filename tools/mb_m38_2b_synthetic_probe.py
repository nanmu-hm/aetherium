"""M38-2B — Synthetic Desire Response Probe (tools-only shadow experiment).

Anchored 0ba1699, spec v4+v4.1 (PR#10 6260386368 + 6262046437),
executed on a new ref pushed with this tool.

SCOPE (synthetic evidence only, M22 discipline):
Inject ONE synthetic Desire via production API MemoryState.add_desire
into the ACTOR's memory_state in an ISOLATED world copy, run dual
arms (control / treatment) for 40 ticks, and measure whether the
injected signal transmits through the decision chain at three layers:
  L1  signal -> utility (at T*, the first clean conduction-band tick >=2)
  L2a selection-score channel (at T*, both arms INERT only)
  L2b actual engine commit (at T*, per each arm's real branch)
  L3  landed event / consequence (at T*)

NO production/test/weight change. Tools-only. No merge to main.
8c5a8fd FROZEN, 0ba1699 READ-ONLY. 342/0 = inherited M33 baseline.

DESIGN (from spec v4+v4.1, per ChatGPT 6261429098 + Arena 6264564177):
- use_arbitration=True (matches all natural-flow configurations)
- Option (a): mirror the full decision path
  (generate -> appraisals -> evaluate -> arbitrate -> apply_arbitration
   -> choose(post-arbitration) -> step once)
- Option (2): T* = first clean conduction-band tick >= 2
  (outcome-independent; computed from arms_world_identical_ex_desire
   + hc_c series, NOT from observed divergence)
- T* = 4 for all 5 seeds (seed-invariant t1-t4 hc series; travel
  hc = 0.081 at t4, in (0.05, 0.64) conduction band, pre-step clean)
- Anchor expectations (Arena-verified, tool must independently
  reproduce): util_c -0.015216 -> util_t 0.180434,
  delta = 0.195650 = 0.35*(0.64-0.081) exact
- L1/L2a/L2b/L3 verdicts at T*; tick-1 = INCONCLUSIVE-by-ceiling
  (travel hc=0.800 >= 0.64, no conduction-band candidate at tick 1)
- L2b FAIL requires L1=PASS (conduction-band utility changed) AND
  identical commits; ceiling cases -> L2b INCONCLUSIVE, NOT FAIL
- L3 FAIL-L2b-identical-event bucket (R13b): L2b=FAIL + events
  identical at T* -> distinct from INCONCLUSIVE and OBSERVATIONAL
- Six-function static audit + step() actual-branch check
- 8 operational halt rules (f1d0c6c: halt-1/2/3 machine-executed
  in-tool, halt-5/7/8 external/manual; see meta.halt_rules)
- canonical_sha256 (env-independent block, same scheme as 2A v5)
- L2a semantic boundary (gate C item, ChatGPT 6280949531): L2a
  strictly tests the selection-score channel (choose() output,
  decision.py:236). The v1 "chosen-differs OR" sub-clause was
  removed (the per-candidate 'chosen' key did not exist on
  candidate records; L2b handles chosen-action identity). L2a
  PASS requires a shared same-ID candidate's selection_score to
  differ by > 1e-9; it does NOT assert that a chosen-action
  difference was observed. This boundary is preserved at the code
  and JSON output level (per-candidate 'selection_score' field in
  pre_step_pool at every tick; L2a verdict + detail in the output).

INJECTION PARAMS (pre-registered, no change from v4):
  Desire(id="m38_2b_syn_<seed>", owner_id="rui",
        priority=0.80, urgency=0.80, opportunity_window_end=None,
        status="active", description="synthetic probe desire (M38-2B)")
  effective memory_urgency = 0.80 * 0.80 = 0.64
"""
from __future__ import annotations
import sys, json, hashlib, subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.decision import DecisionKernel
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world
from engine.memory.models import Desire
from engine.core.actions import generate_action_pool
from engine.core.appraisal import (
    build_appraisals, arbitrate, apply_arbitration)

SEEDS = (1, 3, 7, 42, 99)
ACTOR = "rui"
TICKS = 40
SAMPLE_TICKS = (1, 5, 10, 20, 40)  # trajectory observation only

# Pre-registered anchor expectations (Arena 6264564177, tool must
# independently reproduce; if output disagrees -> halt/leak-class)
ANCHOR_TSTAR = 4
ANCHOR_HC_AT_TSTAR = 0.081
ANCHOR_EXPECTED_DELTA = 0.35 * (0.64 - 0.081)  # = 0.19565
ANCHOR_UTIL_C = -0.015216
ANCHOR_UTIL_T = 0.180434
ANCHOR_KINDS = ("inert", "inert")
TOL = 1e-9


def hc_urgency(world, actor_id, action_type):
    """Replicate decision.py:149-157 _human_condition_urgency,
    action-type-specific mapping."""
    hc = world.characters[actor_id].human_condition
    desires = hc.desires
    if action_type == "rest":
        return max(0.0, min(100.0, hc.fatigue)) / 100.0
    if action_type == "search_person":
        return max(desires.get("reconciliation", 0.0),
                   desires.get("belonging", 0.0)) / 100.0
    mapping = {
        "travel": ("freedom", "curiosity"),
        "contact_person": ("reconciliation", "belonging"),
        "help_person": ("responsibility",),
    }
    return max((max(0.0, min(100.0, desires.get(n, 0.0))) / 100.0
                for n in mapping.get(action_type, ())), default=0.0)


def memory_urgency(world, actor_id):
    """Replicate decision.py:167, read-only."""
    ms = world.memory_state
    return max(
        (d.urgency * d.priority for d in ms.desires.values()
         if d.owner_id == actor_id and d.status == "active"),
        default=0.0,
    )


def pre_step_probe(world, engine, actor_id):
    """Option (a) mirror: full decision path, read-only.
    Returns dict with pool, appraisals, evals, arbitration,
    post_arb, chosen, kind, arb_cand_id, and per-candidate
    metrics (hc_urgency, memory_urgency, utility)."""
    actor = world.characters[actor_id]
    pool = generate_action_pool(world, actor_id)
    appraisals = build_appraisals(engine.decision_kernel, world, actor, pool)
    evals = [engine.decision_kernel.evaluate(world, c) for c in pool]
    arbitration = arbitrate(appraisals, pool, evals)
    post_arb = apply_arbitration(pool, arbitration, evals)
    chosen, selected = engine.decision_kernel.choose(
        world, post_arb, allow_quiet=True)
    kind = arbitration.kind if arbitration else "inert"
    arb_cand_id = arbitration.candidate_id if arbitration else None
    mem_urg = memory_urgency(world, actor_id)
    # Real selection_score per candidate from choose()'s selected list
    # (decision.py:236 = utility + clamped(action.score) + noise).
    # The evaluate() results do NOT carry selection_score (None), so
    # read it from `selected`, matched by action_id.
    sel_by_id = {e.action_id: e for e in selected}
    per_cand = []
    for c in post_arb:
        e = sel_by_id.get(c.id)
        per_cand.append({
            "id": c.id,
            "action_type": c.action_type,
            "hc_urgency": round(hc_urgency(world, actor_id, c.action_type), 9),
            "memory_urgency": round(mem_urg, 9),
            "utility": round(e.utility, 9) if e else None,
            "selection_score": round(e.selection_score, 9)
                                if (e and e.selection_score is not None)
                                else None,
        })
    return {
        "pool": per_cand,
        "post_arb_ids": [c.id for c in post_arb],
        "arbitration_kind": kind,
        "arbitration_cand_id": arb_cand_id,
        "chosen_id": chosen.id if chosen else None,
        "chosen_type": chosen.action_type if chosen else None,
        "mem_urgency": round(mem_urg, 9),
        "pre_step_world_canonical": world_canonical_brief(world),
    }


def world_canonical_brief(world):
    """Brief canonical projection for arms_world_identical_ex_desire
    (excluding memory_state.desires, per R2)."""
    chars = {}
    for cid, c in sorted(world.characters.items()):
        hc = c.human_condition
        chars[cid] = {
            "id": cid, "status": c.status, "location": c.location,
            "desires": {k: round(v, 9) for k, v in hc.desires.items()},
            "emotions": {k: round(v, 9) for k, v in c.emotions.items()},
            "mem_count": len(c.memory_ids),
        }
    return {
        "tick": world.tick,
        "n_memories": len(world.memory_state.memories),
        "characters": chars,
        "locations": sorted(world.locations),
    }


def _consequence_canonical(cq):
    """Consequence full content (id + type + old/new), per registered L3
    scope. D4/D5: L3 verifies event/consequence content, not just
    event id or count."""
    return {
        "target_type": getattr(cq, "target_type", ""),
        "target_id": getattr(cq, "target_id", ""),
        "field": getattr(cq, "field", ""),
        "old_value": getattr(cq, "old_value", None),
        "new_value": getattr(cq, "new_value", None),
        "reason": getattr(cq, "reason", ""),
    }


def result_canonical(res):
    actions = []
    for a in res.actions:
        actions.append({
            "id": a.id, "actor_id": a.actor_id,
            "action_type": a.action_type,
            "score": round(a.score, 9),
        })
    events = []
    for e in res.events:
        cons = getattr(e, "consequences", None) or []
        events.append({
            "id": e.id, "tick": e.tick, "location": e.location,
            "action_type": e.action_type,
            "participants": list(e.participants),
            "consequences": [_consequence_canonical(cq) for cq in cons],
            "n_consequences": len(cons),
        })
    return {
        "tick": res.tick,
        "actions": actions,
        "events": events,
        "n_validation_errors": len(res.validation_errors),
    }


def compute_tstar(clean_flags, hc_series, mem_urg_series):
    """Outcome-independent T* = first tick >= 2 where
    arms_world_identical_ex_desire == True AND at least one
    same-ID candidate (in the post-arbitration pool) has hc_c in the
    conduction band.
    Conduction band: non-travel hc_c < 0.64, travel 0.05 < hc_c < 0.64."""
    for t in range(2, TICKS + 1):
        if not clean_flags.get(t, False):
            continue
        # check if any candidate at this tick is in conduction band
        for cand in hc_series.get(t, []):
            at = cand["action_type"]
            hc = cand["hc_urgency"]
            if at == "travel":
                if 0.05 < hc < 0.64:
                    return t
            else:
                if hc < 0.64:
                    return t
    return None  # no clean conduction-band tick -> INCONCLUSIVE


def in_conduction_band(action_type, hc):
    """Conduction band: non-travel hc < 0.64; travel 0.05 < hc < 0.64."""
    if action_type == "travel":
        return 0.05 < hc < 0.64
    return hc < 0.64


def judge_l1(control_cand, treat_cand, t_star, hc_c_at_tstar):
    """L1 at T*. Per-candidate, same-ID, conduction-band candidates only.
    D4 (ChatGPT 6271192560 item 4): a REAL FAIL-by-mechanism branch is
    required, distinct from INCONCLUSIVE-by-ceiling and INVALID/HALT.
      - PASS: a conduction-band same-ID candidate's observed delta ==
        expected 0.35*(0.64-hc) within TOL.
      - FAIL-by-mechanism: a conduction-band same-ID candidate EXISTS
        but its observed delta does NOT equal the expected value
        (max() wiring broken / signal not transmitted) -> a real
        mechanism result, NOT an anchor/injection error.
      - INCONCLUSIVE-by-ceiling: NO conduction-band candidate exists
        at T* (all candidates in ceiling ranges) -> signal present
        but no transmission detectable; not a mechanism failure.
      - INVALID/HALT is NOT an L1 verdict; it is raised by the anchor
        check (halt-8) when the clean anchor is broken or memory_urgency
        did not register. See run_arm / main.
    Returns (verdict, hc_c, expected_delta, observed_delta, detail)."""
    by_id_c = {c["id"]: c for c in control_cand}
    seen_in_band = False
    for cid, t_c in ((c["id"], c) for c in treat_cand):
        c = by_id_c.get(cid)
        if c is None:
            continue
        hc = c["hc_urgency"]
        at = c["action_type"]
        if not in_conduction_band(at, hc):
            continue
        seen_in_band = True
        expected_delta = 0.35 * (0.64 - hc)
        observed_delta = (t_c.get("utility") or 0) - (c.get("utility") or 0)
        if abs(observed_delta - expected_delta) <= TOL:
            return ("PASS", hc, expected_delta, observed_delta,
                    {"candidate": cid, "action_type": at})
        # A conduction-band candidate whose utility did NOT move the
        # expected amount: FAIL-by-mechanism (real result).
        return ("FAIL-by-mechanism", hc, expected_delta, observed_delta,
                {"candidate": cid, "action_type": at})
    if seen_in_band:
        return ("FAIL-by-mechanism", None, None, None,
                {"note": "conduction-band candidate present but no "
                          "expected delta observed"})
    # No conduction-band candidate at T* -> ceiling, not a failure.
    return ("INCONCLUSIVE-by-ceiling", None, None, None,
            {"note": "no conduction-band candidate at T* (ceiling)"})


def judge_l2a(control_cand, treat_cand, t_star):
    """L2a at T*: compare the REAL selection_score (choose() output,
    decision.py:236) for same-ID candidates in the post-arbitration
    pool. D4 (ChatGPT 6271192560 item 4): PASS iff a shared candidate's
    selection_score differs by > TOL. INCONCLUSIVE if no shared
    candidate has a comparable (non-None) selection_score, or no
    difference is observed. The L2b layer handles chosen-action
    identity; L2a is strictly the selection-score channel (no per-
    candidate 'chosen' key on candidates, only on the arm-level
    pre_step record)."""
    by_id_c = {c["id"]: c for c in control_cand}
    for cid in sorted(by_id_c.keys()):
        c = by_id_c[cid]
        t_c = next((x for x in treat_cand if x["id"] == cid), None)
        if t_c is None:
            continue  # not a shared candidate
        cs, ts = c.get("selection_score"), t_c.get("selection_score")
        if cs is None or ts is None:
            continue  # no real selection_score for this candidate
        if abs(cs - ts) > TOL:
            return "PASS", {"candidate": cid, "control": cs, "treat": ts}
    return "INCONCLUSIVE", {"note": "no shared candidate with a "
                                     "comparable selection_score"}


def judge_l2b(control_committed, treat_committed, l1_verdict, t_star):
    """L2b at T*: per each arm's real branch.
    D4 (ChatGPT 6271192560 item 4): compare the ACTUAL engine landed
    action IDENTITY (id + action_type + actor_id), not just action
    type. 'committed' here is the resolved rui action at T* for each
    arm (a dict {id, action_type, actor_id} or None for no-action).
    PASS iff L1=PASS AND committed action identities differ.
    FAIL iff L1=PASS AND committed action identities identical.
    INCONCLUSIVE iff L1=INCONCLUSIVE-by-ceiling (ceiling explains
    identical commit, NOT mechanism failure) or L1=FAIL-by-mechanism
    (the mechanism layer already failed; commit comparison is N/A)."""
    if l1_verdict.startswith("INCONCLUSIVE"):
        return "INCONCLUSIVE"
    if l1_verdict.startswith("FAIL"):
        return "INCONCLUSIVE"  # upstream mechanism failure; L2b N/A
    # L1 = PASS: signal reached utility
    if control_committed != treat_committed:
        return "PASS"
    else:
        return "FAIL"


def judge_l3(control_events, treat_events, t_star, l2b_verdict):
    """L3 at T*: D4 (ChatGPT 6271192560 item 4): verify landed event /
    consequence CONTENT per the registered scope (event id + type +
    tick + consequences), not just event id.
    PASS iff a landed event or its consequence content differs at T*.
    FAIL-L2b-identical-event (R13b) iff L2b=FAIL AND events are
    identical at T*.
    OBSERVATIONAL iff events differ only at later ticks (not T*).
    INCONCLUSIVE iff L2b INCONCLUSIVE."""
    if l2b_verdict == "INCONCLUSIVE":
        return "INCONCLUSIVE"

    def _content(events):
        # content = id + type + tick + consequences (registered scope)
        return [
            {
                "id": e.get("id"),
                "action_type": e.get("action_type"),
                "tick": e.get("tick"),
                "consequences": e.get("consequences", []),
            }
            for e in events]

    c_content = _content(control_events)
    t_content = _content(treat_events)
    c_sorted = json.dumps(sorted(c_content, key=repr), default=str)
    t_sorted = json.dumps(sorted(t_content, key=repr), default=str)
    if l2b_verdict == "FAIL" and c_sorted == t_sorted:
        return "FAIL-L2b-identical-event"
    if c_sorted != t_sorted:
        return "PASS"
    return "OBSERVATIONAL"


def run_arm(seed, inject: bool):
    """Independent genesis world + engine.
    If inject=True: add the synthetic Desire before the first step().
    D1 (halt-1): injection snapshot check — record the key set
    BEFORE and AFTER the injection; diff must be exactly +1.
    D5: full per-tick records with all registered fields (utility,
    selection_score, hc, kind, commit/event, consequences)."""
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)

    pre_inject_keys = set(world.memory_state.desires.keys())
    if inject:
        desire = Desire(
            id=f"m38_2b_syn_{seed}",
            owner_id=ACTOR,
            description="synthetic probe desire (M38-2B)",
            priority=0.80,
            urgency=0.80,
            opportunity_window_end=None,
            status="active",
        )
        world.memory_state.add_desire(desire)
    post_inject_keys = set(world.memory_state.desires.keys())
    injection_snapshot = {
        "pre_keys": sorted(pre_inject_keys),
        "post_keys": sorted(post_inject_keys),
        "added": sorted(post_inject_keys - pre_inject_keys),
        "removed": sorted(pre_inject_keys - post_inject_keys),
        "halt1_ok": (
            sorted(post_inject_keys - pre_inject_keys) ==
            ([f"m38_2b_syn_{seed}"] if inject else [])
            and not (pre_inject_keys - post_inject_keys)
        ),
    }

    records = []
    for t in range(TICKS):
        tick_num = t + 1
        probe = pre_step_probe(world, engine, ACTOR)
        res = engine.step(world)
        # D5: rui-level committed action + landed events per tick
        rui_committed = next(
            (a for a in res.actions if a.actor_id == ACTOR), None)
        rui_event_ids = [
            e.id for e in res.events
            if ACTOR in (e.participants or [])]
        rec = {
            "tick": tick_num,
            "pre_step": probe,
            "world": world_canonical_brief(world),
            "result": result_canonical(res),
            # D1/halt-3 (Blocker 1, ChatGPT 6284623561): store the
            # POST-STEP full canonical projection (exact 2A v5 field
            # set) so halt-3 compares the registered full {world,
            # result} directly, not a field intersection. The
            # post-step world IS the next tick's pre-step world;
            # storing it here (after step()) gives halt-3 the full
            # tick-level world state to match against 2A arm-N.
            "world_post_full": world_canonical_full(world),
            "result_post_full": result_canonical_full(res),
            "rui_committed_id": (
                rui_committed.id if rui_committed else None),
            "rui_committed_type": (
                rui_committed.action_type if rui_committed else None),
            "rui_event_ids": rui_event_ids,
        }
        records.append(rec)
    return records, injection_snapshot


def halt2_mismatch(off, on, seed):
    """D1/halt-2: mirror purity — the INERT-tick mirrored selection
    must match the actual step() committed action for rui. Any INERT
    tick where the mirror's chosen action differs from the real
    commit is a probe-side leak (the 6-call pre-step sequence is not
    faithfully reflecting the engine's actual decision path)."""
    mismatches = []
    for ro, rp in zip(off, on):
        for arm_label, r in (("control", ro), ("treat", rp)):
            pre = r["pre_step"]
            if pre["arbitration_kind"] == "inert":
                if (pre["chosen_type"] or None) != \
                        (r["rui_committed_type"] or None):
                    mismatches.append(
                        f"{seed}/{arm_label}/t{r['tick']} "
                        f"mirror={pre['chosen_type']} "
                        f"commit={r['rui_committed_type']}")
    return mismatches


def world_canonical_full(world):
    """Full world canonical projection for halt-3 (R12 strong form).
    Same field set as 2A v5's world_canonical: tick, timestamp,
    n_memories, n_desires, desire_keys, all characters with full
    semantic fields, locations. This is the registered projection
    that must match 2A v5 arm-N tick-for-tick."""
    from engine.core.actions import generate_action_pool as _gap  # noqa
    chars = {}
    for cid, c in sorted(world.characters.items()):
        hc = c.human_condition
        chars[cid] = {
            "id": cid, "status": c.status, "location": c.location,
            "desires": {k: round(v, 9) for k, v in hc.desires.items()},
            "emotions": {k: round(v, 9) for k, v in c.emotions.items()},
            "mem_count": len(c.memory_ids),
            "habits": {k: round(v, 9) for k, v in c.habits.items()},
        }
    return {
        "tick": world.tick,
        "timestamp": world.timestamp,
        "n_memories": len(world.memory_state.memories),
        "n_desires": len(world.memory_state.desires),
        "desire_keys": sorted(world.memory_state.desires.keys()),
        "characters": chars,
        "locations": sorted(world.locations),
    }


def result_canonical_full(res):
    """Full result canonical projection for halt-3 (R12 strong form).
    EXACT field set = 2A v5's result_canonical (zero drift):
    all actions with full fields INCLUDING n_risks; all events with
    full consequence content INCLUDING n_consequences; n_validation_
    errors + validation_errors. Any field the 2A projection carries
    is carried here, so halt-3 compares the registered full
    projection directly (not a field intersection)."""
    actions = []
    for a in res.actions:
        actions.append({
            "id": a.id, "actor_id": a.actor_id,
            "action_type": a.action_type,
            "targets": list(a.targets),
            "motivation": a.motivation,
            "confidence": round(a.confidence, 9),
            "score": round(a.score, 9),
            "risks": list(a.risks),
            "n_risks": len(a.risks),
        })
    events = []
    for e in res.events:
        cons = getattr(e, "consequences", None) or []
        events.append({
            "id": e.id, "tick": e.tick, "location": e.location,
            "action_type": e.action_type,
            "participants": list(e.participants),
            "consequences": [
                {
                    "target_type": getattr(cq, "target_type", ""),
                    "target_id": getattr(cq, "target_id", ""),
                    "field": getattr(cq, "field", ""),
                    "old_value": getattr(cq, "old_value", None),
                    "new_value": getattr(cq, "new_value", None),
                    "reason": getattr(cq, "reason", ""),
                }
                for cq in cons],
            "n_consequences": len(cons),
        })
    return {
        "tick": res.tick,
        "n_actions": len(res.actions),
        "actions": actions,
        "n_events": len(res.events),
        "events": events,
        "n_validation_errors": len(res.validation_errors),
        "validation_errors": list(res.validation_errors),
    }


def _world_diff_keys(a_world, b_world):
    """Top-level keys that differ between two full world canonical
    projections (for audit evidence, not the comparison itself)."""
    return [k for k in set(a_world) | set(b_world)
            if a_world.get(k) != b_world.get(k)]


def halt3_control_leak(off_records, seed):
    """D1/halt-3 (R12 strong form, Blocker 1 final form per ChatGPT
    6284623561): the control arm (no injection, with pre-step probe)
    must tick-for-tick match 2A v5 arm-N (no injection, no probe) on
    the FULL registered {world, result} canonical projection — the
    complete 2A v5 field set, NOT a field intersection. Machine
    check: re-run 2A arm-N in-process; for every tick compare the
    in-process 2A arm-N's world_canonical_full + result_canonical_full
    DIRECTLY (exact dict equality) against the 2B control arm's
    stored POST-STEP full projections (ro['world_post_full'] /
    ro['result_post_full'], captured after engine.step() in run_arm).
    Any per-tick mismatch in ANY field -> audit evidence + PROBE-
    LEAKED. This is the tool-internal fail-closed check the gate
    requires; the external Arena 0-x5x40 re-run remains independent
    evidence but does not substitute for this in-tool check.
    Empty = clean."""
    mismatches = []
    world_a = build_genesis_world()
    world_a.timestamp = "0001-01-01T00:00:00"
    eng_a = SimulationEngine(seed=seed, use_arbitration=True)
    for i, ro in enumerate(off_records):
        res_a = eng_a.step(world_a)
        tick = i + 1
        # 2A arm-N in-process FULL canonical projections
        a_world = world_canonical_full(world_a)
        a_res = result_canonical_full(res_a)
        # 2B control arm stored POST-STEP FULL canonical projections
        b_world = ro.get("world_post_full")
        b_res = ro.get("result_post_full")
        # fail-closed: if the stored full projections are missing,
        # that itself is a halt (cannot verify the full check).
        if b_world is None or b_res is None:
            mismatches.append(
                f"seed {seed} t{tick} MISSING stored full "
                f"post-step projection (world_post_full / "
                f"result_post_full) — cannot verify halt-3")
            continue
        # FULL world projection: exact dict equality (all 2A fields).
        if a_world != b_world:
            dk = _world_diff_keys(a_world, b_world)
            mismatches.append(
                f"seed {seed} t{tick} 2A-arm-N vs 2B-control "
                f"WORLD full-projection diff keys={dk}")
        # FULL result projection: exact dict equality (all 2A fields
        # incl. n_risks / n_consequences / full consequence content).
        if a_res != b_res:
            mismatches.append(
                f"seed {seed} t{tick} 2A-arm-N vs 2B-control "
                f"RESULT full-projection diff "
                f"(fields={sorted(set(a_res) | set(b_res))})")
    return mismatches



def first_divergence_rui(off, on):
    """D2/R6 registered definition: first tick where ACTOR (rui)
    committed action identity (id) OR ACTOR's landed event ids
    differ between control and treatment. Cross-actor mixed commits
    are NOT included (D2 fix: the v1 version compared actions[0]
    which could belong to a non-rui actor)."""
    for ro, rp in zip(off, on):
        c_rui_id = next(
            (a["id"] for a in ro["result"]["actions"]
             if a.get("actor_id") == ACTOR), None)
        t_rui_id = next(
            (a["id"] for a in rp["result"]["actions"]
             if a.get("actor_id") == ACTOR), None)
        c_evt = sorted(
            e["id"] for e in ro["result"]["events"]
            if ACTOR in (e.get("participants") or []))
        t_evt = sorted(
            e["id"] for e in rp["result"]["events"]
            if ACTOR in (e.get("participants") or []))
        if c_rui_id != t_rui_id or c_evt != t_evt:
            return ro["tick"]
    return None


def arms_world_identical(off_rec, on_rec):
    """R2: dual-arm PRE-STEP canonical projection diff,
    EXCLUDING memory_state.desires. Measured BEFORE step(), so
    post-step committed-action divergence does NOT contaminate
    the clean check. Compares the pre_step_world_canonical fields
    (characters + locations), NOT n_memories/mem_count (those
    reflect the injection itself, which is the effect under test)."""
    off_w = off_rec["pre_step"]["pre_step_world_canonical"]
    on_w = on_rec["pre_step"]["pre_step_world_canonical"]
    # Compare character fields excluding memory-derived counts and
    # the hc.desires that the injection does NOT touch (injection
    # only adds to memory_state.desires, not hc.desires).
    off_chars = {k: {kk: vv for kk, vv in v.items() if kk not in ("mem_count",)}
                 for k, v in off_w["characters"].items()}
    on_chars = {k: {kk: vv for kk, vv in v.items() if kk not in ("mem_count",)}
                for k, v in on_w["characters"].items()}
    return off_chars == on_chars and off_w["locations"] == on_w["locations"]


def main():
    out = {
        "seeds": {},
        "flags": {"HALT": [], "PROBE-LEAKED": [], "INVALID": []},
        "meta": {
            "python_version": sys.version.split()[0],
            "seeds": list(SEEDS),
            "ticks": TICKS,
            "actor": ACTOR,
            "injection": {
                "api": "MemoryState.add_desire (engine/memory/models.py:128)",
                "params": {
                    "priority": 0.80, "urgency": 0.80,
                    "opportunity_window_end": None,
                    "status": "active",
                    "effective_memory_urgency": 0.64,
                },
                "created_at": "NOT a Desire field (B1 erratum)",
            },
            "anchor_expectations": {
                "T_star": ANCHOR_TSTAR,
                "hc_at_T_star": ANCHOR_HC_AT_TSTAR,
                "expected_delta": round(ANCHOR_EXPECTED_DELTA, 9),
                "util_c": ANCHOR_UTIL_C,
                "util_t": ANCHOR_UTIL_T,
                "kinds": list(ANCHOR_KINDS),
                "note": ("Arena-verified pre-registered values; tool must "
                          "independently reproduce. If output disagrees "
                          "with these values, report as halt/leak-class; "
                          "do NOT post-hoc reconcile."),
            },
            "halt_rules": {
                "D1 (ChatGPT 6271192560 item 1, updated ff2e0eb "
                "Blocker 1 final form; G1 erratum per ChatGPT "
                "6304610817 closeout + Arena 6288251259 §4-G1)": (
                    "Machine-executable halt checks in-tool: "
                    "halt-1 (injection snapshot diff == +1, per "
                    "seed); halt-2 (mirror purity — scans all 400 "
                    "arm-ticks but the in-tool comparison is "
                    "INERT-kind, type-level; Arena's full-kind "
                    "ID-level check is an external supplement, "
                    "0/400); halt-3 (ff2e0eb Blocker 1 FINAL "
                    "form, ChatGPT 6284623561 §①: in-tool "
                    "comparison = EXACT dict equality of the FULL "
                    "registered 2A v5 {world,result} canonical "
                    "projection — world_canonical_full + "
                    "result_canonical_full (incl. n_risks, "
                    "n_consequences, full consequence content) — "
                    "against the control arm's stored POST-STEP "
                    "full projections (world_post_full / "
                    "result_post_full, captured after "
                    "engine.step()); ANY per-tick field mismatch "
                    "-> audit evidence string + PROBE-LEAKED; "
                    "stored-projection-missing -> fail-closed "
                    "MISSING mismatch. The prior 'brief-field "
                    "intersection / strengthened form' "
                    "description in ea7a4eb is STALE — "
                    "implementation now IS the full registered "
                    "projection direct comparison; that line is "
                    "superseded by ff2e0eb. Negative control "
                    "(in-process monkeypatch): clean=0; "
                    "corrupt n_risks=11, n_desires=40, "
                    "missing=40 mismatches; Arena added "
                    "habits/timestamp=40, targets=11 — blind "
                    "spot eliminated). Non-mechanizable conditions "
                    "(halt-5 unknown-kind, halt-7 observer-side "
                    "leak, halt-8 reproducibility/hash failure) "
                    "are flagged but NOT machine-checked in-tool; "
                    "they are external/manual. The v1 claim "
                    "'8 halt rules all green' is "
                    "correction-replaced: only halt-1/2/3 are "
                    "machine-executed in-tool; the rest are "
                    "external."),
                "G1 closeout erratum (ChatGPT 6304610817; Arena "
                "6288251259 §4-G1; non-blocking, no new code ref "
                "required)": (
                    "The halt-3 description in meta.halt_rules "
                    "as of ea7a4eb ('in-tool is a strengthened "
                    "form, not the full registered projection') "
                    "is STALE. ff2e0eb implemented the full "
                    "registered 2A v5 {world,result} projection "
                    "direct comparison; the ea7a4eb wording "
                    "understates the actual implementation. "
                    "Authoritative implementation = ff2e0eb: "
                    "halt3_control_leak compares "
                    "world_canonical_full + result_canonical_full "
                    "(exact dict equality, all fields incl. "
                    "n_risks/n_consequences) at every tick, "
                    "fail-closed. This erratum is the closeout "
                    "record; it does not require a new code ref. "
                    "All verdicts and canonical SHA unchanged."),
                "F4 (ChatGPT 6280949531 item C, R6/R7 preserved, "
                "per Arena 6281604827 F4)": (
                    "R6: canonical-block note is imprecise — "
                    "anchor_check is in-block via seeds (a "
                    "superset, hash-integrity-neutral, wording "
                    "not precise). R7: judge_l1 early-returns on "
                    "the FIRST in-band candidate (order-dependent "
                    "if multiple in-band candidates; not triggered "
                    "this run, single in-band candidate at "
                    "T*=4); L1-FAIL -> L2b INCONCLUSIVE is a "
                    "post-v4 new mapping (documented in code, "
                    "not triggered this run, L1 5/5 PASS). Both "
                    "preserved verbatim, not hidden, per gate C. "
                    "No verdict impact this run."),
            },
            "time_semantics": (
                "Pre-step probe runs BEFORE engine.step() (Option a). "
                "All per-candidate readings are DECISION-TIME (pre-step), "
                "NOT POST-STEP. L1/L2a/L2b/L3 verdicts at T*."),
        },
    }

    per_seed_records = {}  # seed -> (off, on, injection_snapshots)

    for seed in SEEDS:
        off, off_snap = run_arm(seed, inject=False)
        on, on_snap = run_arm(seed, inject=True)
        per_seed_records[seed] = (off, on, off_snap, on_snap)

        # D1/halt-1: injection snapshot check (treatment arm only)
        if not on_snap["halt1_ok"]:
            out["flags"]["HALT"].append(
                f"seed {seed}: halt-1 injection snapshot diff != "
                f"+1 ({on_snap['added']} added, {on_snap['removed']} "
                f"removed)")

        # D1/halt-2: mirror purity (INERT mirror vs actual commit)
        h2 = halt2_mismatch(off, on, seed)
        if h2:
            out["flags"]["PROBE-LEAKED"].extend(h2)

        # D1/halt-3: control arm vs 2A v5 arm-N (R12 strong form)
        h3 = halt3_control_leak(off, seed)
        if h3:
            out["flags"]["PROBE-LEAKED"].extend(
                [f"seed {seed}: halt-3 control-vs-2A {m}"
                 for m in h3[:3]])

        # R2: clean flags per tick (pre-step, ex-desire)
        clean = {}
        for to, tp in zip(off, on):
            clean[to["tick"]] = arms_world_identical(to, tp)

        # hc series (from pre_step post-arb pools, control arm)
        hc_series = {}
        for r in off:
            hc_series[r["tick"]] = [
                {"action_type": c["action_type"],
                 "hc_urgency": c["hc_urgency"]}
                for c in r["pre_step"]["pool"]]

        # T* (outcome-independent)
        t_star = compute_tstar(
            {k: v for k, v in clean.items() if k >= 2},
            hc_series,
            None,
        )

        # Per-seed verdicts
        seed_out = {
            "t_star": t_star,
            "clean_flags": {str(k): v for k, v in clean.items()},
            "anchor_check": {},
            "injection_snapshot": on_snap,
        }

        # D4: explicitly record the tick-1 ceiling INCONCLUSIVE
        # (all candidates travel hc=0.800 >= 0.64 at tick 1, so L1
        # at tick 1 is INCONCLUSIVE-by-ceiling; the causal verdict
        # anchor is T*, not tick 1).
        seed_out["tick1_record"] = {
            "note": ("Tick 1 is the verified clean anchor "
                     "(arms_world_identical_ex_desire=True) but is "
                     "ceiling-degenerate: rui's pool is a single "
                     "travel candidate with hc=0.800 (>= 0.64), so "
                     "no conduction-band candidate exists. L1/L2a/"
                     "L2b/L3 verdicts are made at T*, not tick 1."),
        }

        if t_star is None:
            seed_out["verdicts"] = {
                "L1": "INCONCLUSIVE",
                "L2a": "INCONCLUSIVE",
                "L2b": "INCONCLUSIVE",
                "L3": "INCONCLUSIVE",
            }
            seed_out["note"] = (
                "No clean conduction-band tick >=2 in full "
                "trajectory; INCONCLUSIVE (not FAIL).")
            out["seeds"][str(seed)] = seed_out
            continue

        # Get T* records from both arms
        off_tstar = next(r for r in off if r["tick"] == t_star)
        on_tstar = next(r for r in on if r["tick"] == t_star)
        off_cand = off_tstar["pre_step"]["pool"]
        on_cand = on_tstar["pre_step"]["pool"]

        # Anchor check (compare against pre-registered expectations)
        anchor_hc = None
        for c in off_cand:
            if c["action_type"] == "travel":
                anchor_hc = c["hc_urgency"]
                break
        anchor_delta = None
        for c in off_cand:
            for t_c in on_cand:
                if c["id"] == t_c["id"]:
                    anchor_delta = (
                        (t_c.get("utility") or 0)
                        - (c.get("utility") or 0))
                    break
        anchor_match = (
            t_star == ANCHOR_TSTAR
            and abs((anchor_hc or 0) - ANCHOR_HC_AT_TSTAR) < 1e-6
            and (anchor_delta is not None
                 and abs(anchor_delta - ANCHOR_EXPECTED_DELTA) < 1e-6)
        )
        seed_out["anchor_check"] = {
            "t_star_computed": t_star,
            "t_star_expected": ANCHOR_TSTAR,
            "match": anchor_match,
            "hc_at_tstar": anchor_hc,
            "hc_expected": ANCHOR_HC_AT_TSTAR,
            "delta_observed": (
                round(anchor_delta, 9)
                if anchor_delta is not None else None),
            "delta_expected": round(ANCHOR_EXPECTED_DELTA, 9),
        }
        # D4: anchor mismatch -> HALT (not post-hoc reconcile)
        if not anchor_match:
            out["flags"]["HALT"].append(
                f"seed {seed}: anchor mismatch "
                f"(T*={t_star} vs {ANCHOR_TSTAR}, "
                f"hc={anchor_hc} vs {ANCHOR_HC_AT_TSTAR}, "
                f"delta={round(anchor_delta, 9) if anchor_delta is not None else None}"
                f" vs {round(ANCHOR_EXPECTED_DELTA, 9)})")

        # L1 (D4: 5-tuple with detail)
        l1_v, l1_hc, l1_exp, l1_obs, l1_detail = judge_l1(
            off_cand, on_cand, t_star, anchor_hc)
        seed_out["L1"] = {
            "verdict": l1_v,
            "hc_c": l1_hc,
            "expected_delta": (
                round(l1_exp, 9) if l1_exp is not None else None),
            "observed_delta": (
                round(l1_obs, 9) if l1_obs is not None else None),
            "detail": l1_detail,
        }

        # L2a (only if both arms INERT at T*)
        off_kind = off_tstar["pre_step"]["arbitration_kind"]
        on_kind = on_tstar["pre_step"]["arbitration_kind"]
        both_inert = (off_kind == "inert" and on_kind == "inert")
        seed_out["kinds_at_tstar"] = {
            "control": off_kind, "treat": on_kind}
        if both_inert:
            l2a_v, l2a_detail = judge_l2a(off_cand, on_cand, t_star)
            seed_out["L2a"] = {"verdict": l2a_v, "detail": l2a_detail}
        else:
            seed_out["L2a"] = {
                "verdict": "N/A",
                "detail": {"note": (
                    f"not both INERT at T* "
                    f"(kinds: {off_kind}/{on_kind})")},
            }

        # L2b (Blocker 2 fix: the VERDICT must read the ACTUAL
        # engine landed action identity from result.actions
        # (post-step), NOT the pre-step mirror value. The mirror
        # (pre_step.chosen_id / arbitration_cand_id) is kept as a
        # diagnostic field only, not as the verdict input.)
        def _actual_landed_identity(rec):
            """Read the ACTUAL committed rui action from the
            post-step result (Blocker 2). Returns {id, action_type,
            actor_id} or None for no-action."""
            rui_action = next(
                (a for a in rec["result"]["actions"]
                 if a.get("actor_id") == ACTOR), None)
            if rui_action is None:
                return None
            return {
                "id": rui_action["id"],
                "action_type": rui_action["action_type"],
                "actor_id": rui_action.get("actor_id"),
            }

        def _mirror_diagnostic(rec, kind):
            """Pre-step mirror selection, for diagnostic only
            (Blocker 2: NOT used as the L2b verdict input)."""
            if kind == "resolve":
                return {"mirror_id": rec["pre_step"]["arbitration_cand_id"],
                        "mirror_source": "arbitration.candidate_id"}
            if kind == "inert":
                return {"mirror_id": rec["pre_step"]["chosen_id"],
                        "mirror_source": "choose() pre-step"}
            return {"mirror_id": None,
                    "mirror_source": "abstain (empty pool)"}

        off_landed = _actual_landed_identity(off_tstar)
        on_landed = _actual_landed_identity(on_tstar)
        off_mirror = _mirror_diagnostic(off_tstar, off_kind)
        on_mirror = _mirror_diagnostic(on_tstar, on_kind)
        seed_out["committed_at_tstar"] = {
            # ACTUAL landed identity (verdict input, Blocker 2)
            "control": off_landed, "treat": on_landed,
            # pre-step mirror (diagnostic only, NOT verdict input)
            "control_mirror": off_mirror, "treat_mirror": on_mirror,
        }
        l2b_v = judge_l2b(
            off_landed, on_landed, l1_v, t_star)
        seed_out["L2b"] = {"verdict": l2b_v}

        # L3 (D4: verify event + consequence CONTENT, not just id)
        off_events = off_tstar["result"]["events"]
        on_events = on_tstar["result"]["events"]
        l3_v = judge_l3(off_events, on_events, t_star, l2b_v)
        seed_out["L3"] = {"verdict": l3_v}

        # D5 (Blocker 3 fix): full 40-tick trajectories with ALL
        # registered per-candidate decision-time fields for EVERY
        # tick, not just T*. Each tick record carries:
        #   - per-candidate pre-step pool (utility, selection_score,
        #     hc_urgency, memory_urgency) — DECISION-TIME / pre-step
        #   - arbitration kind
        #   - ACTUAL landed rui committed action identity (post-step)
        #   - landed events + consequences (post-step)
        # All candidate records are explicitly labeled pre-step /
        # decision-time; commit + event records are post-step / landed.
        def _full_tick_record(r):
            return {
                "tick": r["tick"],
                # DECISION-TIME (pre-step) per-candidate records
                "pre_step_pool": r["pre_step"]["pool"],
                "pre_step_kind": r["pre_step"]["arbitration_kind"],
                "pre_step_chosen_id": r["pre_step"]["chosen_id"],
                "pre_step_chosen_type": r["pre_step"]["chosen_type"],
                "pre_step_mem_urgency": r["pre_step"]["mem_urgency"],
                # POST-STEP / LANDED actual committed identity
                "landed_rui_committed_id": r["rui_committed_id"],
                "landed_rui_committed_type": r["rui_committed_type"],
                # POST-STEP / LANDED events + consequence content
                "landed_events": r["result"]["events"],
            }
        seed_out["control_all_ticks"] = [
            _full_tick_record(r) for r in off]
        seed_out["treatment_all_ticks"] = [
            _full_tick_record(r) for r in on]

        # D5: T*-specific per-candidate records (subset of the above,
        # highlighted for verdict reference). The full per-tick data
        # is in control_all_ticks / treatment_all_ticks; this is a
        # convenience view at T*.
        seed_out["pre_step_full_at_tstar"] = {
            "control": off_cand,
            "treat": on_cand,
        }

        out["seeds"][str(seed)] = seed_out

    # Overall aggregation (R4): PASS n/5 at T*, >= 2/5 for overall
    # PASS. D4: L2a N/A, L2b INCONCLUSIVE, L3 OBSERVATIONAL /
    # FAIL-L2b-identical-event are NOT counted as PASS.
    overall = {}
    for layer in ("L1", "L2a", "L2b", "L3"):
        passes = 0
        determinable = 0
        for s in SEEDS:
            sd = out["seeds"][str(s)]
            v = sd.get(layer, {}).get("verdict", "INCONCLUSIVE")
            if v in ("PASS", "FAIL", "FAIL-by-mechanism",
                     "FAIL-L2b-identical-event"):
                determinable += 1
            if v == "PASS":
                passes += 1
        overall[layer] = {
            "pass_n": passes,
            "determinable_denominator": determinable,
            "total": len(SEEDS),
            "overall_pass": passes >= 2,
        }
    out["overall"] = overall

    # D2/R6: first-divergence scan, registered actor-level definition
    # (rui committed action id + landed events). Reproduces
    # {1:4, 3:6, 7:4, 42:6, 99:4} at the anchor.
    first_div = {}
    for s in SEEDS:
        off_s, on_s, *_ = per_seed_records[s]
        first_div[str(s)] = first_divergence_rui(off_s, on_s)
    out["first_divergence"] = first_div
    out["first_divergence_note"] = (
        "R6 supplementary metric, D2-corrected definition: first "
        "tick where ACTOR (rui) committed action ID or rui's landed "
        "event IDs differ between control and treatment. Cross-actor "
        "mixed commits are excluded. Anchor-verified expected values "
        "{1:4, 3:6, 7:4, 42:6, 99:4}. Verdicts are still made at "
        "T*; this field is supplementary only.")

    # Static audit (6 functions + step() branch + add_desire callers)
    root = str(Path(__file__).resolve().parent.parent)

    def _grep(pattern, paths, use_ere=False):
        base = ["grep", "-rn"]
        if use_ere:
            base.append("-E")
        cmd = base + [pattern] + list(paths)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                                cwd=root, timeout=30)
            hits = sorted(l for l in r.stdout.splitlines() if l.strip())
        except Exception as e:
            hits = [f"grep-error: {e}"]
        return {"cmd": " ".join(cmd), "hits": hits, "count": len(hits)}

    PROD = ["engine/", "scripts/"]
    static = {}
    # Six pure-read functions
    static["generate_action_pool"] = _grep(
        "def generate_action_pool", ["engine/core/actions.py"])
    static["build_appraisals"] = _grep(
        "def build_appraisals", ["engine/core/appraisal.py"])
    static["evaluate"] = _grep(
        "def evaluate", ["engine/core/decision.py"])
    static["arbitrate"] = _grep(
        "def arbitrate", ["engine/core/appraisal.py"])
    static["apply_arbitration"] = _grep(
        "def apply_arbitration", ["engine/core/appraisal.py"])
    static["choose_and_noise"] = _grep(
        "def choose|_choice_noise|Random\\(stable_seed\\)",
        ["engine/core/decision.py"], use_ere=True)
    # add_desire callers in production
    static["add_desire_callers_prod"] = _grep(
        "add_desire", PROD)
    # step() branch
    static["step_branch"] = _grep(
        "arbitration|kind\\s*==\\s*\"resolve\"|apply_arbitration|choose\\(",
        ["engine/core/simulation.py"], use_ere=True)
    out["static_audit"] = static
    out["static_audit_note"] = (
        "Six functions verified pure-read w.r.t. world state: "
        "generate_action_pool (actions.py:87), build_appraisals "
        "(appraisal.py:140), evaluate (decision.py:159), arbitrate "
        "(appraisal.py:166), apply_arbitration (appraisal.py:223), "
        "choose/_choice_noise (decision.py:214-220, local Random, "
        "NOT engine RNG). add_desire (engine/memory/models.py:128) "
        "has zero callers in engine/+scripts/ outside the 2B tool "
        "(expected; the tool's injection is the only call site). "
        "step() branch: simulation.py:91-107 RESOLVE commit "
        ":101-103, INERT/empty fallthrough :104-105.")

    # D3 (ChatGPT 6271192560 item 3): canonical block keys aligned with
    # the registered names from spec v4.1 R7:
    #   { "seeds", "flags", "static_audit", "verdicts",
    #     "attribution" }
    # `verdicts` = per-seed L1/L2a/L2b/L3 + overall (was `overall`).
    # `attribution` = per-seed T* + clean flags + first_divergence
    #   (was `first_divergence` at top level; now under `attribution`
    #    as registered). The canonical SHA is RECOMPUTED over the
    #    new block; it will differ from the v1 tool's 88660bf9...
    #    (which hashed a differently-named block). The v1 SHA is NOT
    #    reused.
    verdicts_block = {
        "per_seed": {
            str(s): {
                "L1": out["seeds"][str(s)].get("L1", {}).get(
                    "verdict"),
                "L2a": out["seeds"][str(s)].get("L2a", {}).get(
                    "verdict"),
                "L2b": out["seeds"][str(s)].get("L2b", {}).get(
                    "verdict"),
                "L3": out["seeds"][str(s)].get("L3", {}).get(
                    "verdict"),
                "t_star": out["seeds"][str(s)].get("t_star"),
            }
            for s in SEEDS
        },
        "overall": out["overall"],
    }
    attribution_block = {
        "t_star_per_seed": {
            str(s): out["seeds"][str(s)].get("t_star")
            for s in SEEDS
        },
        "clean_flags_per_seed": {
            str(s): out["seeds"][str(s)].get("clean_flags", {})
            for s in SEEDS
        },
        "first_divergence": out["first_divergence"],
    }
    canonical_block = {
        "seeds": out["seeds"],
        "flags": out["flags"],
        "static_audit": out["static_audit"],
        "verdicts": verdicts_block,
        "attribution": attribution_block,
    }
    canon_bytes = json.dumps(
        canonical_block, sort_keys=True,
        separators=(",", ":"), default=str).encode("utf-8")
    out["canonical_sha256"] = hashlib.sha256(canon_bytes).hexdigest()
    out["canonical_sha256_note"] = (
        "SHA256 of env-INDEPENDENT canonical block "
        "(seeds+flags+static_audit+verdicts+attribution, keys "
        "sorted, compact separators). D3 (ChatGPT 6271192560 item "
        "3): block keys aligned with registered R7 names "
        "(verdicts, attribution); meta (python_version, "
        "anchor_check, note fields) stays OUT. The v1 tool's "
        "canonical_sha256 (88660bf9...) hashed a differently-named "
        "block and is NOT reused; this is a recomputed new value.")

    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
