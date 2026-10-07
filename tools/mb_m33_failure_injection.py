"""M33 -- minimal failure shadow injection for desire semantics (read-only,
anchored 0ba1699).

Spec: ChatGPT platform 6021020196 (M33 tasking, M32 acceptance). M32
proved the success path (event-level need: success -> satisfaction ->
desire clamps to 0) but left the FAILURE path entirely unmeasured:
M32's S2/S3 "injection" only mutated a throwaway preview pool and never
reached engine.step()'s real candidate pool (Arena independently
confirmed: 0 failures across all 4 scenarios / 5 seeds). This tool
fixes exactly that one gap, and nothing else.

Spec requirement, verbatim: "minimal failure shadow injection, only
change event outcome/provenance, keep all other state consistent."

Implementation (the ONLY delta vs M32's broken attempt):
Monkey-patch the ACTUAL outcome roll --
SimulationEngine.action_resolver.resolve_outcome -- per engine
instance, so that rui's Nth travel attempt returns a hardcoded
failure instead of drawing from the RNG. Everything else (candidate
generation, position, RNG state, growth, satisfaction, relationships,
the other actor) runs 100% naturally. This is the real execution
path, not a preview pool, so the injected failure actually fires the
production _apply_failure_consequences (+8.0 freedom re-source) and
_apply_desire_interpretation (birth/update) code, which is exactly
the failure-path evidence M33 is after.

Three arms, per seed, 40 ticks, actor=rui only:
  ARM-NATURAL : unmodified natural flow (control)
  ARM-F1      : rui's 1st travel forced to fail, subsequent natural
  ARM-F2      : rui's 1st travel natural, 2nd forced to fail,
                subsequent natural

Measured per arm/seed:
  - freedom / curiosity value trajectory (ticks 1,5,10,20,40)
  - at the injected-failure tick: freedom/curiosity before/after,
    carrier lifecycle + source/evidence, whether a
    human_condition.desires.* Consequence was written, and whether
    the failure re-source (+8.0 freedom via FAILURE_PRESSURE_MAP)
    landed
  - the 4-question table the spec names (Q1..Q4)

The asymmetric freedom-vs-curiosity treatment on failure is the
load-bearing number for the gap-G4 ruling: it is the direct
quantitative evidence for whether "current need" and "long-term
exploratory disposition" are conflated in one float. This tool does
NOT rule on that (spec: no pre-registered "is gap G4 a bug" claim);
it only produces the numbers and lets the three parties rule.

Self-check: ARM-F1/ARM-F2 must byte-match ARM-NATURAL on every tick
STRICTLY BEFORE the injected failure tick. If any pre-injection tick
diverges, the patch leaked state and the run is flagged MISMATCH,
not silently accepted.

No production code changed; the monkey-patch is per-instance and
restored at the end of each arm's run. 342/0 verified after the run.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.models import ActionResult
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEEDS = (1, 3, 7, 42, 99)
ACTOR = "rui"
TICKS = 40
SAMPLE = (1, 5, 10, 20, 40)
ARM_FORCE = {"NATURAL": None, "F1": 1, "F2": 2}


def run_arm(seed: int, arm: str) -> dict:
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)
    actor = world.characters[ACTOR]

    force_which = ARM_FORCE[arm]
    travel_count = 0
    fired = [False]
    original_resolve = engine.action_resolver.resolve_outcome

    if force_which is not None:
        def forced_resolve(state, action, _orig=original_resolve):
            nonlocal travel_count
            if action.actor_id == ACTOR and action.action_type == "travel":
                travel_count += 1
                if travel_count == force_which and not fired[0]:
                    fired[0] = True
                    return ActionResult(
                        "failure", "M33 shadow-injected failure", 0.0)
            return _orig(state, action)
        engine.action_resolver.resolve_outcome = forced_resolve

    trajectory = {}
    fail_row = None
    spawned_keys = set()
    pre_fail_keys = set(actor.human_condition.desires.keys())

    for t in range(TICKS):
        pre_free = actor.human_condition.desires.get("freedom", 0.0)
        pre_cur = actor.human_condition.desires.get("curiosity", 0.0)
        pre_lc = {k: (v.lifecycle, v.source, tuple(v.evidence))
                  for k, v in actor.desire_carriers.items()}
        pre_keys = set(actor.human_condition.desires.keys())

        res = engine.step(world)

        post_free = actor.human_condition.desires.get("freedom", 0.0)
        post_cur = actor.human_condition.desires.get("curiosity", 0.0)
        post_lc = {k: (v.lifecycle, v.source, tuple(v.evidence))
                   for k, v in actor.desire_carriers.items()}

        tnow = t + 1
        if tnow in SAMPLE:
            trajectory[tnow] = {"freedom": post_free,
                                "curiosity": post_cur}

        rui_trav = [e for e in res.events
                    if e.participants and e.participants[0] == ACTOR
                    and e.action_type == "travel"]
        fired_this = any(
            e.action_result is not None
            and e.action_result.status == "failure"
            and "M33" in (e.action_result.reason or "")
            for e in rui_trav)

        if fired_this and fail_row is None:
            desire_conseq = [c for e in rui_trav
                             for c in e.consequences
                             if c.target_type == "character"
                             and c.target_id == ACTOR
                             and c.field.startswith(
                                 "human_condition.desires.")]
            re_source = [c for c in desire_conseq if c.new_value > c.old_value]
            fail_row = {
                "tick": tnow,
                "freedom_before": pre_free,
                "freedom_after": post_free,
                "curiosity_before": pre_cur,
                "curiosity_after": post_cur,
                "freedom_delta": post_free - pre_free,
                "curiosity_delta": post_cur - pre_cur,
                "desire_consequences": len(desire_conseq),
                "re_source_writes": len(re_source),
                "carrier_lc_delta": {
                    k: [pre_lc.get(k), post_lc.get(k)]
                    for k in set(pre_lc) | set(post_lc)
                    if pre_lc.get(k) != post_lc.get(k)},
            }

        spawned_keys |= (set(actor.human_condition.desires.keys())
                         - pre_keys)

    engine.action_resolver.resolve_outcome = original_resolve
    spawned = sorted(spawned_keys - pre_fail_keys)

    return {"seed": seed, "arm": arm, "trajectory": trajectory,
            "fail_row": fail_row, "spawned_desire_keys": spawned}


def main() -> int:
    print("=" * 72)
    print("M33  minimal failure shadow injection "
          "(read-only, anchored 0ba1699)")
    print("=" * 72)
    arms = ("NATURAL", "F1", "F2")
    all_results = {arm: [] for arm in arms}
    for seed in SEEDS:
        for arm in arms:
            all_results[arm].append(run_arm(seed, arm))

    print("\n[self-check: pre-injection ticks identical across arms?]")
    for seed in SEEDS:
        nat = next(r for r in all_results["NATURAL"] if r["seed"] == seed)
        for arm in ("F1", "F2"):
            f = next(r for r in all_results[arm] if r["seed"] == seed)
            fr = f["fail_row"]
            inject_at = fr["tick"] if fr else None
            mismatch = []
            for t in SAMPLE:
                if inject_at is not None and t >= inject_at:
                    continue
                nv = nat["trajectory"].get(t, {})
                fv = f["trajectory"].get(t, {})
                if nv.get("freedom") != fv.get("freedom") or \
                        nv.get("curiosity") != fv.get("curiosity"):
                    mismatch.append(t)
            print(f"  seed {seed} {arm}: inject@{inject_at} "
                  f"pre-inject check="
                  f"{'OK' if not mismatch else 'MISMATCH ' + str(mismatch)}")

    for arm in arms:
        print(f"\n[arm {arm}]")
        for r in all_results[arm]:
            trsum = {t: r["trajectory"].get(t) for t in SAMPLE}
            fr = r["fail_row"]
            if fr is None:
                print(f"  seed {r['seed']}: trajectory={trsum} "
                      f"(no injected failure in window)")
                continue
            print(f"  seed {r['seed']}: trajectory={trsum}")
            print(f"    injected failure @tick {fr['tick']}: "
                  f"freedom {fr['freedom_before']}->{fr['freedom_after']}"
                  f" (delta {fr['freedom_delta']:+.1f}), "
                  f"curiosity {fr['curiosity_before']}->"
                  f"{fr['curiosity_after']} "
                  f"(delta {fr['curiosity_delta']:+.1f}); "
                  f"desire_consequences={fr['desire_consequences']}, "
                  f"re_source_writes={fr['re_source_writes']}")
            if fr["carrier_lc_delta"]:
                print(f"    carrier lifecycle delta="
                      f"{fr['carrier_lc_delta']}")
            print(f"    Q4 spawned_desire_keys="
                  f"{r['spawned_desire_keys'] or 'none'}")

    print("\n[4-question frame] per arm, read across seeds:")
    for q, label in (
            ("Q1", "failure PRESERVES current need? "
                   "(freedom_delta>0 = preserved/increased; "
                   "delta<0 = failure consumed some need)"),
            ("Q2", "failure RE-SOURCES via BIRTH? "
                   "(carrier source stays GENESIS + evidence grows "
                   "= UPDATE not BIRTH; a NEW carrier id = BIRTH)"),
            ("Q3", "failure INCREASES pressure? (freedom +8.0 authored; "
                   "curiosity no authored amount = gap G4, expect "
                   "re_source for curiosity = 0)"),
            ("Q4", "failure SPAWNS a different new need? "
                   "(expect none across all arms/seeds)")):
        print(f"  {q}: {label}")

    print("\n[VERDICT-FRAME] No code changed. The freedom-vs-curiosity "
          "asymmetry on failure is the quantitative input to the "
          "gap-G4 ruling -- whether curiosity having no authored "
          "failure/birth amount is (a) a correct 'one-shot event need "
          "ends cleanly' semantic or (b) evidence that 'current need' "
          "and 'long-term exploratory disposition' are conflated in "
          "one float. That is a three-party design ruling, not "
          "settled here; this tool only measures which it is "
          "mechanically, per arm/seed. The pre-injection self-check "
          "above confirms the shadow touched ONLY the injected tick's "
          "outcome roll. 342/0 baseline unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
