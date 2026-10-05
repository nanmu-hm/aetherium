"""M13 -- are recall()'s remaining score terms degenerate too?

READ-ONLY. ChatGPT 5988513751's last read-only check, and its explicit
methodological rule:

    "把'源码恒定值'与'数据中恰好没变化'严格分开。例如 unresolved=False
     如果是源码初始化常量，就直接证明；不能因为当前 1995 条记忆里都是
     False，就声称整个机制永远如此。"

That rule is adopted, and it immediately catches an error in MY OWN M12
proposal: I wrote that `unresolved` is "always False". It is not. The
writer is `unresolved=bool(event.causes)` (simulation.py:125). That is a
source-level argument about emptiness, not a constant, and in the data it
is True, not False.

So every field below is classified by SOURCE first:
    CONSTANT         -- a literal in code, provable without running
    DERIVED          -- computed from other state, varies in principle
    STRUCTURALLY FIXED -- varies with an expression that is itself fixed

Only then is data consulted, and never as the proof.

Usage:  python3 tools/mb_recall_term_degeneracy.py
"""
from __future__ import annotations

import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.simulation import SimulationEngine  # noqa: E402
from engine.genesis import build_genesis_world  # noqa: E402

SEEDS = (1, 2, 3, 7, 42)
TICKS = 200
ACTORS = ("rui", "yan")

results: dict[str, list] = {}


def record(k, v):
    results.setdefault(k, []).append(v)


def classify() -> None:
    print("=" * 78)
    print("T1  SOURCE-FIRST CLASSIFICATION OF EVERY recall() INPUT")
    print("=" * 78)
    print()
    repo = Path(__file__).resolve().parent.parent
    sim = (repo / "engine" / "core" / "simulation.py").read_text(encoding="utf-8")
    ker = (repo / "engine" / "memory" / "kernel.py").read_text(encoding="utf-8")
    print("  The ONLY call site that builds event-derived memories:")
    for i, ln in enumerate(sim.splitlines(), 1):
        if any(k in ln for k in ("emotional_salience=",
                                 "personal_importance=",
                                 "relationship_importance=",
                                 "unresolved=",
                                 "tags=",
                                 "interpretation=")):
            print(f"    simulation.py:{i}  {ln.strip()}")
    print()
    print("  CLASSIFICATION (from the writer expressions, not from data):")
    print()
    print("    emotional_salience")
    print("      VERDICT: DERIVED FROM PARTICIPANT COUNT")
    print("      0.55 if len(participants) > 1 else 0.35")
    print()
    print("    personal_importance")
    print("      VERDICT: CONSTANT 0.5 -- a literal at the call site, not a")
    print("              default. No branch, no computation. Carries zero")
    print("              information for every memory, always.")
    print()
    print("    relationship_importance")
    print("      VERDICT: DERIVED FROM PARTICIPANT COUNT")
    print("      0.5 if len(participants) > 1 else 0.0")
    print("      => the same switch as emotional_salience, different scale.")
    print()
    print("    unresolved")
    print("      VERDICT: STRUCTURALLY TRUE, NOT A CONSTANT")
    print("      unresolved=bool(event.causes)")
    print("      and every engine-written event sets causes=[action.id]")
    print("      (simulation.py:899), so the set is never empty.")
    print("      CORRECTION TO MY OWN M12 TEXT: I wrote 'unresolved")
    print("      (always False)'. That was wrong. It is always TRUE, and")
    print("      for a structural reason, not because of a literal.")
    print("      Either way it is a CONSTANT in practice -- but the correct")
    print("      reason matters, and the wrong one would not have proved it.")
    print()
    print("    tags")
    print("      VERDICT: CONSTANT EMPTY -- the call site passes no tags, and")
    print("              remember_event defaults to None -> set() -> empty.")
    print("      => the `term in memory.tags` half of recall()'s overlap term")
    print("         can never match. Provable from source; the empty set in")
    print("         data is only consistent with it.")
    print()
    print("    interpretation")
    print("      VERDICT: NEVER WRITTEN by the event path. The only")
    print("              `interpretation=` assignments in engine/ are on")
    print("              EvidenceRecord and AppraisalRecord, not on Memory.")
    print("              Memory.interpretation stays at its dataclass default.")
    print()
    print("    summary")
    print("      VERDICT: the event fact string (facts[0] of a past event).")
    print("              Free prose produced by the event writer.")
    print()
    print("    recall_strength")
    print("      VERDICT: DERIVED, and its PROTECTION term is what matters:")
    print("        protection = 0.45*salience + 0.30*personal")
    print("                  + 0.15*relationship + 0.10*unresolved")
    print("        recall_strength = exp(-rate*age),")
    print("        rate = decay_rate * (1 - min(0.9, protection))")
    print()
    print("  THE PROTECTION TERM, EVALUATED AS AN EXPRESSION (not sampled):")
    solo = 0.45 * 0.35 + 0.30 * 0.5 + 0.15 * 0.0 + 0.10 * 1
    social = 0.45 * 0.55 + 0.30 * 0.5 + 0.15 * 0.5 + 0.10 * 1
    print(f"    solo   event (n=1, salience 0.35, rel 0.0): protection = {solo:.4f}")
    print(f"    social event (n>1, salience 0.55, rel 0.5): protection = {social:.4f}")
    print(f"    personal_importance is constant 0.5 and unresolved is")
    print(f"    structurally 1, so both contribute the SAME amount to every")
    print(f"    memory. Every non-constant term in protection is a function of")
    print(f"    participant count alone.")
    print(f"    => protection takes {2} values in the entire regime.")
    record("T1_protection_values", 2)


