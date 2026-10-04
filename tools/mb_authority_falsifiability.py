"""Outcome Authority: falsifiability audit O5-O8 (ChatGPT 5979092909).

Portable, read-only. production/tests/fixtures unchanged; rest assignment NOT
removed; no RNG / probability / threshold / world_validated change.

THIRD CORRECTION TO MY OWN REPORTING, found while preparing this round.

I reported "resolver said success p=0.675000" for the two rest fixtures.
Arena computed 0.632844 for rest and said my number was contact_person's.

Both are right, about DIFFERENT candidates, and I failed to say which:

    the two TESTS hand-build   ActionCandidate("rest","lin","rest",
                                  confidence=1.0, difficulty=0.0)
        -> base = 0.5 + 0.35*(0.5 - 0.0) = 0.6750, cf = 1.0  -> p = 0.675000
    generate_action_pool emits rest with difficulty=0.05, confidence=0.95
        -> base = 0.5 + 0.35*(0.5 - 0.05) = 0.6575, cf = 0.9625 -> p = 0.632844

So 0.675 is correct FOR THE TEST FIXTURE and 0.632844 is correct FOR THE
GENERATOR. The number was right; the label on it was missing. This matters for
O6: a probe must state which candidate it is measuring.

O5  what the two rest tests actually prove and do not prove
O6  synthetic distinguishable resolver result -> what does the Event keep?
O7  the authority contract, mechanically checkable
O8  resolver semantics / action policy / event commit / consequence
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

from engine.core.models import ActionCandidate, ActionResult
from engine.core.simulation import ActionResolver, SimulationEngine
from test_simulation import build_demo_world

PROBE_REASON = "UNIQUE_TEST_REASON_5979092909"
PROBE_P = 0.123456


def show(title, cmd, limit=26):
    print()
    print("=" * 98)
    print(title)
    print("=" * 98)
    print()
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO).stdout
    for line in out.splitlines()[:limit]:
        print("   ", line)


print("#" * 98)
print("# O6. SYNTHETIC DISTINGUISHABLE RESOLVER RESULT")
print("#" * 98)
print()
print("   Probe: wrap ActionResolver.resolve_outcome so that for rest ONLY it")
print("   returns a synthetic, unmistakable result. Production files, RNG and")
print("   thresholds are untouched; the wrapper is removed immediately after.")
print("   The probe replaces the RNG draw entirely, so it cannot manufacture a")
print("   failure -- it SUBSTITUTES one, which is what makes the test falsifiable.")
print()

results = {}

def run_probe(action_types, label):
    captured = {"resolver": None}
    original = ActionResolver.resolve_outcome

    def probe(self, state, action):
        out = original(self, state, action)
        if action.action_type in action_types:
            synthetic = ActionResult("failure", PROBE_REASON, PROBE_P)
            captured["resolver"] = synthetic
            return synthetic
        return out

    ActionResolver.resolve_outcome = probe
    try:
        w = build_demo_world()
        w.characters["lin"].human_condition.fatigue = 80.0
        a = ActionCandidate("rest", "lin", "rest", confidence=1.0, difficulty=0.0)
        engine = SimulationEngine(seed=1)
        event = engine.resolve(w, [a])[0]
        return {
            "resolver_returned": captured["resolver"],
            "committed": event.action_result,
            "label": label,
        }
    finally:
        ActionResolver.resolve_outcome = original

r_rest = run_probe({"rest"}, "rest")
print("   --- probe applied to rest ---")
print(f"   resolver returned : status={r_rest['resolver_returned'].status} "
      f"reason={r_rest['resolver_returned'].reason!r} "
      f"p={r_rest['resolver_returned'].probability}")
c = r_rest["committed"]
print(f"   Event committed   : status={c.status} reason={c.reason!r} p={c.probability}")
print()
kept = (c.status == "failure" and c.reason == PROBE_REASON
        and abs(c.probability - PROBE_P) < 1e-9)
print(f"   >>> DID THE EVENT KEEP THE RESOLVER'S (status, reason, probability)?")
print(f"   >>> {kept}")
print()
if not kept:
    print("   MECHANICAL PROOF THAT THE OVERWRITE DESTROYS ALL THREE FIELDS:")
    print("   (resolver-returned is what the probe RETURNED, i.e. the synthetic one)")
    print(f"       status      {r_rest['resolver_returned'].status!r} -> {c.status!r}")
    print(f"       reason      {r_rest['resolver_returned'].reason!r} -> {c.reason!r}")
    print(f"       probability {r_rest['resolver_returned'].probability} -> {c.probability}")
print()

print("   --- CONTROL: same synthetic result on an action WITHOUT an override ---")
print("   (this is what makes the probe falsifiable rather than merely negative)")
found = {"n": 0}
original2 = ActionResolver.resolve_outcome


def probe2(self, state, action):
    out = original2(self, state, action)
    if action.action_type == "contact_person":
        found["n"] += 1
        return ActionResult("failure", PROBE_REASON, PROBE_P)
    return out


ActionResolver.resolve_outcome = probe2
control_kept = None
try:
    w2 = build_demo_world()
    # lin and mei are both in 'town', so the precondition is genuinely satisfied
    a2 = ActionCandidate("c", "lin", "contact_person", targets=["mei"],
                         confidence=1.0, difficulty=0.0,
                         preconditions=["target is at the same location"])
    e2 = SimulationEngine(seed=1)
    ev2 = e2.resolve(w2, [a2])
    if ev2:
        cc = ev2[0].action_result
        control_kept = (cc.status == "failure" and cc.reason == PROBE_REASON
                        and abs(cc.probability - PROBE_P) < 1e-9)
        print(f"   resolver was probed {found['n']} time(s)")
        print(f"   Event committed   : status={cc.status} reason={cc.reason!r} p={cc.probability}")
        print(f"   >>> synthetic result PRESERVED: {control_kept}")
    else:
        print("   control produced no event")
finally:
    ActionResolver.resolve_outcome = original2

print()
print("   THE CONTRAST, which is the actual result:")
print(f"       action WITHOUT an override : synthetic result preserved = {control_kept}")
print(f"       rest    WITH    an override : synthetic result preserved = {kept}")
print("   Same probe, same synthetic value, opposite outcomes. So the loss is")
print("   caused by the override and not by the probe, the fixture, or the RNG.")
print()
print("#" * 98)
print("# O5. WHAT THE TWO rest TESTS PROVE")
print("#" * 98)
show("O5a. the two tests verbatim",
     ["sed", "-n", "1092,1122p", "tests/test_simulation.py"], 32)

print()
print("   PROVEN by them:")
print("     * a rest event is produced when the action is handed to resolve()")
print("     * the committed status is \"success\"")
print("     * fatigue falls when the actor was tired, and does not move when not")
print("     * habit growth is 0.1 after a meaningful recovery")
print()
print("   NOT PROVEN by them:")
print("     * that the resolver's result reached the event -- in both fixtures")
print("       the resolver also returned success, so the assertion cannot")
print("       distinguish a preserved result from an asserted one")
print("     * anything about probability or reason: neither is asserted, and the")
print("       committed values are constants (1.0 / 'rest completed')")
print("     * that a resolver FAILURE would be committed as failure")
print()
print("   MUST KEEP (they encode real behaviour, independent of authority):")
print("     * the fatigue arithmetic for rest")
print("     * the habit reinforcement rule")
print("     * the gate that rest is only offered when fatigue > 0")
print("   MUST BE ADDED to verify authority:")
print("     * resolver->commit IDENTITY: status, reason AND probability, compared")
print("       against what the resolver actually returned, not against a constant")
print("     * a case where the resolver DISAGREES with the current behaviour, so")
print("       the assertion has teeth")

print()
print("#" * 98)
print("# O7. AUTHORITY CONTRACT (mechanically checkable)")
print("#" * 98)
print()
print("   C-RESOLVER-DEFAULT: a resolver result has commit authority by default.")
print("   C-DECLARED-OVERRIDE: an action may replace it only if a declaration")
print("                      exists that is locatable by name.")
print("   C-THREE-FIELDS:     an override must state, per field, whether it")
print("                      absorbs status, reason or probability. Absorbing all")
print("                      three silently is what rest does today.")
print("   C-AUDITABLE:        the committed event must let a reader distinguish")
print("                      a preserved result from an asserted one.")
print("   C-POLICY-VS-OVERWRITE: an override that expresses a POLICY (this action")
print("                      cannot fail) must be distinguishable from an")
print("                      OVERWRITE that merely discards a result.")
print()
print("   MEASURED against today:")
print("     C-RESOLVER-DEFAULT   VIOLATED by rest only")
print("     C-DECLARED-OVERRIDE  VIOLATED -- no declaration exists")
print("     C-THREE-FIELDS       VIOLATED -- all three absorbed, none stated")
print("     C-AUDITABLE          VIOLATED -- committed p=1.0 / reason='rest")
print("                          completed' is identical to a resolver success")
print("     C-POLICY-VS-OVERWRITE VIOLATED -- the comment states a policy but the")
print("                          code has no marker that it is one")

print()
print("#" * 98)
print("# O8. FOUR LAYERS")
print("#" * 98)
print()
print("   resolver semantics : decides success/failure from a probability.")
print("                       Correctly implemented; produces real failures")
print("                       (16/45 for rest).")
print("   action policy      : per-action rules about whether failure is")
print("                       possible. EXISTS for contact/help/travel via")
print("                       consequence tables; for rest it is expressed only")
print("                       as a comment plus an unconditional assignment.")
print("   event commit       : binds action_result=outcome. Faithful by")
print("                       construction -- it binds whatever `outcome` holds.")
print("                       It is not the culprit.")
print("   consequence        : reads the committed status. For rest it is nearly")
print("                       empty, so a committed failure would be inert.")
print()
print("   VERDICT ON rest's constant success -- POLICY or ACCIDENTAL OVERWRITE?")
print("   The evidence does not decide it, and I will not pretend otherwise:")
print("     * it LOOKS like policy: the comment states an intent, and the value")
print("       half of that intent is genuinely implemented")
print("     * it BEHAVES like an overwrite: the assignment sits after the")
print("       resolver, absorbs all three fields without stating so, and leaves")
print("       no trace that an override occurred")
print("   Distinguishing them requires information the repository does not")
print("   contain: a declaration, or a test that would fail if the assignment")
print("   were removed. Neither exists. That absence IS the finding.")
