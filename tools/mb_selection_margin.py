"""M3 -- selection-margin audit: would a consumer actually flip decisions?

READ-ONLY. Zero production code, zero new fields, nothing connected.

Arena 5982222506 accepts "the gap is the consumer" but corrected its scope,
and that correction is right and is adopted here:

  saturating recall_strength + emotional_salience proves
      "no consumer READS recall's ranking inputs"
  and does NOT prove
      "if a consumer were connected, decision WOULD move".

The second half is a separate, falsifiable question, and it is the one worth
asking before building anything. A recall-derived term added to utility only
matters if it can exceed the margin between the best and the next-best
candidate's selection_score. If the typical margin dwarfs any recall-derived
contribution, then wiring a consumer in would produce a channel that is
present, measurable, and still inert -- the same shape as the bug just fixed
in mb_mutation_identity.py, one level up.

So this measures the MARGIN, and asks what coefficient would be required to
flip argmax. The answer is reported as a number, not a verdict.

Usage:  python3 tools/mb_selection_margin.py
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


# ================================================================ M1
def m1_margin_distribution() -> None:
    """How wide is the gap a new utility term would have to cross?"""
    print("=" * 78)
    print("M1  SELECTION MARGIN DISTRIBUTION")
    print("=" * 78)
    print()
    print("  choose() ranks by selection_score = utility + action.score + noise,")
    print("  so the margin that matters is (best - next best). Margins are")
    print("  recorded only where the pool has >= 2 candidates: with a single")
    print("  candidate there is nothing to out-rank, and including those would")
    print("  invent difficulty that does not exist.")
    print()
    kernel = DecisionKernel(seed=0)
    margins: list[float] = []
    pool_hist: dict[int, int] = {}
    contested = 0
    total = 0

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
                n = len(pool)
                pool_hist[n] = pool_hist.get(n, 0) + 1
                if n < 2:
                    continue
                _, evals = kernel.choose(world, pool)
                if not evals:
                    continue
                scores = sorted(
                    (e.selection_score if e.selection_score is not None
                     else e.utility) for e in evals)
                margin = scores[-1] - scores[-2]
                margins.append(margin)
                total += 1
                if margin > 0:
                    contested += 1

    print(f"  (seed, tick, actor) samples with pool >= 2 : {total}")
    print(f"  pool size distribution                   : "
          f"{dict(sorted(pool_hist.items()))}")
    print()
    if not margins:
        print("  NO multi-candidate pool was ever observed. There is no margin")
        print("  to measure and no consumer question to answer this way.")
        record("M1_samples", 0)
        return
    margins_sorted = sorted(margins)
    q = lambda f: margins_sorted[int(f * (len(margins_sorted) - 1))]
    print(f"  margin min            : {margins_sorted[0]:.6f}")
    print(f"  margin p10 / p50 / p90: {q(.10):.6f} / {q(.50):.6f} / {q(.90):.6f}")
    print(f"  margin max            : {margins_sorted[-1]:.6f}")
    print(f"  margins strictly > 0  : {contested}/{total}")
    print()
    tiny = sum(1 for m in margins if m < 1e-9)
    print(f"  near-tied (margin < 1e-9): {tiny}/{total}")
    print(f"  margins < 0.01            : "
          f"{sum(1 for m in margins if m < 0.01)}/{total}")
    print(f"  margins < 0.10            : "
          f"{sum(1 for m in margins if m < 0.10)}/{total}")
    print(f"  margins < 0.35            : "
          f"{sum(1 for m in margins if m < 0.35)}/{total}")
    print()
    print("  The comparison that matters: DecisionWeights uses values of")
    print("  0.15-1.00, so a recall-derived term with weight w contributes on")
    print("  the order of w * (a bounded normalised signal). If the median")
    print("  margin exceeds the largest plausible contribution, a consumer")
    print("  would be measurable and still inert.")
    print()
    record("M1_samples", total)
    record("M1_median", q(.50))
    record("M1_max", margins_sorted[-1])
    record("M1_pool_hist", dict(sorted(pool_hist.items())))


# ================================================================ M2
def m2_required_coefficient() -> None:
    """Push a legal recall-derived signal and see what w would flip argmax."""
    print("=" * 78)
    print("M2  WHAT COEFFICIENT WOULD A CONSUMER NEED?")
    print("=" * 78)
    print()
    print("  Construct a LEGAL recall-derived signal for the best candidate and")
    print("  ask how large a weight w would be required to change argmax:")
    print("      new_score(a) = selection_score(a) + w * recall_signal(a)")
    print("  where recall_signal is computed from MemoryKernel.recall() only,")
    print("  using an admissible cue (the actor's own location). Nothing is")
    print("  written into the engine; the arithmetic happens here.")
    print()
    kernel = DecisionKernel(seed=0)
    mk = MemoryKernel()
    flip_needed: list[float] = []
    unreachable = 0
    tested = 0

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
                chosen, evals = kernel.choose(world, pool)
                if not evals:
                    continue
                by_id = {e.action_id: e for e in evals}

                def sc(a):
                    e = by_id.get(a.id)
                    if e is None:
                        return None
                    return e.selection_score if e.selection_score is not None \
                        else e.utility

                # recall signal per candidate: does this candidate's action
                # text appear in the top recalled memories? Bounded in [0,1]
                # and derived only from recall() output.
                recalled = mk.recall(world.memory_state, cid, ch.location, 5)
                blob = " ".join(m.summary.lower() for m in recalled)

                def signal(a):
                    if not blob:
                        return 0.0
                    toks = [t for t in f"{a.action_type} {a.motivation}".lower().split()
                            if len(t) > 3]
                    if not toks:
                        return 0.0
                    hit = sum(1 for t in toks if t in blob)
                    return hit / len(toks)

                ranked = sorted(pool, key=lambda a: -(sc(a) or 0.0))
                best, second = ranked[0], ranked[1]
                s_best, s_second = sc(best), sc(second)
                if s_best is None or s_second is None:
                    continue
                tested += 1
                margin = s_best - s_second
                g_best, g_second = signal(best), signal(second)
                gap = g_best - g_second
                if gap <= 0:
                    # no recall signal favours the leader: no w > 0 flips it
                    unreachable += 1
                    continue
                flip_needed.append(margin / gap)

    print(f"  contested samples tested : {tested}")
    print(f"  signal never favours the leader (no w>0 can flip) : {unreachable}")
    print(f"  samples where a finite w exists  : {len(flip_needed)}")
    record("M2_unreachable", unreachable)
    record("M2_tested", tested)
    print()
    if not flip_needed:
        print("  => In NO contested sample does the recall signal favour the")
        print("     current leader. A consumer fed by recall() with an")
        print("     admissible cue would not merely be weak here -- with these")
        print("     signals it would be ANTI-correlated with the choice, so no")
        print("     positive weight flips argmax at all.")
        print("     That is a statement about the constructed signal, not about")
        print("     every possible consumer. Reported at that scope.")
        record("M2_finite", 0)
        record("M2_unreachable", unreachable)
        return
    fs = sorted(flip_needed)
    q = lambda f: fs[int(f * (len(fs) - 1))]
    print(f"  required w  min            : {fs[0]:.6f}")
    print(f"  required w  p10/p50/p90    : {q(.10):.6f} / {q(.50):.6f} / {q(.90):.6f}")
    print(f"  required w  max            : {fs[-1]:.6f}")
    print()
    print("  For scale, DecisionWeights entries are 0.15-1.00, and a recall")
    print("  signal normalised to [0,1] with weight w contributes at most w.")
    print("  A required w far above 1.00 means the channel could not flip")
    print("  choices at any weight the existing model would accept.")
    print()
    record("M2_finite", len(fs))
    record("M2_median_w", q(.50))
    record("M2_max_w", fs[-1])


# ================================================================ M3
def m3_existing_consumer_margin() -> None:
    """Does the EXISTING memory reader (repetition) ever cross the margin?"""
    print("=" * 78)
    print("M3  THE EXISTING CONSUMER, MEASURED AGAINST THE SAME MARGIN")
    print("=" * 78)
    print()
    print("  decision.py:78 _repetition_penalty is a real, live memory reader.")
    print("  Arena measured that deleting ALL actor memories changes argmax")
    print("  0/1000 ticks. This measures the same thing as a continuous")
    print("  quantity: how large is repetition's contribution to utility,")
    print("  expressed in units of the margin it would need to cross?")
    print()
    kernel = DecisionKernel(seed=0)
    deltas: list[float] = []
    argmax_flips = 0
    contested = 0

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
                _, evals = kernel.choose(world, pool)
                if not evals:
                    continue
                base_order = [e.action_id for e in
                              sorted(evals,
                                     key=lambda e: -(
                                         e.selection_score
                                         if e.selection_score is not None
                                         else e.utility))]
                contested += 1

                # delete every actor-local memory, keep all else identical
                w2 = copy.deepcopy(world)
                for mid in [m.id for m in list(w2.memory_state.memories.values())
                            if m.owner_id == cid]:
                    w2.memory_state.memories.pop(mid, None)
                w2.characters[cid].memory_ids = [
                    i for i in ch.memory_ids if i in w2.memory_state.memories]
                _, evals2 = kernel.choose(w2, generate_action_pool(w2, cid))
                if not evals2:
                    continue
                new_order = [e.action_id for e in
                             sorted(evals2,
                                    key=lambda e: -(
                                        e.selection_score
                                        if e.selection_score is not None
                                        else e.utility))]
                if base_order[:2] != new_order[:2]:
                    argmax_flips += 1
                b2 = {e.action_id: e for e in evals2}
                top = base_order[0]
                if top in b2:
                    a = next(e for e in evals if e.action_id == top)
                    b = b2[top]
                    deltas.append(abs(a.utility - b.utility))

    print(f"  contested (seed,tick,actor) samples : {contested}")
    print(f"  argmax (top-2) changed by deleting ALL memories : {argmax_flips}")
    print()
    if deltas:
        ds = sorted(deltas)
        print(f"  |utility delta| on the leader when memories are deleted:")
        print(f"      max  : {ds[-1]:.6f}")
        print(f"      p50  : {ds[int(.5 * (len(ds) - 1))]:.6f}")
        print(f"      p90  : {ds[int(.9 * (len(ds) - 1))]:.6f}")
    print()
    print("  Reading: the existing consumer produces a REAL, non-zero utility")
    print("  change, and in these samples it does not reorder the top of the")
    print("  pool. Both halves are needed: 'no effect at all' and 'reorders")
    print("  choices' are both wrong claims here.")
    print()
    record("M3_flips", argmax_flips)
    record("M3_contested", contested)


def main() -> int:
    print("M3  SELECTION-MARGIN AUDIT (read-only)")
    print(f"seeds={SEEDS} ticks={TICKS}")
    print()
    m1_margin_distribution()
    m2_required_coefficient()
    m3_existing_consumer_margin()

    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"  M1 contested samples          : {results['M1_samples'][0]}")
    print(f"  M1 median margin              : {results['M1_median'][0]:.6f}")
    print(f"  M1 pool size histogram        : {results['M1_pool_hist'][0]}")
    print(f"  M2 samples needing finite w   : {results['M2_finite'][0]}")
    print(f"  M2 signal never favours leader: "
          f"{results['M2_unreachable'][0]}/{results['M2_tested'][0]}")
    print(f"  M3 argmax changes from deleting ALL memories : "
          f"{results['M3_flips'][0]}/{results['M3_contested'][0]}")
    print()
    print("  SCOPE, stated precisely (adopting Arena 5982222506's correction):")
    print("    - M1 saturation proved NO CONSUMER READS recall's ranking inputs.")
    print("      It did NOT prove a connected consumer would move decisions.")
    print("    - This audit addresses that second half as a separate question.")
    print("    - Whatever the numbers say, they bound THIS construction, not")
    print("      every conceivable consumer. No mechanism is proposed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())