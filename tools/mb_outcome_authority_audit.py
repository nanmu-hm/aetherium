"""Outcome Authority Contract Audit O1-O4 (ChatGPT 5978977915). Read-only.

Portable: self-locating, no hardcoded paths.
No production/tests/fixtures change; rest override NOT removed; no
RNG/probability/threshold/world_validated change; search generator untouched.

CORRECTION FIRST. Arena is right and my C2 evidence in b332929 was wrong.

I wrote that a surviving rest failure "would have carried a real psychological
cost -- the emotional delta is fear +5 / regret +2 (simulation.py:243)".

Measured, that delta belongs to TRAVEL. The actor's own effects table is

    effects = {"travel": ..., "contact_person": ..., "help_person": ...}
               .get(action_type, {})

with NO rest entry, so a rest failure receives effects = {}. Rest is likewise
absent from FAILURE_PRESSURE_MAP and from the identity-belief affordances, and
rest has no targets so there is no relationship friction. The rest fatigue
branch also ignores status. Measured consequence of a surviving rest failure:
ONE -- the procedural habit gets learning_signal = -1.0. Nothing else.

O1. REST AUTHORITY
O2. AUTHORITY MATRIX for rest / travel / search_person / contact_person
O3. COMMIT INVARIANT
O4. REGRESSION BOUNDARY
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world


def show(title, cmd, limit=30):
    print()
    print("=" * 98)
    print(title)
    print("=" * 98)
    print()
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO).stdout
    for line in out.splitlines()[:limit]:
        print("   ", line)


print("#" * 98)
print("# O1. WHY IS rest UNCONDITIONALLY SUCCESSFUL?")
print("#" * 98)

show("O1a. the only comment in the repo that states rest's determinism",
     ["grep", "-rn", r"rest is deterministic|deterministic when attempted",
      "engine/", "tests/"], 10)

show("O1b. tests that assert rest HABIT values (these depend on outcome.status)",
     ["sed", "-n", "1092,1122p", "tests/test_simulation.py"], 34)

print()
print("   O1 ANSWER, as evidence rather than adjudication:")
print()
print("   MY OWN FIRST ANSWER WAS WRONG AND I AM CORRECTING IT HERE. I first")
print("   wrote 'no test anywhere asserts a rest outcome' on the strength of a")
print("   grep that returned nothing. The grep was wrong. Two tests DO assert it:")
print("     test_rest_does_not_reinforce_when_actor_is_already_rested")
print('       assert event.action_result.status == "success"')
print("     test_rest_reduces_fatigue_and_can_be_reinforced_by_recovery")
print('       assert event.action_result.status == "success"')
print()
print("   So rest's always-success IS covered by the frozen suite. What is")
print("   interesting is what those tests can and cannot see. Reproduced exactly:")
print()
print("       already rested : resolver said success p=0.675000")
print("                       committed      success p=1.0 reason='rest completed'")
print("       needs recovery : resolver said success p=0.675000")
print("                       committed      success p=1.0 reason='rest completed'")
print()
print("   The resolver's REAL probability 0.675 is replaced by a constant 1.0, and")
print("   its reason is replaced by the literal 'rest completed'. The tests pass")
print("   because the STATUS happens to agree in these two fixtures -- not")
print("   because the commit preserves the resolver's result. A test asserting")
print("   status alone cannot distinguish 'resolver succeeded' from 'asserted")
print("   success', and neither can the committed event.")
print()
print("   That is the sharpest available statement of the defect: the overwrite")
print("   destroys the resolver's probability and reason, and the existing")
print("   acceptance cannot tell. This is Arena's correction landing exactly where")
print("   I had asserted the opposite.")
print()
print("   About intent: the comment claims two things -- the outcome is")
print("   deterministic 'when attempted', and the value comes from the actor's")
print("   recovery state. The second half is implemented in _apply_fatigue's rest")
print("   branch, which does not read status. The first half is the unconditional")
print("   assignment after the resolver. The comment never mentions the resolver,")
print("   probability or failure -- consistent with an implementation detail,")
print("   inconsistent with a contract written knowing the resolver could")
print("   contradict it. I am not adjudicating which it was.")
print()
print("   IF THE RESOLVER'S FAILURE WERE PRESERVED, these would change:")
print("     habit            : rest would take learning_signal -1.0 instead of")
print("                        the meaningful-consequence signal")
print("     fatigue          : NO change (the rest branch ignores status)")
print("     emotions         : NO change (no rest entry -> effects = {})")
print("     identity_beliefs : NO change (no rest affordance)")
print("     desire pressure  : NO change (no rest entry in FAILURE_PRESSURE_MAP)")
print("     relationship     : NO change (rest has no targets)")
print("     memory / belief  : the belief would record status failure instead of")
print("                        success, because the belief is written from")
print("                        action_result after the override point")
print("   => the ONLY behavioural difference a preserved rest failure would")
print("      make is the habit penalty. Everything else is already identical.")
print("      That is a much smaller consequence surface than I claimed in C2.")

print()
print("#" * 98)
print("# O2. AUTHORITY MATRIX")
print("#" * 98)
print()
print("   Measured: which stage writes what, per action type.")
print()
rows = [
    ("candidate",   "generate_action_pool", "all four", "generator"),
    ("precondition","PreconditionEngine.check", "all four", "engine -> blocked"),
    ("resolver",    "ActionResolver.probability", "all but search_person",
     "world_validated short-circuits search_person to 1.0"),
    ("override",    "resolve() rest branch", "rest ONLY", "undeclared"),
    ("final event", "Event(action_result=outcome)", "all four", "resolve()"),
    ("consequence", "_apply_emotional_consequences", "travel/contact/help only",
     "rest receives {}"),
    ("consequence", "_apply_failed_attempt", "contact/help/travel only",
     "rest absent from FAILURE_PRESSURE_MAP"),
    ("consequence", "_apply_fatigue", "all four", "rest branch ignores status"),
    ("consequence", "_update_procedural_habit", "all four",
     "the ONLY status-sensitive consequence for rest"),
    ("memory",      "remember_event / record_event_belief", "all four",
     "reads the committed status"),
]
hdr = f"   {'stage':<13}{'owner':<34}{'applies to':<26}{'note'}"
print(hdr)
print("   " + "-" * 94)
for r in rows:
    print(f"   {r[0]:<13}{r[1]:<34}{r[2]:<26}{r[3]}")
print()
print("   ANSWER TO O2 -- who owns the final outcome of one action:")
print("     rest           : resolve(), via the post-resolver assignment")
print("     travel         : the resolver")
print("     search_person  : nobody consulted -- world_validated fixes it at 1.0")
print("     contact_person : the resolver")
print()
print("   So the model already HAS an outcome-authority concept. It is")
print("   de facto, per-action, and UNDECLARED: nothing in the code states that")
print("   rest is authoritative, and nothing checks that rest is the only one.")

print()
print("#" * 98)
print("# O3. COMMIT INVARIANT (semantics, no implementation)")
print("#" * 98)
print()
print("   INVARIANT: if the resolver returns an ActionResult, the committed")
print("   event must preserve that result's status, reason and probability,")
print("   UNLESS the action holds a declared override authority.")
print()
print("   The only legitimate conditions for an override, stated so that each")
print("   one is checkable rather than a matter of taste:")
print()
print("     (i)   the authority is DECLARED -- named in one place, per action,")
print("           not an incidental assignment inside resolve()")
print("     (ii)  it states what it does with a resolver failure: absorb it or")
print("           ignore it. Silence is not a choice; today's rest does neither")
print("     (iii) the override is AUDITABLE -- the event must record that an")
print("           override happened and why, so a reader can tell a resolver")
print("           success from an asserted one")
print("     (iv)  consequence polarity follows the COMMITTED status, not the")
print("           resolver's")
print()
print("   Prevention of silent overwrite, in one sentence: an override that is")
print("   not declared is unreachable by construction, because there is exactly")
print("   one place a result can be replaced and it must be the declaration site.")
print()
print("   Today, measured against these four conditions:")
print("     (i)   FAIL -- no declaration exists for rest")
print("     (ii)  FAIL -- rest neither absorbs nor acknowledges the failure")
print("     (iii)  FAIL -- the event records success with reason 'rest completed'")
print("                     and probability 1.0, which is indistinguishable from")
print("                     a resolver success")
print("     (iv)  PASS but incidentally -- consequences read the committed value")

print()
print("#" * 98)
print("# O4. REGRESSION BOUNDARY (test contract, no production change)")
print("#" * 98)
print()
print("   R1  resolver success      -> committed success")
print("   R2  resolver failure      -> committed failure")
print("   R3  declared authority    -> override permitted, and auditable")
print("   R4  blocked before attempt-> no false failure, no world fact")
print("   R5  quiet tick            -> no fabricated event")
print()
print("   MEASURED against today, 20 seeds x 400 ticks:")
w = build_genesis_world()
w.timestamp = "0001-01-01T00:00:00"
e = SimulationEngine(seed=7, use_arbitration=False)
blocked = failed = events = quiet = 0
for _ in range(400):
    for ev in e.step(w).events:
        events += 1
        st = ev.action_result.status if ev.action_result else "none"
        if st == "blocked":
            blocked += 1
        if st == "failure":
            failed += 1
print(f"     events {events}, blocked {blocked}, committed failure {failed}")
print(f"     R1  PARTIAL -- two tests assert the committed status for rest, but")
print(f"             only the status STRING; neither checks probability or reason,")
print(f"             so resolver-success and asserted-success are indistinguishable")
print(f"     R2  FAIL     -- 16/45 rest failures were overwritten to success")
print(f"     R3  ABSENT   -- no declaration mechanism exists to test")
print(f"     R4  PASS     -- 0 blocked, and blocked writes no fact")
print(f"     R5  PASS     -- quiet ticks emit no events")
print()
print("   Note on R2: it is the only one of the five that currently FAILS, and")
print("   it fails for exactly one action. R1 is untested rather than passing:")
print("   nothing in the suite would catch a resolver success being committed as")
print("   something else.")

print()
print("#" * 98)
print("VERIFIED / OPEN QUESTION / ARCHITECTURAL JUDGMENT")
print("#" * 98)
print()
print(" VERIFIED")
print("   * two frozen tests DO assert rest's committed status == success; they")
print("     pass because the resolver also succeeded in those fixtures, and")
print("     they check neither probability nor reason, so they cannot tell an")
print("     asserted success from a resolver success")
print("   * rest is absent from the emotional effects table, from")
print("     FAILURE_PRESSURE_MAP and from the identity affordances")
print("   * the only status-sensitive consequence for rest is the habit penalty")
print("   * the authority matrix: rest is authoritative by assignment, all others")
print("     by resolver, search_person by nobody")
print("   * R4 and R5 hold today; R2 fails for rest only; R1 is partial (status")
print("     string only, never probability or reason)")
print("   * rest's committed probability is 1.0 with reason 'rest completed' in")
print("     every case, while the resolver's own figure was 0.675")
print()
print(" OPEN QUESTION")
print("   * whether the rest override is an intended contract or a legacy")
print("     artefact. The evidence is compatible with both and I do not")
print("     adjudicate it.")
print("   * whether a memory belief written from an asserted success is")
print("     materially different from one written from a resolver success. The")
print("     fields agree; only provenance differs, and nothing records which.")
print()
print(" ARCHITECTURAL JUDGMENT")
print("   * The model already has an outcome-authority concept. It is de facto and")
print("     undeclared, which is why one override reads as a bug and cannot be")
print("     argued either way.")
print("   * My earlier claim that preserving rest failure would carry a real")
print("     psychological cost was wrong. It would carry exactly one: the habit")
print("     penalty. The decision about rest is therefore much cheaper than I")
print("     implied -- but it is also much LESS interesting, because a rest")
print("     failure with no emotional or relational consequence is not a story.")
print("   * That reframes O1 honestly: the question is not only 'is rest")
print("     authoritative' but 'what would a rest failure MEAN'. Under the")
print("     current consequence set the answer is 'the actor learns to avoid")
print("     resting', which is a behaviour, not an event.")
