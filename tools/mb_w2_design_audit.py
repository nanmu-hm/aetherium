"""M7 -- W2 minimal implementation DESIGN audit (read-only).

Answers ChatGPT's on-platform instruction: "先按 W2 做最小实现设计审计，
再实施" (first do the minimal implementation design audit for W2, then
implement).

ChatGPT ruled:
  * contract (A): RESOLVE(X) => X is committed;
  * RESOLVE authority BEATS quiet-tick -- the choose() quiet gate must not
    swallow an explicit verdict;
  * W2 is the chosen shape, WITH A HARD BOUNDARY: bypass only choose(),
    NOT the rest of the pipeline. Explicitly NOT "RESOLVE fabricates an
    Event". It must be: RESOLVE names the final action, which then ENTERS
    the existing commit / event / consequence pipeline;
  * Outcome Authority untouched; Event/Fact/Consequence keep their original
    lifecycle; no float, no weight change, no new scoring channel;
  * still forbidden: touching weights, recall, or other architecture.

This audit DESIGNS and SIMULATES the change without applying it. It exists
to answer one question precisely: does W2 as scoped really bypass only
choose(), or does bypassing choose() also silently bypass something else
(preconditions in particular)?

Usage:  python3 tools/mb_w2_design_audit.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine.core.appraisal as ap  # noqa: E402
from engine.core.actions import generate_action_pool  # noqa: E402
from engine.core.decision import DecisionKernel  # noqa: E402
from engine.core.simulation import SimulationEngine  # noqa: E402
from engine.genesis import build_genesis_world  # noqa: E402

SEEDS = (1, 2, 3, 7, 42)
TICKS = 200
ACTORS = ("rui", "yan")

results: dict[str, list] = {}


def record(key: str, value) -> None:
    results.setdefault(key, []).append(value)


# ================================================================ D1
def d1_change_site() -> None:
    """The exact site, and what it would and would not touch."""
    print("=" * 78)
    print("D1  THE CHANGE SITE")
    print("=" * 78)
    print()
    print("  engine/core/simulation.py, generate_candidates(), the region")
    print()
    print("      if self.use_arbitration and pool:")
    print("          ... arbitration = arbitrate(appraisals, pool, evaluations)")
    print("          pool = apply_arbitration(pool, arbitration, evaluations)")
    print("      action, _ = self.decision_kernel.choose(state, pool, allow_quiet=True)")
    print("      if action is not None:")
    print("          selected.append(action)")
    print()
    print("  Under W2 the arbitration branch retains its verdict, and the")
    print("  selection becomes:")
    print()
    print("      if verdict.kind == 'resolve' and winner is not None:")
    print("          action = winner          # named by the arbitration layer")
    print("      else:")
    print("          action, _ = choose(state, pool, allow_quiet=True)")
    print()
    print("  Files touched : 1  (engine/core/simulation.py)")
    print("  Functions edited : generate_candidates only")
    print("  choose() edited : NO")
    print("  apply_arbitration edited : NO")
    print("  arbitrate() edited : NO")
    print("  Weights / recall / appraisal semantics : untouched")
    print()
    print("  Arena's correction is accepted and applied here: the previous")
    print("  report called apply_arbitration()'s final return 'the minimal")
    print("  control-flow point'. It is NOT -- measured 0/4. This audit does")
    print("  not repeat that framing.")
    print()
    record("D1_files_touched", 1)


# ================================================================ D2
def d2_only_choose_is_bypassed() -> None:
    """The boundary that matters: is anything ELSE skipped by skipping
    choose()? Specifically precondition screening, which lives in
    resolve(), not choose()."""
    print("=" * 78)
    print("D2  DOES BYPASSING choose() ALSO BYPASS PRECONDITIONS?")
    print("=" * 78)
    print()
    print("  This is the load-bearing question for ChatGPT's boundary")
    print("  ('bypass only choose(), not the commit pipeline').")
    print()
    print("  Where each check actually lives:")
    print("    choose()      : utility ranking, noise, allow_quiet guard")
    print("    resolve()     : precondition_engine.check(...)  <-- NOT in choose")
    print("    resolve()     : resolver/outcome, facts, consequences, event commit")
    print()
    print("  step() is:  actions = generate_candidates(state)")
    print("               events  = resolve(state, actions)")
    print("  generate_candidates RETURNS the action list; resolve() consumes it.")
    print("  So a W2-selected action is still passed to resolve(), which still")
    print("  runs precondition_engine.check() on it. Bypassing choose() does")
    print("  NOT bypass preconditions, the resolver, or event commit.")
    print()
    # prove it, rather than reasoning about it
    print("  PROOF BY SIMULATION: for every overriding RESOLVE witness, run the")
    print("  W2 selection and then pass the chosen action through the REAL")
    print("  resolve(), then confirm an event was committed.")
    print()
    print("  Checked on: engine/core/simulation.py")
    src = Path(__file__).resolve().parent.parent / "engine" / "core" / "simulation.py"
    text = src.read_text(encoding="utf-8")
    has_check = "precondition_engine.check(state, action)" in text
    print(f"    resolve() still calls precondition_engine.check : {has_check}")
    print(f"    step() still calls resolve(actions)              : "
          f"{'actions = self.generate_candidates(state)' in text}")
    print()
    record("D2_precondition_preserved", has_check)


# ================================================================ D3
def d3_witness_simulation() -> None:
    """Run W2 over the witnesses and confirm: committed == verdict, and an
    event really lands."""
    print("=" * 78)
    print("D3  W2 SIMULATED ON THE WITNESSES (no patch applied)")
    print("=" * 78)
    print()
    witnesses = []
    for seed in SEEDS:
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=False)
        k = engine.decision_kernel
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
                evs = [k.evaluate(world, c) for c in pool]
                recs = ap.build_appraisals(k, world, ch, pool)
                res = ap.arbitrate(recs, pool, evs)
                if res.kind != "resolve":
                    continue
                top1 = sorted(evs, key=lambda e: e.utility, reverse=True)[0]
                winner = next((c for c in pool if c.id == res.candidate_id), None)
                if winner is None:
                    continue
                witnesses.append({
                    "seed": seed, "tick": world.tick, "cid": cid,
                    "winner": winner, "top1": top1.action_id,
                    "world": copy.deepcopy(world), "engine": engine,
                    "overrides": res.candidate_id != top1.action_id,
                })
    print(f"  RESOLVE witnesses found : {len(witnesses)}")
    print(f"  of which override top-1 : {sum(1 for w in witnesses if w['overrides'])}")
    print()
    committed = 0
    events_landed = 0
    for w in witnesses:
        if not w["overrides"]:
            continue
        eng = SimulationEngine(seed=w["seed"], use_arbitration=False)
        # W2: the verdict names the action; resolve() still commits it.
        events = eng.resolve(w["world"], [w["winner"]])
        if events:
            events_landed += 1
        committed += 1
        print(f"    seed{w['seed']} t{w['tick']} {w['cid']}: "
              f"W2 action={w['winner'].id} (rival {w['top1']})")
        print(f"       resolve() committed {len(events)} event(s); "
              f"status="
              f"{events[0].action_result.status if events and events[0].action_result else None}")
    print()
    print(f"  W2 action passed to resolve() : {committed}")
    print(f"  events actually committed     : {events_landed}")
    print()
    if committed and events_landed == committed:
        print("  => The W2-selected action DOES enter the existing commit")
        print("     pipeline and produces a real event. The boundary holds:")
        print("     choose() is bypassed, resolve() is not.")
    print()
    record("D3_committed", committed)
    record("D3_events", events_landed)


# ================================================================ D4
def d4_regression_impact() -> None:
    """Which tests change, and how, under W2."""
    print("=" * 78)
    print("D4  REGRESSION IMPACT -- WHICH TESTS CHANGE AND HOW")
    print("=" * 78)
    print()
    print("  MUST CHANGE (its assertion encodes the superseded contract):")
    print("    tests/test_appraisal.py:116 test_apply_arbitration_resolve_")
    print("    narrows_to_top2")
    print("      `assert len(narrowed) == 2`")
    print("      Under W2 apply_arbitration is NOT changed, so the narrowed")
    print("      pool can still be 2 -- this test may survive as-is if W2 is")
    print("      implemented purely at the simulation.py site.")
    print("      That is a material advantage of W2 over W1/W3 and worth")
    print("      stating: W2 does NOT require editing this test.")
    print()
    print("  NEW ASSERTION REQUIRED (the real contract):")
    print("    for a RESOLVE(X) witness:")
    print("        committed_action == X")
    print("    and the deterministic witness:")
    print("        seed3 t4 rui: arbitration OFF -> rest")
    print("                          arbitration ON  -> travel")
    print()
    print("  UNCHANGED (explicitly asserted to be unchanged):")
    print("    ABSTAIN -> pool == [], choose() returns None  (test_appraisal.py:103)")
    print("    INERT   -> pool unchanged, pick == baseline    (test_appraisal.py:60)")
    print()
    print("  THE INHERITED FAILURE:")
    print("    tests/test_appraisal_regression.py::")
    print("    test_extract_seed1_divergence_traces asserts seed1 has >=1")
    print("    divergent tick. Note: the witness ChatGPT named is seed3/t4/rui,")
    print("    but the test asks about SEED1. Whether seed1 has an overriding")
    print("    RESOLVE is therefore a separate, checkable question -- and this")
    print("    audit measured it:")
    print()
    print("    seed1 overriding witnesses: measured below, and it matters,")
    print("    because if seed1 has none then W2 cannot make THAT test pass")
    print("    and the regression would need a different witness or a")
    print("    different assertion. Flagging it now rather than discovering")
    print("    it after patching.")
    print()
    s1 = 0
    for seed in SEEDS:
        if seed != 1:
            continue
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=False)
        k = engine.decision_kernel
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
                evs = [k.evaluate(world, c) for c in pool]
                recs = ap.build_appraisals(k, world, ch, pool)
                res = ap.arbitrate(recs, pool, evs)
                if res.kind != "resolve":
                    continue
                top1 = sorted(evs, key=lambda e: e.utility, reverse=True)[0]
                if res.candidate_id != top1.action_id:
                    s1 += 1
    print(f"      seed1 overriding RESOLVE witnesses : {s1}")
    print()
    if s1 == 0:
        print("      => SEED1 HAS NONE. Under W2, arbitration ON and OFF would")
        print("         still commit identical actions for seed1, because no")
        print("         verdict there ever contradicts utility. The inherited")
        print("         test would STILL FAIL -- not because W2 is wrong, but")
        print("         because it tests a seed with no witnesses.")
        print("      This must be settled BEFORE patching, not after.")
    else:
        print("      => seed1 has overriding witnesses, so ON/OFF would")
        print("         diverge for seed1 and the inherited test can pass.")
    print()
    record("D4_seed1_overrides", s1)


def main() -> int:
    print("M7  W2 MINIMAL IMPLEMENTATION DESIGN AUDIT (read-only, no patch)")
    print()
    d1_change_site()
    d2_only_choose_is_bypassed()
    d3_witness_simulation()
    d4_regression_impact()

    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"  D1 files touched by W2                 : {results['D1_files_touched'][0]}")
    print(f"  D2 resolve() keeps precondition check  : "
          f"{results['D2_precondition_preserved'][0]}")
    print(f"  D3 W2 actions passed to resolve()      : {results['D3_committed'][0]}")
    print(f"  D3 events actually committed           : {results['D3_events'][0]}")
    print(f"  D4 seed1 overriding RESOLVE witnesses  : {results['D4_seed1_overrides'][0]}")
    print()
    print("  THE DESIGN, IN ONE PLACE:")
    print("    engine/core/simulation.py, generate_candidates():")
    print("      if the verdict was RESOLVE and names a winner, append that")
    print("      winner directly; otherwise call choose() exactly as today.")
    print("    One file. choose() is not edited. apply_arbitration() is not")
    print("    edited. Weights, recall and appraisal semantics are untouched.")
    print("    The action still flows into resolve(), so preconditions,")
    print("    the resolver, Outcome Authority, Event/Fact/Consequence and")
    print("    the whole existing lifecycle are unchanged.")
    print()
    print("  ONE BLOCKER FOUND, and it is a TEST question, not a code one:")
    print("    see D4 -- whether seed1 has any overriding RESOLVE witness at")
    print("    all. That determines whether the inherited regression can pass")
    print("    under W2 without changing what that test asserts.")
    print()
    print("  NOTHING PATCHED. Per the instruction, this is the design audit")
    print("  only; implementation follows, and only after this is posted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())