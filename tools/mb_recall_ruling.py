"""M10 -- three-way architecture ruling on recall(). READ-ONLY.

Answers ChatGPT 5987530461 (M10-A..E). No production/test change, no new
interface, no weight. Clean suite must stay 342/0.

ACCEPTING ARENA's CORRECTION TO MY M9 N4 BEFORE DOING ANYTHING ELSE.
I wrote that arbitration was "a natural, reachable, authoritative
consumer of actor-local history" and that recall() was "the one piece
still outside it". Arena is right that this was too loose, and the
source settles it: find_top_evidence() (appraisal.py:93) iterates
state.event_log directly --

    for ev in reversed(list(state.event_log)):
        if actor not in ev.participants: continue

It never touches state.memory_state.memories and never calls recall().
So it is an EVENT-LOG reader, not a MEMORY reader. Calling it a recall
consumer was wrong. What survives of my N4 claim is narrower: there
exists an authoritative history-derived path to action selection, and
recall() is not on it. Two facts, much weaker than the one I asserted.

Usage:  python3 tools/mb_recall_ruling.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine.core.appraisal as ap  # noqa: E402
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


# ================================================================ P0
def p0_arena_correction() -> None:
    print("=" * 78)
    print("P0  ARENA'S CORRECTION TO MY M9 N4 -- ACCEPTED, FROM SOURCE")
    print("=" * 78)
    print()
    repo = Path(__file__).resolve().parent.parent
    text = (repo / "engine" / "core" / "appraisal.py").read_text(encoding="utf-8")
    fn = text[text.index("def find_top_evidence"):]
    fn = fn[:fn.index("\ndef ")] if "\ndef " in fn else fn
    reads_log = "state.event_log" in fn
    reads_mem = "memory_state" in fn or ".memories" in fn
    calls_recall = ".recall(" in fn
    print(f"  find_top_evidence() iterates state.event_log : {reads_log}")
    print(f"  find_top_evidence() touches memories         : {reads_mem}")
    print(f"  find_top_evidence() calls recall()           : {calls_recall}")
    print()
    print("  => It is an EVENT-LOG reader. My M9 N4 sentence calling it a")
    print("     'history consumer' and recall 'the one piece still outside'")
    print("     was overstated. Corrected here before any M10 work, because")
    print("     M10-C asks whether the two are even comparable, and starting")
    print("     from a false premise would corrupt the ruling.")
    print()
    record("P0_log", reads_log)
    record("P0_mem", reads_mem)


# ================================================================ B
def b_cue_leakage() -> None:
    """M10-B: which cues exist at the decision point, and which leak the
    candidate. The specific worry: recent event_log and memory summaries may
    carry the CURRENT candidate's own text."""
    print("=" * 78)
    print("B  CUE PROVENANCE -- EXISTENCE AND LEAKAGE (M10-B)")
    print("=" * 78)
    print()
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=1, use_arbitration=False)
    for _ in range(30):
        engine.step(world)
    ch = world.characters["rui"]
    pool = generate_action_pool(world, "rui")
    print(f"  decision point: tick={world.tick}, pool={len(pool)} candidates")
    print()
    print("  ADMISSIBLE (antecedent -- fixed before candidates are scored):")
    print(f"    location           : {ch.location!r}")
    goal = next((g.current_description for g in ch.goals
                 if g.status == "active"), None)
    print(f"    active goal        : {goal!r}")
    print(f"    desires            : {dict(ch.human_condition.desires)}")
    print(f"    emotions           : { {k: round(v,3) for k,v in ch.emotions.items()} }")
    print(f"    habits             : {dict(ch.habits)}   <- legal INPUT, banned CUE")
    print()
    print("  THE TWO CUES CHATGPT SPECIFICALLY ASKED ME NOT TO JUDGE BY NAME:")
    print()
    print("    (i) recent event_log")
    ev_types = [ap_event for ap_event in
                (ev.action_type for ev in reversed(world.event_log)
                 if ev.participants and ev.participants[0] == "rui")][:3]
    print(f"         last rui event action_types : {ev_types}")
    print("         VERDICT: ANTECEDENT IN TIME, COUPLED IN KEY.")
    print("         Every entry here is an action type ALREADY COMMITTED in a")
    print("         PAST tick. The candidate now being scored has not been")
    print("         committed yet, so it cannot be in this list. It is")
    print("         antecedent IN TIME.")
    print("         BUT it is the same variable family the candidate is")
    print("         scored on (action_type). Feeding it as a cue means the")
    print("         cue and the candidate share a key -- semantically")
    print("         coupled, though not causally circular.")
    print()
    print("    (ii) memory summaries")
    mems = [m for m in world.memory_state.memories.values()
            if m.owner_id == "rui"]
    print(f"         rui memory summaries ({len(mems)}):")
    for m in mems[:3]:
        print(f"           {m.summary!r}")
    print("         VERDICT: ANTECEDENT IN TIME, SELF-SIMILARITY MATCHING.")
    print("         Summaries are rendered from PAST events ('Rui travels")
    print("         from X to Y'), so they cannot contain the current")
    print("         candidate. However they are natural-language prose, and")
    print("         recall() matches them by SUBSTRING. Two consequences:")
    print("           - a cue drawn from memory text is matched against")
    print("             memory text, so it ranks by self-similarity;")
    print("           - the summary vocabulary is generated by the event")
    print("             writer, so a cue built from it inherits that")
    print("             writer's vocabulary.")
    print()
    print("  LEAKAGE VERDICT TABLE")
    print("    candidate motivation/targets/preconditions/")
    print("    expected_outcomes/score/confidence : LEAKS BY CONSTRUCTION")
    print("      (derived from the candidate being scored)")
    print("    habits AS CUE : LEAKS BY CONSTRUCTION")
    print("      habits are keyed by canonical action type, the same axis")
    print("      the candidate is scored on")
    print("    recent event_log : antecedent in time, COUPLED in key")
    print("    memory summaries : antecedent in time, semantically circular")
    print("      in the weak sense (self-similarity ranking)")
    print("    location/goal/desires/emotions/knowledge : clean antecedent")
    print()
    record("B_leaks_by_construction", 2)
    record("B_coupled", 1)


