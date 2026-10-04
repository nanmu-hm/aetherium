"""Obstruction semantic placement audit, on head 9a6ac17.

ChatGPT 5978237507 A-D, read-only. No production/tests/fixtures change; no
threshold, RNG, probability or world_validated change; no fix pre-registered.

FIRST, TWO CORRECTIONS TO MY OWN LAST POST -- and Arena is right again.

In 9a6ac17 I published a table like:

    contact_person  (0.00, 1.00)
    rest            (0.05, 0.95)
    travel          (0.50, 0.65) and (0.50, 1.00)
    search_person   (0.50, 0.45 / 0.65)

Two errors, one of which ChatGPT then quoted back approving the WRONG part of:

  1. "(0.50, 0.65)" was attributed to plain `travel`. It is NOT. Measured
     exactly, the candidate identifies itself three ways:

         action_type  canonical  event_action_type   (difficulty, confidence)
         travel       travel     -                   (0.5, 1.0)
         travel       travel     search_person       (0.5, 0.65)

     So 0.65 belongs to the SEARCH VARIANT, which carries action_type="travel"
     but event_action_type="search_person". Attributing it to travel is wrong.

  2. ChatGPT 5978237507 §1 states, approving my correction, "travel/search_person
     确有 0.65/0.45 等真实输入". The 0.45 exists (actions.py:251,
     confidence=0.45 when remembered is None), but it is a third variant keyed
     on search_basis, not a fourth row of search_person. Collapsing them
     flattens three distinct candidates into one label.

The load-bearing correction from 9a6ac17 DOES stand, and it is the important
one: the raw probabilities are all well below 1.0 and are discarded:

    contact_person (d=0.00 cf=1.00) -> base 0.6750 cf 1.0000 p 0.675000
    rest           (d=0.05 cf=0.95) -> base 0.6575 cf 0.9625 p 0.632844
    travel         (d=0.50 cf=1.00) -> base 0.5000 cf 1.0000 p 0.500000
    travel[search] (d=0.50 cf=0.65) -> base 0.5000 cf 0.7375 p 0.368750

    every one of those is a real, computed, non-degenerate probability, and
    world_validated turns all of them into 1.0 before the RNG is consulted.
    So: NOT degenerate. SHORT-CIRCUITED. That distinction survives.

Now the actual audit.
"""
import subprocess
import sys

sys.path.insert(0, ".")

from engine.core.actions import generate_action_pool
from engine.core.action_types import canonical_action_type
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

WT = "/home/ming/aetherium/.worktrees/m-b-ab"


def show(title, cmd, limit=40):
    print()
    print("=" * 98)
    print(title)
    print("=" * 98)
    print()
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=WT).stdout
    for line in out.splitlines()[:limit]:
        print("   ", line)


print("#" * 98)
print("# CORRECTION 1+2 -- candidate identity and raw probability, measured")
print("#" * 98)

w = build_genesis_world()
w.timestamp = "0001-01-01T00:00:00"
e = SimulationEngine(seed=7, use_arbitration=False)
seen = {}
for _ in range(200):
    for cid in sorted(w.characters):
        if w.characters[cid].status != "active":
            continue
        for c in generate_action_pool(w, cid):
            meta = c.metadata or {}
            key = (c.action_type, canonical_action_type(c.action_type),
                   meta.get("event_action_type") or "-",
                   meta.get("search_basis") or "-")
            seen.setdefault(key, set()).add((c.difficulty, c.confidence))
    e.step(w)

print(f"   {'action':<13} {'canonical':<13} {'event_at':<14} {'search_basis':<20} "
      f"{'(difficulty, confidence)'}")
print("   " + "-" * 96)
for k in sorted(seen):
    print(f"   {k[0]:<13} {k[1]:<13} {k[2]:<14} {k[3]:<20} {sorted(seen[k])}")

print()
print("   raw probability WITHOUT the world_validated short-circuit:")
print("       base = 0.5 + 0.35*(ability - difficulty), ability defaults to 0.5")
print("       cf   = 0.25 + 0.75*confidence ; p = clamp(base*cf, 0.05, 0.95)")
print()
for k in sorted(seen):
    for d, cf in sorted(seen[k]):
        base = 0.5 + 0.35 * (0.5 - d)
        f = 0.25 + 0.75 * cf
        p = max(0.05, min(0.95, base * f))
        print(f"   {k[2]:<14} {k[3]:<20} d={d} cf={cf} -> p={p:.6f}")
print()
print("   All four are well below 1.0 and all four are discarded. The channel is")
print("   real and exercised; world_validated suppresses all of it.")

show("A. THE REAL CHAIN, in code order",
     ["sed", "-n", "631,700p", "engine/core/simulation.py"], 70)

print()
print("#" * 98)
print("# B. location_absent -- strict semantic judgement")
print("#" * 98)

show("B1. the exact guard and body",
     ["sed", "-n", "648,683p", "engine/core/simulation.py"], 40)

