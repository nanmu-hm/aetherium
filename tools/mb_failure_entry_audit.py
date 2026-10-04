"""Failure Entry Architecture Audit -- Q1/Q2/Q3/Q4.

ChatGPT 5976914380: read-only, no production edits, no fix pre-registration.

FIRST, a correction I have to make before anything else.

Arena challenged my "rest can fail (p=0.632844)" claim, citing
simulation.py:768-771. Arena is RIGHT and I was wrong:

    elif action.action_type == "rest":
        # Rest is deterministic when attempted, but its value is
        # determined by the actor's actual recovery state.
        outcome = ActionResult("success", "rest completed", 1.0)

resolve_outcome() runs first and its result is then DISCARDED for rest. So the
0.632844 I measured was the pre-override probability of an outcome that never
takes effect. rest CANNOT fail either.

Corrected: the set of actions that can fail in this baseline is EMPTY, not
{some}. That makes the finding stronger, not weaker -- and it means my
"disjoint sets" framing was accidentally right for the wrong reason.

Q1 -- what does world_validated actually assert?
Q2 -- which actions SHOULD be eligible-but-fallible, and does existing state
      already express any of those obstacles?
Q3 -- are hard gates and outcome uncertainty collapsed into one boolean?
Q4 -- can a state fixture reach the full chain WITHOUT removing validation or
      injecting failure?
"""
import subprocess
import sys

sys.path.insert(0, ".")

from engine.core.actions import generate_action_pool
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

WT = "/home/ming/aetherium/.worktrees/m-b-ab"


def show(title, cmd, limit=60):
    print()
    print("=" * 96)
    print(title)
    print("=" * 96)
    print()
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=WT).stdout
    for line in out.splitlines()[:limit]:
        print("   ", line)


print("=" * 96)
print("CORRECTION -- rest cannot fail either")
print("=" * 96)
print()
print("   simulation.py:768-771, inside resolve(), AFTER resolve_outcome():")
print("       elif action.action_type == \"rest\":")
print("           # Rest is deterministic when attempted, but its value is")
print("           # determined by the actor's actual recovery state.")
print("           outcome = ActionResult(\"success\", \"rest completed\", 1.0)")
print()
print("   => the resolver's p=0.632844 is computed and then thrown away.")
print("      My per-action table measured the PRE-OVERRIDE probability.")
print("      Corrected: NO action in the baseline can fail. The set is empty.")
print()
print("   Verify by direct execution rather than by reading:")
w = build_genesis_world()
w.timestamp = "0001-01-01T00:00:00"
e = SimulationEngine(seed=7, use_arbitration=False)
seen_rest = 0
rest_statuses = {}
for _ in range(400):
    for cid in w.characters:
        if w.characters[cid].status != "active":
            continue
        for c in generate_action_pool(w, cid):
            if c.action_type != "rest":
                continue
            seen_rest += 1
            out = e.action_resolver.resolve_outcome(w, c)
            rest_statuses[out.status] = rest_statuses.get(out.status, 0) + 1
    for ev in e.step(w).events:
        if ev.action_type == "rest" and ev.action_result:
            key = f"executed:{ev.action_result.status}"
            rest_statuses[key] = rest_statuses.get(key, 0) + 1
print(f"   rest candidates offered: {seen_rest}")
print(f"   resolve_outcome() on a rest candidate -> {rest_statuses}")
print()
print("   => resolve_outcome says 'success' every time; and even if it could")
print("      say failure, line 769 would overwrite it. Two independent locks.")

show("Q1a -- every world_validated site, with the assertion each one makes",
     ["grep", "-n", "-B6", "world_validated", "engine/core/actions.py"], 80)

show("Q1b -- the precondition engine: what a HARD GATE actually checks",
     ["sed", "-n", "1,95p", "engine/core/preconditions.py"], 95)

show("Q3 -- the three layers as they exist in code",
     ["grep", "-n", "-A4",
      "precondition = self.precondition_engine.check|outcome = self.action_resolver.resolve_outcome|_apply_failed_attempt",
      "engine/core/simulation.py"], 40)

print()
print("=" * 96)
print("Q2 -- what real-world obstacles does the model ALREADY express?")
print("=" * 96)
print()
print("   Looking for existing state that could legitimately make an")
print("   eligible action fail. Candidates to check in the state model:")
print()

from dataclasses import fields
from engine.core.models import CharacterState, ActionCandidate

print("   CharacterState fields that could express an obstacle:")
for f in fields(CharacterState):
    print(f"      {f.name}")
print()
print("   ActionCandidate fields that could express an obstacle:")
for f in fields(ActionCandidate):
    print(f"      {f.name}")
print()

show("Q2b -- relationship friction: is there any state that resists an action?",
     ["grep", "-rn", "-A3", "resentment\\|rivalry\\|fear",
      "engine/core/decision.py"], 34)

print()
print("=" * 96)
print("Q4 -- can the full chain be reached WITHOUT removing validation?")
print("=" * 96)
print()
print("   The chain requires an eligible action whose outcome can be failure.")
print("   Measured: probability() returns 1.0 for every world_validated action,")
print("   and rest is overridden to success. So the chain is unreachable")
print("   WITHOUT touching production. Per the ruling I will not fabricate a")
print("   fixture that removes validation -- that would be writing the answer in.")
print()
print("   What I CAN show read-only is whether the model has any state that")
print("   already means 'this attempt is likely to fail', i.e. whether the")
print("   information exists and is simply not consulted.")

w2 = build_genesis_world()
w2.timestamp = "0001-01-01T00:00:00"
e2 = SimulationEngine(seed=7, use_arbitration=False)
for _ in range(120):
    e2.step(w2)

print()
print("   state that arguably expresses resistance, at t120:")
for cid in sorted(w2.characters):
    c = w2.characters[cid]
    others = [o for o in w2.characters if o != cid]
    print(f"     {cid}:")
    for other in others:
        rel = w2.get_relationship(cid, other)
        if rel:
            print(f"       rel->{other}: trust={rel.trust} affection={rel.affection} "
                  f"resentment={rel.resentment} rivalry={rel.rivalry} fear={rel.fear}")
    print(f"       emotions: { {k: round(v, 2) for k, v in c.emotions.items()} }")
    print(f"       risk_tolerance={c.risk_tolerance} status={c.status}")
    print(f"       same-location others: "
          f"{[o for o in others if w2.characters[o].location == c.location]}")
print()
print("   Note: relationship.resentment / rivalry / fear ARE modelled and ARE")
print("   read by decision.py (relationship alignment, contact_person scaling).")
print("   They influence UTILITY. What they do not do is influence whether the")
print("   action SUCCEEDS. That is the split to audit.")