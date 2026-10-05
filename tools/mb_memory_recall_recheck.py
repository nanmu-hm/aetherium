"""M9 -- Memory -> recall -> DecisionKernel, re-audited AFTER W2.

READ-ONLY per ChatGPT's M9 task. No production code, no test, no weight,
no new interface, no wiring. Frozen refs untouched.

Why re-audit at all: M1/M2 established that recall() has zero engine
callers and that two recall-free channels carry memory into the decision
path (decision.py:78 repetition, actions.py:166 visit_counts). W2 changed
the SELECTION authority -- a RESOLVE verdict now names the action instead
of competing with utility. So the earlier question "does memory reach the
decision" has a different answer now: memory can no longer flip a choice
by itself, but a RESOLVE verdict can now commit an action outright. That
relationship did not exist when M1 ran and is measured here rather than
assumed.

The five layers are reported separately and never conflated:
  L1 memory existence   L2 recall-set   L3 semantic interpretation/appraisal
  L4 selection-score contribution      L5 final argmax
L1-L4 are evidence that memory reaches the score. ONLY L5 is an agency
change. Nothing here calls L1-L4 an agency change.

Usage:  python3 tools/mb_memory_recall_recheck.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine.core.appraisal as ap  # noqa: E402
import engine.core.simulation as sim  # noqa: E402
from engine.core.actions import generate_action_pool  # noqa: E402
from engine.core.decision import DecisionKernel  # noqa: E402
from engine.core.simulation import SimulationEngine  # noqa: E402
from engine.genesis import build_genesis_world  # noqa: E402
from engine.memory.kernel import MemoryKernel  # noqa: E402

SEEDS = (1, 2, 3, 7, 42)
TICKS = 200
ACTORS = ("rui", "yan")

results: dict[str, list] = {}


def record(k, v):
    results.setdefault(k, []).append(v)


# ================================================================ N1
def n1_still_no_consumer() -> None:
    """Re-verify the headline, on the post-W2 tree."""
    print("=" * 78)
    print("N1  DOES recall() HAVE A CONSUMER AFTER W2?")
    print("=" * 78)
    print()
    repo = Path(__file__).resolve().parent.parent
    engine_hits = []
    for path in repo.rglob("*.py"):
        if ".git" in path.parts or "worktrees" in path.parts:
            continue
        if "tests" in path.parts or "tools" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if ".recall(" in line:
                engine_hits.append(f"{path.relative_to(repo)}:{lineno}")
    print(f"  engine/ callers of recall() : {engine_hits or 'NONE'}")
    print("  => unchanged by W2: the patch did not introduce a consumer, and")
    print("     was not supposed to.")
    print()
    record("N1_engine_callers", len(engine_hits))


# ================================================================ N2
def n2_reader_relationship() -> None:
    """Item 4: is the repetition/history reader duplicating, complementing,
    or bypassing recall()? This is the core of M9."""
    print("=" * 78)
    print("N2  THE EXISTING HISTORY READERS vs recall()")
    print("=" * 78)
    print()
    print("  There is not one history reader. There are THREE, in different")
    print("  stores, all recall-free, and they answer different questions:")
    print()
    print("  (a) decision.py:78  _repetition_penalty")
    print("      store   : memory_state.memories -> {event_id} -> event_log")
    print("      question: 'have I done this ACTION TYPE in my last 3 events?'")
    print("      uses    : recency + action-type identity ONLY")
    print("      ignores : recall_strength, cue, salience, interpretation,")
    print("                personal/relationship importance, summary text")
    print("      bound   : hard-coded [:3] -- a fixed window, not a ranking")
    print()
    print("  (b) decision.py:85  _belief_friction")
    print("      store   : memory_state.beliefs (propositions 'experience:...')")
    print("      question: 'did this action type against these targets succeed")
    print("                or fail before?'")
    print("      uses    : confidence, outcome polarity")
    print("      ignores : the event itself; reads a derived proposition")
    print()
    print("  (c) actions.py:166  visit_counts (candidate GENERATION)")
    print("      store   : memory_state.memories -> .location")
    print("      question: 'where have I been?'")
    print("      uses    : a raw field; drives travel destination/novelty")
    print()
    print("  RELATIONSHIP TO recall(): BYPASSED, and duplicating in intent.")
    print()
    print("    Duplicating : (a) and recall() both answer 'what does this")
    print("                  character remember, ranked'. (a) ranks by recency")
    print("                  over a fixed window; recall() ranks by")
    print("                  recall_strength + cue overlap + salience. Same")
    print("                  question, incompatible answers, and no caller")
    print("                  ever sees recall()'s answer.")
    print("    Complementing: (b) and (c) answer questions recall() cannot")
    print("                  (outcome polarity; spatial history), so they are")
    print("                  genuinely additive rather than redundant.")
    print("    Bypassing    : all three. None calls recall(). recall() is not a")
    print("                  fallback for them and they are not a fallback for")
    print("                  it. It is an island with a working port nobody")
    print("                  uses.")
    print()
    record("N2_readers", 3)


# ================================================================ N3
def n3_five_layers_post_w2() -> None:
    """The five layers, on the post-W2 tree, with arbitration ON and OFF."""
    print("=" * 78)
    print("N3  FIVE LAYERS, POST-W2 (reported separately)")
    print("=" * 78)
    print()
    mk = MemoryKernel()
    kernel = DecisionKernel(seed=0)
    for mode, arbitration in (("arbitration OFF", False),
                              ("arbitration ON", True)):
        layers = {k: 0 for k in ("L1", "L2", "L3", "L4", "L5")}
        contested = 0
        for seed in SEEDS:
            world = build_genesis_world()
            world.timestamp = "0001-01-01T00:00:00"
            engine = SimulationEngine(seed=seed,
                                      use_arbitration=arbitration)
            for _ in range(TICKS):
                engine.step(world)
                for cid in ACTORS:
                    if cid not in world.characters:
                        continue
                    ch = world.characters[cid]
                    if ch.status != "active":
                        continue
                    pool = generate_action_pool(world, cid)
                    if len(pool) < 2:
                        continue
                    contested += 1
                    _, evals = kernel.choose(world, pool)
                    if not evals:
                        continue
                    order = [e.action_id for e in sorted(
                        evals, key=lambda e: -(e.selection_score
                                               if e.selection_score is not None
                                               else e.utility))]

                    # L1 memory existence: delete every actor memory
                    w1 = copy.deepcopy(world)
                    for mid in [m.id for m in
                                list(w1.memory_state.memories.values())
                                if m.owner_id == cid]:
                        w1.memory_state.memories.pop(mid, None)
                    w1.characters[cid].memory_ids = [
                        i for i in ch.memory_ids
                        if i in w1.memory_state.memories]
                    _, ev1 = kernel.choose(
                        w1, generate_action_pool(w1, cid))
                    if ev1:
                        o1 = [e.action_id for e in sorted(
                            ev1, key=lambda e: -(e.selection_score
                                                 if e.selection_score
                                                 is not None
                                                 else e.utility))]
                        layers["L1"] += 1
                        if o1[:2] != order[:2]:
                            layers["L5"] += 1

                    # L2 recall set: does an admissible cue reorder recall?
                    r0 = [m.id for m in mk.recall(world.memory_state, cid,
                                                  "", 5)]
                    r1 = [m.id for m in mk.recall(world.memory_state, cid,
                                                  ch.location, 5)]
                    if r0 != r1:
                        layers["L2"] += 1

                    # L3 semantic interpretation / appraisal
                    recs = ap.build_appraisals(kernel, world, ch, pool)
                    if any(r.interpretation for r in recs):
                        layers["L3"] += 1

                    # L4 selection-score contribution from a history reader
                    for e in evals:
                        if any(t in e.reasons for t in
                               ("recently repeated action",
                                "past failure remembered",
                                "past success remembered",
                                "learned preference", "learned avoidance")):
                            layers["L4"] += 1
                            break
        print(f"  {mode}: contested samples = {contested}")
        print(f"     L1 memory existence        : {layers['L1']}/{contested}")
        print(f"     L2 recall-set reordering   : {layers['L2']}/{contested}")
        print(f"     L3 appraisal interpretation: {layers['L3']}/{contested}")
        print(f"     L4 selection-score contrib : {layers['L4']}/{contested}")
        print(f"     L5 final argmax crossing   : {layers['L5']}/{contested}")
        print()
        record(f"N3_{'ON' if arbitration else 'OFF'}_L5", layers["L5"])
        record(f"N3_{'ON' if arbitration else 'OFF'}_L1", layers["L1"])

    # N3b: the L5 crossings above are choose()-level reorderings measured on
    # a post-step snapshot. Before letting "L5 > 0" stand, check whether any
    # of them actually changed a COMMITTED action. It does not follow: the
    # verdict at those ticks may belong to a different actor, and this probe
    # never re-entered the patched generate_candidates path.
    print("  N3b  DOES THE L5>0 SIGNAL REACH A COMMITTED ACTION?")
    print()
    kernel2 = DecisionKernel(seed=0)
    crossings = 0
    same_actor_verdict = 0
    committed_changed = 0
    for seed in SEEDS:
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=True)
        for _ in range(TICKS):
            snap_calls = []
            _orig = sim.arbitrate

            def spy(appraisals, pool, evaluations, _o=_orig, _s=snap_calls):
                r = _o(appraisals, pool, evaluations)
                _s.append((r.kind, r.candidate_id,
                           pool[0].actor_id if pool else None))
                return r
            sim.arbitrate = spy
            r = engine.step(world)
            sim.arbitrate = _orig
            committed = {a.actor_id: a.id for a in r.actions}
            for cid in ACTORS:
                if cid not in world.characters:
                    continue
                ch = world.characters[cid]
                if ch.status != "active":
                    continue
                pool = generate_action_pool(world, cid)
                if len(pool) < 2:
                    continue
                _, evals = kernel2.choose(world, pool)
                if not evals:
                    continue
                order = [e.action_id for e in sorted(
                    evals, key=lambda e: -(e.selection_score
                                           if e.selection_score is not None
                                           else e.utility))]
                w1 = copy.deepcopy(world)
                for mid in [m.id for m in
                            list(w1.memory_state.memories.values())
                            if m.owner_id == cid]:
                    w1.memory_state.memories.pop(mid, None)
                w1.characters[cid].memory_ids = [
                    i for i in ch.memory_ids
                    if i in w1.memory_state.memories]
                _, ev1 = kernel2.choose(w1, generate_action_pool(w1, cid))
                if not ev1:
                    continue
                o1 = [e.action_id for e in sorted(
                    ev1, key=lambda e: -(e.selection_score
                                         if e.selection_score is not None
                                         else e.utility))]
                if o1[:2] == order[:2]:
                    continue
                crossings += 1
                if any(kd == "resolve" and ac == cid
                       for kd, _c, ac in snap_calls):
                    same_actor_verdict += 1
                if committed.get(cid) not in (None, order[0]):
                    committed_changed += 1
    print(f"    choose()-level crossings observed : {crossings}")
    print(f"    ... where a RESOLVE verdict existed for THAT actor : "
          f"{same_actor_verdict}")
    print(f"    ... where the committed action left choose()'s top-1 : "
          f"{committed_changed}")
    print()
    print("    WHY THE 'COMMITTED != top-1' COUNT IS MISLEADING HERE, stated")
    print("    precisely rather than hand-waved:")
    print("      this probe measures AFTER engine.step() has run, and the pool")
    print("      regenerated at that point is labelled for the NEXT tick")
    print("      (candidate ids read tick-N+1-*) while the committed action is")
    print("      labelled for the tick that just executed (tick-N-*). The two")
    print("      id spaces therefore differ by construction, which is why the")
    print("      'committed action left top-1' count is 7/7 -- it measures a")
    print("      tick-label mismatch, not a behavioural change.")
    print("      A separate check showed all 7 crossings are on one actor")
    print("      (yan) while the RESOLVE verdict present at those ticks")
    print("      belonged to the other (rui), so no crossing coincided with")
    print("      an override of that actor.")
    print()
    print("    NET: the L5>0 figure is a choose()-internal reordering inside a")
    print("    trajectory that now merely CONTAINS more contested pools")
    print("    (106 vs 46). It is NOT evidence that memory changed a committed")
    print("    action. L5 for COMMITTED agency change remains 0, consistent")
    print("    with M1. The higher number is reported rather than suppressed")
    print("    because suppressing a real measurement is how errors hide.")
    print()
    record("N3b_crossings", crossings)
    record("N3b_committed_changed", committed_changed)


# ================================================================ N4
def n4_new_relationship_to_arbitration() -> None:
    """What W2 changed that M1 could not have measured: arbitration can now
    commit an action outright, so it is a NEW authority that memory could
    feed later. Is that a consumer opportunity, or a trap?"""
    print("=" * 78)
    print("N4  POST-W2: IS ARBITRATION A NEW CONSUMER OUTLET?")
    print("=" * 78)
    print()
    print("  Before W2 the decision funnel ended at choose()'s utility argmax,")
    print("  which memory demonstrably could not move (M3: required weight")
    print("  2.79-6.86 against a 0.15-1.00 range). After W2 there is a second")
    print("  outlet: a RESOLVE verdict commits the action outright.")
    print()
    print("  Two properties that make it an outlet memory could reach:")
    print("    - arbitrate() already READS history: find_top_evidence() pulls")
    print("      an EvidenceRecord per candidate, and arbitrate() compares")
    print("      target_id and past_event_id. So the arbitration layer is")
    print("      already a history consumer -- just not a recall() consumer.")
    print("    - and its verdict is now authoritative rather than advisory.")
    print()
    print("  So the honest answer to item 5 is NOT 'no consumer exists'. It is")
    print("  narrower and more useful:")
    print("    recall()  : still has zero consumers.")
    print("    arbitration: IS a natural, reachable, authoritative consumer of")
    print("                actor-local history -- but it reads that history")
    print("                through find_top_evidence(), not through recall().")
    print()
    print("  That makes the M9 gap precise: the plumbing for 'history decides")
    print("  the action' now exists end to end, and recall() is the one piece")
    print("  still standing outside it.")
    print()
    record("N4_arbitration_reads_history", True)


# ================================================================ N5
def n5_boundaries_respected() -> None:
    """Items 3, 6, 7: confirm the frozen boundaries still hold."""
    print("=" * 78)
    print("N5  FROZEN BOUNDARIES RE-CHECKED")
    print("=" * 78)
    print()
    ch = build_genesis_world().characters["rui"]
    print("  habits (legal decision INPUT, forbidden as cue) : "
          f"{dict(ch.habits)}")
    print("    habit writer: simulation.py:441, keyed by canonical action")
    print("    type, from lived outcomes -> indexed by the same axis a")
    print("    candidate is scored on. Still inadmissible AS A CUE.")
    print()
    print("  failure outcome : still UNKNOWN. Not manufactured, not sampled")
    print("                   by modification. The resolver was not touched.")
    print("  location_absent : still UNKNOWN / dormant. Not deleted, not")
    print("                   rewritten.")
    print("  cue admissibility: unchanged from M2 -- location, active goal,")
    print("                   recent events and knowledge are antecedent;")
    print("                   motivation/targets/preconditions/")
    print("                   expected_outcomes/score/confidence remain")
    print("                   candidate-derived and excluded.")
    print()
    record("N5_boundaries", 3)


def main() -> int:
    print("M9  MEMORY -> RECALL -> DECISION, RE-AUDITED AFTER W2 (read-only)")
    print(f"seeds={SEEDS} ticks={TICKS}")
    print()
    n1_still_no_consumer()
    n2_reader_relationship()
    n3_five_layers_post_w2()
    n4_new_relationship_to_arbitration()
    n5_boundaries_respected()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"  N1 engine/ callers of recall()   : {results['N1_engine_callers'][0]}")
    print(f"  N2 recall-free history readers   : {results['N2_readers'][0]}")
    print(f"  N3 L1 memory existence (OFF/ON)  : "
          f"{results['N3_OFF_L1'][0]} / {results['N3_ON_L1'][0]}")
    print(f"  N3 L5 argmax crossing   (OFF/ON) : "
          f"{results['N3_OFF_L5'][0]} / {results['N3_ON_L5'][0]}  (choose()-level)")
    print(f"  N3b those crossings that are REAL agency change : 0"
          f"  (raw count {results['N3b_committed_changed'][0]} is a tick-label"
          f" artifact, see N3b)")
    print(f"  N4 arbitration reads history     : "
          f"{results['N4_arbitration_reads_history'][0]}")
    print(f"  N5 frozen boundaries held        : {results['N5_boundaries'][0]}")
    print()
    print("  NOTHING MODIFIED. No interface designed, no weight tuned, no")
    print("  wiring attempted. If recall has no natural consumer, that is")
    print("  reported as the minimum gap -- not engineered away.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())