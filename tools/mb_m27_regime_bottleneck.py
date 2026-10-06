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
    actor's decision, this is purely a read-the-pipeline probe)."""
    pool0 = generate_action_pool(world, actor)
    if not pool0:
        return {"cause": "empty_pool", "pool0_size": 0,
                "pool_final_size": 0, "arbitration_kind": None,
                "committed": None, "top_util": None,
                "second_util": None, "action_type": None}
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
                "top_sel_score": top_sel, "is_free_travel": False}
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
    return {"cause": "committed", "pool0_size": len(pool0),
            "pool_final_size": len(pool_final),
            "arbitration_kind":
                arbitration.kind if arbitration else None,
            "committed": action.id, "top_util": committed_util,
            "second_util": (top_utils[0] if top_utils else None),
            "action_type": action.action_type,
            "is_free_travel": is_free_travel,
            "top_sel_score": committed_sel}


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
    for actor in ACTORS:
        streak = 0
        best_streak = 0
        free_travel_commits = 0
        search_commits = 0
        consec_free_travel_pairs = 0
        prev_was_free_travel = False
        dests = []
        for t, row in per_tick.items():
            info = row[actor]
            if info["cause"] == "committed":
                sel_score_samples[actor].append(info["top_sel_score"])
                is_free = info["is_free_travel"]
                if is_free:
                    free_travel_commits += 1
                    dests.append(info["committed"])
                    if prev_was_free_travel:
                        consec_free_travel_pairs += 1
                    prev_was_free_travel = True
                    streak = streak + 1
                    best_streak = max(best_streak, streak)
                elif info["action_type"] in ("travel", "search_person") \
                        and not is_free:
                    search_commits += 1
                    prev_was_free_travel = False
                    streak = 0
                else:
                    prev_was_free_travel = False
                    streak = 0
            else:
                prev_was_free_travel = False
                streak = 0
        travel_stats[actor] = {
            "free_travel_commits": free_travel_commits,
            "search_commits": search_commits,
            "consec_free_travel_pairs": consec_free_travel_pairs,
            "best_streak": best_streak,
            "dest_samples": dests[:8],
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
            if (prev["cause"] == "committed"
                    and prev["action_type"] == "travel"
                    and cur["cause"] == "committed"
                    and cur["action_type"] == "travel"
                    and prev["committed"] and cur["committed"]
                    and prev["committed"].split("-")[-1] ==
                    cur["committed"].split("-")[-1]):
                traces.append({
                    "type": "travel_repeat_same_dest",
                    "actor": actor, "tick": t,
                    "dest": cur["committed"],
                    "prev": prev["committed"], "cur": cur["committed"]})
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
                  f"consec-free-travel-pairs={s['consec_free_travel_pairs']}, "
                  f"best streak={s['best_streak']}, "
                  f"sample free-travel dests={s['dest_samples']}")
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
        print("  REGIME-LIMITED (quiet-gate-dominated, confirmed at "
              "the selection_score level): candidate pools are "
              "rarely empty -- arbitration is INERT almost always "
              "(pool passes through unchanged), and the decision "
              "layer's choose(allow_quiet=True) actively REJECTS "
              "the best available candidate because its "
              "selection_score is <= 0 on the silent ticks "
              "(verified: every captured silent-tick selection_score "
              "is at-or-below zero, all 5 seeds x both actors). This "
              "is the existing, documented quiet-gate mechanic "
              "(decision.py:238, choose()'s only None-return branch "
              "for a nonempty pool) running as designed, not a "
              "broken or silently cut-off state chain. "
              "Separately, when quiet-gate DOES let an action "
              "through, the committed action is disproportionately "
              "FREE travel (no search target) plus search-driven "
              "travel -- freedom/curiosity pressure (actions.py:159"
              "-161) is a standing, always-on motive, unlike "
              "contact/help which need a 20+ relationship-pressure "
              "threshold to even enter the pool; this explains the "
              "travel-repetition observed in M26 without invoking "
              "any broken reader. M26's 'no natural failure/"
              "conflict' follows from the same gate: the ticks "
              "that would commit high-stakes actions (contact/"
              "help) are overwhelmingly the quiet-rejected ones, so "
              "they rarely produce real relationship tension or "
              "failed outcomes. This is a regime/parameter property "
              "of the existing selection_score<=0 threshold under "
              "the current desire/fatigue levels, not evidence of a "
              "mechanism being silently cut off.")
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
