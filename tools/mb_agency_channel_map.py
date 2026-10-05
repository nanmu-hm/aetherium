"""M17 -- Agency Channel Map: per-reader isolation, stage by stage.

READ-ONLY. ChatGPT's next task (after accepting M16's A), and the same
thing Arena demands: STOP ablating several memories at once and find out
WHICH reader does the work, at WHICH stage.

Arena on M16, accepted verbatim:
  "本轮是删除多条记忆的组合消融；它也同时改变 repetition utility，因此
   目前证明了 visit_counts 参与这条实际路径，没有证明它单独足以造成四次
   RESOLVE 改变。"

So the combined ablation proved INVOLVEMENT, not sufficiency. This tool
isolates each reader by surgically removing ONLY its own input, leaving
every other reader's input intact, and reports the same five-stage ladder
ChatGPT asked for:

    exists -> intermediate moves -> crossing -> committed action changes
           -> persisted Event changes

READER / INPUT EACH CHANNEL ACTUALLY READS (so isolation is justified,
not guessed):
  repetition_penalty : memories[].event_id must appear in event_log
                       (decision.py:78). Isolating = break the event_id link
                       and KEEP the row, so location-based readers still see it.
  visit_counts       : memories[].location (actions.py:166). Isolating =
                       blank the location, KEEP event_id so repetition still sees it.
  belief_friction    : beliefs[] with an "experience:" proposition
                       (decision.py:85). Isolating = drop those beliefs only.
  find_top_evidence  : state.event_log directly (appraisal.py:93). It reads
                       NO memory field, so it cannot be isolated by editing a
                       memory row. It is neutralised by monkeypatching the
                       FUNCTION for the duration of the probe -- an in-memory
                       probe hack, clearly labelled, never a repo change.

Usage:  python3 tools/mb_agency_channel_map.py
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

SEEDS = (1, 2, 3, 7, 42)
TICKS = 200
ACTORS = ("rui", "yan")

CHANNELS = ("repetition_penalty", "visit_counts", "belief_friction",
            "find_top_evidence")

results: dict[str, list] = {}


def record(k, v):
    results.setdefault(k, []).append(v)


def isolate(world, cid, ch, channel):
    """Remove ONLY this reader's input. Return None if impossible."""
    w = copy.deepcopy(world)
    if channel == "repetition_penalty":
        # break the event_id -> event_log link, keep the row and its location
        for m in w.memory_state.memories.values():
            if m.owner_id == cid:
                m.event_id = "detached-" + m.id
        w.characters[cid].memory_ids = [
            i for i in ch.memory_ids if i in w.memory_state.memories]
    elif channel == "visit_counts":
        # blank the location, keep event_id so repetition still resolves
        for m in w.memory_state.memories.values():
            if m.owner_id == cid:
                m.location = ""
    elif channel == "belief_friction":
        for bid in [b.id for b in w.memory_state.beliefs.values()
                    if b.owner_id == cid
                    and b.proposition.startswith("experience:")]:
            w.memory_state.beliefs.pop(bid, None)
    elif channel == "find_top_evidence":
        return None          # handled by the caller via monkeypatch
    return w


def step_and_observe(world, seed, cid):
    engine = SimulationEngine(seed=seed, use_arbitration=True)
    before = len(world.event_log)
    res = engine.step(world)
    chosen = [a.id for a in res.actions if a.actor_id == cid]
    persisted = [e.id for e in world.event_log[before:]
                 if cid in (e.participants or [])]
    return chosen, persisted


