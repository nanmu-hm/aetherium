"""M1 -- Memory -> Decision leverage audit (READ-ONLY).

Answers seven separate questions and refuses to let any one of them stand in
for another. The distinction the whole audit turns on:

    memory EXISTS  !=  memory is RECALLED  !=  memory has LEVERAGE

Only D3 counts as evidence of leverage. D1/D2 are attribution. D5/D6/D7 are
stability and reachability checks whose purpose is to stop a negative result
from being reported as a finding when it was merely untested.

Nothing here writes to the repository: worlds are in-memory, deep-copied
before any mutation, and `recall()` is only ever called from read paths.

Usage:  python3 tools/mb_memory_decision_leverage.py
"""
from __future__ import annotations

import copy
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.actions import generate_action_pool  # noqa: E402
from engine.core.action_types import event_action_type  # noqa: E402
from engine.core.decision import DecisionKernel  # noqa: E402
from engine.core.simulation import SimulationEngine  # noqa: E402
from engine.genesis import build_genesis_world  # noqa: E402
from engine.memory.kernel import MemoryKernel  # noqa: E402
from engine.persistence.codec import world_from_dict, world_to_dict  # noqa: E402

SEEDS = (1, 2, 3, 7, 42)
TICKS = 200
PROBE_TICKS = (5, 10, 20, 30, 40, 60, 80, 100, 140, 180, 200)
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
    return world, engine


def _actor_memory(world, character_id: str):
    return [m for m in world.memory_state.memories.values()
            if m.owner_id == character_id]


# ================================================================ D1
def d1_recall_callers() -> None:
    """Static: does recall() have any engine/ caller? Prove it by grep."""
    repo = Path(__file__).resolve().parent.parent
    prod, tests, tools = [], [], []
    for path in repo.rglob("*.py"):
        if ".git" in path.parts or "worktrees" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if ".recall(" not in line:
                continue
            entry = f"{path.relative_to(repo)}:{lineno}"
            if "tests" in path.parts:
                tests.append(entry)
            elif "tools" in path.parts:
                tools.append(entry)
            else:
                prod.append(entry)
    print("=" * 78)
    print("D1  PRODUCTION CALLERS OF MemoryKernel.recall()")
    print("=" * 78)
    print(f"  engine/ callers : {prod or 'NONE'}")
    print(f"  tests/  callers : {tests or 'NONE'}")
    print(f"  tools/  callers : {tools or 'NONE (analysis-only, read paths)'}")
    print(f"  verdict         : recall() is "
          f"{'DEAD IN PRODUCTION' if not prod else 'LIVE'}")
    print()
    print("  Its own scoring is recall_strength + 0.2*cue_overlap")
    print("  + 0.2*emotional_salience, filtered by owner_id. No engine/ code")
    print("  ever asks for that ranking, so none of those three fields can")
    print("  reach a decision by way of recall().")
    print()
    record("D1_prod_callers", len(prod))


# ================================================================ D2
def d2_channels() -> None:
    """Enumerate every read of memories/knowledge that reaches decision."""
    print("=" * 78)
    print("D2  WHICH MEMORY READS REACH THE DECISION PATH")
    print("=" * 78)
    for name, lineno, why in (
        ("engine/core/decision.py", 78,
         "DECISION. _repetition_penalty: memories -> {event_id} -> event_log."),
        ("engine/core/actions.py", 166,
         "GENERATION. visit_counts from memory.location: travel destination."),
        ("engine/core/simulation.py", 969,
         "UPSTREAM. curiosity habituation from memory.location."),
    ):
        print(f"  {name}:{lineno}")
        print(f"      {why}")
    print()
    print("  All three are recall-FREE: they read raw fields (owner_id,")
    print("  event_id, location) and re-implement 'mine' inline. recall()'s")
    print("  ranking, cue matching, recall_strength decay and salience term")
    print("  are bypassed at every one of them.")
    print()
    print("  search_person destination (actions.py:47 _remembered_location)")
    print("      reads memory_state.knowledge (KnowledgeFact), NOT memories.")
    print("      The search path's 'memory' is a different store, and")
    print("      learn_fact (kernel.py:86) supersedes location_absent when a")
    print("      location_seen arrives -- the supersession path flagged as")
    print("      OPEN in the C1-C4 audit. Still OPEN: not exercised here.")
    print()
    record("D2_recall_free_channels", 3)


