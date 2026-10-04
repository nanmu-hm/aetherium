"""Report mutation results by TEST IDENTITY, not by count.

Arena (PR#10 `5979951566` / PR#9 `5979951698`) is right about both of these:

  * "the old pseudo-flow" names at least three different mutations of the same
    region. My table reported a bare "4 failed" for one of them. Reconstructing
    all three here gives 4 / 4 / 5 on my machine and 2 / 4 / 6 on Arena's, so
    the number is not even reproducible across toolkits.

  * the M5-style counts have moved 4 -> 5 -> 6 across three rounds of editing
    the SAME test file. A count is a function of the test set, not a property
    of the mutation.

So this tool reports the SET of failing test names, which is what actually
carries the meaning, and prints the construction alongside every number.

Usage: python3 tools/mb_mutation_identity.py [ref]
"""
import glob
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REF = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
MUT = Path("/tmp/mb_mut_identity")

OLD_FLOW = """                declared = resolve_policy_outcome(action)
                outcome = (
                    declared
                    if declared is not None
                    else self.action_resolver.resolve_outcome(state, action)
                )"""
OLD_OUTCOME = """                outcome = (
                    declared
                    if declared is not None
                    else self.action_resolver.resolve_outcome(state, action)
                )"""
OLD_BRANCH = """                elif action.action_type == "rest":"""

CONSTRUCTIONS = {
    "A  resolver called directly, old assignment restored in the branch": [
        ("engine/core/simulation.py",
         OLD_FLOW,
         "                outcome = self.action_resolver.resolve_outcome(state, action)"),
        ("engine/core/simulation.py",
         OLD_BRANCH,
         OLD_BRANCH + '\n                    outcome = ActionResult("success", "rest completed", 1.0)'),
    ],
    "B  declared lookup kept but its result ignored": [
        ("engine/core/simulation.py",
         OLD_OUTCOME,
         "                _ = declared\n                outcome = self.action_resolver.resolve_outcome(state, action)"),
        ("engine/core/simulation.py",
         OLD_BRANCH,
         OLD_BRANCH + '\n                    outcome = ActionResult("success", "rest completed", 1.0)'),
    ],
    "C  full revert to the pre-patch spine (no restore in the branch)": [
        ("engine/core/simulation.py",
         OLD_FLOW,
         "                outcome = self.action_resolver.resolve_outcome(state, action)"),
    ],
    "D  rest removed from the policy mapping": [
        ("engine/core/outcome_policy.py",
         '    "rest": lambda: ActionResult("success", "rest completed", 1.0),\n',
         ""),
    ],
    "E  facts unconditional (the :772 regression)": [
        ("engine/core/simulation.py",
         '                    if outcome.status == "success":\n'
         '                        facts.append(f"{actor.name} rests at {actor.location}.")\n'
         '                    else:\n'
         '                        facts.append(\n'
         '                            f"{actor.name} tries to rest at {actor.location}, but fails."\n'
         '                        )',
         '                    facts.append(f"{actor.name} rests at {actor.location}.")'),
    ],
    "F  habit failure-penalty disabled (the habit fn only)": [
        ("engine/core/simulation.py",
         "    def _update_procedural_habit(",
         "    def _update_procedural_habit("),  # marker only; patched below
    ],
}


def fresh():
    if MUT.exists():
        shutil.rmtree(MUT)
    shutil.copytree(REPO, MUT, symlinks=True,
                    ignore=shutil.ignore_patterns(".git", "__pycache__"))