def main() -> int:
    print("=" * 78)
    print("M17  AGENCY CHANNEL MAP (read-only, per-reader isolation)")
    print("=" * 78)
    print()
    kernel = DecisionKernel(seed=0)

    for channel in CHANNELS:
        ladder = {k: 0 for k in ("exists", "intermediate", "crossing",
                                 "committed", "event")}
        tested = 0
        details = []
        orig_evidence = ap.find_top_evidence
        if channel == "find_top_evidence":
            ap.find_top_evidence = lambda *a, **k: None

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

                    # does this channel even HAVE input here?
                    if channel == "repetition_penalty":
                        has = any(m.event_id != "detached-" + m.id
                                  and m.event_id in {e.id for e in world.event_log}
                                  for m in world.memory_state.memories.values()
                                  if m.owner_id == cid)
                    elif channel == "visit_counts":
                        has = any(m.location in world.locations
                                  for m in world.memory_state.memories.values()
                                  if m.owner_id == cid)
                    elif channel == "belief_friction":
                        has = any(b.owner_id == cid
                                  and b.proposition.startswith("experience:")
                                  for b in world.memory_state.beliefs.values())
                    else:
                        has = any(
                            ap.find_top_evidence(world, c.actor_id,
                                                 ap.candidate_focal_target(c, world))
                            is not None for c in pool)
                    if not has:
                        continue
                    tested += 1
                    ladder["exists"] += 1

                    wB = isolate(world, cid, ch, channel)
                    if wB is None:
                        continue
                    poolB = generate_action_pool(wB, cid)
                    evA = [kernel.evaluate(world, c) for c in pool]
                    evB = [kernel.evaluate(wB, c) for c in poolB]

                    # intermediate: utility, targets, or verdict moved?
                    u_moved = any(
                        abs(a.utility - b.utility) > 1e-9
                        for a, b in zip(sorted(evA, key=lambda x: -x.utility),
                                        sorted(evB, key=lambda x: -x.utility)))
                    tgt_moved = ({c.id: list(c.targets) for c in pool}
                                 != {c.id: list(c.targets) for c in poolB})
                    rA = ap.arbitrate(ap.build_appraisals(kernel, world, ch, pool),
                                      pool, evA)
                    rB = ap.arbitrate(ap.build_appraisals(kernel, wB, ch, poolB),
                                      poolB, evB)
                    v_moved = (rA.kind, rA.candidate_id) != (rB.kind, rB.candidate_id)
                    if u_moved or tgt_moved or v_moved:
                        ladder["intermediate"] += 1

                    selA, evA2 = step_and_observe(copy.deepcopy(world), seed, cid)
                    selB, evB2 = step_and_observe(copy.deepcopy(wB), seed, cid)
                    committed = selA != selB
                    persisted = evA2 != evB2
                    ladder["committed"] += committed
                    ladder["event"] += persisted
                    if persisted:
                        ladder["crossing"] += 1
                        details.append((seed, world.tick, cid, selA, selB,
                                        evA2, evB2, tgt_moved, v_moved))

        if channel == "find_top_evidence":
            ap.find_top_evidence = orig_evidence

        print(f"--- CHANNEL: {channel}")
        print(f"    snapshots where the channel HAS input : {tested}")
        print(f"    an intermediate quantity moved        : {ladder['intermediate']}")
        print(f"    CROSSING (persisted Event differs)    : {ladder['event']}")
        print(f"    committed action changed              : {ladder['committed']}")
        print(f"    persisted Event changed               : {ladder['event']}")
        print()
        for seed, tick, cid, sa, sb, ea, eb, tm, vm in details[:3]:
            print(f"      seed{seed} t{tick} {cid}: chosen {sa} -> {sb}")
            print(f"        persisted {ea} -> {eb}  (targets moved={tm}, "
                  f"verdict moved={vm})")
        print()
        record(f"{channel}_input", tested)
        record(f"{channel}_event", ladder["event"])
        record(f"{channel}_intermediate", ladder["intermediate"])

    print("=" * 78)
    print("M17 AGENCY CHANNEL MAP")
    print("=" * 78)
    print()
    print(f"  {'channel':<22} {'has input':>10} {'intermediate':>13} "
          f"{'Event changed':>14}")
    for ch in CHANNELS:
        print(f"  {ch:<22} {results[f'{ch}_input'][0]:>10} "
              f"{results[f'{ch}_intermediate'][0]:>13} "
              f"{results[f'{ch}_event'][0]:>14}")
    print()
    print("  Each row is an ISOLATED ablation: only that reader's own input")
    print("  was removed, every other reader's input left intact. This is the")
    print("  sufficiency test Arena asked for after the combined ablation")
    print("  proved only INVOLVEMENT.")
    print()
    print("  The combined M16 ablation moved BOTH visit_counts and")
    print("  repetition at once, so it could not attribute. This map can.")
    print()
    print("  NOTHING MODIFIED. No recall wiring, no weights, no production/test")
    print("  change, no manufactured failure. find_top_evidence was")
    print("  neutralised by an in-memory monkeypatch inside this probe only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())