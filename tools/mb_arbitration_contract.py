"""M5 -- contract audit: which arbitration statement is actually supported?

READ-ONLY. Answers ChatGPT 5985662549. Nothing is modified: not
apply_arbitration(), not choose(), not weights, not recall, not any
production code, not any test.

The contradiction, stated once so the evidence can be lined up against it:

  (A) "the side with the live EvidenceRecord WINS the local tie"
      -- engine/core/appraisal.py, arbitrate() docstring
  (B) "the kernel STILL RUNS ITS OWN ARGMAX on exactly this
       2-candidate set, UNCHANGED MECHANICS"
      -- engine/core/appraisal.py, apply_arbitration() docstring

This audit does NOT decide which yields. It establishes, from the repository
alone, what each side would have to mean, and which of them the existing
tests, types and callers actually pin down.

Method: every claim below is anchored to a file:line, and the four
RESOLVE-over-top1 witnesses are re-run mechanically rather than asserted.

Usage:  python3 tools/mb_arbitration_contract.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine.core.appraisal as ap  # noqa: E402
from engine.core.actions import generate_action_pool  # noqa: E402
from engine.core.models import ArbitrationResult  # noqa: E402
from engine.core.simulation import SimulationEngine  # noqa: E402
from engine.genesis import build_genesis_world  # noqa: E402

SEEDS = (1, 2, 3, 7, 42)
TICKS = 200
ACTORS = ("rui", "yan")

results: dict[str, list] = {}


def record(key: str, value) -> None:
    results.setdefault(key, []).append(value)


def _line(path: str, needle: str) -> str:
    """Return 'file:lineno' for the first line containing needle."""
    repo = Path(__file__).resolve().parent.parent
    for i, ln in enumerate((repo / path).read_text(encoding="utf-8").splitlines(), 1):
        if needle in ln:
            return f"{path}:{i}"
    return f"{path}:(not found)"


# ================================================================ C1
def c1_call_sites() -> None:
    """Who calls arbitration at all, and with what expectations?"""
    print("=" * 78)
    print("C1  CALL SITES AND THE DEFAULT")
    print("=" * 78)
    print()
    print("  Single production call site:")
    print(f"    {_line('engine/core/simulation.py', 'if self.use_arbitration and pool:')}")
    print(f"      -> build_appraisals -> arbitrate -> apply_arbitration")
    print(f"      -> pool = apply_arbitration(pool, arbitration, evaluations)")
    print(f"      -> then UNCONDITIONALLY: choose(state, pool, allow_quiet=True)")
    print()
    print("  Two facts that constrain any contract:")
    print()
    print(f"  1. DEFAULT IS OFF. use_arbitration defaults to False at")
    print(f"     {_line('engine/core/simulation.py', 'use_arbitration: bool = False,')}")
    print("     So every other test in the suite (causal_ledger, mc_stagnation,")
    print("     outcome_policy_authority) runs with the layer OFF and is")
    print("     unaffected by either side of this contradiction.")
    print()
    print("  2. THERE IS NO FLOAT FIELD. ArbitrationResult carries no scalar:")
    print(f"     {_line('engine/core/models.py', 'This type carries NO float field')}")
    print("     and that is asserted by")
    print(f"     {_line('tests/test_appraisal.py', 'def test_arbitration_result_has_no_float_field')}")
    print("     => neither side may be implemented by adding a utility bonus.")
    print("        The ONLY available channels are: narrow the pool, or bypass")
    print("        choose()'s ranking. That is the whole design space.")
    print()
    record("C1_default_off", True)


# ================================================================ C2
def c2_statement_a() -> None:
    """What would (A) 'wins the local tie' have to mean?"""
    print("=" * 78)
    print("C2  STATEMENT (A): 'THE SIDE WITH THE LIVE EvidenceRecord WINS")
    print("    THE LOCAL TIE'")
    print("=" * 78)
    print()
    print("  Anchors:")
    print(f"    {_line('engine/core/appraisal.py', 'wins the')}")
    print(f"    {_line('engine/core/appraisal.py', 'RESOLVE -> the side with the Distinguishable live EvidenceRecord wins the')}")
    print()
    print("  MINIMUM CONTRACT (A) IMPLIES:")
    print("    A1. When arbitrate() returns RESOLVE with candidate_id = X,")
    print("        the committed action MUST be X.")
    print("    A2. 'wins' is not satisfied by X merely SURVIVING narrowing.")
    print("        If the kernel can still select the rival, X did not win.")
    print("    A3. Therefore either the narrowed pool must exclude the rival,")
    print("        or choose() must be bypassed for that tick.")
    print("    A4. A4 corollary: ABSTAIN (pool -> empty -> quiet tick) is")
    print("        already authoritative, because an empty pool leaves")
    print("        choose() nothing to rank. So the SAME layer is")
    print("        authoritative in ABSTAIN and non-authoritative in RESOLVE,")
    print("        which is internally inconsistent within one function.")
    print()
    print("  SUPPORTING EVIDENCE FOR (A):")
    print(f"    {_line('engine/core/models.py', 'the named candidate')}")
    print("      ArbitrationResult docstring: RESOLVE = 'the named candidate's")
    print("      evidence distinguishes it; it survives the pool-narrowing step")
    print("      and the kernel executes it through its normal path.'")
    print("      -- note this sentence is ITSELF ambiguous: 'survives the")
    print("      narrowing' is satisfied by the current code, while 'the")
    print("      kernel executes it' is NOT.")
    print()
    print("  EVIDENCE AGAINST (A) / FOR (B):")
    print("    NONE found in code. (A) is asserted only in docstrings.")
    print()
    record("C2_A_min_contract", 4)


# ================================================================ C3
def c3_statement_b() -> None:
    """What would (B) 'kernel re-runs its own argmax' have to mean?"""
    print("=" * 78)
    print("C3  STATEMENT (B): 'THE KERNEL STILL RUNS ITS OWN ARGMAX ...")
    print("    UNCHANGED MECHANICS'")
    print("=" * 78)
    print()
    print("  Anchors:")
    print(f"    {_line('engine/core/appraisal.py', 'still runs')}")
    print(f"    {_line('engine/core/appraisal.py', 'the kernel still runs its own argmax on exactly this')}")
    print()
    print("  MINIMUM CONTRACT (B) IMPLIES:")
    print("    B1. apply_arbitration's ONLY effect is to REDUCE the candidate")
    print("        set. It never selects.")
    print("    B2. 'unchanged mechanics' = choose() keeps full authority over")
    print("        the final pick, including its utility ordering.")
    print("    B3. Therefore a RESOLVE verdict is a CONSTRAINT ('keep these")
    print("        two in contention'), not a SELECTION ('pick this one').")
    print("    B4. Under (B), narrowing to [winner, utility_runner_up] is")
    print("        correct and complete: the winner is already IN the set, so")
    print("        the set is exactly 'the two in tension'.")
    print("    B5. Under (B), ON and OFF arms being bit-identical is NOT a bug")
    print("        -- it is the expected consequence of a constraint that the")
    print("        kernel already satisfies on its own.")
    print()
    print("  SUPPORTING EVIDENCE FOR (B) -- and this is the strongest in the")
    print("  repository, because it is a TEST, not a comment:")
    print()
    print(f"    {_line('tests/test_appraisal.py', 'def test_apply_arbitration_resolve_narrows_to_top2')}")
    print("      asserts, for a RESOLVE verdict:")
    print("        len(narrowed) == 2")
    print("        result.candidate_id IN {narrowed}")
    print("        each narrowed candidate's evaluate() is UNCHANGED")
    print("      It asserts MEMBERSHIP and NO-SCORE-MUTATION. It never asserts")
    print("      that the winner is chosen. Under statement (A) this test is")
    print("      INCOMPLETE; under statement (B) it is EXACTLY the contract.")
    print()
    print("  AND THE MODULE DOCSTRING OF THAT TEST FILE:")
    print(f"    {_line('tests/test_appraisal.py', 'no longer holds by design')}")
    print("      'Phase 4 wires the actual pool-narrowing into")
    print("       generate_candidates; the original shadow-inert assertion")
    print("       (use_arbitration=True == use_arbitration=False) NO LONGER")
    print("       HOLDS BY DESIGN.'")
    print("      => the suite EXPLICITLY expects arbitration to become")
    print("         observable in behaviour. Statement (B) predicts it never")
    print("         becomes observable. The test file's stated intent and")
    print("         statement (B) are in direct conflict.")
    print()
    print("  AGAINST (B):")
    print("    tests/test_appraisal_regression.py::")
    print("    test_extract_seed1_divergence_traces REQUIRES at least one")
    print("    tick where ON and OFF diverge. Under (B) as implemented, that is")
    print("    unreachable -- which is why that inherited test fails.")
    print()
    record("C3_B_min_contract", 5)


# ================================================================ C4
def c4_witnesses() -> None:
    """Re-run every RESOLVE-over-top1 case mechanically."""
    print("=" * 78)
    print("C4  THE WITNESSES, RE-RUN MECHANICALLY")
    print("=" * 78)
    print()
    print("  For every tick where arbitrate() returns RESOLVE and the verdict")
    print("  disagrees with the utility top-1, record whether the committed")
    print("  action matches the verdict.")
    print()
    rows = []
    totals = {"resolve": 0, "override": 0, "committed_matches": 0,
              "committed_differs": 0}
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
                if res.kind == "resolve":
                    totals["resolve"] += 1
                if res.kind != "resolve":
                    continue
                top1 = sorted(evs, key=lambda e: e.utility, reverse=True)[0]
                if res.candidate_id == top1.action_id:
                    continue
                totals["override"] += 1
                narrowed = ap.apply_arbitration(pool, res, evs)
                pick, _ = k.choose(world, narrowed, allow_quiet=True)
                committed = pick.id if pick else None
                if committed == res.candidate_id:
                    totals["committed_matches"] += 1
                    kind = "A satisfied"
                elif committed is None:
                    # choose() took its allow_quiet path: the winner's
                    # selection_score was <= 0. That is a THIRD outcome,
                    # distinct from "the rival was chosen" -- reporting it
                    # as the same violation would overstate the case.
                    totals["committed_quiet"] = totals.get(
                        "committed_quiet", 0) + 1
                    kind = "QUIET (not a rival pick)"
                else:
                    totals["committed_rival"] = totals.get(
                        "committed_rival", 0) + 1
                    kind = "RIVAL chosen"
                rows.append((seed, world.tick, cid, res.candidate_id,
                             top1.action_id, committed,
                             [c.id for c in narrowed], kind))

    print(f"  RESOLVE verdicts total                    : {totals['resolve']}")
    print(f"  of which OVERRIDE the utility top-1        : {totals['override']}")
    print(f"  committed == verdict            (A holds)   : "
          f"{totals['committed_matches']}")
    print(f"  committed == the REJECTED rival           : "
          f"{totals.get('committed_rival', 0)}")
    print(f"  committed == None (quiet tick)            : "
          f"{totals.get('committed_quiet', 0)}")
    print()
    for seed, tick, cid, verdict, top1, committed, narrowed, kind in rows:
        print(f"    seed{seed} t{tick} {cid}")
        print(f"       verdict (A says commit this) : {verdict}")
        print(f"       utility top-1 (B re-selects) : {top1}")
        print(f"       actually committed           : {committed}")
        print(f"       narrowed pool                : {narrowed}")
        print(f"       outcome: {kind}")
    print()
    if totals["override"] and totals["committed_matches"] == 0:
        print("  => Under contract (A), NO overriding verdict reached the")
        print("     committed action. Precise breakdown:")
        print(f"       {totals.get('committed_rival', 0)} chose the candidate the")
        print("         verdict had just REJECTED -- this is the direct")
        print("         contradiction, and it is the case that makes (B)")
        print("         self-defeating.")
        print(f"       {totals.get('committed_quiet', 0)} produced a QUIET tick")
        print("         (choose()'s allow_quiet path, because the winner's")
        print("         selection_score <= 0). That also violates (A), but by")
        print("         a DIFFERENT mechanism: not 'the rival won' but 'nothing")
        print("         was executed'. Reported separately on purpose --")
        print("         collapsing these two would overstate the evidence.")
        print("     So (A) is not merely imprecisely worded: as implemented it")
        print("     is never satisfied in any of these cases.")
    print()
    record("C4_override", totals["override"])
    record("C4_A_satisfied", totals["committed_matches"])


# ================================================================ C5
def c5_inert_and_abstain() -> None:
    """The two verdicts that are NOT in conflict, for contrast."""
    print("=" * 78)
    print("C5  CONTRAST: THE VERDICTS THAT ALREADY WORK")
    print("=" * 78)
    print()
    print("  INERT  -> pool returned unchanged. kernel_pick == baseline_pick")
    print(f"    asserted at {_line('tests/test_appraisal.py', 'assert kernel_pick == baseline_pick')}")
    print("    This is the ONE arm where ON and OFF are MEANT to be identical,")
    print("    and the test says so explicitly.")
    print()
    print("  ABSTAIN -> pool -> [] -> choose()'s existing empty-pool guard.")
    print(f"    asserted at {_line('tests/test_appraisal.py', 'assert narrowed == []')}")
    print("    This IS authoritative: an empty pool cannot be ranked, so the")
    print("    verdict's consequence (no action) necessarily holds.")
    print()
    print("  So within one function, arbitrate():")
    print("    INERT   -> no authority needed, pool passes through")
    print("    ABSTAIN -> FULL authority (empty pool forces the outcome)")
    print("    RESOLVE -> NO authority (kernel re-ranks the two and may pick")
    print("               the candidate the verdict rejected)")
    print()
    print("  ABSTAIN and RESOLVE are the two CROSS-MOTIVATION verdicts, i.e.")
    print("  the two the layer exists to produce. One is authoritative and one")
    print("  is not, with nothing in the design distinguishing them.")
    print()
    record("C5_abstain_authoritative", True)


def main() -> int:
    print("M5  ARBITRATION CONTRACT AUDIT (read-only)")
    print("establishes what (A) and (B) each imply; decides NEITHER")
    print()
    c1_call_sites()
    c2_statement_a()
    c3_statement_b()
    c4_witnesses()
    c5_inert_and_abstain()

    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"  C1 arbitration default                : OFF")
    print(f"  C2 (A) minimum contract clauses       : {results['C2_A_min_contract'][0]}")
    print(f"  C3 (B) minimum contract clauses       : {results['C3_B_min_contract'][0]}")
    print(f"  C4 RESOLVE overriding utility top-1   : {results['C4_override'][0]}")
    print(f"  C4 committed == verdict (A satisfied) : {results['C4_A_satisfied'][0]}")
    print()
    print("  WHAT IS PINNED BY THE REPOSITORY, WITHOUT JUDGEMENT:")
    print("    - test_appraisal.py::test_apply_arbitration_resolve_narrows_to_top2")
    print("      asserts membership + no score mutation. That pins (B).")
    print("    - test_appraisal.py module docstring says the shadow-inert")
    print("      property 'no longer holds BY DESIGN'. That contradicts (B)")
    print("      and is the strongest single piece of intent evidence.")
    print("    - test_appraisal_regression.py requires ON/OFF divergence.")
    print("      Unreachable under (B) as implemented. This is the inherited")
    print("      failure, and it is consistent with (A).")
    print("    - (A) is asserted ONLY in docstrings; no test asserts it.")
    print()
    print("  SO THE DISAGREEMENT IS NOT SYMMETRIC, and I state that as fact,")
    print("  not as a recommendation:")
    print("    (B) has direct test-level support for its letter.")
    print("    (A) has the stated design intent, the regression test, and the")
    print("    fact that ABSTAIN -- its sibling -- is already authoritative.")
    print("    Neither is adopted here. ChatGPT adjudicates which yields.")
    print()
    print("  FIVE-RUNG TERMINOLOGY PRESERVED, unchanged from M4:")
    print("    existence / recall-set / appraisal / selection-score /")
    print("    final argmax. Rungs 1-4 are evidence that memory reaches the")
    print("    score; rung 5 (0/46) is the only one that would be an agency")
    print("    change. Nothing here calls 1-4 an agency change.")
    print()
    print("  location_absent: remains UNKNOWN / dormant under the established")
    print("  boundary. Not touched by this audit.")
    print()
    print("  NOTHING MODIFIED: no apply_arbitration, no choose(), no weights,")
    print("  no recall, no production code, no test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())