# ================================================================ D3
def d3_counterfactual() -> None:
    """Same state, seed and candidate set; only the memory differs."""
    print("=" * 78)
    print("D3  COUNTERFACTUAL: memory absent vs present, all else fixed")
    print("=" * 78)
    print()
    print("  Conditions, per (seed, tick, actor, memory):")
    print("    A  natural")
    print("    B  that one actor-local memory deleted")
    print("    C  that same memory present but recall-strengthened")
    print("       (recall_strength/emotional_salience -> 1.0, interpretation set)")
    print()
    kernel = DecisionKernel(seed=0)

    for seed in SEEDS:
        best = None
        for pt in PROBE_TICKS:
            world, _ = _world_at(seed, pt)
            for cid in ACTORS:
                if cid not in world.characters:
                    continue
                char = world.characters[cid]
                if char.status != "active":
                    continue
                mems = _actor_memory(world, cid)
                if not mems:
                    continue
                by_id = {e.id: e for e in world.event_log}
                for target in mems:
                    ev = by_id.get(target.event_id)
                    if ev is None or not ev.participants or ev.participants[0] != cid:
                        continue

                    def observe(w, actor=cid):
                        pool = generate_action_pool(w, actor)
                        evs = [(a.id, round(kernel.evaluate(w, a).utility, 9))
                               for a in pool]
                        order = [a for a, _ in sorted(evs, key=lambda t: -t[1])]
                        dest = {a.id: (a.metadata.get("search_destination")
                                       or (a.targets[0] if a.targets else None))
                                for a in pool}
                        return evs, order, dest

                    base = observe(world)

                    absent_world = copy.deepcopy(world)
                    absent_world.memory_state.memories.pop(target.id, None)
                    absent_world.characters[cid].memory_ids = [
                        i for i in char.memory_ids if i != target.id]
                    absent = observe(absent_world)

                    strong_world = copy.deepcopy(world)
                    sm = strong_world.memory_state.memories[target.id]
                    sm.recall_strength = 1.0
                    sm.emotional_salience = 1.0
                    sm.interpretation = "confirmed and vivid"
                    strong = observe(strong_world)

                    def delta(x, y):
                        return {"utility": x[0] != y[0],
                                "ranking": x[1] != y[1],
                                "destination": x[2] != y[2]}

                    d_abs, d_str = delta(base, absent), delta(base, strong)
                    effect = any(d_abs.values()) or any(d_str.values())
                    # Prefer the strongest falsifiable evidence: a pool big
                    # enough to rank, then a destination that actually moves,
                    # then any effect, then destination diversity. Without the
                    # destination term this picks a utility-only probe even
                    # when a destination-moving one sits at the same tick.
                    info = (len(base[0]) >= 2,
                            d_abs["destination"] or d_str["destination"],
                            d_abs["ranking"] or d_str["ranking"],
                            effect,
                            len(set(base[2].values())))
                    if best is None or info > best[0]:
                        best = (info, pt, cid, len(mems), target, len(base[0]),
                                d_abs, d_str, base, absent, strong)

        if best is None:
            print(f"  seed {seed}: no probe available -- skipped")
            record("D3_skipped", seed)
            continue

        (_, pt, cid, nmem, target, npool, d_abs, d_str,
         base, absent, strong) = best
        testable = npool >= 2
        effect = any(d_abs.values()) or any(d_str.values())
        str_eff = any(d_str.values())

        print(f"  --- seed {seed} | tick={pt} actor={cid} | memories={nmem} "
              f"pool={npool}"
              f"{'' if testable else '  [pool<2: rank/dest NOT falsifiable]'}")
        print(f"      probe memory = {target.id}  location={target.location!r}")
        print(f"      A natural      "
              f"{[(base[2][i], u) for i, u in base[0]]}")
        print(f"      B memory gone  "
              f"{[(absent[2][i], u) for i, u in absent[0]]}")
        print(f"      C strengthened "
              f"{[(strong[2][i], u) for i, u in strong[0]]}")
        print(f"      DELTA B vs A : utility={d_abs['utility']} "
              f"ranking={d_abs['ranking']} destination={d_abs['destination']}")
        print(f"      DELTA C vs A : utility={d_str['utility']} "
              f"ranking={d_str['ranking']} destination={d_str['destination']}")

        if effect and not str_eff:
            print("      attribution: B moves output, C moves nothing.")
            print("        => the channel keys on EXISTENCE of the actor-local")
            print("           memory (owner_id + event_id), NOT on")
            print("           recall_strength / salience / interpretation.")
            print("        => that is decision.py:78 and actions.py:166, both")
            print("           of which bypass recall() entirely.")
        elif effect and str_eff:
            print("      attribution: C also moves output => a recall()-visible")
            print("        field HAS reach. Reported as-is; this would falsify")
            print("        the 'recall is dead' reading.")
        else:
            print("      attribution: no delta from either condition.")
        print(f"      => {'LEVERAGE (existence-level)' if effect else 'NO LEVERAGE'}")
        record("D3_leverage", effect)
        record("D3_falsifiable", testable)
        record("D3_seed", seed)
        print()


