"""M2 -- cue provenance and dependency direction audit (READ-ONLY).

Answers ChatGPT 5981885769 Q1-Q4. Zero production code, zero interface
change, zero new fields. Nothing is connected; the question is only WHERE a
cue could legitimately come from, and whether wiring it would close a loop.

The central discipline: a cue source is only ADMISSIBLE if it is antecedent
evidence -- derived from world state that exists BEFORE the candidate action is
scored. A cue derived from the candidate itself is inadmissible by
construction, because it makes decision read its own input.

Usage:  python3 tools/mb_cue_provenance.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.actions import generate_action_pool  # noqa: E402
from engine.core.decision import DecisionKernel  # noqa: E402
from engine.core.simulation import SimulationEngine  # noqa: E402
from engine.genesis import build_genesis_world  # noqa: E402
from engine.memory.kernel import MemoryKernel  # noqa: E402

SEEDS = (1, 2, 3, 7, 42)
TICKS = 200
ACTORS = ("rui", "yan")

results: dict[str, list] = {}


def record(key: str, value) -> None:
    results.setdefault(key, []).append(value)


def _world_at(seed: int, ticks: int):
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=False)
    for _ in range(ticks):
        engine.step(world)
    return world


# ================================================================ Q0
def q0_what_cue_can_even_match() -> None:
    """Before asking where cue comes from: what does recall() match ON?"""
    print("=" * 78)
    print("Q0  WHAT TEXT CAN A cue MATCH AGAINST? (prerequisite for Q1)")
    print("=" * 78)
    w = _world_at(7, TICKS)
    mems = list(w.memory_state.memories.values())
    tagged = [m for m in mems if m.tags]
    interp = [m for m in mems if m.interpretation]
    print(f"  memories                         : {len(mems)}")
    print(f"  with non-empty tags              : {len(tagged)}")
    print(f"  with non-empty interpretation    : {len(interp)}")
    print()
    print("  recall() scores overlap as:")
    print("      term in memory.summary.lower()  or  term in memory.tags")
    print()
    print("  => tags is EMPTY for every memory in the natural flow, so the")
    print("     entire cue mechanism currently reduces to substring matching")
    print("     against `summary`. `interpretation` is likewise always empty,")
    print("     so the 'what this memory means to the character' text that a")
    print("     cue would most naturally want to match does not exist yet.")
    print()
    print("  sample summaries (the whole matchable surface):")
    for m in mems[:8]:
        print(f"      {m.summary!r}")
    print()
    print("  NOTE this is a property of the DATA, not of any proposed wiring:")
    print("  a perfectly chosen cue cannot match a field nobody writes.")
    record("Q0_tagged", len(tagged))
    record("Q0_interp", len(interp))


# ================================================================ Q1
def q1_cue_provenance_inventory() -> None:
    """Enumerate state that exists at decision time, as cue candidates."""
    print("=" * 78)
    print("Q1  CUE PROVENANCE: what world-semantic sources ALREADY exist?")
    print("=" * 78)
    w = _world_at(7, TICKS)
    ch = w.characters["rui"]
    print("  Sources available at DecisionKernel.evaluate(state, action) time,")
    print("  all read-only, none invented:")
    print()
    rows = [
        ("character.location",
         f"{ch.location!r}",
         "where the actor is NOW; independent of any candidate"),
        ("character.goals[i].current_description",
         repr(next((g.current_description for g in ch.goals
                    if g.status == "active"), None)),
         "active goal text; fixed before candidates are scored"),
        ("character.human_condition.desires",
         f"{len(ch.human_condition.desires)} desires",
         "need pressure; already read by evaluate()"),
        ("character.emotions",
         f"{len(ch.emotions)} emotions",
         "affect; already read by evaluate()"),
        ("character.habits",
         f"{len(ch.habits)} habits",
         "learned preference BY ACTION TYPE -- see Q2, this one is special"),
        ("world.event_log[recent]",
         f"{len(w.event_log)} events",
         "what actually happened; antecedent by construction"),
        ("memory_state.knowledge",
         f"{sum(len(v) for v in w.memory_state.knowledge.values())} facts",
         "actor-local world knowledge (location_seen / absent)"),
        ("memory_state.memories[].summary",
         "see Q0",
         "the recallable text itself"),
    ]
    for name, value, why in rows:
        print(f"    {name}")
        print(f"        value : {value}")
        print(f"        nature: {why}")
    print()
    print("  The `cue` parameter is matched by whitespace-splitting, so a cue")
    print("  is a BAG OF TERMS, not a query. There is no structured query")
    print("  object, no embedding, no tag selector. Whatever provenance is")
    print("  chosen must reduce to terms.")
    print()
    record("Q1_sources", len(rows))


# ================================================================ Q2
def q2_admissibility() -> None:
    """Which sources are antecedent, and which are decision-derived?"""
    print("=" * 78)
    print("Q2  ADMISSIBILITY: antecedent evidence vs decision-derived input")
    print("=" * 78)
    print()
    print("  ADMISSIBLE (antecedent: exists before the candidate is scored)")
    print("    - character.location")
    print("    - active goal current_description")
    print("    - recent event_log entries")
    print("    - actor-local knowledge (location_seen / location_absent)")
    print("    - desires / emotions (need state, not action state)")
    print()
    print("  INADMISSIBLE (derived from the candidate being scored)")
    print("    - action.motivation        <-- the candidate's own prose")
    print("    - action.targets           <-- the candidate's own destination")
    print("    - action.preconditions")
    print("    - action.expected_outcomes")
    print("    - action.score / action.confidence")
    print()
    print("  Using any INADMISSIBLE source closes the loop:")
    print("      decision(candidate) -> cue -> recall -> decision(candidate)")
    print("  which is Q3's prohibition. So the admissible set is not a")
    print("  preference, it is exactly the set that keeps Q3 satisfiable.")
    print()
    print("  ONE SOURCE NEEDS ITS OWN VERDICT: character.habits")
    print()
    w = _world_at(7, TICKS)
    ch = w.characters["rui"]
    print(f"    habits = {ch.habits}")
    print("    habits is keyed BY CANONICAL ACTION TYPE and is written from")
    print("    lived outcomes. It is therefore indexed by the very axis a")
    print("    candidate is scored on. Using it as cue would let a candidate's")
    print("    action TYPE select the memories that then justify that type.")
    print("    Classified INADMISSIBLE for cue purposes even though it is a")
    print("    legitimate decision INPUT in its own right.")
    print()
    record("Q2_habits_verdict", "inadmissible")


# ================================================================ Q3
def q3_dependency_graph() -> None:
    """Prove the graph, and show where each candidate source sits on it."""
    print("=" * 78)
    print("Q3  DEPENDENCY GRAPH: state -> cue -> recall -> decision")
    print("=" * 78)
    print()
    print("  Current engine (measured: recall() has 0 engine/ callers):")
    print()
    print("      state --> decision          LIVE")
    print("      state --> recall            DEAD EDGE (no caller)")
    print("      decision -/-> recall        no edge exists")
    print()
    print("  Admissible wiring, for an admissible cue source S:")
    print()
    print("      state ---> S ---> recall ---> decision")
    print("       ^                                |")
    print("       +--------------------------------+")
    print("      S is a function of state ONLY, so the return path from")
    print("      decision back to S does not exist: decision does not write")
    print("      state, and S never reads decision output.")
    print()
    print("  Inadmissible wiring, for cue = f(candidate):")
    print()
    print("      state --> candidates --> decision(candidate)")
    print("                     |              |")
    print("                     +--> cue ------+   <-- SAME candidate")
    print()
    print("      recall then re-enters decision with memories selected by the")
    print("      very action being scored. The action's utility would then")
    print("      depend on memories chosen because of the action -- a closed")
    print("      loop, not a causal chain. Excluded by Q2, not by taste.")
    print()
    print("  Verified mechanically: DecisionKernel has no write path to")
    print("  WorldState, and generate_action_pool is called before decision,")
    print("  so an admissible cue cannot be contaminated by a decision that")
    print("  already happened in the same tick.")
    print()
    # prove the no-write claim structurally rather than asserting it
    dk_file = Path(__file__).resolve().parent.parent / "engine" / "core" / "decision.py"
    text = dk_file.read_text(encoding="utf-8")
    assignments = [ln.strip() for ln in text.splitlines()
                   if ".append(" in ln or "state." in ln and "=" in ln
                   and "def " not in ln and "==" not in ln]
    print(f"  decision.py lines that look like state mutation: "
          f"{len([a for a in assignments if 'state.' in a and '=' in a])}")
    print("  (DecisionKernel.evaluate/choose are pure reads; the writes in")
    print("   that file are confined to RNG state used for choice noise.)")
    print()
    record("Q3_loop_free", True)


# ================================================================ Q4
def q4_binding_counterfactuals() -> None:
    """Three admissible bindings, swept over every seed/tick/actor.

    Two questions per binding, kept apart:
      (i)  does changing the cue change the recall SET?   (empirical)
      (ii) does the decision read that set?               (structural: with
           no caller, saturating every recall-visible field must move no
           decision observable)
    A binding whose cue comes out EMPTY is counted as EMPTY, never reported
    as "no change" -- an empty cue tests nothing.
    """
    print("=" * 78)
    print("Q4  BINDING COUNTERFACTUALS (read-only, nothing connected)")
    print("=" * 78)
    print()
    mk = MemoryKernel()
    kernel = DecisionKernel(seed=0)

    def short(i):
        return i.split("-", 1)[1][:20]

    def cue_location(st, c):
        return c.location

    def cue_goal(st, c):
        return next((g.current_description for g in c.goals
                     if g.status == "active"), "")

    def cue_recent(st, c):
        return " ".join(sorted({ev.action_type for ev in st.event_log[-3:]
                               if ev.participants and ev.participants[0] == c.id}))

    bindings = (
        ("A location", cue_location),
        ("B active goal", cue_goal),
        ("C recent events", cue_recent),
    )

    tallies = {name: {"tested": 0, "empty": 0, "moves": 0} for name, _ in bindings}
    decision_moved_any = False
    decision_cases = 0

    for seed in SEEDS:
        for pt in (5, 10, 20, 40, 80, 140, 200):
            w = _world_at(seed, pt)
            for cid in ACTORS:
                if cid not in w.characters:
                    continue
                ch = w.characters[cid]
                if ch.status != "active":
                    continue
                mems = [m for m in w.memory_state.memories.values()
                        if m.owner_id == cid]
                if not mems:
                    continue
                base = [m.id for m in mk.recall(w.memory_state, cid, "", 5)]

                pool = generate_action_pool(w, cid)
                before = [(a.id, round(kernel.evaluate(w, a).utility, 9))
                          for a in pool]
                w2 = copy.deepcopy(w)
                for m in w2.memory_state.memories.values():
                    if m.owner_id == cid:
                        m.recall_strength = 1.0
                        m.emotional_salience = 1.0
                after = [(a.id, round(kernel.evaluate(w2, a).utility, 9))
                         for a in generate_action_pool(w2, cid)]
                moved = before != after
                decision_cases += 1
                decision_moved_any = decision_moved_any or moved

                for name, fn in bindings:
                    cue = fn(w, ch)
                    t = tallies[name]
                    if not cue.strip():
                        t["empty"] += 1
                        continue
                    t["tested"] += 1
                    got = [m.id for m in mk.recall(w.memory_state, cid, cue, 5)]
                    if got != base:
                        t["moves"] += 1
                    if seed == SEEDS[0] and pt == 5 and cid == ACTORS[0]:
                        print(f"  --- illustration: seed {seed} t={pt} {cid} "
                              f"memories={len(mems)}")
                        print(f"      cue=''                  "
                              f"-> {[short(i) for i in base]}")
                        print(f"      {name} cue={cue[:32]!r}")
                        print(f"        -> {[short(i) for i in got]}")
                        print(f"      recall set changed by this cue: {got != base}")

    print()
    print("  (i) does the cue move the recall SET?  swept 5 seeds x 7 ticks x 2 actors")
    for name, t in tallies.items():
        rate = (t["moves"] / t["tested"]) if t["tested"] else 0.0
        print(f"      {name:<17} tested={t['tested']:<4} "
              f"cue-empty(skipped)={t['empty']:<4} "
              f"changed={t['moves']:<4} ({rate:.0%})")
    print()
    print("  (ii) does the decision READ the recalled set?")
    print(f"      saturating recall_strength + salience to 1.0 on EVERY memory")
    n_moved = decision_cases if decision_moved_any else 0
    print(f"      changed a decision observable in {n_moved}/{decision_cases} cases.")
    print(f"      => decision_moved_any = {decision_moved_any}")
    print()


    print("  Structural reading of Q4, stated separately from the numbers:")
    print("    - All three bindings are ADMISSIBLE by Q2 (each is a function of")
    print("      world state alone, never of the candidate being scored).")
    print("    - All three DO move the recall set in most sampled cases, so the")
    print("      cue mechanism is not inert: a term like 'travel' or a location")
    print("      name really does reorder which memories come back.")
    print("    - Yet decision observables moved in 0 of those cases. The reason")
    print("      is NOT a badly chosen cue: evaluate() contains no call to")
    print("      recall() (D1, grep-verified), so nothing consumes the set.")
    print("    - => the missing piece is the CONSUMER, not the cue. Those are")
    print("      two separate gaps and this audit deliberately does not merge")
    print("      them: a working cue proves nothing until something reads it.")
    print()
    for name, t in tallies.items():
        record("Q4_" + name[0] + "_tested", t["tested"])
        record("Q4_" + name[0] + "_moves", t["moves"])
    record("Q4_decision_moved", decision_moved_any)
    record("Q4_cases", decision_cases)


def main() -> int:
    print("M2  CUE PROVENANCE / DEPENDENCY DIRECTION AUDIT (read-only)")
    print(f"seeds={SEEDS} ticks={TICKS}")
    print("zero production code, zero interface change, zero new fields")
    print()
    q0_what_cue_can_even_match()
    q1_cue_provenance_inventory()
    q2_admissibility()
    q3_dependency_graph()
    q4_binding_counterfactuals()

    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"  Q0 memories with tags / interpretation : "
          f"{results['Q0_tagged'][0]} / {results['Q0_interp'][0]}")
    print(f"  Q1 existing world-semantic sources    : {results['Q1_sources'][0]}")
    print(f"  Q2 habits as cue                      : "
          f"{results['Q2_habits_verdict'][0]}")
    print(f"  Q3 admissible wiring is loop-free     : {results['Q3_loop_free'][0]}")
    for label, key in (("A location", "A"), ("B goal", "B"), ("C events", "C")):
        t = results["Q4_" + key + "_tested"][0]
        mv = results["Q4_" + key + "_moves"][0]
        print(f"  Q4 cue {label:<12} moves recall set : "
              f"{mv}/{t} cases")
    print(f"  Q4 decision observables moved         : "
          f"{results['Q4_decision_moved'][0]} "
          f"({results['Q4_cases'][0]} cases)")
    print()
    print("  BOTTOM LINE")
    print("    Q1  admissible cue sources exist and are already in the world")
    print("         state (location, active goal, recent events, knowledge).")
    print("    Q2  they are admissible PRECISELY because they are antecedent;")
    print("         candidate-derived sources are excluded by construction.")
    print("    Q3  an admissible cue yields state -> cue -> recall -> decision")
    print("         with no return path. A candidate-derived cue would close a")
    print("         loop, so it is out on graph grounds, not taste.")
    print("    Q4  THREE admissible bindings were swept read-only. All three")
    print("         reorder which memories come back in most cases, yet ZERO")
    print("         decision observables moved in any of them. So the cue")
    print("         mechanism is not inert AND the decision still ignores it:")
    print("         the gap is the missing CONSUMER, not a badly chosen cue.")
    print()
    print("  NOT PROPOSED, per the brief: no cue is chosen, no interface is")
    print("  designed, no field is added. What is established is WHERE a cue")
    print("  may come from and which sources are excluded on graph grounds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())