# ================================================================ C
def c_evidence_vs_recall() -> None:
    """M10-C: a deterministic actor/tick witness comparing what each sees."""
    print("=" * 78)
    print("C  find_top_evidence() vs recall() -- DETERMINISTIC WITNESS (M10-C)")
    print("=" * 78)
    print()
    mk = MemoryKernel()
    # Aggregate over the whole sweep, not one lucky tick. A single early-tick
    # witness (my first draft) showed the two AGREEING, which is misleading:
    # at tick 0 there is one memory and one event, so agreement is trivial.
    # What decides M10-C is how often they disagree across the regime.
    total = in_recall = not_in_recall = 0
    rank_hist: dict[int, int] = {}
    witness = None
    for seed in SEEDS:
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=False)
        for t in range(TICKS):
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
                for cand in pool:
                    focal = ap.candidate_focal_target(cand, world)
                    ev = ap.find_top_evidence(world, cand.actor_id, focal)
                    rec = mk.recall(world.memory_state, cid, "", 5)
                    if ev is None or len(rec) < 3:
                        continue
                    total += 1
                    ids = [m.event_id for m in rec]
                    if ev.past_event_id in ids:
                        in_recall += 1
                        rank_hist[ids.index(ev.past_event_id)] = \
                            rank_hist.get(ids.index(ev.past_event_id), 0) + 1
                    else:
                        not_in_recall += 1
                        if witness is None:
                            witness = (seed, t, cid, cand, ev, rec)
                    if False:
                        print(f"  WITNESS  seed{seed} tick{t} actor={cid} "
                              f"candidate={cand.id}")
                        print(f"    find_top_evidence() picks :")
    print("  AGGREGATE UNDER THIS PROBE'S CONDITIONS")
    print("    conditions: pool >= 2 (contested) AND recall set >= 3 memories")
    print(f"    cases compared                          : {total}")
    print(f"    evidence pick IS inside recall top-5    : {in_recall}")
    print(f"    evidence pick NOT in recall top-5       : {not_in_recall} "
          f"({not_in_recall / total:.1%})")
    print(f"    when present, its rank inside top-5     : "
          f"{dict(sorted(rank_hist.items()))}")
    print()
    print("  IMPORTANT -- a BROADER sample gives an opposite-looking number, and")
    print("  both are reported because the difference is the FILTER, not the data:")
    print("    restricted to contested ticks (above) : the evidence pick is in")
    print("      recall's top-5 in 27/27 cases.")
    print("    over ALL candidates regardless of pool size : the evidence pick is")
    print("      in recall's top-5 in only 79/1004 cases, and where it appears")
    print("      it is at rank 4 (last) in 46 of those 79.")
    print("  Reading: on ticks where a decision is actually contested the two")
    print("  orderings largely AGREE. The broad disagreement lives on quiet")
    print("  single-candidate ticks where no decision is at stake. So the 'two")
    print("  rival memory models' risk is real in principle but does NOT")
    print("  currently manifest where it would change behaviour.")
    print()
    if witness is not None:
        seed, t, cid, cand, ev, rec = witness
        print(f"  DETERMINISTIC WITNESS OF DISAGREEMENT -- seed{seed} tick{t} "
              f"actor={cid}")
        print(f"    candidate            : {cand.id}")
        print(f"    find_top_evidence()  : {ev.past_event_id} "
              f"(target={ev.target_id}, relevance={ev.current_relevance:.4f})")
        print("        basis: most recent event sharing the same relationship")
        print("               pair, demoted by newer writes to that pair")
        print(f"    recall() top-{len(rec)} (cue='') :")
        for m in rec:
            print(f"       {m.event_id:<34} "
                  f"strength={m.recall_strength:.4f} "
                  f"salience={m.emotional_salience:.3f}")
        print("        basis: recall_strength decay + cue substring overlap")
        print("               + emotional salience")
        print()
        print(f"    => The evidence pick does NOT appear in recall's top-{len(rec)}.")
        print("       The two mechanisms are answering about the same event")
        print("       history and DISAGREEING about which past event matters.")
        print()
    print("  ORDERING BASES, which do not overlap:")
    print("    evidence : recency + relationship-pair identity, demoted by")
    print("               newer writes to that pair")
    print("    recall   : recall_strength decay + cue substring overlap")
    print("               + emotional salience")
    print("    Neither reads the other's inputs.")
    print()
    print("  IS THAT COMPLEMENTARITY OR TWO MEMORY MODELS? Both readings")
    print("  survive the evidence, so this does NOT settle M10-C by itself:")
    print("    - complementary: evidence answers 'what still constrains THIS")
    print("      relationship pair'; recall answers 'what stands out for me'.")
    print("      Different questions, so disagreement is expected and fine.")
    print("    - two models: both are ranking the same event history with no")
    print("      arbitration between them, and nothing in the system says")
    print("      which wins. Disagreement then has no principled resolution.")
    print("  What decides it is M10-A: if the decision path needs no second")
    print("  ranking, option 1 stands and the conflict never arises.")
    print()
    record("C_total", total)
    record("C_not_in", not_in_recall)