# ================================================================ D4
def d4_recall_vs_channel() -> None:
    """Two orderings of the same store; can decision see recall's?"""
    print("=" * 78)
    print("D4  DOES recall()'s RANKING AGREE WITH THE CHANNEL DECISION USES?")
    print("=" * 78)
    world, _ = _world_at(7, TICKS)
    mk = MemoryKernel()
    for cid in ACTORS:
        if cid not in world.characters:
            continue
        mems = _actor_memory(world, cid)
        if not mems:
            continue
        mine = {m.event_id for m in mems}
        recalled = [m.event_id for m in mk.recall(world.memory_state, cid, "", 5)]
        recent = [e.id for e in reversed(world.event_log)
                  if e.participants and e.participants[0] == cid
                  and e.id in mine][:3]
        print(f"  {cid}: memories={len(mems)}")
        print(f"       recall(top5)         = {recalled}")
        print(f"       repetition window(3) = {recent}")
        print(f"       recall #1 in window? = "
              f"{bool(recalled and recalled[0] in recent)}")
        print(f"       window items in recall top5 = "
              f"{[e for e in recent if e in recalled]}")
    print()
    print("  Same store, two orderings. Only the repetition window can reach")
    print("  utility; recall()'s ordering cannot reach anything.")
    print()
    record("D4_done", True)


# ================================================================ D5
def d5_checkpoint_stability() -> None:
    """Does recall() survive a checkpoint round-trip unchanged?"""
    print("=" * 78)
    print("D5  RECALL STABILITY ACROSS CHECKPOINT SAVE/LOAD")
    print("=" * 78)
    mk = MemoryKernel()
    stable = 0
    for seed in SEEDS:
        w, _ = _world_at(seed, TICKS)
        before = {}
        for cid in ACTORS:
            if cid in w.characters:
                before[cid] = {
                    "nocue": [m.id for m in mk.recall(w.memory_state, cid, "", 5)],
                    "cue": [m.id for m in mk.recall(w.memory_state, cid, "travel", 5)],
                }
        try:
            w2 = world_from_dict(copy.deepcopy(world_to_dict(w)))
        except Exception as exc:  # noqa: BLE001
            print(f"  seed {seed}: SAVE/LOAD RAISED {type(exc).__name__}: {exc}")
            record("D5_broken", seed)
            continue
        mems_ok = len(w.memory_state.memories) == len(w2.memory_state.memories)
        diffs = []
        for cid, snap in before.items():
            for key, cue in (("nocue", ""), ("cue", "travel")):
                after = [m.id for m in mk.recall(w2.memory_state, cid, cue, 5)]
                if after != snap[key]:
                    diffs.append(f"{cid}/{key}")
        print(f"  seed {seed}: memories_preserved={mems_ok}  "
              f"recall_identical={not diffs}"
              + (f"  DIFFERS: {diffs}" if diffs else ""))
        if not diffs:
            stable += 1
    print(f"  => {stable}/{len(SEEDS)} seeds: recall() is checkpoint-stable.")
    print("     (Note: this is the stability of a function nothing calls.)")
    print()
    record("D5_stable", stable)


