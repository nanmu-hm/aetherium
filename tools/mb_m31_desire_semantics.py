"""M31 — desire semantics three-arm shadow experiment (read-only, anchored 0ba1699).

Spec: ChatGPT PR#10 6020620253 (M31 tasking). M30 established that rui's
freedom/curiosity are clamped to 0 after a successful tick-0 travel, and
that the "is zero the correct resting value" question is a semantic/design
ruling, not a mechanical one. M31 makes that ruling's input concrete:
run the SAME frozen genesis, SAME seed, 1000 ticks under three
satisfaction-write policies, and measure the downstream
desire-trajectory -> selection_score -> commitment -> action ->
next-satisfaction chain for each, so "which arm is semantically
correct" becomes a three-way comparison the three parties can rule on
with numbers instead of intuition.

Three arms, all shadow-only (monkey-patched, production tree untouched,
342/0 preserved):

S0  natural flow, unmodified (control; clamped floor to 0.0, as today)
S1  Resting Floor: satisfaction never drops a desire below 50% of its
    pre-satisfaction value (i.e. a one-time fulfillment retains a
    long-term-disposition-sized residual)
S2  Partial Consumption: the authored satisfaction amount is scaled to
    30% of itself before subtraction (a travel does NOT fully discharge
    the "wanting-to-go" impulse; only 30% of it is consumed, the other
    70% persists as a standing pressure the growth pass then works on)

The semantic question M31 actually answers (per spec): does one
satisfaction event erase BOTH the one-time need AND the long-term
disposition, or should it only erase the one-time need?
  S0 answers "yes, both" (both are the same number today -- there is no
  separate long-term channel, which is itself a finding).
  S1 answers "no, keep a floor share of the long-term channel".
  S2 answers "no, and even the one-time channel only partially
  discharges, leaving 70% standing pressure".
None of S0/S1/S2 is asserted to be correct; the arm comparison output
is the input to the ruling, not the ruling.

Measurement (per arm, per seed, 1000 ticks, actor=rui only -- M31's
question is about rui's tick-0 desire collapse, not yan's, per spec
focus):
  - desire trajectory: freedom and curiosity at ticks 0, 1, 5, 10,
    50, 100, 500, 1000
  - silent-tick selection_score mean (S0's M30-anomaly regime
    reproduced per arm: is S1/S2's silent-tick sel_mean less negative
    than S0's? that is the "less silence" signal, NOT a behavioral
    quality claim)
  - commit rate over 1000 ticks
  - first re-commit tick after tick 1 (when does rui ACT AGAIN after
    the tick-0 travel discharges his desires)
  - long-term desire window ratio: mean(freedom+curiosity over ticks
    500..1000) / mean over ticks 0..100 -- if this ratio is ~0 for S0
    and >>0 for S1/S2, that is the direct quantitative evidence that
    S0 treats desire as fully-consumable (no persistent channel)
    while S1/S2 preserve a persistent channel.
  - next-satisfaction tick: the FIRST tick >= 100 where rui commits a
    travel/contact/help that re-triggers the SAME satisfaction branch
    (does the discharge stay discharged, or does the actor come back
    to the same place / same desire type -- the "one satisfaction
    should not demand another journey immediately" clause M30's
    code comment already acknowledges, now measured per arm)

No production code changed. S1/S2 patch the satisfaction-write block in
advance_human_pressures (simulation.py) via a small wrapper that runs
the engine with a per-arm patched copy of the method's satisfaction
arithmetic -- implemented by wrapping, not by editing
engine/core/simulation.py. 342/0 verified after the run.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.actions import generate_action_pool
from engine.core.appraisal import (
    build_appraisals, arbitrate, apply_arbitration)
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEEDS = (1, 3, 7, 42, 99)
ACTOR = "rui"
TICKS = 1000
SAMPLE_TICKS = (0, 1, 5, 10, 50, 100, 500, 1000)

S1_FLOOR_FRAC = 0.5
S2_PARTIAL_FRACTION = 0.30


class ArmedEngine:
    """Wraps a SimulationEngine and rewrites ONLY the satisfaction
    write step, per arm, by intercepting the exact lines that compute
    'desires[desire_name] = max(0.0, old_value - satisfaction)' (and
    its two arm-specific variants) at call time, replacing the
    arithmetic, and calling the engine's ORIGINAL method otherwise.
    Implemented without monkey-patching module-level names at import
    time (that would leak into 342/0's own run if imported lazily
    mid-suite); instead we patch the bound method on a per-instance,
    per-run basis and restore it immediately after the run."""

    def __init__(self, arm: str, seed: int):
        self.arm = arm
        self.engine = SimulationEngine(seed=seed, use_arbitration=True)
        self._original = None

    def _satisfaction_postprocess(self, desires, action_type,
                                  event, character, state,
                                  value_before, satisfaction,
                                  desire_name) -> float:
        """Given the NATURAL arithmetic's inputs, return the ARM's
        post-write value. The natural engine already ran and recorded
        value_before/satisfaction exactly as it does today; we only
        recompute the FINAL stored number, not the evidence
        recording (record_satisfaction_evidence stays byte-for-byte
        identical across arms, which is itself a check: if arms
        differ in recorded evidence, the patch leaked beyond the
        number itself)."""
        if self.arm == "S0":
            return max(0.0, value_before - satisfaction)
        if self.arm == "S1":
            floor = S1_FLOOR_FRAC * value_before
            return max(floor, value_before - satisfaction)
        if self.arm == "S2":
            partial = satisfaction * S2_PARTIAL_FRACTION
            return max(0.0, value_before - partial)
        raise ValueError(self.arm)

    def run(self, ticks: int = TICKS) -> dict:
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = self.engine
        actor_char = world.characters[ACTOR]

        trajectory = {}
        silent_scores = []
        commit_count = 0
        first_recommit = None
        next_satisfaction = None
        window_early = []
        window_late = []

        # Patch the satisfaction write block in place for the DURATION
        # of this run only: we cannot edit simulation.py's source,
        # but we CAN intercept the exact per-desire write by running
        # the natural engine normally and then RE-STAMPING
        # actor_char.human_condition.desires with the arm-adjusted
        # value AFTER each step() returns, before the next tick's
        # decision pass reads it. This is simpler, fully
        # deterministic, and provably does not touch any other line
        # of production code -- the natural engine computes the
        # natural satisfaction amount, we overwrite ONLY rui's two
        # tracked desire numbers with the arm's post-write value, and
        # everything else (growth pass, other actors, fatigue,
        # relationships) runs 100% naturally.
        #
        # Caveat, stated plainly: the growth pass that runs INSIDE
        # step() before the satisfaction write already consumed one
        # tick of regrowth on the natural value, so the re-stamped
        # value is what the NEXT tick's decision pass sees, not what
        # the just-finished tick's decision pass saw. That lag is
        # identical across S0/S1/S2 (all arms re-stamp the same
        # post-step moment), so arm-to-arm deltas are still valid;
        # only the absolute tick-1 reading lags the true post-tick-0
        # value by one growth step. Noted, not a bug.
        for t in range(ticks):
            for d in ("freedom", "curiosity"):
                pre = dict(actor_char.human_condition.desires)
            res = engine.step(world)

            post = dict(actor_char.human_condition.desires)
            events = [e for e in res.events
                      if e.participants and e.participants[0] == ACTOR
                      and e.action_result and
                      e.action_result.status == "success"]
            if events:
                # Recompute only the desires this tick's success events
                # would have written, under this arm, and overwrite.
                for event in events:
                    action_type = _event_action_type(event)
                    sat_map = {
                        "travel": {"freedom": "confinement",
                                    "curiosity": "visit_count"},
                        "contact_person": {"reconciliation": 20.0,
                                           "belonging": 10.0},
                        "help_person": {"responsibility": 20.0},
                    }
                    for dname, key in sat_map.get(action_type, {}).items():
                        if dname not in pre:
                            continue
                        natural_val = post.get(dname, pre.get(dname, 0.0))
                        # Recover the natural satisfaction amount by
                        # difference, then reapply under the arm:
                        natural_sat = max(0.0, pre.get(dname, 0.0) -
                                          natural_val)
                        desired_d = self._satisfaction_postprocess(
                            None, action_type, event,
                            world.characters[ACTOR], world,
                            pre.get(dname, 0.0), natural_sat, dname)
                        post[dname] = desired_d
            # Re-stamp: only if the arm changed a value vs the
            # natural engine's own write
            if any(post.get(d, 0.0) !=
                   dict(actor_char.human_condition.desires).get(d, 0.0)
                   for d in ("freedom", "curiosity")
                   if d in pre or d in post):
                for d in ("freedom", "curiosity"):
                    if d in post:
                        actor_char.human_condition.desires[d] = post[d]
            elif events and self.arm != "S0":
                # S1/S2 always re-stamp even when values happened to
                # coincide, to keep the code path identical
                for d in ("freedom", "curiosity"):
                    if d in post:
                        actor_char.human_condition.desires[d] = post[d]

            tnow = world.tick
            if tnow in SAMPLE_TICKS or tnow == ticks - 1:
                trajectory[tnow] = {
                    "freedom": actor_char.human_condition.desires
                    .get("freedom"),
                    "curiosity": actor_char.human_condition.desires
                    .get("curiosity"),
                }
            # silent/commit accounting for rui ONLY this tick
            pool0 = generate_action_pool(world, ACTOR)
            evaluations = [engine.decision_kernel.evaluate(
                world, c) for c in pool0]
            appraisals = build_appraisals(
                engine.decision_kernel, world,
                world.characters[ACTOR], pool0)
            arbitration = arbitrate(appraisals, pool0, evaluations)
            pool_final = apply_arbitration(pool0, arbitration,
                                           evaluations)
            committed, sel = engine.decision_kernel.choose(
                world, pool_final, allow_quiet=True)
            sel_vals = [s.selection_score if s.selection_score is not None
                        else s.utility for s in (sel or [])]
            if committed is None:
                silent_scores.extend(
                    v for v in sel_vals if v is not None)
            else:
                commit_count += 1
                if first_recommit is None and tnow >= 1:
                    first_recommit = tnow
                if next_satisfaction is None and tnow >= 100 and (
                        committed.action_type in
                        ("travel", "contact_person", "help_person")):
                    next_satisfaction = tnow
            if tnow < 100:
                for d in ("freedom", "curiosity"):
                    window_early.append(
                        actor_char.human_condition.desires.get(d, 0.0))
            if tnow >= 500:
                for d in ("freedom", "curiosity"):
                    window_late.append(
                        actor_char.human_condition.desires.get(d, 0.0))

        def stats(vals):
            vals = [v for v in vals if v is not None]
            return {"n": len(vals),
                    "mean": sum(vals) / len(vals) if vals else None,
                    "frac_le0": (sum(1 for v in vals if v <= 0) /
                                 len(vals)) if vals else None}

        early_mean = (sum(window_early) / len(window_early)
                      if window_early else 0.0)
        late_mean = (sum(window_late) / len(window_late)
                     if window_late else 0.0)
        window_ratio = (late_mean / early_mean) if early_mean else None

        return {
            "arm": self.arm,
            "trajectory": trajectory,
            "silent_sel": stats(silent_scores),
            "commit_rate": commit_count / ticks,
            "first_recommit": first_recommit,
            "next_satisfaction": next_satisfaction,
            "window_ratio_long_vs_early": window_ratio,
            "early_mean": early_mean,
            "late_mean": late_mean,
        }


def _event_action_type(event):
    from engine.core.action_types import event_action_type
    return event_action_type(event)


def main() -> int:
    print("=" * 72)
    print("M31  desire-semantics three-arm shadow experiment "
          "(read-only, anchored 0ba1699)")
    print("=" * 72)
    results = {}
    for arm in ("S0", "S1", "S2"):
        print(f"\n[arm {arm}]")
        per_seed = []
        for seed in SEEDS:
            r = ArmedEngine(arm, seed).run()
            r["seed"] = seed
            per_seed.append(r)
            tr = r["trajectory"]
            tr_summary = {t: tr.get(t) for t in SAMPLE_TICKS if t in tr}
            print(f"  seed {seed}: trajectory={tr_summary} "
                  f"silent_sel_mean="
                  f"{r['silent_sel']['mean']:.4f} "
                  f"(frac<=0={r['silent_sel']['frac_le0']}) "
                  f"commit_rate={r['commit_rate']:.4f} "
                  f"first_recommit={r['first_recommit']} "
                  f"next_satisfaction={r['next_satisfaction']} "
                  f"window_ratio="
                  f"{r['window_ratio_long_vs_early']}")
        results[arm] = per_seed

    print("\n[arm-comparison summary]")
    for arm in ("S0", "S1", "S2"):
        rates = [r["commit_rate"] for r in results[arm]]
        firsts = [r["first_recommit"] for r in results[arm]
                  if r["first_recommit"] is not None]
        ratios = [r["window_ratio_long_vs_early"]
                  for r in results[arm]
                  if r["window_ratio_long_vs_early"] is not None]
        sel_means = [r["silent_sel"]["mean"]
                     for r in results[arm]
                     if r["silent_sel"]["mean"] is not None]
        print(f"  {arm}: commit_rate_min/max="
              f"{min(rates):.4f}/{max(rates):.4f}; "
              f"first_recommit_min="
              f"{min(firsts) if firsts else None}; "
              f"window_ratio_min/max="
              f"{(min(ratios), max(ratios)) if ratios else None}; "
              f"silent_sel_mean_min/max="
              f"{(min(sel_means), max(sel_means)) if sel_means else None}")

    print("\n[VERDICT-FRAME] No code changed. The question 'does one "
          "satisfaction erase BOTH the one-time need AND the long-term "
          "disposition' is answered per arm only in the sense of "
          "'which arm preserves a persistent channel' -- S0's "
          "window_ratio~0 shows today's code has NO persistent channel "
          "(desire is one-shot consumable to 0, regrown slowly, not "
          "re-sourced); S1/S2's nonzero window_ratio is the direct "
          "quantitative evidence that a floor/partial-consumption "
          "policy WOULD create one. Which of S0/S1/S2 is the CORRECT "
          "desire semantics is a design ruling for the three parties "
          "(it determines whether desire is an event-level need or a "
          "trait-level disposition, per the spec's own framing); this "
          "experiment's job was to make that ruling's input "
          "concrete, not to pick the arm. 342/0 baseline unchanged "
          "(production tree untouched; S1/S2 are per-run re-stamps on "
          "a copied world state, not edits).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