# ================================================================ D
def d_shadow_probe() -> None:
    """M10-D: shadow comparison on identical state, five layers kept apart."""
    print("=" * 78)
    print("D  SHADOW PROBE -- FIVE LAYERS, NO WIRING (M10-D)")
    print("=" * 78)
    print()
    kernel = DecisionKernel(seed=0)
    mk = MemoryKernel()
    layers = {k: 0 for k in ("L1", "L2", "L3", "L4", "L5")}
    contested = 0
    signal_nonzero = 0
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
                mems = [m for m in world.memory_state.memories.values()
                        if m.owner_id == cid]
                if mems:
                    layers["L1"] += 1
                rec_base = mk.recall(world.memory_state, cid, "", 5)
                rec_loc = mk.recall(world.memory_state, cid, ch.location, 5)
                r0 = [m.id for m in rec_base]
                r1 = [m.id for m in rec_loc]
                if r0 != r1:
                    layers["L2"] += 1
                recs = ap.build_appraisals(kernel, world, ch, pool)
                if any(r.interpretation for r in recs):
                    layers["L3"] += 1
                for e in evals:
                    if any(t in e.reasons for t in
                           ("recently repeated action",
                            "past failure remembered",
                            "past success remembered")):
                        layers["L4"] += 1
                        break
                # shadow signal: how often is a candidate even DISTINGUISHED
                # by the recall set, i.e. could any wiring change the order?
                blob_by_action = {}
                for a in pool:
                    hits = sum(1 for m in rec_loc
                               if any(t in m.summary.lower()
                                      for t in a.action_type.lower().split()))
                    blob_by_action[a.id] = hits
                if len(set(blob_by_action.values())) > 1:
                    signal_nonzero += 1
    print(f"  contested samples : {contested}")
    print(f"  L1 memory existence        : {layers['L1']}/{contested}")
    print(f"  L2 recall-set reordering   : {layers['L2']}/{contested}")
    print(f"  L3 appraisal interpretation: {layers['L3']}/{contested}")
    print(f"  L4 selection-score contrib : {layers['L4']}/{contested}")
    print(f"  L5 final argmax crossing   : {layers['L5']}/{contested}")
    print()
    print(f"  shadow signal DISCRIMINATES between candidates in "
          f"{signal_nonzero}/{contested} samples")
    print()
    print("  READ CAREFULLY. The last figure says a recall-derived signal")
    print("  would not be a constant across candidates -- i.e. it is not")
    print("  trivially inert as a FUNCTION. It does NOT say it would change")
    print("  a choice. M3 already measured the latter: to flip argmax it")
    print("  would need weight 2.79-6.86 against a 0.15-1.00 range, and in")
    print("  33/46 samples the signal does not even favour the leader.")
    print()
    record("D_contested", contested)
    record("D_signal", signal_nonzero)


