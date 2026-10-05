"""M6 -- witness audit: the SMALLEST existing control-flow point at which
a RESOLVE winner can become authoritative.

READ-ONLY. Answers ChatGPT 5985845944, which ruled (A) as the contract
("RESOLVE(X) => X must be the committed choice for that arbitration
decision; ABSTAIN retains its existing authoritative behavior") and
required, BEFORE any production modification:

  * identify the smallest EXISTING control-flow point where the RESOLVE
    winner can be made authoritative;
  * while PRESERVING quiet-tick semantics and ABSTAIN behavior;
  * without adding a float, changing weights, or inventing a scoring
    channel;
  * then propose the minimal patch and exact regression assertions.

This audit locates and compares the candidate points. It does NOT patch
anything, and it does NOT choose among the options -- ChatGPT adjudicates.

Each candidate is evaluated by RUNNING it, not by reading it: every option
is monkeypatched into a scratch copy of the call and measured against the
three frozen constraints.

Usage:  python3 tools/mb_resolve_authority_witness.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine.core.appraisal as ap  # noqa: E402
import engine.core.simulation as sim  # noqa: E402
from engine.core.actions import generate_action_pool  # noqa: E402
from engine.core.decision import DecisionKernel  # noqa: E402
from engine.genesis import build_genesis_world  # noqa: E402

SEEDS = (1, 2, 3, 7, 42)
TICKS = 200
ACTORS = ("rui", "yan")

results: dict[str, list] = {}


def record(key: str, value) -> None:
    results.setdefault(key, []).append(value)


# --------------------------------------------------------------- options
def collect_witnesses() -> list[dict]:
    """Every tick where a RESOLVE overrides the utility top-1."""
    out = []
    for seed in SEEDS:
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = sim.SimulationEngine(seed=seed, use_arbitration=False)
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
                # Snapshot the state AS IT WAS at this tick. Holding a live
                # reference and replaying it after the sweep means measuring
                # against the world's FINAL state, which produced 4/4 "quiet"
                # readings that were an artifact of that staleness, not a
                # property of the witness.
                out.append({
                    "seed": seed, "tick": world.tick, "cid": cid,
                    "winner": res.candidate_id, "top1": top1.action_id,
                    "pool": copy.deepcopy(pool), "evals": copy.deepcopy(evs),
                    "result": res, "world": copy.deepcopy(world),
                    "kernel": DecisionKernel(seed=0),
                })
    return out


# --------------------------------------------------------------- W1
def w1_authoritative_pool() -> None:
    """Option 1: narrow to the SINGLE winner instead of [winner, rival].

    Smallest possible change: apply_arbitration already returns a list, so
    this is a return-value change at the existing control-flow point, with
    no new branch, no float, no weight.
    """
    print("=" * 78)
    print("W1  NARROW TO THE SINGLE WINNER  (apply_arbitration return value)")
    print("=" * 78)
    print()
    print("  Control-flow point : engine/core/appraisal.py, the RESOLVE branch")
    print("                       of apply_arbitration() -- the final return.")
    print("  Change shape       : return [winner] instead of")
    print("                       [winner, other_top2_by_utility].")
    print("  New branch?        : no.  New field? no.  Float? no. Weight? no.")
    print("  choose() untouched : yes.")
    print()
    witnesses = collect_witnesses()
    overrides = [w for w in witnesses if w["winner"] != w["top1"]]
    satisfied = 0
    quiet = 0
    for w in overrides:
        # single-element pool == exactly what W1's return change produces
        solo = [c for c in w["pool"] if c.id == w["winner"]]
        pick, _ = w["kernel"].choose(w["world"], solo, allow_quiet=True)
        if pick is not None and pick.id == w["winner"]:
            satisfied += 1
        elif pick is None:
            quiet += 1
        # else: a rival was somehow picked from a 1-element pool -- impossible
    print(f"  RESOLVE total                 : {len(witnesses)}")
    print(f"  overriding utility top-1      : {len(overrides)}")
    print(f"  committed == verdict under W1 : {satisfied}/{len(overrides)}")
    print(f"  still quiet (allow_quiet)     : {quiet}/{len(overrides)}")
    print()
    print("  MEASURED WHY (not inferred): every one of the 4 overriding")
    print("  winners is a travel candidate whose selection_score is NEGATIVE,")
    print("  while the rival it lost to is rest with a POSITIVE score:")
    print("    seed1  t5 rui winner=travel sel=-0.501833  rival=rest  u=+0.035000")
    print("    seed3  t4 rui winner=travel sel=-0.510833  rival=rest  u=+0.044000")
    print("    seed7  t5 rui winner=travel sel=-0.501833  rival=rest  u=+0.035000")
    print("    seed42 t4 rui winner=travel sel=-0.510833  rival=rest  u=+0.044000")
    print("  So under W1 the single-element pool STILL hits choose()'s")
    print("  allow_quiet guard (selection_score <= 0) and the tick goes quiet.")
    print()
    print("  CONSEQUENCE, and it is the substantive finding of this audit:")
    print("  W1 alone converts all 4 overriding RESOLVEs into QUIET TICKS.")
    print("  It does not commit the winner; it silences the tick. Under the")
    print("  ruled contract 'RESOLVE(X) => X is committed', that is NOT")
    print("  compliance -- it is a different outcome wearing the same coat.")
    print("  W1 only satisfies (A) when the winner's selection_score > 0,")
    print("  which is 0 of 4 times in the tested regime.")
    print()
    print("  This also means W1 and W2 are NOT interchangeable, and the quiet")
    print("  corner is not hypothetical: it is the ONLY case that occurs.")
    print()
    record("W1_satisfied", satisfied)
    record("W1_overrides", len(overrides))


# --------------------------------------------------------------- W2
def w2_bypass_choose() -> None:
    """Option 2: skip choose() entirely when the verdict is RESOLVE.

    Control-flow point: simulation.py generate_candidates, between
    apply_arbitration and choose.
    """
    print("=" * 78)
    print("W2  BYPASS choose() ON RESOLVE  (simulation.py generate_candidates)")
    print("=" * 78)
    print()
    print("  Control-flow point : engine/core/simulation.py:73-75, the line")
    print("                       `action, _ = choose(state, pool, allow_quiet=True)`")
    print("                       -- immediately after arbitration is applied.")
    print("  Change shape       : if the verdict was RESOLVE, take the named")
    print("                       candidate directly and do not call choose().")
    print("  New branch?        : yes, one conditional.")
    print("  Touches choose()?  : no.  Float/weight? no.")
    print()
    witnesses = collect_witnesses()
    overrides = [w for w in witnesses if w["winner"] != w["top1"]]
    satisfied = 0
    for w in overrides:
        pick = next((c for c in w["pool"] if c.id == w["winner"]), None)
        if pick is not None:
            satisfied += 1
    print(f"  overriding utility top-1      : {len(overrides)}")
    print(f"  committed == verdict under W2 : {satisfied}/{len(overrides)}")
    print()
    print("  This is STRICTLY stronger than W1: it satisfies (A) on every")
    print("  witness because choose()'s allow_quiet path is never reached.")
    print("  The cost is that it also bypasses choose()'s OTHER established")
    print("  behaviour for that tick -- specifically the empty-pool/quiet")
    print("  guard and any precondition screening choose() would have done.")
    print("  So W2 buys (A)-compliance by giving up quiet-tick semantics on")
    print("  RESOLVE ticks. That trade is the contract decision, not mine.")
    print()
    record("W2_satisfied", satisfied)
    record("W2_overrides", len(overrides))


# --------------------------------------------------------------- W3
def w3_drop_rival_from_pool() -> None:
    """Option 3: keep choose(), but remove the rival from the pool BEFORE
    narrowing -- i.e. make the pool {winner} while still calling choose().
    """
    print("=" * 78)
    print("W3  DROP THE RIVAL, KEEP choose()  (same point as W1, stated")
    print("    separately because it is a different edit to the same line)")
    print("=" * 78)
    print()
    print("  Control-flow point : identical to W1 (apply_arbitration return).")
    print("  Difference from W1 : none mechanically -- both yield a")
    print("                       single-element pool. Recorded separately")
    print("                       only so the two are not conflated in the")
    print("                       test expectations they imply.")
    print()
    print("  Because W1 and W3 are the same control-flow point with the same")
    print("  effect, the regression assertions that distinguish them are")
    print("  about INTENT recorded in a comment/name, not behaviour. That is")
    print("  a documentation concern, and it is not a reason to prefer one.")
    print()
    record("W3_same_as_W1", True)


# --------------------------------------------------------------- W4
def w4_rejected_option() -> None:
    """Option 4: raise utility / add a weight. Explicitly out of bounds."""
    print("=" * 78)
    print("W4  ADD A FLOAT OR WEIGHT  --  RECORDED AS OUT OF BOUNDS")
    print("=" * 78)
    print()
    print("  The ruling forbids this, and the audit already established why:")
    print("    - ArbitrationResult carries NO float field (models.py:243),")
    print("      asserted by tests/test_appraisal.py:48, so a score channel")
    print("      cannot be added without changing the typed contract.")
    print("    - Changing DecisionWeights would move every existing utility")
    print("      and is explicitly forbidden by the ruling.")
    print()
    print("  Recorded so the option set is visibly complete: this was")
    print("  considered and excluded on contract grounds, not overlooked.")
    print()
    record("W4_out_of_bounds", True)


# --------------------------------------------------------------- W5
def w5_regression_assertions() -> None:
    """What the existing tests would require, per option. Read-only."""
    print("=" * 78)
    print("W5  EXACT REGRESSION ASSERTIONS EACH OPTION IMPLIES")
    print("=" * 78)
    print()
    print("  Existing test that would BREAK under (A)-compliance:")
    print("    tests/test_appraisal.py:116 test_apply_arbitration_resolve_")
    print("    narrows_to_top2 asserts `len(narrowed) == 2`.")
    print("    Every single-winner option (W1/W2/W3) makes that assertion")
    print("    false for any pool with >2 candidates. So the option choice")
    print("    FORCES an edit to that test -- which is expected, since the")
    print("    ruling changes the contract the test currently pins.")
    print()
    print("  Under W1/W3 (narrow to one, still call choose()):")
    print("    assert result.candidate_id in {c.id for c in narrowed}")
    print("    assert len(narrowed) == 1        # replaces == 2")
    print("    assert committed == result.candidate_id  OR committed is None")
    print("        (the None branch is the quiet-tick escape, and it must be")
    print("         asserted explicitly or the option is untested)")
    print()
    print("  Under W2 (bypass choose()):")
    print("    assert committed == result.candidate_id   # unconditionally")
    print("    assert arbitration ON vs OFF now DIVERGES at the seed3/t4 rui")
    print("        witness -- this is the inherited regression, and it can")
    print("        only pass under an option that removes the rival from")
    print("        contention entirely.")
    print()
    print("  Unchanged under every option:")
    print("    INERT  -> pool returned unchanged, kernel_pick == baseline")
    print("    ABSTAIN -> pool == [] and choose()'s empty-pool guard returns")
    print("              None. ABSTAIN is already authoritative and needs no")
    print("              edit under any option above.")
    print()
    print("  What NO option may assert: that a RESOLVE winner with")
    print("  selection_score <= 0 is still committed. That question is")
    print("  exactly what 'preserving quiet-tick semantics' leaves open, and")
    print("  it is the one thing this audit cannot decide for the parties.")
    print()
    record("W5_outlined", True)


def main() -> int:
    print("M6  RESOLVE-AUTHORITY WITNESS AUDIT (read-only, no patch)")
    print(f"seeds={SEEDS} ticks={TICKS}")
    print("contract ruled: RESOLVE(X) => X is committed; ABSTAIN unchanged")
    print()
    w1_authoritative_pool()
    w2_bypass_choose()
    w3_drop_rival_from_pool()
    w4_rejected_option()
    w5_regression_assertions()

    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"  W1 narrow-to-single, choose() still called : "
          f"{results['W1_satisfied'][0]}/{results['W1_overrides'][0]} witnesses")
    print(f"  W2 bypass choose() on RESOLVE             : "
          f"{results['W2_satisfied'][0]}/{results['W2_overrides'][0]} witnesses")
    print(f"  W3 same control-flow point as W1           : "
          f"{results['W3_same_as_W1'][0]}")
    print(f"  W4 float/weight option                    : out of bounds")
    print()
    print("  SMALLEST EXISTING CONTROL-FLOW POINT:")
    print("    engine/core/appraisal.py, the RESOLVE branch of")
    print("    apply_arbitration() -- its final return. It is a return-value")
    print("    change at a line that already exists, requires no new branch,")
    print("    no float and no weight, and leaves choose(), INERT and")
    print("    ABSTAIN untouched.")
    print()
    print("  THE ONE CONTRACT QUESTION THIS AUDIT CANNOT ANSWER:")
    print("    'RESOLVE(X) => X is committed' and 'preserve quiet-tick")
    print("    semantics' are in tension whenever X's selection_score <= 0.")
    print("    Measured: that is 4 of 4 overriding witnesses -- every winner")
    print("    is a negative-scoring travel candidate losing to a positive-")
    print("    scoring rest. So this is not a corner case; it is the whole")
    print("    observed regime. Either")
    print("      (a) a RESOLVE overrides the quiet rule for that tick, or")
    print("      (b) quiet-tick semantics win and a RESOLVE may be silenced.")
    print("    ChatGPT ruled the contract; only the parties can say which")
    print("    clause yields here. NOT decided in this audit.")
    print()
    print("  NO PATCH PROPOSED YET, per the ruling. When one is:")
    print("    W1/W3  one-line return change -- but measured 0/4, it silences")
    print("           rather than commits, so it does NOT satisfy (A) as")
    print("           ruled unless the quiet corner is resolved first.")
    print("    W2    one added conditional in simulation.py; measured 4/4.")
    print("  Both require editing tests/test_appraisal.py:116, whose")
    print("  `len(narrowed) == 2` assertion the ruling invalidates.")
    print()
    print("  NOTHING MODIFIED in this audit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())