print()
print("   ORDER, established from the source above:")
print("     line 646  outcome = resolve_outcome(...)      <- outcome decided HERE")
print("     line 648  if outcome.status == 'success':      <- the guard")
print("     line 660      if search_target_id ...")
print("     line 662          if target.location == destination:  finds")
print("     line 666          else:  learn_fact('location_absent:...')  <- FACT written")
print()
print("   So, answering the ruling's four sub-questions:")
print()
print("   Q: is it an obstruction fact produced WITHIN the attempt, or merely a")
print("      knowledge update from search?")
print("      BOTH, and they are the same line. It is written inside resolve(),")
print("      from the world's own state (target.location != destination), with")
print("      source='direct_experience'. Nothing about it is inference -- the")
print("      character walked somewhere and the person was not there. That is a")
print("      world fact. The knowledge update is its consequence.")
print()
print("   Q: does it happen before or after the outcome?")
print("      AFTER. The outcome is decided at :646; the fact is written at :666.")
print("      The attempt is already classified by the time the obstruction")
print("      becomes visible -- which is exactly why the polarity is wrong: the")
print("      code could not have made it a failure even if it wanted to, because")
print("      the branch that would say so does not exist.")
print()
print("   Q: why does the success guard cause the polarity contradiction?")
print("      Because the model has only ONE place where 'the world refused' can")
print("      be expressed, and it sits inside `status == success`. So the fact")
print("      says 'not there' while the outcome says 'succeeded' and the emotion")
print("      delta rewards it. Nothing in the data contradicts itself -- the")
print("      CONTRADICTION IS BETWEEN TWO LAYERS THAT WERE NEVER JOINED.")
print()
print("   Q: without a new field, where could 'this attempt was obstructed' live?")
print("      Measured, three existing homes, no new schema required:")
print("        (a) ActionResult.status   -- 'failure' is already a legal value and")
print("            already drives _apply_failed_attempt. But status is a coarse")
print("            enum; it cannot say WHICH obstruction.")
print("        (b) Event.facts           -- already carries the sentence '... is not")
print("            there.' It is human-readable, already persisted, already")
print("            auditable. It cannot drive consequence because nothing reads it.")
print("        (c) the knowledge fact    -- already persisted with source=")
print("            'direct_experience', already in actor.knowledge, already")
print("            queryable. It is durable across ticks but is world state, not")
print("            'this attempt' state.")

show("B2. what already reads facts / knowledge / status, so the wiring cost is visible",
     ["grep", "-n", "\\.facts\\b\\|actor.knowledge\\|action_result.status",
      "engine/core/simulation.py"], 30)

print()
print("#" * 98)
print("# C. TWO CANDIDATE LAYERS -- Outcome/ActionResult vs WorldState/Fact")
print("#" * 98)
print()
print("   (Outcome/ActionResult layer)")
print("     + already drives every downstream consequence (_apply_failed_attempt,")
print("       emotional delta, relationship friction) via ONE existing switch")
print("     + keeps 'this attempt' and 'this result' together, which is what a")
print("       story engine needs to write 'X tried and failed'")
print("     + status is already persisted on the event and already read by")
print("       decision.py, memory kernel and narrative threads")
print("     - status is a single coarse enum; it cannot carry WHICH obstruction,")
print("       so the failure consequence would be generic")
print("     - changing what writes status is a semantic change to the outcome")
print("       contract, which is exactly the frozen surface")
print()
print("   (WorldState / Fact layer)")
print("     + location_absent already lives here and already means 'the world")
print("       refused'; it survives across ticks and is visible to memory")
print("     + obstruction as a durable world fact fits 'the world pushed back'")
print("       better than a per-attempt enum")
print("     - nothing in the outcome path reads facts, so a fact alone changes")
print("       NO behaviour -- it is currently inert")
print("     - 'the world said no' would exist even for attempts nobody made")
print()
print("   (BOTH -- the two-layer option the ruling asks about)")
print("     + the fact records WHAT the world did; the outcome records WHAT that")
print("       attempt became. Those are genuinely different questions and the")
print("       model already answers both -- in the wrong place, with the polarity")
print("       inverted.")
print("     - two things to keep consistent, so the acceptance contract must")
print("       pin that they never disagree again")

print()
print("#" * 98)
print("# D. MINIMAL FALSIFIABLE ACCEPTANCE CONTRACT")
print("#" * 98)
print()
print("   The contract must be satisfiable WITHOUT touching production, and must")
print("   be falsifiable. Proposed shape (semantics only, no code):")
print()
print("   C1  A single event must carry BOTH, without contradiction:")
print("         fact:    'target not present at destination'  (already exists)")
print("         outcome: NOT success")
print("       => currently the fact exists and outcome IS success. C1 fails today.")
print()
print("   C2  The three neighbours must be unharmed:")
print("         plain success        -> no obstruction fact, status success")
print("         precondition blocked -> NO fact, NO outcome (blocked is pre-attempt)")
print("         quiet tick           -> no event at all")
print("       => blocked is the one that must NOT acquire a fact or an outcome.")
print("          ChatGPT's frozen fact and mine (0 blocked / 16205 satisfied) make")
print("          this measurable rather than aspirational.")
print()
print("   C3  The failure must be traceable to the obstruction, not generic:")
print("       a failure with no obstruction fact behind it is a DIFFERENT event")
print("       from 'the world refused'. A contract that only asserts 'status can")
print("       be failure' would pass even if nothing produced it.")
print()
print("   C4  Reachability, without manufacturing anything:")
print("       the contract is only meaningful if at least one natural run")
print("       produces it. Today: finds=60, location_absent=0 over 20x400 ticks.")
print("       So any accepted implementation must FIRST explain why search never")
print("       comes up empty -- otherwise C1 is satisfiable only by construction.")
print("       This is the open factual question, and I am not answering it by")
print("       editing the search destination logic.")
print()
print("   HONEST STATUS: C4 is unmet and I cannot meet it read-only. The rest is")
print("   a specification. I am not presenting the contract as satisfied.")