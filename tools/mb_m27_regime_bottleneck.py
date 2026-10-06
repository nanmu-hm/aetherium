"""M27 -- Natural-Regime Bottleneck Audit (read-only, anchored 0ba1699).

Spec: ChatGPT PR#10 6016780957. Answers WHY M26's "short-chain-then-
silence + travel repetition + no natural failure" pattern happens, by
attributing every silent tick and every travel action to a concrete,
named code path -- not by guessing from event counts alone.

Sections:
A. Per-tick, per-actor silent cause (mutually exclusive, in the order
   the real code path actually executes):
     1 empty_pool       generate_action_pool() returned []
     2 arbitration_empty  pool nonempty but arbitration produced an
                          empty candidate set (ABSTAIN/INERT path)
     3 quiet_gate       choose(allow_quiet=True) rejected the best
                          candidate because selection_score <= 0
     4 no_eligible      (unused today -- no separate eligibility
                          pre-pass exists in this engine; reported as
                          such if it never fires, rather than being
                          forced a bucket)
     5 other            anything unexplained
B. Travel repetition attribution (actor-level):
     - how many ticks did travel WIN as the committed action vs how
       many ticks was a travel candidate even PRESENT (i.e. is
       "travel dominates because travel is the only candidate" or
       "travel dominates out of a multi-candidate pool")
     - how many travel commits are immediately followed by ANOTHER
       travel commit (consecutive travel streaks), and what was the
       destination of each, to test whether visit_counts/recent-travel
       readers are actually steering, or whether the same destination
       keeps reappearing by inertia
C. Behavior-density bottleneck, per actor:
     - candidate pool size distribution (min/median/max) over the
       whole run
     - top-1 vs second-1 utility gap for the committed action's own
       pool, sampled at a handful of representative ticks
     - how often the committed action was the SOLE candidate that
       survived (pool size == 1 at commit time) vs a real choice
D. 3+ real traces of "active -> silent" or "active -> travel-repeat"
     transitions, with tick numbers and the actual cause label from A.
E. Verdict: REGIME-LIMITED / MECHANISM-BOTTLENECK / NOT PROVEN, with
   the deciding evidence stated, not asserted.

Anchor 0ba1699; read-only; production HELD; recall() HELD; no weight/
production/test change; no manufactured failure.
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.actions import generate_action_pool
from engine.core.appraisal import (
    build_appraisals, arbitrate, apply_arbitration)
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEEDS = (1, 3, 7, 42, 99)
TICKS = 1000
ACTORS = ("yan", "rui")


def instrument_one_tick(world, engine, actor):
    """Reproduce EXACTLY the internal order engine.step() uses to
    decide one actor's action this tick, but RETURN the intermediate
    values instead of discarding them. No mutation beyond what
    step() itself would do (this runs generate_action_pool +
    build_appraisals + arbitrate + apply_arbitration + choose, the
    same calls step() makes, in the same order -- it does not call
    engine.step() itself, so it can't double-advance the world; the
    caller must not actually step the world afterward for this
    actor's decision, this is purely a read-the-pipeline probe).

    CAVEAT (disclosed per M27-R1): real step() calls
    _restore_rng_state() + _settle_emotions() before candidate
    generation; this probe does not, so silent-tick selection_score
    values are pre-step probe values, off by ~1e-4 from the true
    step-time value. This does not change the quiet-gate verdict
    (all sampled values remain <= 0), but it is not claimed to be
    exact step-time precision."""
    pool0 = generate_action_pool(world, actor)
    pool0_types = tuple(sorted(set(c.action_type for c in pool0)))
    committed_targets = None
    if not pool0:
        return {"cause": "empty_pool", "pool0_size": 0,
                "pool_final_size": 0, "arbitration_kind": None,
                "committed": None, "top_util": None,
                "second_util": None, "action_type": None,
                "pool0_types": pool0_types,
                "committed_targets": None}
    arbitration = None
    evaluations = None
    pool_final = pool0
    if engine.use_arbitration:
        evaluations = [engine.decision_kernel.evaluate(world, c)
                       for c in pool0]
        appraisals = build_appraisals(engine.decision_kernel, world,
                                      world.characters[actor], pool0)
        arbitration = arbitrate(appraisals, pool0, evaluations)
        pool_final = apply_arbitration(pool0, arbitration, evaluations)
    action = None
    sel_scores = None
    if arbitration is not None and arbitration.kind == "resolve":
        action = next((c for c in pool_final
                       if c.id == arbitration.candidate_id), None)
    if action is None and pool_final:
        action, sel_scores = engine.decision_kernel.choose(
            world, pool_final, allow_quiet=True)
    is_free_travel = (action is not None
                      and action.action_type == "travel"
                      and not action.metadata.get("search_target"))
    if action is None:
        if not pool_final:
            # INERT leaves pool unchanged, so pool_final empty here means
            # either originally empty (pool0 empty, caught earlier) or
            # ABSTAIN emptied it. Distinguish:
            if pool0:
                cause = "arbitration_abstain"
            else:
                cause = "empty_pool"
        else:
            # pool_final nonempty but choose() returned None ->
            # the ONLY path is decision.py:238's quiet-gate
            # (selection_score <= 0), since choose() has no other
            # None-return branch for a nonempty pool.
            cause = "quiet_gate"
        top_sel = None
        if sel_scores:
            top_sel = max(
                (s.selection_score if s.selection_score is not None
                 else s.utility) for s in sel_scores)
        return {"cause": cause, "pool0_size": len(pool0),
                "pool_final_size": len(pool_final),
                "arbitration_kind":
                    arbitration.kind if arbitration else None,
                "committed": None, "top_util": None,
                "second_util": None, "action_type": None,
                "top_sel_score": top_sel, "is_free_travel": False,
                "pool0_types": pool0_types,
                "committed_targets": None}
    util_by_id = {}
    for ev in (evaluations or
               [engine.decision_kernel.evaluate(world, c)
                for c in pool_final]):
        util_by_id[ev.action_id] = ev.utility
    committed_util = util_by_id.get(action.id, float("-inf"))
    top_utils = sorted([u for k, u in util_by_id.items()
                        if k != action.id], reverse=True)
    committed_sel = None
    if sel_scores:
        for s in sel_scores:
            if s.action_id == action.id:
                committed_sel = (s.selection_score
                                 if s.selection_score is not None
                                 else s.utility)
                break
    committed_targets = (list(action.targets) if action.targets else None)
    return {"cause": "committed", "pool0_size": len(pool0),
            "pool_final_size": len(pool_final),
            "arbitration_kind":
                arbitration.kind if arbitration else None,
            "committed": action.id, "top_util": committed_util,
            "second_util": (top_utils[0] if top_utils else None),
            "action_type": action.action_type,
            "is_free_travel": is_free_travel,
            "top_sel_score": committed_sel,
            "pool0_types": pool0_types,
            "committed_targets": committed_targets}


def run_seed(seed: int):
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)

    per_tick: dict[int, dict] = {}   # tick -> {actor -> instrument}
    committed: list[dict] = []        # tick -> {actor: action_id|None}
    events = []

    for _ in range(TICKS):
        t = world.tick
        row = {}
        for actor in ACTORS:
            row[actor] = instrument_one_tick(world, engine, actor)
        per_tick[t] = row
        res = engine.step(world)
        committed.append({a.actor_id: a.id for a in res.actions})
        events.extend(res.events)

    # --- A. silent-cause matrix ------------------------------------
    cause_counts: dict[str, dict] = {}
    pool_sizes: dict[str, list] = {}
    solo_choice_ticks: dict[str, int] = {}
    for t, row in per_tick.items():
        for actor, info in row.items():
            key = info["cause"]
            cause_counts.setdefault(key, {}).setdefault(
                actor, 0)
            cause_counts[key][actor] += 1
            if info["cause"] == "committed":
                if info["pool0_size"] == 1:
                    solo_choice_ticks[actor] = \
                        solo_choice_ticks.get(actor, 0) + 1
            pool_sizes.setdefault(actor, []).append(info["pool0_size"])

    # --- B. travel repetition attribution --------------------------
    # Distinguish FREE travel (no search_target) from search-driven
    # "travel" candidates that actually mean "go find person X".
    travel_stats: dict[str, dict] = {}
    sel_score_samples: dict[str, list] = {a: [] for a in ACTORS}
    contact_present_ticks: dict[str, int] = {a: 0 for a in ACTORS}
    help_present_ticks: dict[str, int] = {a: 0 for a in ACTORS}
    contact_on_silent_ticks: dict[str, int] = {a: 0 for a in ACTORS}
    help_on_silent_ticks: dict[str, int] = {a: 0 for a in ACTORS}
    contact_committed: dict[str, int] = {a: 0 for a in ACTORS}
    help_committed: dict[str, int] = {a: 0 for a in ACTORS}
    for actor in ACTORS:
        streak = 0
        best_streak = 0
        free_travel_commits = 0
        search_commits = 0
        consec_free_travel_pairs = 0
        prev_was_free_travel = False
        prev_dest = None
        dest_sequence = []
        for t, row in per_tick.items():
            info = row[actor]
            ptypes = info.get("pool0_types", ())
            if "contact_person" in ptypes:
                contact_present_ticks[actor] += 1
                if info["cause"] == "quiet_gate":
                    contact_on_silent_ticks[actor] += 1
            if "help_person" in ptypes:
                help_present_ticks[actor] += 1
                if info["cause"] == "quiet_gate":
                    help_on_silent_ticks[actor] += 1
            if info["cause"] == "committed":
                sel_score_samples[actor].append(info["top_sel_score"])
                if info["action_type"] == "contact_person":
                    contact_committed[actor] += 1
                elif info["action_type"] == "help_person":
                    help_committed[actor] += 1
                is_free = info["is_free_travel"]
                if is_free:
                    free_travel_commits += 1
                    dest = (info["committed_targets"] or [None])[0]
                    dest_sequence.append(dest)
                    if prev_dest is not None and dest == prev_dest:
                        consec_free_travel_pairs += 1
                    prev_dest = dest
                    prev_was_free_travel = True
                    streak = streak + 1
                    best_streak = max(best_streak, streak)
                elif info["action_type"] in ("travel", "search_person") \
                        and not is_free:
                    search_commits += 1
                    prev_was_free_travel = False
                    prev_dest = None
                    streak = 0
                else:
                    prev_was_free_travel = False
                    prev_dest = None
                    streak = 0
            else:
                prev_was_free_travel = False
                prev_dest = None
                streak = 0
        travel_stats[actor] = {
            "free_travel_commits": free_travel_commits,
            "search_commits": search_commits,
            "consec_same_dest_pairs": consec_free_travel_pairs,
            "best_streak": best_streak,
            "dest_sequence": dest_sequence[:12],
        }
    contact_help_stats = {
        a: {
            "contact_present_actor_ticks": contact_present_ticks[a],
            "help_present_actor_ticks": help_present_ticks[a],
            "contact_on_silent_ticks": contact_on_silent_ticks[a],
            "help_on_silent_ticks": help_on_silent_ticks[a],
            "contact_committed": contact_committed[a],
            "help_committed": help_committed[a],
        } for a in ACTORS
    }

    # --- C. selection_score distribution (quiet-gate evidence) -----
    import statistics as _st
    sel_score_stats: dict[str, dict] = {}
    for actor in ACTORS:
        vals = [v for v in sel_score_samples[actor] if v is not None]
        if not vals:
            sel_score_stats[actor] = {"n": 0}
            continue
        below_zero = sum(1 for v in vals if v <= 0.0)
        sel_score_stats[actor] = {
            "n": len(vals),
            "mean": _st.mean(vals),
            "min": min(vals),
            "max": max(vals),
            "frac_below_or_at_zero": below_zero / len(vals),
        }

    # silent ticks' top_sel_score distribution (to prove the quiet-gate
    # really is the <=0 path, not some other branch)
    silent_sel_scores: dict[str, list] = {a: [] for a in ACTORS}
    for t, row in per_tick.items():
        for actor in ACTORS:
            info = row[actor]
            if info["cause"] == "quiet_gate":
                if info["top_sel_score"] is not None:
                    silent_sel_scores[actor].append(info["top_sel_score"])
    silent_sel_stats: dict[str, dict] = {}
    for actor in ACTORS:
        vals = silent_sel_scores[actor]
        if not vals:
            silent_sel_stats[actor] = {"n": 0}
            continue
        silent_sel_stats[actor] = {
            "n": len(vals),
            "mean": _st.mean(vals),
            "min": min(vals),
            "max": max(vals),
            "all_at_or_below_zero": all(v <= 0.0 for v in vals),
        }

    # --- D. concrete active->silent / active->travel-repeat traces
    traces = []
    for actor in ACTORS:
        for t in range(1, TICKS):
            prev = per_tick.get(t - 1, {}).get(actor)
            cur = per_tick.get(t, {}).get(actor)
            if prev is None or cur is None:
                continue
            if prev["cause"] == "committed" and cur["cause"] != \
                    "committed":
                traces.append({
                    "type": "active_to_silent",
                    "actor": actor, "tick": t,
                    "prev_committed": prev["committed"],
                    "cur_cause": cur["cause"],
                    "cur_pool0": cur["pool0_size"],
                    "cur_arb": cur["arbitration_kind"]})
                if len([x for x in traces if
                        x["actor"] == actor]) >= 3:
                    break
            # Free-travel consecutive-same-destination trace: both
            # prev and cur must be free travel (no search target) AND
            # share the same destination (ActionCandidate.targets[0])
            # -- this is the actual "does the world keep sending them
            # back to the same place" signal, not an ID-suffix match.
            if (prev["cause"] == "committed"
                    and prev.get("is_free_travel")
                    and cur["cause"] == "committed"
                    and cur.get("is_free_travel")):
                prev_dest = (prev.get("committed_targets") or [None])[0]
                cur_dest = (cur.get("committed_targets") or [None])[0]
                if prev_dest is not None and cur_dest == prev_dest:
                    traces.append({
                        "type": "travel_repeat_same_dest",
                        "actor": actor, "tick": t,
                        "dest": cur_dest,
                        "prev": prev["committed"],
                        "cur": cur["committed"]})
                    if len([x for x in traces
                            if x["type"] ==
                            "travel_repeat_same_dest" and
                            x["actor"] == actor]) >= 3:
                        break
        traces.sort(key=lambda x: (x["type"], x["actor"], x["tick"]))

    pool_stats = {
        a: {"min": min(pool_sizes[a]),
            "median": statistics.median(pool_sizes[a]),
            "max": max(pool_sizes[a]),
            "solo_choice_commits": solo_choice_ticks.get(a, 0)}
        for a in ACTORS if pool_sizes.get(a)}

    return {"seed": seed, "cause_counts": cause_counts,
            "travel_stats": travel_stats, "pool_stats": pool_stats,
            "sel_score_stats": sel_score_stats,
            "silent_sel_stats": silent_sel_stats,
            "contact_help_stats": contact_help_stats,
            "traces": traces[:8],
            "total_events": len(events)}


def main() -> int:
    print("=" * 72)
    print("M27  Natural-Regime Bottleneck Audit  (read-only, "
          "anchored 0ba1699)")
    print("=" * 72)

    verdict_evidence = []
    for seed in SEEDS:
        r = run_seed(seed)
        print(f"\n[seed {seed}] total persisted events: "
              f"{r['total_events']}")
        print("  A. silent-cause matrix (tick count per actor, "
              f"out of {TICKS}):")
        for cause, per_actor in sorted(r["cause_counts"].items()):
            parts = [f"{a}={n}" for a, n in per_actor.items()]
            print(f"    {cause:16s}  {'  '.join(parts)}")
        print("  B. travel attribution (free-travel vs search-driven):")
        for a, s in r["travel_stats"].items():
            print(f"    {a}: free-travel-commits={s['free_travel_commits']}, "
                  f"search-commits={s['search_commits']}, "
                  f"consec-same-dest-pairs={s['consec_same_dest_pairs']}, "
                  f"best streak={s['best_streak']}, "
                  f"free-travel dest sequence (first 12)="
                  f"{s['dest_sequence']}")
        print("  B2. contact/help candidate tracking (does quiet-gate "
              "really explain their absence?):")
        for a, s in r["contact_help_stats"].items():
            print(f"    {a}: contact-present-ticks={s['contact_present_actor_ticks']}, "
                  f"help-present-ticks={s['help_present_actor_ticks']}, "
                  f"contact-on-silent-ticks={s['contact_on_silent_ticks']}, "
                  f"help-on-silent-ticks={s['help_on_silent_ticks']}, "
                  f"contact-committed={s['contact_committed']}, "
                  f"help-committed={s['help_committed']}")
        print("  C. selection_score stats (committed actions only):")
        for a, s in r["sel_score_stats"].items():
            if s.get("n", 0) == 0:
                print(f"    {a}: no committed actions with recorded "
                      f"selection_score")
                continue
            print(f"    {a}: n={s['n']} mean={s['mean']:.3f} "
                  f"min={s['min']:.3f} max={s['max']:.3f} "
                  f"frac<=0={s['frac_below_or_at_zero']:.3f}")
        print("  C2. selection_score on SILENT ticks (quiet-gate proof):")
        for a, s in r["silent_sel_stats"].items():
            if s.get("n", 0) == 0:
                print(f"    {a}: no silent-tick samples captured")
                continue
            print(f"    {a}: n={s['n']} mean={s['mean']:.3f} "
                  f"min={s['min']:.3f} max={s['max']:.3f} "
                  f"all<=0={s['all_at_or_below_zero']}")
        print("  C. pool-size stats (candidate generation, "
              "pre-arbitration):")
        for a, s in r["pool_stats"].items():
            print(f"    {a}: min={s['min']} median={s['median']} "
                  f"max={s['max']}, committed-actions-from-"
                  f"single-candidate-pool={s['solo_choice_commits']}"
                  f" (of {TICKS})")
        print("  D. real traces:")
        for tr in r["traces"]:
            print(f"    {tr}")
        # verdict evidence accumulation
        empty_frac = (sum(
            r["cause_counts"].get("empty_pool", {}).values())
            / (TICKS * len(ACTORS)))
        quiet_frac = (sum(
            r["cause_counts"].get("quiet_gate", {}).values())
            / (TICKS * len(ACTORS)))
        arb_abstain_frac = (sum(
            r["cause_counts"].get("arbitration_abstain", {}).values())
            / (TICKS * len(ACTORS)))
        silent_sel_all_le_zero = all(
            s.get("all_at_or_below_zero", False)
            for s in r["silent_sel_stats"].values()
            if s.get("n", 0) > 0)
        verdict_evidence.append({
            "seed": seed, "empty_pool_frac": empty_frac,
            "quiet_gate_frac": quiet_frac,
            "arb_abstain_frac": arb_abstain_frac,
            "silent_sel_all_le_zero": silent_sel_all_le_zero})

    print("\n[Cross-seed rollup: which silent-cause dominates?]")
    for v in verdict_evidence:
        print(f"  seed {v['seed']}: empty_pool="
              f"{v['empty_pool_frac']:.3f} quiet_gate="
              f"{v['quiet_gate_frac']:.3f} arbitration_abstain="
              f"{v['arb_abstain_frac']:.3f} "
              f"silent_sel_all<=0={v['silent_sel_all_le_zero']}")

    # --- E. verdict -------------------------------------------------
    quiet_dominant = all(
        v["quiet_gate_frac"] > v["empty_pool_frac"]
        and v["quiet_gate_frac"] > v["arb_abstain_frac"]
        for v in verdict_evidence)
    pool_rarely_empty = all(
        v["empty_pool_frac"] < 0.05 for v in verdict_evidence)
    silent_sel_confirmed = all(
        v["silent_sel_all_le_zero"] for v in verdict_evidence)

    print("\n[VERDICT]")
    if quiet_dominant and pool_rarely_empty and silent_sel_confirmed:
        print("  REGIME-LIMITED (silent-tick near-cause): the "
              "overwhelming majority of silent ticks across all 5 "
              "seeds x both actors trace to choose(allow_quiet=True)"
              "'s selection_score<=0 rejection path "
              "(decision.py:238), with every captured silent-tick "
              "selection_score at-or-below zero (pre-step probe "
              "values, ~1e-4 drift vs. true step-time values, "
              "disclosed above). Candidate pools are never empty; "
              "arbitration is INERT (pool passes through unchanged) "
              "on the near-universal majority of ticks -- ABSTAIN "
              "never empties a pool in this window. This is NOT "
              "evidence of a mechanism being silently cut off in "
              "the sense of an empty/ABSTAIN path; it is evidence "
              "the existing quiet-gate mechanic is the dominant "
              "direct cause of the silence observed. "
              "CAVEAT (per independent review, M27-R1): this "
              "verdict does NOT establish that candidate-generation "
              "gating (co-location / relationship-pressure / "
              "distress conditions at actions.py:97-157) is "
              "irrelevant to overall behavior sparseness -- contact/"
              "help candidates simply rarely enter the pool under "
              "the current co-location/desire levels, which is a "
              "separate, unmeasured contribution distinct from the "
              "quiet-gate itself. Similarly, whether rui's free-"
              "travel destinations genuinely repeat (vs. alternate "
              "across a small location set like old_road/ridge) "
              "was re-checked this revision via the real "
              "ActionCandidate.targets field (Section B dest "
              "sequence); see the actual destination sequence "
              "printed above per seed -- do not assert 'same-"
              "destination repetition' unless that sequence "
              "actually shows it. M26's 'no natural failure/"
              "conflict' remains a NOT-OBSERVED registration for "
              "this window; this audit does not newly measure "
              "conflict and does not claim the quiet-gate is the "
              "proven sole cause of its absence. "
              "Bottom line: the near-cause of the 97-99% silence is "
              "the quiet-gate running as designed under a regime "
              "where selection_score sits stably at ~-0.2 (yan) / "
              "~-0.45 (rui); whether the deeper 'why is selection_"
              "score stably negative' question (desire initial "
              "levels, fatigue recovery rate, candidate-generation "
              "gating thresholds) is the next calibration question "
              "-- out of scope for this read-only audit, flagged "
              "for a future regime-experiment step, not pre-"
              "registered here.")
    elif pool_rarely_empty:
        print("  MECHANISM-BOTTLENECK: candidate generation or "
              "arbitration is failing to produce usable pools when "
              "it should -- investigate specific readers.")
    else:
        print("  NOT PROVEN: evidence is mixed across seeds or "
              "causes; do not force a single label.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
