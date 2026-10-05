"""M11 -- salience-vs-recency probe: does recall() produce an ordering that
recency cannot express?

READ-ONLY. Runs the probe ChatGPT asked for on-platform and Arena already
executed independently. Nothing is wired; no cue derived from a candidate;
blank cue only; natural memories only.

The question, tightened by ChatGPT: find a DETERMINISTIC case where
  - same actor,
  - same historical event set,
  - same action/type conditions,
  - event_log recency puts event X first,
  - recall() puts an OLDER event first, on score,
and then judge whether that difference carries semantic value.

Arena's independent run reported 359/1995 snapshots with >=2 memories,
and 9/41 among contested pools, with a named example. This file
reproduces both numbers rather than citing them.

Usage:  python3 tools/mb_salience_vs_recency.py
"""
from __future__ import annotations

import sys
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


def score(memory, cue_terms):
    """recall()'s own scoring, reproduced so the probe cannot drift from it."""
    overlap = sum(t in memory.summary.lower() or t in memory.tags
                  for t in cue_terms)
    return memory.recall_strength + 0.2 * overlap + 0.2 * memory.emotional_salience


def main() -> int:
    print("=" * 78)
    print("M11  SALIENCE vs RECENCY -- DOES recall() RANK DIFFERENTLY?")
    print("=" * 78)
    print()
    print("  Cue: BLANK. No candidate-derived information enters at any point.")
    print("  Compared, on identical state:")
    print("    recency : newest committed event for this actor")
    print("    recall  : recall_strength + 0.2*cue_overlap + 0.2*salience")
    print()
    mk = MemoryKernel()
    snapshots = 0
    contested_snapshots = 0
    disagreements = 0
    contested_disagreements = 0
    examples = []
    actor_totals = {}

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
                snapshots += 1
                pool = generate_action_pool(world, cid)
                contested = len(pool) >= 2
                if contested:
                    contested_snapshots += 1

                rec = mk.recall(world.memory_state, cid, "", 5)
                if not rec:
                    continue
                top = rec[0]
                # Newest committed event THIS ACTOR PARTICIPATED IN, in any
                # position. The first version filtered on
                # ev.participants[0] == cid, but _record_memories records a
                # memory for EVERY participant regardless of position. That
                # mismatch compared a rui-first event against a memory of an
                # event where rui came second, which made ordinary recency
                # look like a salience disagreement -- and inflated the count
                # to 1344 against Arena's 359.
                owned = [e for e in world.event_log if cid in e.participants]
                if not owned:
                    continue
                newest = max(owned, key=lambda e: (e.tick, e.id))

                if top.event_id != newest.id:
                    # confirm recall's pick really outscores the newest one
                    new_mem = next((m for m in mems
                                    if m.event_id == newest.id), None)
                    if new_mem is None:
                        continue
                    s_top = score(top, ())
                    s_new = score(new_mem, ())
                    if s_top > s_new:
                        disagreements += 1
                        actor_totals[cid] = actor_totals.get(cid, 0) + 1
                        if contested:
                            contested_disagreements += 1
                        if len(examples) < 4:
                            # SNAPSHOT THE SCALARS NOW. Memory objects are
                            # live references and memory_kernel.decay()
                            # mutates recall_strength on every subsequent
                            # tick, so storing the objects and printing
                            # later prints strengths that contradict the
                            # scores -- which is exactly what the first
                            # version of this probe did.
                            examples.append({
                                "seed": seed, "cid": cid,
                                "tick": world.tick, "contested": contested,
                                "top_id": top.event_id,
                                "top_score": s_top,
                                "top_strength": top.recall_strength,
                                "top_salience": top.emotional_salience,
                                "top_tick": top.tick,
                                "new_id": new_mem.event_id,
                                "new_score": s_new,
                                "new_strength": new_mem.recall_strength,
                                "new_salience": new_mem.emotional_salience,
                                "new_tick": new_mem.tick,
                                "newest_event": newest.id,
                                "n_mems": len(mems),
                            })

    print(f"  snapshots with >= 2 memories : {snapshots}")
    print(f"  ... of which contested (pool >= 2) : {contested_snapshots}")
    print(f"  recall ranks an OLDER memory first, strictly outscoring the")
    print(f"  newest one                        : {disagreements}")
    print(f"  ... among contested snapshots      : {contested_disagreements}")
    print(f"  by actor : {actor_totals}")
    print()
    print("  DETERMINISTIC COUNTEREXAMPLES")
    print()
    for ex in examples:
        print(f"    seed{ex['seed']} actor={ex['cid']} tick={ex['tick']} "
              f"(contested={ex['contested']}, memories={ex['n_mems']})")
        print(f"      recall #1 (event tick {ex['top_tick']}) : {ex['top_id']}  "
              f"score={ex['top_score']:.6f}")
        print(f"                   strength={ex['top_strength']:.4f} "
              f"salience={ex['top_salience']:.3f}")
        print(f"      newest    (event tick {ex['new_tick']}) : {ex['new_id']}  "
              f"score={ex['new_score']:.6f}")
        print(f"                   strength={ex['new_strength']:.4f} "
              f"salience={ex['new_salience']:.3f}")
        d_str = ex['top_strength'] - ex['new_strength']
        d_sal = ex['top_salience'] - ex['new_salience']
        driver = ("salience" if d_sal > 0 and d_str < 0
                  else ("recall_strength" if d_str > 0 and d_sal <= 0
                        else "both"))
        relation = ("OLDER" if ex['top_tick'] < ex['new_tick']
                    else ("NEWER" if ex['top_tick'] > ex['new_tick']
                          else "same tick"))
        print(f"      => event tick {ex['top_tick']} is {relation} than "
              f"{ex['new_tick']}, yet scores higher.")
        print(f"         d(recall_strength)={d_str:+.4f}  "
              f"d(salience)={d_sal:+.3f}  -> driver: {driver}")
        print()
    record("snapshots", snapshots)
    record("disagreements", disagreements)
    record("contested_disagreements", contested_disagreements)
    record("contested_snapshots", contested_snapshots)

    print("=" * 78)
    print("WHAT THIS ESTABLISHES, AND WHAT IT DOES NOT")
    print("=" * 78)
    print()
    if disagreements:
        print(f"  ESTABLISHED: recall() DOES produce an ordering recency cannot")
        print(f"  express -- {disagreements} snapshots, including")
        print(f"  {contested_disagreements} contested ones. This FALSIFIES the")
        print("  conditional branch I attached to option 1 ('if salience never")
        print("  outranks recency, recall is just a re-presentation of event")
        print("  history'). Arena measured this independently; the branch is")
        print("  dead and my option-1 justification must not rest on it.")
        print()
        print("  NOT ESTABLISHED: that this ordering should influence action")
        print("  selection. Nothing here is wired. An ordering that differs is")
        print("  a retrieval property, not a decision necessity. No agency")
        print("  change is claimed, because rung 5 was 0/46.")
    else:
        print("  NOT REPRODUCED: recall() never outranks recency here, which")
        print("  would leave option 1 resting on its strongest ground. Arena")
        print("  reported the opposite, so a disagreement would need resolving")
        print("  before any ruling.")
    print()
    print("  SEMANTIC VALUE, judged rather than asserted:")
    print("    salience is written at 0.55 for emotionally-typed events and")
    print("    0.35 for others, and recall_strength decays with age. So the")
    print("    disagreement is not noise -- it is a real trade between 'how")
    print("    recent' and 'how emotionally loaded', using data the event")
    print("    writer already produced.")
    print("    That is a genuinely different retrieval policy, and it is the")
    print("    first evidence in this audit that recall() carries information")
    print("    no existing reader expresses. It is STILL not evidence that")
    print("    the decision needs it.")
    print()
    print("  NOTHING MODIFIED. No wiring, no cue from candidates, no weights.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())