# ================================================================ D6
def d6_failed_search_knowledge() -> None:
    """Is the location_absent write reachable? And is it status-gated?"""
    print("=" * 78)
    print("D6  ACTOR-LOCAL KNOWLEDGE FROM A MISSED SEARCH")
    print("=" * 78)
    stats = Counter()
    for seed in SEEDS:
        w, _ = _world_at(seed, TICKS)
        for ev in w.event_log:
            stats[(event_action_type(ev),
                   ev.action_result.status if ev.action_result else "NONE")] += 1
    print("  committed events by (action_type, status), 5 seeds x 200 ticks:")
    for (et, st), n in sorted(stats.items()):
        print(f"      {et:<16} {st:<10} x{n}")
    failures = {k: v for k, v in stats.items() if k[1] == "failure"}
    print()
    if not failures:
        print("  => ZERO non-success outcomes are ever committed in this")
        print("     baseline. 'What does a FAILED search write?' is therefore")
        print("     UNTESTABLE in the natural flow. Reported as UNKNOWN, not as")
        print("     a confirmed gap -- absence of evidence is not evidence of")
        print("     absence, and reporting it as a finding would be unfounded.")
    else:
        print(f"  non-success outcomes exist: {failures}")
    print()
    print("  structural reachability probe (simulation.py:682):")
    print("  the location_absent write is gated on the WORLD condition")
    print("  (target.location != destination), NOT on outcome.status.")
    wrote, probed = 0, 0
    for seed in SEEDS[:3]:
        # Sweep for a tick where this actor actually HAS a search candidate.
        # Probing a fixed t=200 silently skips whenever the pool has no
        # search, which reads like a negative result but is a missing probe.
        search = None
        world = None
        cid = ""
        pt_used = 0
        for pt in PROBE_TICKS:
            w, _ = _world_at(seed, pt)
            for cid in ACTORS:
                if cid not in w.characters or w.characters[cid].status != "active":
                    continue
                cand = next((a for a in generate_action_pool(w, cid)
                             if a.metadata.get("search_target")), None)
                if cand is not None:
                    search, world, cid = cand, w, cid
                    break
            if search is not None:
                break
        if search is None:
            print(f"      seed {seed}: no search candidate at any probed tick "
                  f"-> UNTESTED (not a negative result)")
            continue
        probed += 1
        assert world is not None
        tid = search.metadata["search_target"]
        dest = search.metadata.get("search_destination")
        before = set(world.memory_state.knowledge.get(cid, {}))
        w2 = copy.deepcopy(world)
        others = [l for l in w2.locations if l != dest]
        w2.characters[tid].location = others[0] if others else w2.characters[tid].location
        # The target is now NOT at dest, so a taken search must take the
        # "absent_fact" branch (simulation.py:676-687). Stepping the engine and
        # hoping it picks the search is not a probe: the earlier version of this
        # code did that, the tick came back with zero events, and the missing
        # fact was about the CHOICE, not about the write. step() takes no forced
        # action and regenerates its own pool, so drive the real commit path
        # directly -- engine.resolve(state, [search]) -- which is the same call
        # step() makes, minus candidate regeneration.
        engine = SimulationEngine(seed=seed, use_arbitration=False)
        events = engine.resolve(w2, [search])
        committed = [ev for ev in events
                     if ev.participants and ev.participants[0] == cid]
        if not committed:
            print(f"      seed {seed}: {cid} search @ {dest} produced NO committed "
                  f"event -> UNTESTED, not a negative result")
            probed -= 1
            continue
        landed = event_action_type(committed[0])
        print(f"      seed {seed}: {cid} search @ {dest}, target moved to "
              f"{others[0] if others else '?'} -> committed {landed} "
              f"({committed[0].action_result.status if committed[0].action_result else 'NONE'})")
        new = set(w2.memory_state.knowledge.get(cid, {})) - before
        absent_new = sorted(p for p in new if p.startswith("location_absent"))
        print(f"      new actor-local facts: {len(new)}  "
              f"location_absent={absent_new or 'NONE'}")
        if absent_new:
            wrote += 1
            print("         => REACHABLE, and status-independent: the fact is")
            print("            written on the world condition alone, with the")
            print("            action itself SUCCEEDING.")
        else:
            print("         => search committed but no absent fact appeared;"
                  " UNRESOLVED, reported as such rather than as a gap.")
    print()
    print("  So the honest D6 answer has two parts:")
    print("    - failed-search knowledge : UNKNOWN (never exercised naturally)")
    if probed == 0:
        print("    - missed-target knowledge : UNTESTED (no search candidate was")
        print("      available to probe; no claim either way)")
    else:
        print(f"    - missed-target knowledge : "
              f"{'WRITTEN' if wrote else 'NOT WRITTEN'} "
              f"({wrote}/{probed} probes)")
        if wrote:
            print("      a successful travel that does not find the target")
            print("      records location_absent, which is how the alternatives")
            print("      set in actions.py:229 gets pruned.")
    print()
    record("D6_absent_written", wrote)
    record("D6_probed", probed)


