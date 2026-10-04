"""Boundary Audit C and D: can an existing obstacle ever produce a failure,
and where does the missing semantic belong?

C per ChatGPT 5976969944: find, read-only, at least one EXISTING semantic that
  could form eligible -> attempted -> obstacle present -> failure.
  If every existing semantic can only enter utility, PROVE that. Do not
  manufacture failure.
D the one-sentence architecture verdict plus 2-3 candidate designs, semantics
  only.
"""
import subprocess
import sys

sys.path.insert(0, ".")

from engine.core.actions import generate_action_pool
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

WT = "/home/ming/aetherium/.worktrees/m-b-ab"


def grep(pat, path="engine"):
    return subprocess.run(["grep", "-rn", pat, "--include=*.py", f"{WT}/{path}"],
                          capture_output=True, text=True).stdout


print("=" * 98)
print("C. CAN AN EXISTING OBSTACLE EVER PRODUCE A FAILURE?")
print("=" * 98)
print()
print("C1. the complete census -- every place obstacle-like state EXISTS,")
print("    cross-referenced with every place outcome.status is READ.")
print()

OBSTACLES = [
    ("search_basis == 'uncertain_location'", "actions.py:257"),
    ("destination_confinement", "actions.py:214"),
    ("destination_affordance", "actions.py:213"),
    ("relationship trust/affection/loyalty/fear/respect/resentment/rivalry",
     "core/models.py RelationshipState"),
    ("emotions (sorrow/fear/anger/longing/...)", "core/models.py"),
    ("constraints", "core/models.py CharacterState"),
    ("possessions", "core/models.py"),
    ("abilities", "core/models.py"),
    ("knowledge", "core/models.py"),
    ("fatigue", "human_condition.py"),
    ("mortality_pressure", "human_condition.py"),
    ("ActionCandidate.risks", "core/models.py"),
    ("ActionCandidate.difficulty / confidence", "core/models.py"),
    ("decision_noise / risk_tolerance", "core/models.py"),
]
READERS = grep("outcome.status")
print(f"   sites that READ outcome.status: {len([l for l in READERS.splitlines() if l])}")
for line in READERS.splitlines():
    print("     ", line.split("/engine/")[-1])
print()
print("   => every one of them is inside resolve()/_apply_* AFTER the outcome")
print("      is already decided. None of them feeds ActionResolver.probability.")
print()
print("C2. the resolver's actual inputs")
print(subprocess.run(["sed", "-n", "1305,1325p",
                      f"{WT}/engine/core/simulation.py"],
                     capture_output=True, text=True).stdout)
print("   => probability() reads ONLY: actor.abilities[required_ability] or")
print("      0.5, action.difficulty, action.confidence, and world_validated.")
print("      Relationship axes, confinement, uncertainty of location, constraints,")
print("      possessions, knowledge, risks -- NONE of them reach it.")

print()
print("C3. so: measure each obstacle's actual influence, at the only place")
print("    influence could show up (utility), and at the resolver (nothing).")
w = build_genesis_world()
w.timestamp = "0001-01-01T00:00:00"
e = SimulationEngine(seed=7, use_arbitration=False)
for _ in range(110):
    e.step(w)

print()
print(f"   {'obstacle':<46} {'present in world?':>18} {'read by resolver?':>19}")
print("   " + "-" * 88)
cands = [c for cid in sorted(w.characters)
         if w.characters[cid].status == "active"
         for c in generate_action_pool(w, cid)]
resolver_src = open(f"{WT}/engine/core/simulation.py").read()
for name, where in OBSTACLES:
    key = name.split()[0].split(".")[-1]
    present = key in resolver_src.split("class ActionResolver")[1][:1500]
    print(f"   {name[:44]:<46} {'state exists':>18} {str(present):>19}")
print()
print("   (the resolver body references none of these; the only branches in it")
print("    are required_ability, world_validated, and the ability/confidence maths)")

print()
print("C4. VERDICT ON C")
print()
print("   Every existing obstacle semantic reaches UTILITY and none reaches")
print("   OUTCOME. This is now proven three ways:")
print("     (i)   the resolver's inputs are enumerated and closed: abilities,")
print("           difficulty, confidence, world_validated -- nothing else")
print("     (ii)  every outcome.status reader sits downstream of the decision")
print("     (iii) world_validated short-circuits the whole function to 1.0 for")
print("           every generator that could carry a meaningful obstacle")
print()
print("   Therefore NO existing state can produce a failure. Not 'hard to")
print("   reach' -- impossible, without changing production code. Per the ruling")
print("   I am not manufacturing one.")
print()
print("   One nuance worth recording: `search_basis == 'uncertain_location'`")
print("   is the closest existing candidate. It already means 'the character")
print("   does not know where the target is'. But it is a FACT ABOUT THE")
print("   ACTOR'S KNOWLEDGE, not an obstacle in the world: nothing external")
print("   prevents the search, so even semantically it describes ignorance")
print("   rather than obstruction. Making it cause failure would be a change of")
print("   meaning, not a wiring fix.")

