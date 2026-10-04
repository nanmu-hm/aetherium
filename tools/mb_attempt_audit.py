"""ChatGPT 5978207192: local mechanical verification on head 7e8a030.

Read-only. No production/tests/fixtures changes, no fix pre-registration.

  1. attempt fact audit  -- where exactly is "selected and executing" and
     resolve_outcome() separated, and in what order do event creation,
     action_result and memory-belief writes happen
  2. existing-obstacle census -- eligibility / utility / outcome for each
  3. minimal counterfactual -- is there ANY natural
     eligible -> selected -> attempted -> obstacle -> failure path
  4. frozen baseline -- 323 passed / 1 failed
  5. precise conclusions

Plus the finding Arena raised that my own 7e8a030 audit MISSED, and which
changes the shape of the answer:

  simulation.py:661-679 already contains a "came up empty" representation:
      learn_fact("location_absent:<target>:<destination>")
      actor.knowledge.add(absent_fact.proposition)
      facts.append("<actor> searches for <target> at <destination>,
                    but <target> is not there.")
  yet the enclosing branch requires outcome.status == "success", so the search
  is recorded as SUCCESSFUL, and _apply_emotional_consequences then gives
  joy +3 / hope +3 / identity_beliefs +0.08.

  So the model already HAS an obstruction representation, it is unreachable
  (search always finds), and where it does fire its polarity is POSITIVE --
  the opposite of failure. That is a third correction to my own reporting,
  and the most consequential one, because it says the missing piece is not
  "invent obstruction" but "the obstruction that already exists is
  mis-polarised and gated behind success".
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.actions import generate_action_pool
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

WT = str(Path(__file__).resolve().parent.parent)


def show(title, cmd, limit=40, path=None):
    print()
    print("=" * 98)
    print(title)
    print("=" * 98)
    print()
    out = subprocess.run(cmd, capture_output=True, text=True,
                         cwd=path or WT).stdout
    for line in out.splitlines()[:limit]:
        print("   ", line)


print("#" * 98)
print("# 0. THE FINDING ARENA RAISED, AND WHY IT MATTERS MORE THAN MINE")
print("#" * 98)
show("simulation.py:660-682 -- the existing 'came up empty' representation",
     ["sed", "-n", "660,682p", "engine/core/simulation.py"], 26)

print()
print("   Read the guard: the branch is `if outcome.status == \"success\":`")
print("   and the target is either found (finds) or absent (location_absent).")
print("   So the MODEL distinguishes the two, but only INSIDE success.")
print("   There is no branch where a search is attempted and comes up empty")
print("   AND the attempt is a failure.")
print()
print("   Consequence: 'the world said no' is already expressible in the data")
print("   model (a knowledge fact with source=direct_experience) and is wired")
print("   to the WRONG outcome. Making it a failure is a semantic change with")
print("   measurable consequence, not a missing feature.")

print()
print("#" * 98)
print("# 1. ATTEMPT FACT AUDIT -- the exact boundary and the write order")
print("#" * 98)

show("1a. selection -> resolve: where the chosen action enters resolve()",
     ["grep", "-n", "choose(\\|def resolve(\\|resolve_outcome(\\|_apply_emotional_consequences(\\|_apply_failed_attempt(\\|learn_fact(\\|remember_event(\\|record_event_belief(",
      "engine/core/simulation.py"], 34)

show("1b. the select call site, in context",
     ["sed", "-n", "64,80p", "engine/core/simulation.py"], 20)

print()
print("   ORDER, measured by reading resolve() top to bottom:")
print("     1. precondition_engine.check          -> blocked | continue")
print("     2. action_resolver.resolve_outcome    -> success | failure")
print("     3. action-specific consequence writes (location, relationship,")
print("        knowledge facts such as location_absent)")
print("     4. _apply_emotional_consequences      -> psychology deltas")
print("     5. _apply_failed_attempt              -> ONLY if status == failure")
print("     6. event built with action_result + consequences")
print("     7. memory: learn_fact / remember_event / record_event_belief")
print()
print("   KEY ORDERING FACT for the ruling: step 3 runs BEFORE step 5, and")
print("   step 3 includes writing the knowledge fact that says the target was")
print("   NOT there. So an obstruction is recorded in memory while the attempt")
print("   is still classified as a success. The fact and the outcome disagree")
print("   inside the same event.")

print()
print("#" * 98)
print("# 2. EXISTING-OBSTACLE CENSUS -- eligibility / utility / outcome")
print("#" * 98)
print()
print(f"   {'obstacle':<40} {'eligibility':>12} {'utility':>9} {'outcome':>9}")
print("   " + "-" * 74)
rows = [
    ("search_basis='uncertain_location'", "no", "no", "no"),
    ("location_absent (knowledge fact)", "no", "no", "PARTIAL"),
    ("destination_confinement", "no", "yes", "no"),
    ("destination_affordance", "no", "yes", "no"),
    ("relationship trust/affection/loyalty", "no", "yes", "no"),
    ("relationship resentment/fear/rivalry", "no", "yes", "no"),
    ("emotions (sorrow/fear/anger/longing)", "no", "yes", "no"),
    ("constraints / possessions / abilities", "YES (hard gate)", "no", "no"),
    ("fatigue", "no", "yes", "no"),
    ("mortality_pressure", "no", "no", "no"),
    ("ActionCandidate.risks", "no", "no", "no"),
    ("ActionCandidate.difficulty/confidence", "YES (probability only)", "yes", "YES"),
]
for name, e, u, o in rows:
    print(f"   {name:<40} {e:>12} {u:>9} {o:>9}")
print()
print("   location_absent is the only entry that reaches any outcome-side code,")
print("   and it reaches it from INSIDE the success branch.")
print()
print("   NOTE ON DIFFICULTY/CONFIDENCE: these DO reach outcome, via")
print("   ActionResolver.probability. They are the sole existing channel by")
print("   which a candidate can fail at all. But every generator sets")
print("   difficulty=0.0 and confidence=1.0, so the arithmetic yields 1.0.")
print("   The channel is real and unused -- which is a materially different")
print("   situation from 'there is no channel'.")

show("2b. verify that claim: difficulty/confidence as actually emitted",
     ["grep", "-n", "difficulty=\\|confidence=", "engine/core/actions.py"], 30)

print()
print("#" * 98)
print("# 3. MINIMAL COUNTERFACTUAL -- is there a natural failure path?")
print("#" * 98)
print()
print("3a. can search ever come up empty? (the one candidate representation)")


def search_outcomes(seed, ticks=400):
    w = build_genesis_world()
    w.timestamp = "0001-01-01T00:00:00"
    e = SimulationEngine(seed=seed, use_arbitration=False)
    found = absent = 0
    absent_examples = []
    for _ in range(ticks):
        for ev in e.step(w).events:
            meta = None
            if ev.action_result is None:
                continue
            facts = " ".join(getattr(ev, "facts", []) or [])
            if "is not there" in facts:
                absent += 1
                if len(absent_examples) < 2:
                    absent_examples.append((ev.tick, facts[:100]))
            elif "finds" in facts:
                found += 1
    return found, absent, absent_examples


tot_f = tot_a = 0
ex = []
for seed in range(1, 21):
    f, a, e2 = search_outcomes(seed)
    tot_f += f
    tot_a += a
    if e2 and len(ex) < 2:
        ex += e2
print(f"   20 seeds x 400 ticks:  search FINDS = {tot_f}   search 'is not there' = {tot_a}")
if ex:
    for t, f in ex:
        print(f"      t{t}: {f}")
else:
    print("      no 'is not there' fact ever produced")

print()
print("3b. does difficulty/confidence ever take a non-degenerate value?")
vals = {}
for seed in (1, 7, 13, 42):
    w = build_genesis_world()
    w.timestamp = "0001-01-01T00:00:00"
    e = SimulationEngine(seed=seed, use_arbitration=False)
    for _ in range(150):
        for cid in w.characters:
            if w.characters[cid].status != "active":
                continue
            for c in generate_action_pool(w, cid):
                vals.setdefault(c.action_type, set()).add(
                    (c.difficulty, c.confidence))
        e.step(w)
for k in sorted(vals):
    print(f"   {k:<16} (difficulty, confidence) pairs: {sorted(vals[k])}")

print()
print("3c. VERDICT ON 3")
print()
nondeg = {k: v for k, v in vals.items() if any(d > 0 or c < 1.0 for d, c in v)}
if nondeg:
    print("   candidates with a non-degenerate success probability DO exist:")
    for k, v in nondeg.items():
        print(f"      {k}: {sorted(v)}")
else:
    print("   Every generated candidate carries difficulty=0.0 and confidence=1.0,")
    print("   so probability() short-circuits to 1.0 for every one of them.")
    print("   CONCLUSION: there is NO natural eligible -> attempted -> obstacle")
    print("   -> failure path reachable from the current generator. Not 'hard to")
    print("   reach' -- the input values that would produce it are never emitted.")
print()
print("   Important nuance vs my own 7e8a030 wording. I said the model 'lacks a")
print("   representation of obstruction'. That was too strong. What exists:")
print("     * location_absent  -- a real obstruction fact, written on success")
print("     * difficulty/confidence -- a real probability channel, never exercised")
print("   What is missing is the WIRING from either to a non-success outcome.")