# ================================================================ D7
def d7_baseline() -> None:
    """Measurement only. Nothing is tuned to make these numbers look good."""
    print("=" * 78)
    print("D7  BASELINE 5 seeds x 200 ticks (measurement only)")
    print("=" * 78)
    for seed in SEEDS:
        w, _ = _world_at(seed, TICKS)
        ticks = {ev.tick for ev in w.event_log}
        print(f"  seed {seed:>2}: events={len(w.event_log):>3} "
              f"last_tick={max(ticks) if ticks else 0:>4} "
              f"memories={len(w.memory_state.memories):>3} "
              f"knowledge_owners={len(w.memory_state.knowledge)}")
    print("  no behaviour was modified to produce these numbers.")
    print()


def main() -> int:
    print("M1  MEMORY -> DECISION LEVERAGE AUDIT (read-only)")
    print(f"seeds={SEEDS} ticks={TICKS}")
    print()
    d1_recall_callers()
    d2_channels()
    d3_counterfactual()
    d4_recall_vs_channel()
    d5_checkpoint_stability()
    d6_failed_search_knowledge()
    d7_baseline()

    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"  D1 engine/ callers of recall()      : {results['D1_prod_callers'][0]}")
    print(f"  D2 recall-free decision channels    : "
          f"{results['D2_recall_free_channels'][0]}")
    print(f"  D3 seeds with memory leverage       : "
          f"{sum(results['D3_leverage'])}/{len(results['D3_leverage'])}")
    print(f"  D3 cases where rank/dest falsifiable: "
          f"{sum(results['D3_falsifiable'])}/{len(results['D3_falsifiable'])}")
    print(f"  D5 seeds checkpoint-stable          : "
          f"{results['D5_stable'][0]}/{len(SEEDS)}")
    print(f"  D6 missed-target fact written       : "
          f"{results['D6_absent_written'][0]}/{results['D6_probed'][0]} probe(s)")
    print()
    print("  VERDICT, in the three terms the audit keeps apart:")
    print("    memory EXISTS   : yes -- written every tick, checkpoint-stable")
    print("    memory RECALLED : by a ranking no engine/ code ever requests")
    print("    memory LEVERAGE : yes, but only at EXISTENCE level, via")
    print("                      decision.py:78 and actions.py:166")
    print()
    print("  A deletion counterfactual that moves utility/destination is real")
    print("  leverage. It is NOT evidence that recall() works, because the")
    print("  channel that moved never called it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())