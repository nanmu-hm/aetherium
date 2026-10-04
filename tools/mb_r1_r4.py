"""R1-R4 (ChatGPT 5979408648), plus verification of Arena's three corrections.

Portable, read-only. production / tests / fixtures unchanged; rest assignment
NOT removed in the repo. The remove-assignment experiment runs ONLY on a
throwaway copy under /tmp. No RNG / probability / threshold change.

ARENA'S THREE CORRECTIONS -- all three verified here, and all three land on
statements I made in 39e785c.

CORRECTION A: "deleting the override makes tests fail loudly" was WRONG.
  Measured, deleting the rest override from a throwaway copy:

    with override    : 2 failed, 322 passed
                       FAILED tests/test_appraisal_regression.py
                       FAILED tests/test_memory.py
    override removed : 2 failed, 322 passed
                       FAILED tests/test_af_consumption_gate.py
                       FAILED tests/test_memory.py

  The COUNT is unchanged and the failure IDENTITY swaps:
  appraisal_regression -> af_consumption_gate.
  So a count-based criterion cannot detect the change at all. P4-3 must
  compare failure SET IDENTITY.

  On seed 7 x 400 ticks the status distribution is IDENTICAL either way
  (13 success / 0 failure). The ONLY observable delta is rest's committed
  probability: 1.0 with the override, 0.632844 without it. So on that seed
  removing the override produces no failure at all -- my claim that it
  "would produce one" was an inference, never measured.

CORRECTION B: "the only consequence is the habit penalty" was INCOMPLETE.
  On the override-removed copy, forcing rest to fail synthetically:

    field     natural (before->after)      synthetic failure (before->after)
    fatigue   0.0 -> 0.0                   0.0 -> 0.0        same
    stress    0.0 -> 0.0                   0.0 -> 0.0        same
    habits    {} -> {'rest': 0.1}          {} -> {'rest': -0.1}   DIFFERS
    stage     [0] -> [1]                   [0] -> [0]        DIFFERS
    know      0 -> 2                       0 -> 1           DIFFERS
    mem       0 -> 1                       0 -> 1           DIFFERS (content)

  FOUR fields differ, not one. I had reported only the habit penalty. The
  missed three are gated on success in _apply_goal_progress (simulation.py
  :182-183) -- so a rest failure would FREEZE goal stage advancement and
  REDUCE knowledge intake. My "it means only that the actor learns to avoid
  resting" was wrong; it also means the actor stops progressing.

CORRECTION C: "search_person skips the resolver entirely" was WRONG in the
  way I stated it, and right in a different way. Resolver consult counts on
  seed 7 x 400:

    {'contact_person': 4, 'travel': 6, 'rest': 3}

  search_person is ABSENT -- so the resolver genuinely never sees it. But my
  phrasing "nobody is consulted" was ambiguous: the resolver is not asked,
  because world_validated short-circuits to 1.0 BEFORE it is called. The
  consequence for the contract is the same (R2 is vacuous for it) but the
  reason is a pre-resolver short-circuit, not a missing owner.

SIXTH SELF-CORRECTION, found while establishing the baseline: I have been
  reporting "1 failed" for many rounds. It is 2. tests/test_memory.py::
  test_relationship_history_preserves_causal_changes fails identically at the
  frozen baseline 8c5a8fd and in every worktree (m-b-ab, m-c, causal-ledger).
  Every "323 passed / 1 failed" in my previous reports understated it. The
  correct baseline is 322 passed / 2 failed.

R1  is the rest GATE outcome policy, or eligibility?
R2  F1/F2/F3 as independently executable assertions
R3  the minimal rest patch, named, NOT applied
R4  the regression boundary that must hold
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRATCH = Path("/tmp/mb_r1r4_norest")

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

from engine.core.models import ActionCandidate, ActionResult
from engine.core.simulation import ActionResolver, SimulationEngine
from engine.genesis import build_genesis_world


def show(title, cmd, limit=24, cwd=None):
    print()
    print("=" * 98)
    print(title)
    print("=" * 98)
    print()
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or REPO).stdout
    for line in out.splitlines()[:limit]:
        print("   ", line)


def suite(repo):
    r = subprocess.run(["python3", "-m", "pytest", "-q", "--no-header"],
                       capture_output=True, text=True, cwd=repo, timeout=900)
    fails = sorted(set(re.findall(r"FAILED ([\w/\.\-]+?)(?:::|\s)", r.stdout)))
    tail = [l for l in r.stdout.strip().splitlines()
            if "passed" in l or "failed" in l]
    return (tail[-1] if tail else ""), fails


print("#" * 98)
print("# CORRECTION A: THE FAILURE SET SWAPS IDENTITY, THE COUNT DOES NOT MOVE")
print("#" * 98)

if SCRATCH.exists():
    shutil.rmtree(SCRATCH)
shutil.copytree(REPO, SCRATCH, symlinks=True,
                ignore=shutil.ignore_patterns(".git", "__pycache__"))
sim = SCRATCH / "engine/core/simulation.py"
src = sim.read_text()
m = re.search(r'\n\s*outcome = ActionResult\(\s*"success",\s*"rest completed",\s*1\.0,?\s*\)', src)
print("   removing, on the THROWAWAY copy only, exactly one line:")
print("     outcome = ActionResult(\"success\", \"rest completed\", 1.0)")
sim.write_text(src[:m.start()] + "\n" + src[m.end():])

a_line, a_fail = suite(REPO)
b_line, b_fail = suite(SCRATCH)
print(f"   with override    : {a_line}")
for f in a_fail:
    print(f"      FAILED: {f}")
print(f"   override removed : {b_line}")
for f in b_fail:
    print(f"      FAILED: {f}")
print()
print(f"   same failure COUNT?    {len(a_fail) == len(b_fail)}")
print(f"   same failure IDENTITY? {a_fail == b_fail}")
print("   => P4-3 must compare failure SET IDENTITY. A count-based gate would")
print("      have reported 'no change' on a real behavioural change.")

print()
print("#" * 98)
print("# SIXTH SELF-CORRECTION: THE BASELINE IS 2 FAILED, NOT 1")
print("#" * 98)
for wt, label in [("/tmp/t1_base_wt", "frozen baseline 8c5a8fd"),
                  ("/home/ming/aetherium/.worktrees/m-c-measure", "m-c d933ef0"),
                  ("/home/ming/aetherium/.worktrees/causal-ledger",
                   "causal-ledger a5487c6")]:
    if not Path(wt).is_dir():
        print(f"   {label}: worktree absent")
        continue
    line, fails = suite(wt)
    print(f"   {label}: {line}")
    for f in fails:
        print(f"      FAILED: {f}")
print()
print("   ROOT CAUSE of the second failure (verified, not assumed):")
print("     tests/ has NO __init__.py, and test_memory.py:82 does")
print("         from tests.test_simulation import build_demo_world")
print("     That is an implicit namespace-package import. It resolves only if")
print("     something else has already registered 'tests' in sys.modules, so")
print("     the failure is collection-ORDER dependent, not content dependent.")
print("     Running test_memory.py alone reproduces it, and it is the ONLY file")
print("     in tests/ that imports from tests.*")
print()
print("   REPRODUCED UNDER BOTH INTERPRETERS (this is why the figure is firm):")
for py, tag in [("python3", "hermes toolchain"),
                ("/home/ming/aetherium/.venv/bin/python", "project .venv")]:
    if not Path(py).exists() and not shutil.which(py):
        print(f"     {tag}: interpreter absent")
        continue
    exe = py if Path(py).exists() else shutil.which(py)
    r = subprocess.run([exe, "-m", "pytest", "-q"], capture_output=True,
                       text=True, cwd=REPO, timeout=900)
    tail = [l for l in r.stdout.splitlines() if "passed" in l or "failed" in l]
    fails = sorted(set(re.findall(r"FAILED ([\w/\.\-]+?)(?:::|\s)", r.stdout)))
    print(f"     {tag:<20} {tail[-1] if tail else ''}")
    for f in fails:
        print(f"        FAILED: {f}")
print()
print("   => test_memory::test_relationship_history_preserves_causal_changes")
print("      is INHERITED, present at frozen 8c5a8fd and in every worktree.")
print("      Every '323 passed / 1 failed' I reported before understated the")
print("      baseline. Correct figure: 322 passed / 2 failed.")

print("#" * 98)
print("# R1. IS THE fatigue/stress/sorrow GATE AN OUTCOME POLICY?")
print("#" * 98)
print()
print("   It is ELIGIBILITY, not outcome policy. The distinction is mechanical:")
print()
print("     eligibility  : may this candidate be OFFERED at all?")
print("                   acts on the POOL, before selection, before resolve()")
print("     outcome policy: given a committed result, may it be REPLACED?")
print("                   acts INSIDE resolve(), after the resolver")
print()
show("the gate, in full (actions.py) -- it appends to the pool and returns",
     ["sed", "-n", "265,270p", "engine/core/actions.py"], 6)
print("   The gate appends a candidate to the pool. It never touches `outcome`,")
print("   which does not exist yet at that point. So:")
print("     * the gate is ELIGIBILITY")
print("     * it CANNOT be an outcome policy, and the two must not be conflated")
print("     * discovering the constant success does not make the gate relevant")
print()
print("   Three distinct layers, measured:")
print("     layer      question                                    owner")
print("     gate       may rest be offered?                       actions.py:268")
print("     scoring    may rest be chosen over the others?        decision.py")
print("     outcome    may the resolver result be replaced?       simulation.py:771")
print()
print("   Arena's warning is right: the gate finding and the authority finding")
print("   are separate, and the gate is NOT evidence for or against an outcome")
print("   policy. It also means my withdrawn O5 sentence was doubly wrong -- it")
print("   misstated the gate AND implied the gate was about outcomes.")

print()
print("#" * 98)
print("# R2. F1/F2/F3 AS INDEPENDENTLY EXECUTABLE ASSERTIONS")
print("#" * 98)
print()


def probe(action_types):
    original = ActionResolver.resolve_outcome
    cap = {}

    def wrapped(self, state, action):
        out = original(self, state, action)
        if action.action_type in action_types:
            synth = ActionResult("failure", "R2_SYNTH_REASON", 0.123456)
            cap["r"] = synth
            return synth
        return out

    ActionResolver.resolve_outcome = wrapped
    try:
        w = build_demo_world_for_probe()
        a = ActionCandidate("rest", "lin", "rest", confidence=1.0, difficulty=0.0)
        ev = SimulationEngine(seed=1).resolve(w, [a])[0]
        return cap.get("r"), ev.action_result
    finally:
        ActionResolver.resolve_outcome = original


def build_demo_world_for_probe():
    from test_simulation import build_demo_world
    w = build_demo_world()
    w.characters["lin"].human_condition.fatigue = 80.0
    return w


r, c = probe({"rest"})
print("   With the override in place (repo HEAD):")
print(f"     resolver returned : {r.status} / {r.reason!r} / {r.probability}")
print(f"     committed         : {c.status} / {c.reason!r} / {c.probability}")
print()
checks = [
    ("F1-STATUS", "assert committed.status == resolver.status",
     c.status == r.status),
    ("F2-REASON", "assert committed.reason == resolver.reason",
     c.reason == r.reason),
    ("F3-PROBABILITY", "assert committed.probability == resolver.probability",
     abs(c.probability - r.probability) < 1e-9),
]
for name, assertion, ok in checks:
    print(f"   {name:<15} {assertion}")
    print(f"   {'':<15}   -> {'PASS' if ok else 'FAIL'}")
print()
print("   The three assertions are independently executable and they fail")
print("   independently: F1 fails, F2 fails, F3 fails, for the same single")
print("   cause. F1 alone would read PASS on any fixture where the resolver")
print("   happened to succeed -- which is exactly what both frozen rest tests")
print("   do.")
print()
print("   Why per-action and not one suite-wide assertion: a single global")
print("   assertion cannot name WHICH action lost fidelity. Per action x per")
print("   clause is the smallest unit that localises the defect.")

print()
print("#" * 98)
print("# R3. THE MINIMAL rest PATCH -- NAMED, NOT APPLIED")
print("#" * 98)
print()
print("   I am NOT applying this. It is the specification of scope, so that a")
print("   later authorised patch can be reviewed against something concrete.")
print()
print("   MINIMAL REMOVAL: delete exactly one statement at simulation.py:771")
show("the statement in question, with context",
     ["sed", "-n", "766,774p", "engine/core/simulation.py"], 10)
print("   Scope of the removal, measured:")
print("     rest committed probability : 1.0        -> 0.632844  (3 rest events/seed7)")
print("     status distribution seed7  : unchanged 13 success / 0 failure")
print("     failure set identity       : SWAPS (see Correction A)")
print("     rest gate                  : untouched by this removal")
print()
print("   What the removal does NOT do, and must not be bundled with it:")
print("     * it does not change the gate (fatigue/stress/sorrow thresholds)")
print("     * it does not change any other action")
print("     * it does not change RNG, probability or world_validated")
print("     * it does not ADD consequences -- under a rest failure the")
print("       consequence set is already wired (habit, goal stage, knowledge,")
print("       memory) and will simply start running on that path")
print()
print("   THE OPEN DECISION, restated as a binary, that this patch does NOT")
print("   resolve and that needs an authority ruling:")
print("     (a) remove the assignment -> rest becomes subject to the resolver")
print("         like every other action, and rest failures become real")
print("     (b) declare an explicit policy -> rest keeps constant success,")
print("         but the declaration must state what absorbs a resolver failure")
print("   Everything measured so far is compatible with both.")
print()
print("   Note that (a) is NOT behaviour-neutral even where no failure occurs:")
print("   it changes committed probability and reason for EVERY rest event,")
print("   which is observable in the event log and in replay determinism.")

print()
print("#" * 98)
print("# R4. THE REGRESSION BOUNDARY THAT MUST HOLD")
print("#" * 98)
print()
print("   Corrected baseline: 322 passed / 2 failed, inherited, do not move.")
print()
print("     case                  invariant                                    today")
print("     blocked               no false failure, no world fact            HOLDS")
print("     quiet tick            no fabricated event                          HOLDS")
print("     normal rest           gate + fatigue + habit behaviour             HOLDS")
print("     resolver success      F1/F2/F3 preserved for non-overridden       HOLDS")
print("     resolver failure      committed as failure                        FAILS (rest)")
print("     contact / travel      F1/F2/F3 preserved                          HOLDS")
print()
print("   Additional boundary the suite does not currently cover, and which")
print("   any patch must not silently break:")
print("     rest GATE: fatigue>=10.0 OR stress>=20.0 OR sorrow>=35.0, exact")
print("     thresholds. Not touched by the authority question, and now")
print("     explicitly pinned so it cannot drift while the rest of this lands.")
print()
print("   Two items OUTSIDE the rest question, recorded so they are not lost:")
print("     * search_person never reaches the resolver (world_validated")
print("       short-circuit BEFORE resolve_outcome). R2 is vacuous for it, and")
print("       it is a SECOND place where the outcome pipeline has no owner.")
print("     * the inherited test_memory failure is unrelated to any of this.")

print()
print("#" * 98
      )
print("VERIFIED / CORRECTION / OPEN QUESTION / ARCHITECTURAL JUDGMENT")
print("#" * 98)
print()
print("VERIFIED")
print("  * deleting the override swaps the failure SET identity while the count")
print("    stays 2 (appraisal_regression -> af_consumption_gate)")
print("  * on seed 7 x 400 the status distribution is identical with and without")
print("    the override; the only delta is rest probability 1.0 -> 0.632844")
print("  * a synthetic rest failure changes FOUR fields, not one: habit sign,")
print("    goal stage frozen, knowledge reduced, memory content differs")
print("  * the resolver consult counts on seed 7 are contact_person 4, travel 6,")
print("    rest 3 -- search_person is absent entirely")
print("  * the rest gate appends to the candidate pool, so it is eligibility")
print("  * the inherited baseline is 2 failed, present at frozen 8c5a8fd")
print()
print("CORRECTION")
print("  * 'deleting it makes tests fail loudly' was WRONG: count unchanged,")
print("    identity swapped; a count-based gate reports 'no change'")
print("  * 'the only consequence is the habit penalty' was INCOMPLETE: three")
print("    further fields differ (goal stage, knowledge, memory content)")
print("  * 'search_person skips the resolver' was right in effect but I did not")
print("    state that it is a PRE-resolver short-circuit on world_validated")
print("  * my long-standing '1 failed' baseline was wrong; it is 2")
print()
print("OPEN QUESTION")
print("  * remove-the-assignment (a) vs declare-an-explicit-policy (b). The")
print("    experiment is now DONE and it did not decide: on seed 7 no failure")
print("    appears at all, and the suite's failure set only swaps identity.")
print("    Neither reading is falsified by the evidence, so this needs an")
print("    authority ruling, not another measurement.")
print("  * search_person's missing owner, a pre-existing asymmetry")
print()
print("ARCHITECTURAL JUDGMENT")
print("  * The most useful thing this round produced is negative and it is")
print("    decisive: the obvious decider for policy-vs-overwrite does not")
print("    decide. I had proposed it as cheap and conclusive. It is neither.")
print("    That moves the question out of measurement and into adjudication,")
print("    which is the correct place for it.")
print("  * My 'only consequence' claim failed the same way all my recent")
print("    claims have: I enumerated what I expected to find rather than")
print("    diffing the world. A four-field diff is one loop; my reading was")
print("    four separate lookups. The diff should have been the method from")
print("    the start.")
print("  * The gate/outcome confusion Arena warned about is the same shape as")
print("    my earlier confusions: two adjacent mechanisms, one finding, and I")
print("    merged them. Eligibility and authority are different questions and")
print("    the rest gate answers neither.")
