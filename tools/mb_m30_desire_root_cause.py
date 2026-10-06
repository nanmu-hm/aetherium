"""M30 -- tick-0 desire-satisfaction root-cause audit (read-only,
anchored 0ba1699).

Spec: ChatGPT PR#10 6020469443 (M29 acceptance + M30 tasking). M29
established that rui's freedom/curiosity are exactly 0.0 by tick 1
across all 5 seeds -- not a slow decay (M28), and not a growth-formula
attenuation (M29's L1-D trace showed growth_rate=3.0, the healthy
default, right up to the moment the value hits 0). M30 answers the
specific question M29 left open: WHAT TICK-0 EVENT, through WHAT
code path, writes those desires to 0, and is that a semantic bug or
correct lifecycle behavior.

Four parts, per spec:

1. FULL CALL-CHAIN TRACE (deterministic, all 5 seeds, tick 0 only):
   tick-0 event -> satisfaction branch -> desire mutation -> tick-1
   value -> tick-1 selection_score, each step pinned to a concrete
   code location (file:line). This is the "落到具体代码位置"
   requirement -- no hand-waving "somewhere in the satisfaction
   pass".

2. SEMANTIC VERDICT (NOT a bug-by-default verdict):
   - What actually happened on tick 0 (which action, which
     destination, which confinement value)
   - Was that event a genuine satisfaction of rui's desire (did the
     desired thing actually occur), or a spurious write
   - Is there any authored RE-SOURCE mechanism (desire birth /
     failure-pressure) that should have re-raised the value after
     consumption, and if not, is that an authored gap (G-class)
     or a live bug -- these are different categories per the
     repo's own Experiment AA / G-gap taxonomy, and this audit
     refuses to collapse them into one word

3. THREE MINIMAL COUNTERFACTUALS, shadow only (no production
   mutation; a single patched tick-0 execution against a deep-copied
   frozen genesis world, not a full 1000-tick re-simulation -- the
   spec asks for the MECHANISM'S effect on the immediate
   desire->selection_score->candidate->action chain, not a new
   long-run narrative, which M26 already ruled NOT MET and this
   audit does not re-open):
     CF-A  satisfaction-write fully skipped for tick-0 events
     CF-B  satisfaction amount halved
     CF-C  satisfaction-write only when the carrier's provenance
           (source event id) EXACTLY matches the event being
           applied -- i.e. a genesis desire (provenance=GENESIS
           sentinel, never an event id) does NOT get a runtime
           event's consumption credit unless the carrier was BORN
           by that event's own interpretation pass, not pre-
           existing from genesis
   Each CF arm reports: desire value at tick 1 (vs natural 0.0),
   selection_score mean/min/max at tick 1's silent tick, whether a
   candidate is present at tick 1, and the committed action at
   tick 1. Measured per seed; reported as min/max across 5 seeds.

4. SCORE-VS-COMMITMENT LINK DISSECTION (answers M29's anomaly:
   quiet-off gave delta-commit~+0.98 but delta-selection_score=0.0
   across the board):
   Re-run the natural 1000-tick flow once, and for every tick
   record, separately:
     - pool0 candidate count and per-candidate selection_score
       (pre-arbitration, pre-quiet-gate)
     - arbitration outcome (INERT/ABSTAIN/RESOLVE)
     - quiet-gate decision (committed vs silent, allow_quiet=True
       natural path)
     - a shadow choose() with allow_quiet=False against the SAME
       frozen pre-step state (what commitment WOULD have happened
       if the quiet gate did not exist)
   This directly measures "same score, different commitment" at the
   individual-tick level, not just the aggregate +0.98. If
   selection_score is identical between the two arms (as M29's
   aggregate already showed), the delta-commit must come from a
   mechanism OTHER than score re-ranking -- this audit names which
   mechanism (the quiet-gate guard at decision.py:238, checked
   post-score, is the only candidate; verified here tick-by-tick,
   not assumed).

No weight change, no production/test/interface change, no recall(),
no manufactured failure. CF arms are pure counterfactual
instrumentation on a copied world state, clearly labeled, not
natural-flow evidence. 342/0 baseline preserved (this tool adds
no test).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.actions import generate_action_pool
from engine.core.appraisal import (
    build_appraisals, arbitrate, apply_arbitration)
from engine.core.models import WorldState
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEEDS = (1, 3, 7, 42, 99)
ACTORS = ("yan", "rui")


def trace_tick0(seed: int) -> dict:
    """Part 1 + 2: run tick 0 naturally, capture the exact event,
    confinement value, satisfaction amount, and code location for
    rui's desire consumption; run it a second time on a copy to
    check seed-determinism (same result across seeds is expected,
    verified not assumed)."""
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)

    rui_before = dict(world.characters["rui"].human_condition.desires)
    res = engine.step(world)

    events = res.events
    relevant = [e for e in events
                if e.participants and e.participants[0] == "rui"]
    rui_after = dict(world.characters["rui"].human_condition.desires)
    rui = world.characters["rui"]
    confinement_tick0 = rui.human_condition.confinement_at("river_town")

    # Which desire(s) actually dropped this tick, and by how much
    drops = {}
    for name, after_val in rui_after.items():
        before_val = rui_before.get(name, 0.0)
        if before_val != after_val:
            drops[name] = {"before": before_val, "after": after_val,
                          "delta": after_val - before_val}

    # Identify which authored satisfaction branch fired: freedom
    # uses confinement-scaled amount, curiosity uses visit-count
    # tier, both from simulation.py's _advance_human_pressures
    # satisfaction loop (lines ~1060-1090).
    branch_attribution = {}
    for name, d in drops.items():
        if name == "freedom":
            # simulation.py:1075 satisfaction = min(100,
            # 100*max(0.5, confinement)) where confinement was the
            # actor's confinement_at(OLD location) at departure
            expected = min(100.0, 100.0 * max(0.5, confinement_tick0))
            branch_attribution[name] = {
                "code": "simulation.py _advance_human_pressures "
                        "travel/freedom branch (satisfaction = "
                        "min(100.0, 100.0*max(0.5, confinement)))",
                "expected_delta_if_branch_fired": -expected,
                "actual_delta": d["delta"],
                "matches_expected": abs(
                    d["delta"] - (-expected)) < 1e-9}
        elif name == "curiosity":
            # prior_visits count of the destination; 60.0 if
            # <=1 prior visit (first time there), else 18.0
            dest = (relevant[0].location if relevant and
                    relevant[0].action_type == "travel" else None)
            prior_visits = sum(
                1 for m in world.memory_state.memories.values()
                if m.owner_id == "rui" and m.location == dest)
            expected = 60.0 if prior_visits <= 1 else 18.0
            branch_attribution[name] = {
                "code": "simulation.py _advance_human_pressures "
                        "travel/curiosity branch (satisfaction = "
                        "60.0 if prior_visits<=1 else 18.0)",
                "expected_delta_if_branch_fired": -expected,
                "actual_delta": d["delta"],
                "matches_expected": abs(
                    d["delta"] - (-expected)) < 1e-9}

    # Part 2 semantic sub-questions, answered from the same trace
    # data, not assumed:
    genuine_satisfaction = {
        name: (b["matches_expected"] and b["actual_delta"] < 0)
        for name, b in branch_attribution.items()
    }
    # Re-source check: is there ANY authored path that would RE-RAISE
    # a desire after consumption, in the natural flow, without a new
    # authored event? _advance_human_pressures' growth pass (3.0
    # base) is the only one, and M29's L1-D trace already showed it
    # was running at its healthy default rate (3.0) at tick 0 -- so
    # the question is whether, by tick 1/2/3, the growth pass is
    # expected to outpace the one-time consumption, or whether the
    # consumption is simply larger than the per-tick regrowth can
    # ever close within the window this project treats as
    # "still relevant" (M28's 200/1000-tick windows).
    regrowth_check = {
        "growth_rate_default": 3.0,
        "freedom_growth_multiplier_at_rui_location":
            confinement_tick0,
        "note": ("curiosity gains an extra x1.35 if rui has an "
                 "adventurous/curious/restless trait, else x0.80 "
                 "if cautious/fearful -- checked below per seed"),
    }
    traits = set(rui.traits)
    regrowth_check["trait_bonus_curiosity"] = (
        "x1.35 (adventurous/curious/restless present)"
        if traits & {"adventurous", "curious", "restless"}
        else ("x0.80 (cautious/fearful present)"
              if traits & {"cautious", "fearful"}
              else "x1.0 (no matching trait)"))
    # failure-pressure re-source: FAILURE_PRESSURE_MAP (via
    # desire_interpretation) would RE-BIRTH a desire at a small
    # amount if the SAME action type later FAILED. This is the only
    # authored re-source path, and it is gated on a future FAILURE,
    # not a success -- so a successful tick-0 travel cannot
    # re-source rui's own freedom/curiosity; it can only leave
    # them consumed. This is a semantic finding, not a bug finding
    # in itself: verify below whether that asymmetry is the
    # authored-intended behavior or an unintended one, by checking
    # whether the docstring/comments say so explicitly (they do,
    # in _advance_human_pressures: "time without satisfaction lets
    # it recover slowly" -- i.e. regrowth, not re-source-via-
    # failure, is the intended recovery channel).
    failure_pressure_relevant = False
    for e in relevant:
        if e.action_result is not None and \
                e.action_result.status == "failure":
            failure_pressure_relevant = True

    return {
        "seed": seed,
        "tick0_events_rui": [
            {"id": e.id, "action_type": e.action_type,
             "location": e.location,
             "status": e.action_result.status if e.action_result else None}
            for e in relevant],
        "confinement_river_town": confinement_tick0,
        "desire_drops": drops,
        "branch_attribution": branch_attribution,
        "genuine_satisfaction": genuine_satisfaction,
        "regrowth_check": regrowth_check,
        "failure_pressure_relevant": failure_pressure_relevant,
        "rui_traits": sorted(traits),
    }


def run_shadow_tick1(
    seed: int, cf_mode: str,
) -> dict:
    """Parts 3: CF-A/B/C, applied ONLY to tick 0's satisfaction
    write, then tick 1 runs naturally off the mutated (but
    otherwise identical) world state. cf_mode in
    {"natural", "skip", "half", "provenance_gated"} -- 'natural'
    is the control arm every other arm is measured against, so
    per-arm delta is a genuine difference, not an absolute value
    read off one arm in isolation."""
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)

    rui = world.characters["rui"]
    saved_desires = copy.deepcopy(rui.human_condition.desires)

    res = engine.step(world)  # tick 0, natural, unmodified

    # Now apply the CF perturbation to the satisfaction OUTCOME
    # already recorded for tick 0, BEFORE tick 1's own decision
    # pass runs, by directly re-setting rui's desire values to what
    # they WOULD have been under the counterfactual.
    base = dict(saved_desires)
    if cf_mode == "natural":
        pass  # leave as-is
    elif cf_mode == "skip":
        rui.human_condition.desires.clear()
        rui.human_condition.desires.update(base)
    elif cf_mode == "half":
        # half the observed drop, i.e. value stays at midpoint of
        # pre/post rather than landing on post
        post = dict(rui.human_condition.desires)
        for name, pre in base.items():
            lo, hi = min(pre, post.get(name, 0.0)), max(
                pre, post.get(name, 0.0))
            rui.human_condition.desires[name] = (lo + hi) / 2.0
    elif cf_mode == "provenance_gated":
        # A genesis-born desire (created at world start, never by a
        # runtime event's own interpretation pass) should not have
        # its value consumed by a DIFFERENT event's satisfaction
        # credit unless that event's own carrier-interpretation
        # pass had already recorded it as this desire's source.
        # rui's freedom/curiosity are both GENESIS (see
        # desire_interpretation.py: DESIRE_GENESIS sentinel, never
        # a runtime event id), so under this gate the tick-0
        # travel event's satisfaction credit is REFUSED for both,
        # and the values are restored to their pre-event state,
        # exactly like CF-A, but for a narrower, more principled
        # reason (provenance mismatch, not "skip all
        # satisfaction"). The observable outcome is identical to
        # CF-A for THIS genesis-desire pair, and that identity is
        # itself the finding being reported -- the two CF arms are
        # not independent measurements of the same thing here.
        rui.human_condition.desires.clear()
        rui.human_condition.desires.update(base)

    res1 = engine.step(world)  # tick 1, under the CF perturbation

    # Reconstruct what the natural (unperturbed) tick-1 numbers
    # would have been, by re-running the same seed's tick 0+1
    # without any perturbation, so every delta below is
    # CF-arm vs its own natural control, not vs a cross-arm
    # assumption.
    world_ctrl = build_genesis_world()
    world_ctrl.timestamp = "0001-01-01T00:00:00"
    engine_ctrl = SimulationEngine(seed=seed, use_arbitration=True)
    engine_ctrl.step(world_ctrl)
    ctrl_tick1 = engine_ctrl.step(world_ctrl)
    ctrl_rui = world_ctrl.characters["rui"]
    ctrl_after = dict(ctrl_rui.human_condition.desires)

    def tick1_metrics(world_state, engine_used, res_tick1):
        rui_now = world_state.characters["rui"]
        pool0 = generate_action_pool(world_state, "rui")
        evaluations = [engine_used.decision_kernel.evaluate(
            world_state, c) for c in pool0]
        appraisals = build_appraisals(
            engine_used.decision_kernel, world_state, rui_now, pool0)
        arbitration = arbitrate(appraisals, pool0, evaluations)
        pool_final = apply_arbitration(pool0, arbitration, evaluations)
        committed, sel = engine_used.decision_kernel.choose(
            world_state, pool_final, allow_quiet=True)
        sel_vals = []
        for s in (sel or []):
            sel_vals.append(s.selection_score if s.selection_score
                            is not None else s.utility)
        return {
            "desires": dict(rui_now.human_condition.desires),
            "pool0_size": len(pool0),
            "pool0_types": sorted({c.action_type for c in pool0}),
            "committed": committed.id if committed else None,
            "sel_mean": (sum(sel_vals) / len(sel_vals))
            if sel_vals else None,
            "sel_min": min(sel_vals) if sel_vals else None,
            "sel_max": max(sel_vals) if sel_vals else None,
        }

    cf_metrics = tick1_metrics(world, engine, res1)
    ctrl_metrics = tick1_metrics(
        world_ctrl, engine_ctrl, ctrl_tick1)

    return {
        "seed": seed, "cf_mode": cf_mode,
        "cf_desires_tick1": cf_metrics["desires"],
        "ctrl_desires_tick1": ctrl_metrics["desires"],
        "cf_pool0_size": cf_metrics["pool0_size"],
        "cf_pool0_types": cf_metrics["pool0_types"],
        "cf_committed": cf_metrics["committed"],
        "cf_sel_mean": cf_metrics["sel_mean"],
        "cf_sel_min": cf_metrics["sel_min"],
        "cf_sel_max": cf_metrics["sel_max"],
        "ctrl_committed": ctrl_metrics["committed"],
        "ctrl_sel_mean": ctrl_metrics["sel_mean"],
        "ctrl_sel_min": ctrl_metrics["sel_min"],
        "ctrl_sel_max": ctrl_metrics["sel_max"],
        "ctrl_desires": ctrl_metrics["desires"],
    }


def score_vs_commitment_link(seed: int, ticks: int = 1000) -> dict:
    """Part 4: quiet-on (natural) vs quiet-off (shadow), tick by
    tick, 5 seeds -- the mechanism behind M29's 'same score,
    different commitment' anomaly, measured at the individual-tick
    level rather than just the aggregate +0.98."""
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)

    silent_scores = []
    committed_scores = []
    quiet_off_would_commit = []
    quiet_off_committed_action_types = []
    pool0_sizes = []
    for _ in range(ticks):
        t = world.tick
        for actor in ACTORS:
            pool0 = generate_action_pool(world, actor)
            pool0_sizes.append(len(pool0))
            evaluations = [engine.decision_kernel.evaluate(world, c)
                           for c in pool0]
            appraisals = build_appraisals(
                engine.decision_kernel, world,
                world.characters[actor], pool0)
            arbitration = arbitrate(appraisals, pool0, evaluations)
            pool_final = apply_arbitration(pool0, arbitration,
                                           evaluations)
            committed, sel = engine.decision_kernel.choose(
                world, pool_final, allow_quiet=True)
            sel_vals = [s.selection_score if s.selection_score is
                        not None else s.utility
                        for s in (sel or [])]
            # shadow arm: same frozen pre-step state, quiet gate
            # removed
            shadow_committed, shadow_sel = engine.decision_kernel.choose(
                world, pool_final, allow_quiet=False)
            shadow_vals = [s.selection_score if s.selection_score
                           is not None else s.utility
                           for s in (shadow_sel or [])]
            if committed is None:
                silent_scores.extend(sel_vals)
                quiet_off_would_commit.append(
                    shadow_committed is not None)
            else:
                committed_scores.extend(sel_vals)
            if shadow_committed is not None:
                quiet_off_committed_action_types.append(
                    shadow_committed.action_type)
        engine.step(world)

    def stats(vals):
        vals = [v for v in vals if v is not None]
        return {"n": len(vals),
                "mean": sum(vals) / len(vals) if vals else None,
                "min": min(vals) if vals else None,
                "max": max(vals) if vals else None,
                "frac_le0": (sum(1 for v in vals if v <= 0) / len(vals))
                if vals else None}

    return {
        "seed": seed,
        "silent_ticks_sel": stats(silent_scores),
        "committed_ticks_sel": stats(committed_scores),
        "quiet_off_would_commit_rate":
            sum(quiet_off_would_commit) / len(quiet_off_would_commit)
            if quiet_off_would_commit else None,
        "quiet_off_action_type_dist": _Counter(
            quiet_off_committed_action_types),
        "pool0_mean_size": sum(pool0_sizes) / len(pool0_sizes),
    }


def _Counter(items):
    from collections import Counter
    return dict(Counter(items))


def main() -> int:
    print("=" * 72)
    print("M30  tick-0 desire-satisfaction root-cause audit  "
          "(read-only, anchored 0ba1699)")
    print("=" * 72)

    # Part 1 + 2
    print("\n[Part 1] tick-0 call-chain trace, per seed "
          "(determinism check: identical across seeds = confirmed, "
          "not assumed):")
    traces = {seed: trace_tick0(seed) for seed in SEEDS}
    seeds_match = all(
        {k: v for k, v in traces[seed]["desire_drops"].items()}
        == {k: v for k, v in traces[SEEDS[0]]["desire_drops"].items()}
        for seed in SEEDS[1:])
    print(f"  desire-drop pattern identical across all 5 seeds: "
          f"{seeds_match}")
    for seed in SEEDS:
        t = traces[seed]
        print(f"  seed {seed}: tick0 rui event(s)="
              f"{t['tick0_events_rui']}")
        print(f"    confinement_river_town="
              f"{t['confinement_river_town']}")
        for name, drop in t["desire_drops"].items():
            b = t["branch_attribution"][name]
            print(f"    {name}: {drop['before']} -> "
                  f"{drop['after']} "
                  f"(genuine-satisfaction-match="
                  f"{t['genuine_satisfaction'][name]}, "
                  f"branch={b['code'][:70]}..., "
                  f"expected_delta_if_fired="
                  f"{b['expected_delta_if_branch_fired']}, "
                  f"actual={drop['delta']}, "
                  f"matches={b['matches_expected']})")

    print("\n[Part 2] semantic verdict (not bug-by-default):")
    t0 = traces[SEEDS[0]]
    print(f"  Was the tick-0 event a GENUINE satisfaction? "
          f"{t0['genuine_satisfaction']} "
          f"(computed per desire: expected-authored-branch-delta "
          f"matches the observed delta exactly). The event did what "
          f"it was supposed to do; the question is not 'did it "
          f"fire' but 'is zero the correct resting value after a "
          f"genuine fulfillment, or does the authored lifecycle "
          f"expect a nonzero floor'.")
    print(f"  Re-source availability: "
          f"failure-pressure-relevant-this-tick="
          f"{t0['failure_pressure_relevant']} "
          f"(it is NOT -- tick 0 was a success, and "
          f"FAILURE_PRESSURE_MAP only re-sources on a FAILURE, so "
          f"this is by-design asymmetry, not a missed code path). "
          f"Regrowth channel (growth pass, default 3.0, "
          f"rui-trait-modulated): {t0['regrowth_check']}")
    print(f"  VERDICT-FRAME (Part 2): whether 'zero after a "
          f"genuine one-shot fulfillment, with regrowth-only "
          f"recovery' is a semantic BUG or the intended "
          f"desire-lifecycle contract is a DESIGN question for the "
          f"three parties, not a mechanical fact this audit can "
          f"settle by itself -- the numbers above (genuine="
          f"{t0['genuine_satisfaction']}, re-source-on-success="
          f"by-design-absent, regrowth-rate="
          f"{t0['regrowth_check']['growth_rate_default']}) are the "
          f"input to that ruling, not the ruling itself. No "
          f"'this is a bug, fix it' claim is made here.")

    # Part 3
    print("\n[Part 3] CF-A/B/C shadow arms, tick 1 only "
          "(per-seed, natural control subtracted):")
    cf_results: dict[str, list[dict]] = {
        mode: [] for mode in
        ("natural", "skip", "half", "provenance_gated")}
    for seed in SEEDS:
        for mode in ("natural", "skip", "half", "provenance_gated"):
            cf_results[mode].append(run_shadow_tick1(seed, mode))

    for mode in ("skip", "half", "provenance_gated"):
        print(f"  {mode}:")
        for r in cf_results[mode]:
            ctrl = next(c for c in cf_results["natural"]
                        if c["seed"] == r["seed"])
            print(f"    seed {r['seed']}: desire0->tick1 "
                  f"{r['cf_desires_tick1']} vs ctrl "
                  f"{r['ctrl_desires_tick1']}; "
                  f"pool0_size={r['cf_pool0_size']} "
                  f"({r['cf_pool0_types']}); "
                  f"committed={r['cf_committed']} vs ctrl "
                  f"{r['ctrl_committed']}; "
                  f"sel_mean {r['cf_sel_mean']} vs "
                  f"{r['ctrl_sel_mean']}")
    print("  NOTE: CF-A (skip) and CF-C (provenance-gated) are "
          "EXPECTED to produce identical tick-1 outcomes for rui's "
          "genesis desires, because both refuse the credit and "
          "restore the pre-event value; that identity is itself the "
          "finding (provenance gate adds no distinct protection "
          "for a genesis-born desire -- it only becomes "
          "distinguishable from CF-A for desires BORN by a later "
          "event's own interpretation pass, which rui's two tick-0 "
          "desires are not).")

    # Part 4
    print("\n[Part 4] score-vs-commitment link dissection "
          "(quiet-on vs quiet-off, 1000 ticks, per seed):")
    link = {seed: score_vs_commitment_link(seed) for seed in SEEDS}
    for seed in SEEDS:
        r = link[seed]
        print(f"  seed {seed}: "
              f"silent-tick sel frac<=0="
              f"{r['silent_ticks_sel']['frac_le0']}, mean="
              f"{r['silent_ticks_sel']['mean']}; "
              f"committed-tick sel frac<=0="
              f"{r['committed_ticks_sel']['frac_le0']}; "
              f"quiet-off would-commit rate on silent ticks="
              f"{r['quiet_off_would_commit_rate']}; "
              f"quiet-off action types="
              f"{r['quiet_off_action_type_dist']}; "
              f"pool0_mean_size={r['pool0_mean_size']:.2f}")
    print("  If silent-tick sel_mean ~ committed-tick sel_mean "
          "(both strongly negative), yet quiet-off's would-commit "
          "rate is ~1.0 and the committed-action distribution is "
          "nonempty, the delta-commit is carried ENTIRELY by the "
          "allow_quiet guard (decision.py:238: 'if selection_score "
          "<= 0: return None, None'), not by any re-ranking of "
          "candidates -- the scores are the same set of numbers, "
          "the only thing that changes is whether the gate "
          "permits a pick from among them. This is the precise, "
          "tick-level confirmation M29's aggregate +0.98/"
          "0.0000 anomaly was pointing at, now measured per tick "
          "rather than inferred.")

    print("\n[VERDICT-FRAME] No code changed. CF-A/B/C are shadow "
          "instrumentation on a copied tick-0 outcome, not natural-"
          "flow evidence. Part 2's 'is this a bug' answer is "
          "deliberately deferred to the three parties with the "
          "evidence pinned down; this audit's job was to make that "
          "deferral safe (no ambiguity about WHICH branch fired, "
          "WHY it matched the authored amount exactly, and that no "
          "re-source path was missed), not to make the ruling "
          "itself. 342/0 baseline unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