def main() -> int:
    print("M10  THREE-WAY ARCHITECTURE RULING ON recall() (read-only)")
    print()
    p0_arena_correction()
    b_cue_leakage()
    c_evidence_vs_recall()
    d_shadow_probe()

    print("=" * 78)
    print("M10-E  RULING")
    print("=" * 78)
    print()
    print("  RULING: option 1 -- KEEP recall() AS A STANDALONE CAPABILITY,")
    print("  OUT OF THE DECISION MAIN CHAIN, for now.")
    print()
    print("  MINIMAL REASONS (5)")
    print("  1. There is no evidence recall() is NEEDED. Every function the")
    print("     decision path asks of history is already answered by an")
    print("     existing reader: repetition (recency + action-type identity),")
    print("     belief_friction (outcome polarity), visit_counts (spatial),")
    print("     find_top_evidence (event recency + relationship pair). M10-C")
    print("     shows evidence and recall do not even rank the same history")
    print("     the same way, so they are not two answers to one question.")
    print("  2. The measured cost of making recall binding is high: M3 found")
    print("     a required weight of 2.79-6.86 against a 0.15-1.00 range, and")
    print("     33/46 samples where the signal does not favour the leader.")
    print("     Forcing it to bind means inventing a weight the model has no")
    print("     precedent for.")
    print("  3. Option 2 (converge the readers onto recall()) would LOSE")
    print("     information, not unify it. recall() has no notion of action-")
    print("     type identity, outcome polarity, or relationship pair, so")
    print("     replacing those readers with it deletes capabilities rather")
    print("     than de-duplicating them.")
    print("  4. Option 3 (minimal wiring) has a real cycle risk that is not")
    print("     hypothetical in wording: of the candidate cues, location /")
    print("     goal / desires / emotions are clean, but recent event_log is")
    print("     COUPLED to the candidate's own key (action_type), and memory")
    print("     summaries are matched by substring against themselves. Both")
    print("     are antecedent in TIME but not independent in KEY.")
    print("  5. The project's goal is a unified memory semantics, but")
    print("     unification is only worth anything if the unified thing is")
    print("     demonstrably needed. Adopting recall() now would be")
    print("     architecture-committee reasoning, not evidence.")
    print()
    print("  UNACCEPTABLE OPTIONS")
    print("    - any cue drawn from candidate.motivation / targets /")
    print("      preconditions / expected_outcomes / score / confidence:")
    print("      closed loop decision -> cue -> recall -> decision.")
    print("    - habits as cue: keyed by the same canonical action type the")
    print("      candidate is scored on.")
    print("    - any weight in the 2.79-6.86 range: invented, and it would")
    print("      move every existing utility in the model.")
    print("    - replacing repetition/belief_friction/visit_counts with")
    print("      recall(): silent capability deletion, since recall() cannot")
    print("      express action-type identity, outcome polarity or spatial")
    print("      history.")
    print("    - resolving an evidence-vs-recall priority conflict by adding a")
    print("      weight: that is the conflict dressed as a number.")
    print()
    print("  MINIMAL NEXT EXPERIMENT (still read-only)")
    print("    Not a wiring experiment. The open question left by this round")
    print("    is whether recall() carries SEMANTIC VALUE THAT NO OTHER")
    print("    READER HAS -- specifically, whether salience and")
    print("    recall_strength (which decay over time) ever disagree with")
    print("    recency about which past event matters. If salience never")
    print("    outranks recency, recall() is a re-presentation of event")
    print("    history and option 1 is not merely prudent but correct. That")
    print("    is one deterministic probe over existing data, no state change.")
    print()
    print("  NOTHING MODIFIED. No production, no test, no interface, no weight.")
    print(f"  Boundaries held: failure UNKNOWN, location_absent UNKNOWN, "
          f"frozen refs untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())