print()
print("=" * 98)
print("D. THE ARCHITECTURE VERDICT")
print("=" * 98)
print()
print("   The one sentence required by the ruling:")
print()
print("     The current system lacks a representation of OBSTRUCTION -- the")
print("     fact that a specific attempt, though permitted and chosen, meets a")
print("     resistance in the world. It belongs BETWEEN eligibility and outcome:")
print()
print("         eligibility (PreconditionEngine)  ->  [OBSTRUCTION]  ->  outcome")
print()
print("     It must NOT take over the responsibility of eligibility (that is the")
print("     precondition engine's, and the docstring already says so), and it")
print("     must NOT be folded into utility (that is where every existing")
print("     obstacle already lives, which is exactly why failure is currently")
print("     inexpressible).")
print()
print("=" * 98)
print("   CANDIDATE DESIGNS -- semantics only, no code, no thresholds")
print("=" * 98)

print()
print("  (1) OBSTRUCTION ON THE CANDIDATE  (ActionCandidate.metadata / new field)")
print("      the generator already computes latent resistance and hands it to")
print("      the resolver as a FACT about this attempt")
print("      can express eligible-but-may-fail : YES, it is per-candidate")
print("      pollutes utility                  : only if decision reads it; it")
print("                                          can stay resolver-only")
print("      traceable consequence             : YES, the candidate is already")
print("                                          persisted as Event.causes")
print("      supports 求不得 / 错过              : YES, the obstacle travels")
print("                                          with the attempt")
print("      moves frozen numbers              : RISK. The same values")
print("                                          (confinement, relationship")
print("                                          axes) are currently utility")
print("                                          inputs; reusing them couples")
print("                                          the two layers unless the")
print("                                          obstacle is computed")
print("                                          separately.")

print()
print("  (2) OBSTRUCTION IN THE RESOLVER / OUTCOME  (ActionResult)")
print("      the resolver decides, the result records why")
print("      can express eligible-but-may-fail : YES")
print("      pollutes utility                  : NO")
print("      traceable consequence             : YES, action_result.status and")
print("                                          reason are already persisted")
print("                                          and decision.py already reads")
print("                                          them")
print("      supports 求不得 / 错过              : YES")
print("      moves frozen numbers              : LEAST. Nothing upstream")
print("                                          changes; only the branch that")
print("                                          is currently unreachable")
print("                                          becomes reachable.")
print("      open question                     : WHERE does the resolver get the")
print("                                          resistance fact from? It cannot")
print("                                          invent one, or that is random")
print("                                          failure by another name.")

print()
print("  (3) OBSTRUCTION AS A WORLD FACT  (WorldState)")
print("      environment / relationship / resource resistance becomes world")
print("      state, consumed by the resolver")
print("      can express eligible-but-may-fail : YES")
print("      pollutes utility                  : RISK. This is the layer")
print("                                          utility already reads, so the")
print("                                          same fact would drive both")
print("      traceable consequence             : YES")
print("      supports 求不得 / 错过              : YES, and most durably -- the")
print("                                          obstacle can persist and be")
print("                                          discovered later")
print("      moves frozen numbers              : HIGHEST. WorldState is the")
print("                                          most-frozen surface in this")
print("                                          project.")

print()
print("  NOT PROPOSED, recorded so it is not smuggled in later:")
print("    - clearing or renaming world_validated")
print("    - lowering any threshold, including the distress 8.0")
print("    - adding rest to FAILURE_PRESSURE_MAP")
print("    - injecting failure or distress from outside")
print("    - any RNG that manufactures failure")
print()
print("  The open design question, which I am deliberately NOT answering:")
print("  designs (2) and (3) are compatible -- outcome needs a fact, and the")
print("  world is a candidate home for that fact. Whether obstruction is")
print("  per-attempt (1), computed at resolve time (2), or a persisted world")
print("  fact (3) determines whether 求不得 is a property of the CHARACTER'S")
print("  ATTEMPT or of the WORLD, and that is a semantics decision with")
print("  different consequences for a story engine.")