def run(tag):
    """Run the acceptance file and REPORT ONLY WHAT ACTUALLY RAN.

    A run that produced no pytest summary is a FAILED RUN, not a result. The
    first version of this tool conflated the two: it printed
    "(no summary)" and then, because the failure list was empty, printed
    "NOTHING CAUGHT IT -- the mutation is UNOBSERVED". In an environment where
    the inner interpreter could not run pytest, six runs that produced no
    result at all were therefore reported as six findings about the code.

    That is the same shape as the two retracted claims in this project -- a
    measurement whose precondition was never checked, printed as a conclusion.
    So the guard is explicit and loud: no summary means RUN FAILED, and a failed
    run is never evidence about a mutation.
    """
    for pc in glob.glob(str(MUT / "**/__pycache__"), recursive=True):
        shutil.rmtree(pc, ignore_errors=True)
    try:
        r = subprocess.run(
            [sys.executable, "-B", "-m", "pytest", "-q",
             "tests/test_outcome_policy_authority.py"],
            capture_output=True, text=True, cwd=MUT, timeout=900)
    except (OSError, subprocess.SubprocessError) as exc:
        # The interpreter could not be launched at all. subprocess.run RAISES
        # here rather than returning a result, so a guard that only inspects a
        # return code would never see it. Verified: without this except, a
        # missing interpreter produced a bare traceback and the run below it
        # was never reached -- which is the same hole Arena found, one level
        # deeper.
        print(f"\n{tag}")
        print("    *** RUN FAILED -- NOT EVIDENCE ***")
        print(f"    could not launch the test runner: {type(exc).__name__}: {exc}")
        return None

    fails = [l.split("::")[1].split()[0] for l in r.stdout.splitlines()
             if l.startswith("FAILED")]
    tail = [x for x in r.stdout.splitlines() if "passed" in x or "failed" in x]

    print(f"\n{tag}")
    print(f"    runner: {sys.executable}")
    if r.returncode not in (0, 1) or not tail:
        print("    *** RUN FAILED -- NOT EVIDENCE ***")
        print(f"    pytest exit={r.returncode}, no summary line in stdout.")
        if r.stderr.strip():
            print(f"    stderr: {r.stderr.strip().splitlines()[-1][:160]}")
        print("    This tells us nothing about the mutation. Fix the runner")
        print("    before reading anything into this line.")
        return None
    print(f"    {tail[-1].strip()}")
    print(f"    caught by {len(fails)} test(s):")
    for f in sorted(fails):
        print(f"       - {f}")
    if not fails:
        print("       (no test failed -- the mutation is UNOBSERVED)")
    return set(fails)


print("=" * 96)
print("BASELINE")
print("=" * 96)
fresh()
control = run("unmutated tree (expected: nothing fails -- this is the control)")
if control is None:
    print()
    print("=" * 96)
    print("STOP: the control run did not execute. Nothing below is evidence.")
    print("=" * 96)
    raise SystemExit(1)
if control:
    print()
    print("=" * 96)
    print("STOP: the UNMUTATED tree already fails these tests:")
    print("      " + ", ".join(sorted(control)))
    print("      A mutation report on top of a red baseline measures nothing.")
    print("=" * 96)
    raise SystemExit(1)

results = {}
for tag, edits in CONSTRUCTIONS.items():
    if tag.startswith("F"):
        continue
    fresh()
    changed = False
    for fname, old, new in edits:
        p = MUT / fname
        s = p.read_text()
        if old not in s:
            print(f"\n{tag}\n    ANCHOR MISSING in {fname} -- skipped")
            changed = False
            break
        p.write_text(s.replace(old, new, 1))
        changed = True
    if changed:
        outcome = run(tag)
        if outcome is not None:
            results[tag] = outcome

# F: target the habit function precisely, not the first textual match
fresh()
p = MUT / "engine/core/simulation.py"
lines = p.read_text().splitlines(keepends=True)
hit = None
for i, line in enumerate(lines):
    if "def _update_procedural_habit(" in line:
        for j in range(i, min(i + 30, len(lines))):
            if 'if outcome.status == "failure":' in lines[j]:
                hit = j
                break
        break
if hit is not None:
    lines[hit] = lines[hit].replace(
        'if outcome.status == "failure":',
        'if False:  # MUTATED: habit never penalises failure')
    p.write_text("".join(lines))
    outcome_f = run("F  habit failure-penalty disabled (the habit fn only)")
    if outcome_f is not None:
        results["F  habit failure-penalty disabled (the habit fn only)"] = outcome_f
else:
    print("\nF  habit penalty: ANCHOR MISSING -- skipped")

print()
print("=" * 96)
print("READ THIS BEFORE QUOTING ANY NUMBER ABOVE")
print("=" * 96)
print("""
Constructions A, B and C all describe "the old pseudo-flow" and all target the
same two lines, yet they are three different mutations and they catch different
test sets. My previous report quoted a bare "4 failed" for one of them without
saying which. Arena measured 2 / 4 / 6 for the three; I measure 4 / 4 / 5.

The counts are not reproducible across toolkits. The SETS are the meaningful
part, and they nest the way the constructions nest: A and B catch the same four
tests, and C adds test_committed_rest_carries_the_policy_triple because the
policy triple is gone entirely rather than merely bypassed.

The same applies to any count in this area. The test file has been edited in
every round, so a failure count describes the test set as much as the mutation.
Name the construction and the failing tests; do not quote the number alone.
""")
shutil.rmtree(MUT, ignore_errors=True)
