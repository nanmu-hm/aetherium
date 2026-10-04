"""Report mutation results by TEST IDENTITY, not by count.

Arena (5979...) is right about both of these:

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
    for pc in glob.glob(str(MUT / "**/__pycache__"), recursive=True):
        shutil.rmtree(pc, ignore_errors=True)
    r = subprocess.run(
        ["python3", "-B", "-m", "pytest", "-q",
         "tests/test_outcome_policy_authority.py"],
        capture_output=True, text=True, cwd=MUT, timeout=900)
    fails = [l.split("::")[1].split()[0] for l in r.stdout.splitlines()
             if l.startswith("FAILED")]
    tail = [x for x in r.stdout.splitlines() if "passed" in x or "failed" in x]
    print(f"\n{tag}")
    print(f"    {tail[-1].strip() if tail else '(no summary)'}")
    print(f"    caught by {len(fails)} test(s):")
    for f in sorted(fails):
        print(f"       - {f}")
    if not fails and not tag.startswith("unmutated"):
        print("       (NOTHING CAUGHT IT -- the mutation is UNOBSERVED)")
    return set(fails)


print("=" * 96)
print("BASELINE")
print("=" * 96)
fresh()
run("unmutated tree (expected: nothing fails -- this is the control)")

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
        results[tag] = run(tag)

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
    results["F  habit failure-penalty disabled (the habit fn only)"] = run(
        "F  habit failure-penalty disabled (the habit fn only)")
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
