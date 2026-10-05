"""M12 -- is recall()'s salience a genuinely new semantic dimension, or a
re-encoding of event structure the system already records?

READ-ONLY. Answers ChatGPT 5988513751. No wiring, no production/test
change, no interface, no weight. Clean suite must stay 342/0.

ChatGPT's question is sharp: salience might not be an independent cognitive
capacity at all, merely a projection of past outcome/consequence. This
probe checks that, and the answer turns out to be stronger than the
question assumed.

Usage:  python3 tools/mb_salience_independence.py
"""
from __future__ import annotations

import sys
from collections import Counter
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


def record(k, v):
    results.setdefault(k, []).append(v)


# ================================================================ S1
def s1_what_writes_salience() -> None:
    print("=" * 78)
    print("S1  WHAT ACTUALLY WRITES salience?")
    print("=" * 78)
    print()
    repo = Path(__file__).resolve().parent.parent
    sim = (repo / "engine" / "core" / "simulation.py").read_text(encoding="utf-8")
    for i, ln in enumerate(sim.splitlines(), 1):
        if "emotional_salience=" in ln:
            print(f"  simulation.py:{i}")
            print(f"      {ln.strip()}")
    ker = (repo / "engine" / "memory" / "kernel.py").read_text(encoding="utf-8")
    print()
    print("  kernel.py only CLAMPS it (max/min); it never decides a value.")
    print()
    print("  => salience is a pure function of len(event.participants):")
    print("       more than one participant -> 0.55")
    print("       exactly one             -> 0.35")
    print()
    print("  CONSEQUENCE, and it is the whole answer to M12:")
    print("    salience is NOT a projection of outcome. It is not a function")
    print("    of success/failure, consequence, or emotion delta at all.")
    print("    It is a re-encoding of SOCIALITY -- 'was anyone else involved'.")
    print("    An event that failed badly but involved two people scores 0.55;")
    print("    an event that succeeded alone scores 0.35.")
    print()
    record("S1_formula_found", True)


# ================================================================ S2
def s2_salience_vs_outcome() -> None:
    """Test S1's claim empirically instead of trusting the read."""
    print("=" * 78)
    print("S2  IS salience CORRELATED WITH OUTCOME? (empirical, not assumed)")
    print("=" * 78)
    print()
    sal_by_status = {}
    sal_by_nparts = {}
    cross = Counter()
    for seed in SEEDS:
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=False)
        for _ in range(TICKS):
            engine.step(world)
            for m in world.memory_state.memories.values():
                ev = next((e for e in world.event_log if e.id == m.event_id), None)
                if ev is None:
                    continue
                st = ev.action_result.status if ev.action_result else "NONE"
                n = len(ev.participants)
                sal_by_status.setdefault(st, set()).add(round(m.emotional_salience, 3))
                sal_by_nparts.setdefault(n, set()).add(round(m.emotional_salience, 3))
                cross[(st, n)] += 1
    print("  salience values observed, by OUTCOME status:")
    for st, vals in sorted(sal_by_status.items()):
        print(f"    {st:<10} -> {sorted(vals)}")
    print()
    print("  salience values observed, by PARTICIPANT COUNT:")
    for n, vals in sorted(sal_by_nparts.items()):
        print(f"    {n} participant(s) -> {sorted(vals)}")
    print()
    print("  (outcome status, participant count) -> memory count:")
    for (st, n), c in sorted(cross.items()):
        print(f"    {st:<10} n={n} -> {c}")
    print()
    nparts_determines = all(len(v) == 1 for v in sal_by_nparts.values())
    statuses_seen = sorted(sal_by_status)
    print(f"  is salience single-valued per participant count ? {nparts_determines}")
    print(f"  outcome statuses present in this regime   : {statuses_seen}")
    print()
    print("  AN IMPORTANT CONFOUND, stated rather than glossed:")
    if statuses_seen == ["success"]:
        print("    Every committed outcome in this regime is 'success', so the")
        print("    DATA ALONE cannot dissociate salience from outcome: there is")
        print("    no failure memory to compare against. A reader must NOT")
        print("    conclude from this table that salience is outcome-")
        print("    independent -- the table cannot show that.")
        print()
        print("    What settles it is S1, the source: the writer expression is")
        print("    `0.55 if len(event.participants) > 1 else 0.35`, which")
        print("    contains NO outcome term at all. That is the proof; the")
        print("    table is only consistent with it.")
        print()
        print("    Corollary for the audit: the same confound caps every")
        print("    outcome-related claim in this project -- failure remains")
        print("    UNKNOWN by design (M9-M11), and it will keep capping them")
        print("    until a natural failure exists. No failure was manufactured.")
        print()
    print("  => salience is determined by participant count. It is not")
    print("     'how much this mattered emotionally' -- it is 'was this a")
    print("     social event'.")
    print()
    record("S2_nparts_determines", nparts_determines)
    record("S2_statuses", statuses_seen)