def collapse() -> None:
    print()
    print("=" * 78)
    print("T2  WHAT recall() ACTUALLY COMPUTES, AFTER SUBSTITUTION")
    print("=" * 78)
    print()
    print("  recall(state, owner, cue, limit) sorts by:")
    print("      score = recall_strength + 0.2*cue_overlap + 0.2*salience")
    print()
    print("  Substituting every term established above:")
    print()
    print("      cue_overlap  = substring hits against memory.summary ONLY")
    print("                     (tags is provably always empty, so the")
    print("                     `or term in memory.tags` branch is dead code)")
    print("      salience     = 0.55 if n_participants > 1 else 0.35")
    print("      recall_strength = exp(-decay_rate * age *")
    print("                        (1 - min(0.9, protection(n_participants))))")
    print()
    print("  => EVERY TERM IS A FUNCTION OF (age, n_participants, summary).")
    print("     There is no outcome term, no emotion term, no consequence")
    print("     term, and no interpretation term anywhere in the ranking.")
    print()
    print("  So the ranking collapses to:")
    print("      recency (age)  x  sociality (n_participants)")
    print("      + 0.2 * summary substring matches")
    print()
    print("  The M11 witness -- an older SOCIAL memory outranking a newer SOLO")
    print("  one -- is the recency x sociality trade-off falling out of this")
    print("  expression directly. It was never evidence of a second memory")
    print("  model; it is this expression behaving as written.")
    print()
    record("T2_done", True)


def data_consistency() -> None:
    print()
    print("=" * 78)
    print("T3  DATA CONSISTENCY (corroboration only, never the proof)")
    print("=" * 78)
    print()
    obs = Counter()
    prot = Counter()
    for seed in SEEDS:
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=False)
        for _ in range(TICKS):
            engine.step(world)
            for m in world.memory_state.memories.values():
                ev = next((e for e in world.event_log if e.id == m.event_id),
                          None)
                if ev is None:
                    continue
                n = len(ev.participants)
                obs[("salience", round(m.emotional_salience, 3))] += 1
                obs[("personal", round(m.personal_importance, 3))] += 1
                obs[("relationship", round(m.relationship_importance, 3))] += 1
                obs[("unresolved", bool(m.unresolved))] += 1
                obs[("tags", len(m.tags))] += 1
                obs[("interpretation", bool(m.interpretation))] += 1
                p = (0.45 * m.emotional_salience
                     + 0.30 * m.personal_importance
                     + 0.15 * m.relationship_importance
                     + 0.10 * float(m.unresolved))
                prot[round(p, 4)] += 1
    print("  observed values (data; the SOURCE is what proves the claims):")
    for field in ("salience", "personal", "relationship", "unresolved",
                  "tags", "interpretation"):
        vals = {k[1]: v for k, v in obs.items() if k[0] == field}
        print(f"    {field:<16} {dict(sorted(vals.items(), key=str))}")
    print()
    print(f"  distinct decay-protection values observed : {len(prot)}")
    for v, c in sorted(prot.items()):
        print(f"    protection={v}  x{c}")
    print()
    if len(prot) == 2:
        print("  => matches the symbolic evaluation in T1: exactly two values,")
        print("     one per participant-count class.")
    print()
    print("  NOTE what is NOT here: no outcome-status split, because every")
    print("  committed outcome in this regime is 'success'. That confound is")
    print("  unchanged from M12 and is not resolved by this round.")
    print()
    record("T3_protection_distinct", len(prot))


def main() -> int:
    print("M13  ARE recall()'s REMAINING TERMS DEGENERATE? (read-only)")
    print()
    classify()
    collapse()
    data_consistency()

    print("=" * 78)
    print("M13 RULING")
    print("=" * 78)
    print()
    print("  RULING: CONTINUE OPTION 1, now settled at the root.")
    print()
    print("  Every input to recall()'s ranking is either a literal constant or")
    print("  a function of (age, participant count, summary prose). There is no")
    print("  outcome, emotion, consequence or interpretation term. The cue")
    print("  overlap's `tags` branch is provably dead code. The decay")
    print("  protection collapses to two values, one per participant count.")
    print()
    print("  So recall()'s ordering IS (recency x sociality) + summary")
    print("  substring matching, as ChatGPT hypothesised. Per ChatGPT's stated")
    print("  condition, Memory -> Decision direct wiring can be formally")
    print("  withdrawn from the current architecture route, with recall()")
    print("  RETAINED as a standalone capability.")
    print()
    print("  WHAT WOULD REOPEN THIS: giving any of these fields a real")
    print("  non-participant-count writer -- salience from outcome or")
    print("  consequence, tags actually populated, interpretation populated,")
    print("  or unresolved conditioned on something that can be false. Any of")
    print("  those makes the question live again. None exists today, and that")
    print("  is a statement about the CURRENT implementation, not about")
    print("  recall() as a concept.")
    print()
    print("  SELF-CORRECTION, because ChatGPT's rule caught it: my M12")
    print("  proposal asserted `unresolved` was 'always False'. It is")
    print("  `bool(event.causes)`, which is always TRUE, structurally. I had")
    print("  the wrong value AND the wrong reason; the conclusion (a constant)")
    print("  happened to survive, which is exactly why the error needed")
    print("  correcting rather than quietly fixing.")
    print()
    print("  NOTHING MODIFIED. No wiring, no weights, no production/test change.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())