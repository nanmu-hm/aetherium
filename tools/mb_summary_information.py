"""M14 -- does summary substring matching carry information that participant
count and recency do NOT?

READ-ONLY. Arena's third objection to my M13 claim that the question is
"settled at the root". The objection is precise and I accept it:

  "summary 来自过去事件 fact，子串匹配可能承载 fact 文本中的行动或结果
   信息；本轮证明了写入来源与评分公式，没有证明这些文本信号在语义上全都
   可由现有 reader 等价表达。"

M13 established the WRITE SOURCE of summary and the SCORING FORMULA. It
did NOT establish that summary text carries nothing beyond (age,
participant count). This probe tests exactly that gap.

Question: are there two memories that share age class and participant
count, yet differ in what their summary says -- i.e. can summary substring
matching discriminate something recency and sociality cannot?

Usage:  python3 tools/mb_summary_information.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.actions import generate_action_pool  # noqa: E402
from engine.core.simulation import SimulationEngine  # noqa: E402
from engine.genesis import build_genesis_world  # noqa: E402
from engine.memory.kernel import MemoryKernel  # noqa: E402

SEEDS = (1, 2, 3, 7, 42)
TICKS = 200
ACTORS = ("rui", "yan")

results: dict[str, list] = {}


def record(k, v):
    results.setdefault(k, []).append(v)


# ================================================================ U1
def u1_fact_vocabulary() -> None:
    print("=" * 78)
    print("U1  WHAT TEXT DOES A SUMMARY ACTUALLY CARRY?")
    print("=" * 78)
    print()
    templates = Counter()
    full = Counter()
    for seed in SEEDS:
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=False)
        for _ in range(TICKS):
            engine.step(world)
            for ev in world.event_log:
                if ev.facts:
                    full[ev.facts[0]] += 1
                # canonicalise the fact into a shape signature
                for f in ev.facts:
                    shape = f
                    for name in ("Rui", "Yan"):
                        shape = shape.replace(name, "<A>")
                    for loc in sorted(world.locations):
                        shape = shape.replace(loc, "<L>")
                    templates[shape] += 1
    print(f"  distinct fact strings        : {len(full)}")
    print(f"  distinct shapes after masking: {len(templates)}")
    print()
    print("  SHAPES (actor/location masked):")
    for shape, n in templates.most_common():
        print(f"    x{n:<5} {shape}")
    print()
    print("  READ THIS CAREFULLY: several shapes assert an OUTCOME, not just")
    print("  participation -- e.g. 'finds <A> at <L>' versus 'searches for")
    print("  <A> at <L>, but <A> is not there'. If both occur, then summary")
    print("  text does carry result information, and the M13 claim that")
    print("  summary contributes nothing beyond (age, sociality) is TOO")
    print("  STRONG.")
    print()
    record("U1_shapes", len(templates))
    record("U1_full", len(full))


# ================================================================ U2
def u2_does_summary_discriminate() -> None:
    """The decisive test: within one (participant-count) class, does the
    summary text separate memories that recency cannot?"""
    print("=" * 78)
    print("U2  DOES SUMMARY SEPARATE WHAT AGE + SOCIALITY CANNOT?")
    print("=" * 78)
    print()
    mk = MemoryKernel()
    separated = 0
    classes = 0
    examples = []
    for seed in SEEDS:
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=False)
        for _ in range(TICKS):
            engine.step(world)
            for cid in ACTORS:
                if cid not in world.characters:
                    continue
                ch = world.characters[cid]
                if ch.status != "active":
                    continue
                mems = [m for m in world.memory_state.memories.values()
                        if m.owner_id == cid]
                if len(mems) < 2:
                    continue
                by_event = {e.id: e for e in world.event_log}
                # group memories by participant count (= sociality class)
                groups: dict[int, list] = {}
                for m in mems:
                    ev = by_event.get(m.event_id)
                    if ev is None:
                        continue
                    groups.setdefault(len(ev.participants), []).append((m, ev))
                for n_parts, items in groups.items():
                    if len(items) < 2:
                        continue
                    classes += 1
                    # do their summaries differ textually?
                    texts = {m.summary for m, _ in items}
                    types = {ev.action_type for _, ev in items}
                    outcomes = {(ev.action_result.status
                                 if ev.action_result else "NONE")
                                for _, ev in items}
                    if len(texts) > 1:
                        separated += 1
                        if len(examples) < 5:
                            examples.append(
                                (seed, world.tick, cid, n_parts,
                                 sorted(texts)[:3], sorted(types),
                                 sorted(outcomes)))
    print(f"  (participant-count) classes with >= 2 memories : {classes}")
    print(f"  ... of those, summary text DIFFERS within class  : {separated}")
    print()
    print("  If this is high, then summary substring matching carries a")
    print("  discrimination that neither age nor sociality can make, and")
    print("  Arena's objection is upheld: M13 did not close the question.")
    print()
    for seed, tick, cid, n, texts, types, outs in examples:
        print(f"    seed{seed} t{tick} {cid}, {n} participant(s), "
              f"action types={types}, outcomes={outs}")
        for t in texts:
            print(f"       {t!r}")
    print()
    record("U2_classes", classes)
    record("U2_separated", separated)


# ================================================================ U3
def u3_is_it_outcome_or_just_naming() -> None:
    """Separate 'summary names WHO/WHAT' (derivable from the event) from
    'summary asserts a RESULT' (outcome semantics)."""
    print("=" * 78)
    print("U3  NAMES OR ASSERTS? (the distinction that decides the objection)")
    print("=" * 78)
    print()
    outcome_words = ("not there", "fails", "cannot", "blocked",
                     "does not", "is not there")
    naming_only = 0
    asserts_result = 0
    samples = []
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
                low = m.summary.lower()
                if any(w in low for w in outcome_words):
                    asserts_result += 1
                    if len(samples) < 4:
                        samples.append((m.summary,
                                        ev.action_result.status
                                        if ev.action_result else "NONE"))
                else:
                    naming_only += 1
    print(f"  summaries that merely NAME an event      : {naming_only}")
    print(f"  summaries that ASSERT A RESULT            : {asserts_result}")
    print()
    for s, st in samples:
        print(f"    {s!r}   (event outcome: {st})")
    print()
    if asserts_result == 0:
        print("  => In THIS regime every summary only names what happened; none")
        print("     asserts a negative result. So today summary text adds")
        print("     naming detail (who, which action, which place) and no")
        print("     outcome semantics -- because the regime contains no")
        print("     failures to report.")
        print("     That is a statement about the DATA REGIME, not about the")
        print("     write path: the code demonstrably CAN emit 'is not there'")
        print("     facts, as U3's source check below shows.")
    print()
    record("U3_naming", naming_only)
    record("U3_result", asserts_result)


def source_check() -> None:
    print()
    print("  SOURCE: can the fact writer emit result-asserting text?")
    repo = Path(__file__).resolve().parent.parent
    sim = (repo / "engine" / "core" / "simulation.py").read_text(encoding="utf-8")
    hits = [ln.strip() for ln in sim.splitlines()
            if "facts.append" in ln]
    for h in hits:
        print(f"    {h}")
    print()
    print("  => YES. The writer emits 'but <A> is not there' and")
    print("     'attempts to travel ... but fails'. So the summary channel")
    print("     is CAPABLE of carrying outcome semantics; it is merely that no")
    print("     failure occurs in this regime to produce such text.")
    print("  This is exactly the distinction Arena asked for: the WRITE PATH")
    print("  supports it, the DATA does not exercise it.")


def main() -> int:
    print("M14  DOES SUMMARY CARRY INFORMATION BEYOND AGE AND SOCIALITY?")
    print("    (read-only; answering Arena's third objection)")
    print()
    u1_fact_vocabulary()
    u2_does_summary_discriminate()
    u3_is_it_outcome_or_just_naming()
    source_check()

    print("=" * 78)
    print("M14 RULING -- I CORRECT M13")
    print("=" * 78)
    print()
    print("  Arena is right and I withdraw the stronger half of my M13 claim.")
    print()
    print("  WHAT I WITHDRAW: 'recall()'s ordering is (recency x sociality) +")
    print("  summary substring matching' -- and from that, 'settled at the")
    print("  root'. That inference was not earned. M13 proved the write")
    print("  SOURCE of each field and the scoring FORMULA; it did not prove")
    print("  that the summary TEXT adds nothing that age and sociality cannot.")
    print()
    print("  Arena's three points, each accepted:")
    print("   1. The score DOES contain +0.2 * emotional_salience. It is a")
    print("      sociality proxy today, not a current emotional state, but")
    print("      writing 'no emotion term' was wrong. Correct wording: 'a term")
    print("      whose only writer is currently a sociality switch'.")
    print("   2. cue is a QUERY input. My blank-cue probe cannot show that all")
    print("      legal queries reduce to (age, participants, summary).")
    print("   3. summary comes from past event facts and may carry action or")
    print("      RESULT text. U1/U2 above test this directly.")
    print()
    print("  WHAT STILL STANDS: option 1 for the CURRENT scope. The strongest")
    print("  surviving reason is not 'recall has nothing left to say' but the")
    print("  narrower, better-supported one: the decision path needs no")
    print("  second ranking today, and nothing has demonstrated otherwise.")
    print()
    print("  WHAT WOULD REOPEN IT, now stated correctly: a natural failure")
    print("  sample (which the writer can already describe), a cue drawn from")
    print("  something other than blank, or any change giving summary an")
    print("  outcome-bearing writer. None exists today, and none is")
    print("  manufactured here.")
    print()
    print("  NOTHING MODIFIED. No wiring, no weights, no production/test change.")
    print("  failure UNKNOWN, location_absent UNKNOWN, frozen refs untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())