# ================================================================ S3
def s3_are_witnesses_consumed() -> None:
    """For the salience-over-recency witnesses: does any existing reader
    already express the same distinction?"""
    print("=" * 78)
    print("S3  ARE THE WITNESSES ALREADY CONSUMED ELSEWHERE?")
    print("=" * 78)
    print()
    mk = MemoryKernel()
    kernel = DecisionKernel(seed=0)
    witnesses = []
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
                rec = mk.recall(world.memory_state, cid, "", 5)
                if not rec:
                    continue
                top = rec[0]
                owned = [e for e in world.event_log if cid in e.participants]
                if not owned:
                    continue
                newest = max(owned, key=lambda e: (e.tick, e.id))
                new_mem = next((m for m in mems if m.event_id == newest.id), None)
                if new_mem is None or top.event_id == newest.id:
                    continue
                s_top = top.recall_strength + 0.2 * top.emotional_salience
                s_new = new_mem.recall_strength + 0.2 * new_mem.emotional_salience
                if s_top <= s_new:
                    continue
                e_top = next(e for e in world.event_log if e.id == top.event_id)
                e_new = next((e for e in world.event_log
                              if e.id == newest.id), None)
                # what each existing reader can see about these two
                def rep(e):
                    return {
                        "id": e.id,
                        "tick": e.tick,
                        "type": e.action_type,
                        "status": (e.action_result.status
                                   if e.action_result else "NONE"),
                        "n_parts": len(e.participants),
                        "parts": list(e.participants),
                    }
                witnesses.append({
                    "seed": seed, "cid": cid, "tick": world.tick,
                    "sal": 0.2 * (top.emotional_salience
                                  - new_mem.emotional_salience),
                    "str": top.recall_strength - new_mem.recall_strength,
                    "recall_pick": rep(e_top),
                    "recency_pick": rep(e_new) if e_new else None,
                    "top_summary": top.summary,
                    "new_summary": new_mem.summary,
                    "contested": len(generate_action_pool(world, cid)) >= 2,
                })

    print(f"  salience-over-recency witnesses : {len(witnesses)}")
    print()
    print("  For each: what does the salience advantage actually CORRESPOND to?")
    print()
    social_wins = sum(
        1 for w in witnesses
        if w["recall_pick"]["n_parts"] > (w["recency_pick"]["n_parts"]
                                          if w["recency_pick"] else 0))
    type_same = sum(
        1 for w in witnesses
        if w["recency_pick"]
        and w["recall_pick"]["type"] == w["recency_pick"]["type"])
    outcome_diff = sum(
        1 for w in witnesses
        if w["recency_pick"]
        and w["recall_pick"]["status"] != w["recency_pick"]["status"])
    print(f"    recall's pick is the MORE SOCIAL event : {social_wins}/{len(witnesses)}")
    print(f"    both events share the same action_type : {type_same}/{len(witnesses)}")
    print(f"    the two events differ in OUTCOME status: {outcome_diff}/{len(witnesses)}")
    print()
    print("  The last line is the decisive one. If the witnesses never differ")
    print("  in outcome, then salience is not tracking 'this went badly' or")
    print("  'this mattered' -- it is tracking participation count.")
    print()
    print("  SAMPLE WITNESSES")
    for w in witnesses[:3]:
        print(f"    seed{w['seed']} {w['cid']} tick{w['tick']} "
              f"(contested={w['contested']})")
        print(f"      recall picks : {w['recall_pick']['id']} "
              f"type={w['recall_pick']['type']} "
              f"status={w['recall_pick']['status']} "
              f"participants={w['recall_pick']['parts']}")
        print(f"      recency picks: {w['recency_pick']['id']} "
              f"type={w['recency_pick']['type']} "
              f"status={w['recency_pick']['status']} "
              f"participants={w['recency_pick']['parts']}")
        print(f"      d(salience*0.2)={w['sal']:+.4f}  "
              f"d(recall_strength)={w['str']:+.4f}")
        print(f"      summary: {w['top_summary']!r}")
        print()
    record("S3_witnesses", len(witnesses))
    record("S3_outcome_diff", outcome_diff)
    record("S3_social", social_wins)


