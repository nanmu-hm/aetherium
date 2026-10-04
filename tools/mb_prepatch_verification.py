"""Pre-patch verification: four Arena corrections, and a falsified premise in
the (a) ruling.

ChatGPT 5979580831 ruled (a): delete simulation.py:771, and authorised the
production patch. This tool does NOT implement it. It records why not.

THE RULING'S STATED REASON IS FACTUALLY FALSE.

ChatGPT's justification: "no evidence proves rest has an independent 'must
succeed regardless of the resolver' business semantic", and "keeping it would
require us to invent a 'rest always succeeds' rule out of thin air".

git history says otherwise. `git log -S 'rest completed'` has exactly one
commit, 3ad2b21 "Make goal progress and pressure state-driven", whose diff is:

    -                    if outcome.status == "success":
    -                        facts.append(f"{actor.name} rests at {actor.location}.")
    -                    else:
    -                        facts.append(f"{actor.name} tries to rest at {actor.location}, but fails.")
    +                    # Rest is a non-contestable biological/social action in this
    +                    # model: if it is available, it succeeds rather than rolling
    +                    # against an arbitrary success probability.
    +                    outcome = ActionResult("success", "rest completed", 1.0)
    +                    facts.append(f"{actor.name} rests at {actor.location}.")

The always-succeeds business semantic WAS written down, in that comment. A later
commit removed the comment and kept the assignment.

So all three of these hold:
    * "there is no declaration today"          -> TRUE
    * "keeping it means inventing a semantic"  -> FALSE, it was documented
    * "therefore (a) removes an accidental overwrite" -> it removes a REVOKED
      POLICY, which is a different act with a different justification

ARENA'S FOUR CORRECTIONS -- all four verified here.

A. The (a) ruling's second premise ("search_person is not consulted by the
   resolver, so R2 is vacuous for it because of a pre-resolver short-circuit")
   is WRONG. Resolver consult counts on seed 7 x 400, keyed by
   (action_type, metadata.event_action_type):

       ('travel', 'search_person'): 3
       ('travel', None):           3
       ('contact_person', None):   4
       ('rest', None):             3

   search candidates ARE consulted. My earlier "travel 6" was travel 3 PLUS
   search 3 -- I aggregated on action_type and then declared search absent from
   the aggregate. The short-circuit is inside probability(), which
   resolve_outcome CALLS:

       def probability(self, state, action):
           if action.metadata.get("world_validated"):
               return 1.0

   So it is a short-circuit on the PROBABILITY, inside the resolver, not a
   bypass of the resolver. The correct statement of the second case object is
   "four families pin probability to 1.0 via world_validated", not "search
   skips the resolver". This is the SECOND time I aggregated candidates by
   action_type and lost a distinction; the first was the C3 miscount.

B. The "322 passed / 2 failed" baseline I reported last round is WRONG, and it
   was an artefact of MY OWN HARNESS, not of the project. tests/ has no
   __init__.py and tests/test_memory.py:82 does
   `from tests.test_simulation import build_demo_world`, which is an implicit
   namespace-package import. When the parent process has already imported a
   package named `tests`, the child pytest inherits that binding and resolves
   it elsewhere. Measured:

     terminal,   `python3 -m pytest -q`             : 1 failed, 323 passed
     terminal,   project .venv `python -m pytest`  : 1 failed, 323 passed
     execute_code subprocess, same command         : 2 failed, 322 passed

   The difference is that inside the execute_code kernel `'tests' in
   sys.modules` is already True and the worktree path is injected twice into
   sys.path. So the TRUE baseline is 323 passed / 1 failed -- exactly what I
   reported for many rounds before I "corrected" it last round. My correction
   was an over-correction, caused by my own measurement harness.

   The uncomfortable lesson: I corrected a number using the same instrument
   that produced the wrong number.

   Also: that import was found by ME, not by Arena. Last round I credited
   Arena with it. Wrong attribution.

C. THE PATCH-BLOCKING DEFECT: after deleting the override, a rest FAILURE
   still records the success text. simulation.py:772 is unconditional inside
   the rest branch:

       outcome = ActionResult("success", "rest completed", 1.0)   # 771, deleted
       facts.append(f"{actor.name} rests at {actor.location}.")   # 772, unconditional

   In 3ad2b21 the facts append used to sit inside `if outcome.status ==
   "success": ... else: ... fails`, and the replacement flattened that guard.
   So deleting line 771 alone makes a failed rest write "Yan rests at
   river_town." into facts. Verified on the override-removed copy: forced rest
   failure commits status=failure and the rest branch's facts append is reached
   regardless of status.

   This is a real defect the patch would introduce and it needs its own
   decision. ChatGPT's scope forbids touching consequence, so I am not
   deciding it.

D. Mechanical acceptance input Arena supplied, recorded for the authorised
   patch: expected failure swap; committed rest failures 14 over 20x400;
   behavioural divergence on 10/20 seeds; events 245 -> 243; every rest event's
   reason and probability change; rng_state unchanged.

WHAT I AM DOING, AND NOT DOING

I am NOT implementing (a). Not because I prefer (b) -- that would be exactly
the unilateral technical position I am not allowed to take. Because the
authorisation's stated premise is contradicted by the repository, so acting on
it would mean implementing a decision whose stated reason is known to be
false. The decision itself may well still be (a); it just has to be made on
grounds that survive the history.

The minimum this needs from the arbitrators:
    1. Re-decide (a) vs (b) knowing the semantic WAS documented in 3ad2b21, and
       that (a) is therefore revoking a once-written policy.
    2. Rule on the facts line at :772, which the current scope excludes but the
       patch would expose.
    3. Pin the baseline as node-id SET plus runner invocation, not a count:
       `python3 -m pytest -q` -> 323 passed / 1 failed
       FAILED tests/test_appraisal_regression.py::test_extract_seed1_divergence_traces
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def show(title, cmd, limit=30, cwd=None):
    print()
    print("=" * 98)
    print(title)
    print("=" * 98)
    print()
    out = subprocess.run(cmd, capture_output=True, text=True,
                         cwd=cwd or REPO).stdout
    for line in out.splitlines()[:limit]:
        print("   ", line)


print("#" * 98)
print("# 1. THE RULING'S PREMISE vs GIT HISTORY")
print("#" * 98)
show("git log -S 'rest completed' -- the ONLY commit that introduced it",
     ["git", "log", "-S", "rest completed", "--oneline",
      "--", "engine/core/simulation.py"], 6)
show("that commit's diff",
     ["git", "show", "3ad2b21", "--", "engine/core/simulation.py"], 500)

print()
print("   READ THIS CAREFULLY. The always-succeeds business semantic was")
print("   WRITTEN DOWN in that comment. The ruling says keeping it would mean")
print("   inventing the rule from nothing. It was not invented from nothing.")
print()
print("   What survives of the ruling: 'there is no declaration TODAY' -- true.")
print("   What does not survive: 'no semantic evidence exists' -- false.")
print("   So (a) is not 'delete an accidental overwrite'. It is 'revoke a")
print("   policy that was documented and later un-documented'. Different act.")

print()
print("#" * 98)
print("# 2. CORRECTION A: search_person IS CONSULTED BY THE RESOLVER")
print("#" * 98)

probe = r'''
import sys, json
sys.path.insert(0, REPO)
from engine.core.simulation import ActionResolver, SimulationEngine
from engine.genesis import build_genesis_world
seen = {}
orig = ActionResolver.resolve_outcome
def wrap(self, state, action):
    key = (action.action_type,
           action.metadata.get("event_action_type") if action.metadata else None)
    seen[key] = seen.get(key, 0) + 1
    return orig(self, state, action)
ActionResolver.resolve_outcome = wrap
w = build_genesis_world(); w.timestamp = "0001-01-01T00:00:00"
e = SimulationEngine(seed=7, use_arbitration=False)
for _ in range(400):
    e.step(w)
ActionResolver.resolve_outcome = orig
print(json.dumps({str(k): v for k, v in sorted(seen.items(), key=lambda kv: str(kv[0]))},
                 indent=1))
'''
Path("/tmp/mb_prepatch_counts.py").write_text(
    "import sys\nREPO = sys.argv[1]\nsys.argv = [sys.argv[0]]\n" + probe)
print("   resolver consult counts, keyed by (action_type, metadata.event_action_type):")
print(subprocess.run([sys.executable, "/tmp/mb_prepatch_counts.py", str(REPO)],
                     capture_output=True, text=True, cwd=str(REPO)).stdout)
show("where the short-circuit actually lives",
     ["sed", "-n", "1308,1320p", "engine/core/simulation.py"], 14)
print("   => the short-circuit is inside probability(), which resolve_outcome")
print("      CALLS. search candidates ARE consulted; only their probability is")
print("      pinned. My 'travel 6' was travel 3 + search 3 -- I aggregated on")
print("      action_type and then declared search absent from the aggregate.")

print()
print("#" * 98)
print("# 3. CORRECTION B: THE 322/2 BASELINE IS MY HARNESS, NOT THE PROJECT")
print("#" * 98)
print("   tests/__init__.py exists:", (REPO / "tests/__init__.py").exists())
show("the coupling: the only tests/ file that imports from tests.*",
     ["grep", "-rn", "from tests\\.", "tests/"], 6)
print("   In THIS process, 'tests' already in sys.modules:", "tests" in sys.modules)
print("   sys.path entries mentioning this worktree:",
      sum(1 for p in sys.path if REPO.name in p))
print()
print("   Run `python3 -m pytest -q` from a clean shell for the real figure.")
print("   Measured there: 1 failed, 323 passed")
print("   FAILED tests/test_appraisal_regression.py::test_extract_seed1_divergence_traces")
print()
print("   Last round I 'corrected' 1 failed -> 2 failed using this same")
print("   contaminated harness. That correction was itself wrong, and it was")
print("   wrong because I used the instrument that produced the error to")
print("   adjudicate the error. The number before it was right all along.")

print()
print("#" * 98)
print("# 4. CORRECTION C: THE DEFECT THE PATCH WOULD INTRODUCE")
print("#" * 98)
show("the rest branch",
     ["sed", "-n", "768,775p", "engine/core/simulation.py"], 10)
print("   Line 771 is what the ruling authorises deleting.")
print("   Line 772 is UNCONDITIONAL. In 3ad2b21 it used to be guarded by")
print("   `if outcome.status == 'success' / else: ... but fails`. The")
print("   replacement flattened that guard.")
print()
print("   => deleting 771 alone makes a FAILED rest write")
print("      'Yan rests at river_town.' into facts.")
print("      Verified on the override-removed copy: forced rest failure")
print("      commits status=failure and the facts append is still reached.")

print()
print("#" * 98)
print("# VERIFIED / CORRECTION / OPEN QUESTION / ARCHITECTURAL JUDGMENT")
print("#" * 98)
print()
print("VERIFIED")
print("  * 3ad2b21 documented the always-succeeds semantic in a comment")
print("  * the (a) ruling's 'no semantic evidence' premise is contradicted")
print("  * search_person is consulted by the resolver; only its probability")
print("    is pinned, inside probability()")
print("  * the real baseline is 323 passed / 1 failed under a clean runner")
print("  * line 772 is unconditional and would record success on failure")
print()
print("CORRECTION")
print("  * my Correction C (search skips the resolver): wrong again")
print("  * my Correction last round (2 failed baseline): wrong, and caused by")
print("    my own harness")
print("  * my attribution of the test_memory import to Arena: wrong, it was me")
print("  * this is the second time I aggregated candidates by action_type and")
print("    lost a distinction the count depended on")
print()
print("OPEN QUESTION")
print("  * (a) vs (b) must be re-decided on grounds that survive the history")
print("  * what happens to line 772 once rest can fail")
print()
print("ARCHITECTURAL JUDGMENT")
print("  * The most serious error in this whole sequence is not any single")
print("    miscount. It is that I have been using inference where measurement")
print("    was available, then treating my own corrections as trustworthy")
print("    without re-running them under a different instrument. Two of the")
print("    last four corrections were themselves wrong, each because I trusted")
print("    the shape of the answer over the conditions under which I measured")
print("    it. A correction is not self-validating.")
print("  * The (a) decision may still be right. But a decision whose stated")
print("    reason is contradicted by the repository is not one anyone should")
print("    execute, and the history here is short enough to read.")
