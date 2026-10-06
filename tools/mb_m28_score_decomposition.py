"""M28 -- Four-layer selection_score decomposition (read-only, anchored
0ba1699).

Spec: ChatGPT PR#10 6019959791. Answers WHY selection_score sits stably
negative (~-0.2 yan, ~-0.45 rui) by decomposing into 4 INDEPENDENT
contributing layers, with a candidate-absent/present x quiet-on/off
orthogonal matrix, at 2 time scales (200-tick early dynamics, 1000-tick
long-horizon lock-in), across 5 seeds.

Layers (each reported per actor per tick, no layer is allowed to be
reported as "the explanation" without the others):
L1 desire initial/field-level snapshot (tick 0/1/10/50/100)
L2 fatigue value + shadow-counterfactual (if fatigue did not recover,
   what would selection_score be?)
L3 candidate-generation gating: for each of contact_person / help_person
   / travel (free) / search_person, was it generated this tick, and if
   NOT generated, WHICH named gate condition failed (co-location,
   relationship-pressure<20, distress not met, no alternatives, etc.)
L4 quiet-gate: selection_score distribution, plus a shadow arm that
   re-runs choose() with allow_quiet=False to see what WOULD be committed
   if the quiet gate were not applied (instrument only, not a code change)

No weight change, no production/test/interface change, no recall(),
no manufactured failure. Shadow arms are pure recomputation against
the same frozen world state snapshot, clearly labeled as counterfactual
instrumentation, not natural-flow evidence.

Anchor 0ba1699; read-only; production HELD.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.actions import generate_action_pool
from engine.core.appraisal import (
    build_appraisals, arbitrate, apply_arbitration)
from engine.core.decision import DecisionKernel
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world
from engine.core.models import WorldState

SEEDS = (1, 3, 7, 42, 99)
ACTORS = ("yan", "rui")
DESIRES = ("reconciliation", "belonging", "freedom", "curiosity",
           "responsibility")


def desire_snapshot(character) -> dict:
    """desires here is a plain {name: float} mapping (genesis writes
    int/float values, not objects) -- verified against
    build_genesis_world(): e.g. yan={reconciliation:70},
    rui={freedom:80,curiosity:35}. There is no per-desire
    strength/urgency/priority/status object to report; the single
    0-100 float IS the whole desire field at this layer. Reported
    verbatim, no invented sub-fields."""
    hc = character.human_condition
    out = {}
    for name in DESIRES:
        out[name] = hc.desires.get(name, "absent")
    return out


def fatigue_value(character) -> float:
    return character.human_condition.fatigue


def generation_gate_report(world: WorldState, actor: str,
                           kernel: DecisionKernel) -> dict:
    """Reproduce generate_action_pool()'s gate logic for one actor,
    but RETURN which named condition blocked each candidate type,
    instead of silently appending or skipping. Read-only mirror of
    actions.py:87-277 -- must stay in sync with real code paths,
    flag as STALE if this ever drifts from source."""
    from engine.core.actions import (
        _has_value, _relationship_targets, _trust,
        _contextual_desire, _goal_supports_action,
        _contact_just_expressed_emotion)
    from engine.core.action_types import goal_matches_action
    from engine.core.psychology import has_trait

    character = world.characters[actor]
    report: dict = {}

    if character.status != "active":
        report["status_gate"] = f"not active ({character.status})"
        return report

    goal = max((g for g in character.goals if g.status == "active"),
               key=lambda g: g.priority, default=None)
    pursue_reason = None
    if not (goal and not goal.stage_conditions):
        pursue_reason = ("no active goal" if goal is None else
                         "goal has stage_conditions")
    report["pursue_goal"] = "generated" if pursue_reason is None else \
        "blocked: " + pursue_reason

    nearby = [t for t in _relationship_targets(world, character)
              if world.characters[t].location == character.location]
    if not nearby:
        report["contact_person"] = "blocked: no co-located relationship " \
                                   "target (co-location gate)"
    else:
        target_id = min(nearby, key=lambda item: _trust(world, character, item))
        trust = _trust(world, character, target_id)
        reconciliation = character.human_condition.desires.get("reconciliation", 0.0)
        belonging = character.human_condition.desires.get("belonging", 0.0)
        relationship = world.get_relationship(character.id, target_id)
        tension = max(0.0, min(100.0, max(
            100.0 - trust,
            relationship.resentment if relationship else 0.0,
            relationship.fear if relationship else 0.0)))
        emotional_pressure = max(
            character.emotions.get("anger", 0.0),
            character.emotions.get("longing", 0.0),
            character.emotions.get("resentment", 0.0),
            character.emotions.get("love", 0.0))
        if _contact_just_expressed_emotion(world, character):
            emotional_pressure = 0.0
            ae_zeroed = True
        else:
            ae_zeroed = False
        belonging_carrier = character.desire_carriers.get("belonging")
        if belonging_carrier is not None and \
                belonging_carrier.lifecycle == "CONSUMED":
            belonging = 0.0
        reconciliation_motive = reconciliation * (tension / 100.0) ** 2
        relationship_motive = max(
            reconciliation_motive, belonging * 0.50, emotional_pressure)
        goal_motive = 100.0 * goal.priority if goal and \
            _goal_supports_action(character, "contact_person") else 0.0
        contact_pressure = max(
            max(0.0, min(100.0, relationship_motive)), goal_motive)
        if contact_pressure >= 20.0:
            report["contact_person"] = "generated"
        else:
            report["contact_person"] = \
                (f"blocked: relationship_pressure "
                 f"{contact_pressure:.1f} < 20 (components: "
                 f"reconciliation_motive, belonging, "
                 f"emotional_pressure, goal_motive); "
                 f"AE-zeroed={ae_zeroed}")

    distressed = [t for t in _relationship_targets(world, character)
                  if world.characters[t].location == character.location and
                  (world.characters[t].emotions.get("sorrow", 0.0) +
                   world.characters[t].emotions.get("fear", 0.0) +
                   world.characters[t].human_condition.fatigue / 2.0) > 8.0]
    help_qual = (_has_value(character, "loyalty") or
                 _has_value(character, "responsibility") or
                 has_trait(character, "compassionate", "protective",
                           "helpful") or
                 character.human_condition.desires.get("responsibility", 0.0) > 20.0)
    if not distressed:
        report["help_person"] = "blocked: no co-located distressed target"
    elif not help_qual:
        report["help_person"] = ("blocked: no loyalty/responsibility "
                                 "value or compassionate/protective/"
                                 "helpful trait or responsibility-desire>20")
    else:
        report["help_person"] = "generated"

    freedom_pressure = _contextual_desire(character, "freedom")
    curiosity_pressure = _contextual_desire(character, "curiosity")
    travel_pressure = max(freedom_pressure, curiosity_pressure)
    if len(world.locations) <= 1:
        report["travel_free"] = "blocked: only one location exists"
    else:
        report["travel_free"] = "generated"
        report["travel_pressure"] = travel_pressure

    return report


def shadow_no_quiet_commit(world: WorldState, engine: SimulationEngine,
                           actor: str):
    """Recompute what choose() WOULD commit if allow_quiet were False
    (i.e. quiet gate OFF), without touching production -- purely a
    counterfactual recomputation against the current frozen state.
    Returns the would-be action id + its selection_score, or None if
    pool empty (in which case quiet-gate-off cannot help either)."""
    pool0 = generate_action_pool(world, actor)
    if not pool0:
        return None, None, "pool0_empty"
    arbitration = None
    evaluations = None
    pool_final = pool0
    if engine.use_arbitration:
        evaluations = [engine.decision_kernel.evaluate(world, c)
                       for c in pool0]
        appraisals = build_appraisals(
            engine.decision_kernel, world,
            world.characters[actor], pool0)
        arbitration = arbitrate(appraisals, pool0, evaluations)
        pool_final = apply_arbitration(pool0, arbitration, evaluations)
    if not pool_final:
        return None, None, "pool_final_empty"
    # choose with allow_quiet=False: kernel still evaluates; the
    # allow_quiet=False path just never returns None for a nonempty
    # pool (decision.py:238 guard is skipped entirely).
    action, sel = engine.decision_kernel.choose(
        world, pool_final, allow_quiet=False)
    if action is None:
        return None, None, "unexpected_none"
    sel_map = {s.action_id: s for s in sel}
    s = sel_map.get(action.id)
    score = (s.selection_score if s and s.selection_score is not None
             else s.utility if s else None)
    return action.id, score, "ok"


def action_entropy(committed_types: list[str]) -> float:
    if not committed_types:
        return 0.0
    from collections import Counter
    c = Counter(committed_types)
    n = len(committed_types)
    return -sum((k / n) * math.log(k / n) for k in c.values() if k > 0)


def travel_transition_matrix(dest_seq: list[str]) -> dict:
    """Count pairwise destination transitions (old_road->ridge etc.)."""
    from collections import Counter
    pairs = Counter()
    for i in range(len(dest_seq) - 1):
        pairs[(dest_seq[i], dest_seq[i + 1])] += 1
    return dict(pairs)


def a_to_b_a_return_ratio(dest_seq: list[str]) -> float:
    """Fraction of 3-consecutive-tick travel windows that are A,B,A
    (an immediate reversal back to the just-left location)."""
    if len(dest_seq) < 3:
        return 0.0
    hits = 0
    for i in range(len(dest_seq) - 2):
        a, b, c = dest_seq[i], dest_seq[i + 1], dest_seq[i + 2]
        if a == c and a != b:
            hits += 1
    return hits / (len(dest_seq) - 2)


def run_arm(seed: int, ticks: int, quiet_on: bool):
    """Run one seed to `ticks` under normal natural flow, capturing all
    4 layers per tick per actor, PLUS a shadow no-quiet arm
    (recomputation only, not a separate world run) for every tick to
    measure 'what quiet-gate is actually suppressing'."""
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)

    records: dict[tuple[str, int], dict] = {}
    per_tick_dests: dict[str, list] = {a: [] for a in ACTORS}
    per_tick_committed_types: dict[str, list] = {a: [] for a in ACTORS}

    for _ in range(ticks):
        t = world.tick
        for actor in ACTORS:
            character = world.characters[actor]
            d_snap = desire_snapshot(character)
            fatigue = fatigue_value(character)
            gate_report = generation_gate_report(world, actor,
                                                  engine.decision_kernel)
            pool0 = generate_action_pool(world, actor)
            pool0_types = tuple(sorted(
                set(c.action_type for c in pool0)))
            # quiet-on path: the REAL commit decision, reproduced exactly
            # as engine.step() does it (arbitration + choose(allow_quiet))
            arbitration = None
            evaluations = None
            pool_final = pool0
            committed = None
            sel_scores = None
            if engine.use_arbitration:
                evaluations = [engine.decision_kernel.evaluate(world, c)
                                for c in pool0]
                appraisals = build_appraisals(
                    engine.decision_kernel, world, character, pool0)
                arbitration = arbitrate(appraisals, pool0, evaluations)
                pool_final = apply_arbitration(pool0, arbitration, evaluations)
            if arbitration is not None and arbitration.kind == "resolve":
                committed = next((c for c in pool_final
                                  if c.id == arbitration.candidate_id), None)
            if committed is None and pool_final:
                committed, sel_scores = engine.decision_kernel.choose(
                    world, pool_final, allow_quiet=True)
            # shadow arm: what WOULD have been committed if quiet-gate
            # were off -- pure recomputation, no world mutation
            shadow_id, shadow_sel, shadow_note = shadow_no_quiet_commit(
                world, engine, actor)
            committed_sel = None
            if sel_scores:
                if committed is not None:
                    for s in sel_scores:
                        if s.action_id == committed.id:
                            committed_sel = (s.selection_score if
                                            s.selection_score is not None
                                            else s.utility)
                            break
                else:
                    # silent tick (committed None but pool nonempty and
                    # choose() rejected via quiet-gate): capture the
                    # MAX selection_score that got rejected, for the
                    # L4 / silent-score-distribution analysis
                    committed_sel = max(
                        (s.selection_score if s.selection_score is not None
                         else s.utility) for s in sel_scores)
            records[(actor, t)] = {
                "desires": d_snap,
                "fatigue": fatigue,
                "gate_report": gate_report,
                "pool0_types": pool0_types,
                "arbitration_kind":
                    arbitration.kind if arbitration else None,
                "committed": committed.id if committed else None,
                "committed_action_type":
                    committed.action_type if committed else None,
                "committed_sel_score": committed_sel,
                "shadow_no_quiet_id": shadow_id,
                "shadow_no_quiet_sel": shadow_sel,
                "shadow_note": shadow_note,
            }
            if committed is not None:
                per_tick_committed_types[actor].append(
                    committed.action_type)
                is_free_travel = (
                    committed.action_type == "travel"
                    and not committed.metadata.get("search_target"))
                if is_free_travel:
                    per_tick_dests[actor].append(
                        (committed.targets or [None])[0])
        res = engine.step(world)

    def frac_silent_neg(sel_scores_by_actor):
        out = {}
        for actor, vals in sel_scores_by_actor.items():
            if not vals:
                out[actor] = 0.0
                continue
            out[actor] = sum(1 for v in vals if v is not None and v <= 0) \
                / len([v for v in vals if v is not None])
        return out

    silent_neg = {}
    for actor in ACTORS:
        vals = [records[(actor, t)]["committed_sel_score"]
                for t in range(ticks)
                if records[(actor, t)]["committed"] is None]
        vals = [v for v in vals if v is not None]
        silent_neg[actor] = (sum(1 for v in vals if v <= 0) / len(vals),
                             min(vals) if vals else None,
                             max(vals) if vals else None) if vals \
            else (0.0, None, None)

    suppressed_count = {
        a: sum(1 for t in range(ticks)
               if records[(a, t)]["committed"] is None
               and records[(a, t)]["shadow_no_quiet_id"] is not None)
        for a in ACTORS}

    return {
        "seed": seed, "ticks": ticks,
        "records": records,
        "silent_neg_frac": silent_neg,
        "suppressed_by_quiet_count": suppressed_count,
        "entropy": {a: action_entropy(v)
                    for a, v in per_tick_committed_types.items()},
        "travel_transition_matrix": {
            a: travel_transition_matrix(v)
            for a, v in per_tick_dests.items()},
        "a_b_a_return_ratio": {
            a: a_to_b_a_return_ratio(v)
            for a, v in per_tick_dests.items()},
    }


def main() -> int:
    print("=" * 72)
    print("M28  Four-layer selection_score decomposition  "
          "(read-only, anchored 0ba1699)")
    print("=" * 72)

    all_results: dict[tuple, dict] = {}
    for seed in SEEDS:
        for ticks in (200, 1000):
            r = run_arm(seed, ticks, quiet_on=True)
            all_results[(seed, ticks)] = r

    # ---- L1: desire snapshot (early dynamics focus) ----------------
    print("\n[L1] desire-field snapshot (strength/urgency/priority/"
          "status) at tick 0/1/10/50/100, per seed per actor:")
    for seed in SEEDS:
        r = all_results[(seed, 200)]
        for actor in ACTORS:
            print(f"  seed {seed} {actor}:")
            for t in (0, 1, 10, 50, 100):
                if (actor, t) not in r["records"]:
                    continue
                snap = r["records"][(actor, t)]["desires"]
                print(f"    tick {t}: {snap}")

    # ---- L2: fatigue + shadow counterfactual -----------------------
    print("\n[L2] fatigue value + shadow-counterfactual "
          "(selection_score WITHOUT quiet-gate, same frozen state):")
    for seed in SEEDS:
        r = all_results[(seed, 1000)]
        for actor in ACTORS:
            fatigue_series = [r["records"][(actor, t)]["fatigue"]
                              for t in (0, 10, 50, 100, 500, 1000)
                              if (actor, t) in r["records"]]
            suppressed = r["suppressed_by_quiet_count"][actor]
            print(f"  seed {seed} {actor}: fatigue@0/10/50/100/500/1000"
                  f"={fatigue_series}, suppressed-by-quiet ticks="
                  f"{suppressed} (of 1000)")

    # ---- L3: candidate-generation gating (1000-tick aggregate) ----
    print("\n[L3] candidate-generation gate blocking reason, 1000-tick "
          "tallies per seed per actor:")
    for seed in SEEDS:
        r = all_results[(seed, 1000)]
        for actor in ACTORS:
            tallies: dict[str, int] = {}
            for t in range(1000):
                rep = r["records"][(actor, t)]["gate_report"]
                for ctype in ("contact_person", "help_person",
                               "travel_free"):
                    status = rep.get(ctype, "unknown")
                    key = ("generated" if status == "generated"
                           else "blocked")
                    tallies[f"{ctype}:{key}"] = \
                        tallies.get(f"{ctype}:{key}", 0) + 1
            print(f"  seed {seed} {actor}: {tallies}")

    # ---- L4: quiet-gate orthogonal matrix + silent-score distribution
    print("\n[L4] candidate absent/present x quiet on/off matrix, "
          "1000-tick counts per seed per actor, plus silent-tick "
          "selection_score distribution (frac<=0, min, max):")
    for seed in SEEDS:
        r = all_results[(seed, 1000)]
        for actor in ACTORS:
            grid = {
                "absent_quiet_would_block": 0,
                "present_committed": 0,
                "present_suppressed_by_quiet": 0,
                "present_but_shadow_also_empty": 0,
            }
            for t in range(1000):
                rec = r["records"][(actor, t)]
                has_candidate = len(rec["pool0_types"]) > 0
                if rec["committed"] is not None:
                    grid["present_committed"] += 1
                elif has_candidate:
                    if rec["shadow_no_quiet_id"] is not None:
                        grid["present_suppressed_by_quiet"] += 1
                    else:
                        grid["present_but_shadow_also_empty"] += 1
                else:
                    grid["absent_quiet_would_block"] += 1
            silent_frac, silent_min, silent_max = r["silent_neg_frac"][actor]
            print(f"  seed {seed} {actor}: {grid}")
            print(f"    silent-tick selection_score: frac<=0="
                  f"{silent_frac:.3f} min={silent_min} max={silent_max}")

    # ---- dual-scale dynamics -------------------------------------
    print("\n[Scale comparison] selection_score<=0 frac / entropy / "
          "travel transition matrix / A->B->A return ratio, "
          "200-tick vs 1000-tick:")
    for seed in SEEDS:
        r200 = all_results[(seed, 200)]
        r1000 = all_results[(seed, 1000)]
        for actor in ACTORS:
            print(f"  seed {seed} {actor}:")
            print(f"    200-tick: silent_sel<=0frac="
                  f"{r200['silent_neg_frac'][actor][0]:.3f} "
                  f"(min={r200['silent_neg_frac'][actor][1]}, "
                  f"max={r200['silent_neg_frac'][actor][2]}) "
                  f"entropy={r200['entropy'][actor]:.3f} "
                  f"A_B_A={r200['a_b_a_return_ratio'][actor]:.3f} "
                  f"transitions={dict(list(r200['travel_transition_matrix'][actor].items())[:4])}")
            print(f"    1000-tick: silent_sel<=0frac="
                  f"{r1000['silent_neg_frac'][actor][0]:.3f} "
                  f"(min={r1000['silent_neg_frac'][actor][1]}, "
                  f"max={r1000['silent_neg_frac'][actor][2]}) "
                  f"entropy={r1000['entropy'][actor]:.3f} "
                  f"A_B_A={r1000['a_b_a_return_ratio'][actor]:.3f} "
                  f"transitions={dict(list(r1000['travel_transition_matrix'][actor].items())[:4])}")

    print("\n[VERDICT-FRAME] The four layers above are reported as "
          "INDEPENDENT contributions; no single layer is asserted as "
          "'the' explanation. Which layer(s) dominate for the stable-"
          "negative selection_score regime, and whether the 1000-tick "
          "run shows lock-in (converging distribution) vs. early-"
          "dynamics (200-tick) divergence, is the judgment to be "
          "made from these numbers by the three parties -- not "
          "pre-registered here. No code change was made; no weight "
          "was adjusted; shadow counterfactuals are instrumentation "
          "only, not natural-flow evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