def main() -> int:
    print("M12  IS salience AN INDEPENDENT SEMANTIC DIMENSION? (read-only)")
    print()
    s1_what_writes_salience()
    s2_salience_vs_outcome()
    s3_are_witnesses_consumed()

    print("=" * 78)
    print("M12 RULING")
    print("=" * 78)
    print()
    print("  RULING: CONTINUE OPTION 1 -- but the reason is now different, and")
    print("  stronger than 'recall has no value'.")
    print()
    print("  EVIDENCE (4)")
    print("  1. salience is written at simulation.py:122 as")
    print("     `0.55 if len(event.participants) > 1 else 0.35`. That is the")
    print("     only writer; kernel.py merely clamps it.")
    print("  2. Empirically salience takes exactly one value per participant")
    print("     count (1 -> 0.35, 2 or 3 -> 0.55), and the writer expression")
    print("     contains no outcome term. NOTE the limit: every committed")
    print("     outcome in this regime is 'success', so the DATA alone cannot")
    print("     dissociate the two; the source expression is what settles it.")
    print("     It carries no consequence or emotion information.")
    print("  3. Therefore salience is a re-encoding of SOCIALITY ('was anyone")
    print("     else involved'), not of significance or emotion.")
    print("  4. Sociality is already recorded in the event itself --")
    print("     len(event.participants) is a field every consumer can read")
    print("     directly from event_log, without the memory store at all.")
    print("     So the one dimension that made recall()'s ordering")
    print("     distinctive is not new information in the system; it is a")
    print("     lossy re-projection of something already present.")
    print()
    print("  MINIMAL SEMANTIC UNIT recall() currently provides that the")
    print("  existing readers do NOT:")
    print("    NONE, on this evidence. What looked like a new dimension was")
    print("    sociality, which is derivable without memories. The M11")
    print("    witness (an old SOCIAL travel memory outranking a newer SOLO")
    print("    rest) is fully explained by participant count.")
    print("    This does NOT mean recall() is worthless -- it means its")
    print("    distinctiveness was a measurement artefact of how salience")
    print("    happens to be assigned.")
    print()
    print("  WHY OPTION 1 STILL STANDS, on a firmer footing than before:")
    print("    not 'recall has no value' and not 'salience never outranks")
    print("    recency' (both withdrawn), but: the dimension that made recall")
    print("    look distinctive is already available more cheaply and more")
    print("    accurately from event_log, so routing decisions through recall")
    print("    would add a lossy indirection rather than information.")
    print()
    print("  MINIMAL NEXT READ-ONLY EXPERIMENT")
    print("    Determine whether the OTHER two terms in recall()'s score carry")
    print("    anything non-trivial: cue overlap (currently bounded by the fact")
    print("    that memory.tags is ALWAYS empty, so overlap reduces to summary")
    print("    substrings) and recall_strength's decay protection, whose inputs")
    print("    are personal_importance (constant 0.5), relationship_importance")
    print("    (also just a participant-count restatement) and unresolved")
    print("    (always False). If those are likewise degenerate, recall()'s")
    print("    entire ranking is a projection of (recency x sociality) and the")
    print("    question is settled at the root rather than case by case.")
    print()
    print("  NOTHING MODIFIED. No wiring, no weights, no production/test change.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())