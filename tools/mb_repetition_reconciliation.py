"""M17-Rb: corrected repetition witness reconciliation.

Supersedes 2603928's tool. Arena (on the platform, 11 minutes after my
post) accepted the SEMANTIC ruling but rejected 2603928's B3 as
evidence for three concrete reasons, each now fixed and re-verified:

  1. My "matched" B3 detach picked the actor's FIRST-3-linked memory
     rows in dict order (event-0/1/2), not the three M16's ablation
     removed (the most-recent three event-linked rows, which for these
     witnesses include event-13). The matched intervention — detaching
     exactly M16's three rows' event links, rows kept — gives
     -0.132167, penalty 1/3, IDENTICAL to M16's row-drop. Verified.

  2. New-events slicing used `event_log[-len(res.actions):]`, which
     returns the ENTIRE log when 0 actions were selected (`[-0:]`).
     B2's "PERSISTED event B" list was therefore the whole history,
     not the new events. Fixed with `before = len(event_log)`.

  3. B3 stepped a deepcopy of w_b3 and then read w_b3.event_log (the
     un-stepped world). Fixed: step the world being read.

M17's actual table row (detach ALL of the actor's links) is retained as
B4: window empties, penalty back to 0, rest selected again. This is the
non-monotonic effect: row-drop (M16) and link-detach (M17) are
different interventions on the same reader, landing on opposite sides
of the "which older event the window falls back to" cliff.

READ-ONLY. No production/test/weight change, no recall wiring, no
manufactured failure.

Usage:  python3 tools/mb_repetition_reconciliation.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.actions import generate_action_pool
from engine.core.decision import DecisionKernel
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world


def recent3_event_ids(world, cid):
    """The three event IDs M16's combined ablation targeted: the actor's
    three most recent event-linked event_log entries."""
    return [e.id for e in
            [e for e in reversed(world.event_log)
             if e.participants and e.participants[0] == cid][:3]]


def main() -> int:
    kernel = DecisionKernel(seed=0)
    for seed, tick in ((1, 41), (42, 35)):
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=False)
        for _ in range(tick):
            engine.step(world)
        cid = "yan"
        ch = world.characters[cid]
        r3 = recent3_event_ids(world, cid)

        pool_a = generate_action_pool(world, cid)
        evs_a = [kernel.evaluate(world, c) for c in pool_a]
        byid_a = {e.action_id: e for e in evs_a}
        rest = next((c for c in pool_a if c.id.endswith("-rest")), None)
        u_a = byid_a[rest.id].utility if rest else 0.0

        print(f"=== seed{seed} t{tick} actor={cid}")
        print(f"  M16 recent3 = {r3}")
        print(f"  A: pool={[c.id for c in pool_a]}  rest utility={u_a:+.6f}  "
              f"reasons={byid_a[rest.id].reasons if rest else None}")
        print()

        # ---- B1: M16's exact combined ablation: drop the 3 rows ----
        w_b1 = copy.deepcopy(world)
        for m in [m for m in list(w_b1.memory_state.memories.values())
                  if m.owner_id == cid and m.event_id in set(r3)]:
            w_b1.memory_state.memories.pop(m.id, None)
        w_b1.characters[cid].memory_ids = [
            i for i in ch.memory_ids if i in w_b1.memory_state.memories]
        pool_b1 = generate_action_pool(w_b1, cid)
        rest_b1 = next((c for c in pool_b1 if c.id.endswith("-rest")), None)
        e_b1 = kernel.evaluate(w_b1, rest_b1) if rest_b1 else None
        u_b1 = e_b1.utility if e_b1 else 0.0
        known_b1 = {m.event_id for m in w_b1.memory_state.memories.values()
                    if m.owner_id == cid}
        win_b1 = [e.id for e in [e for e in reversed(w_b1.event_log)
                                  if e.id in known_b1 and e.participants
                                  and e.participants[0] == cid][:3]]
        print(f"  B1 rows dropped (M16):")
        pen_b1 = DecisionKernel._repetition_penalty(w_b1, ch, rest_b1) if rest_b1 else 0.0
        print(f"     window falls back to = {win_b1}")
        print(f"     rest utility = {u_b1:+.6f}  penalty = {pen_b1}  "
              f"reasons = {e_b1.reasons if e_b1 else None}")
        w_b1s = copy.deepcopy(w_b1)
        before = len(w_b1s.event_log)
        res_b1 = SimulationEngine(seed=seed, use_arbitration=True).step(w_b1s)
        print(f"     step(): actions={[a.id for a in res_b1.actions]}  "
              f"new events={[e.id for e in w_b1s.event_log[before:]]}")
        print()

        # ---- B2: MATCHED single-reader intervention: detach exactly
        #          M16's three rows' event links, rows kept ----
        w_b2 = copy.deepcopy(world)
        for m in w_b2.memory_state.memories.values():
            if m.owner_id == cid and m.event_id in set(r3):
                m.event_id = "detached-" + m.id
        w_b2.characters[cid].memory_ids = [
            i for i in ch.memory_ids if i in w_b2.memory_state.memories]
        pool_b2 = generate_action_pool(w_b2, cid)
        rest_b2 = next((c for c in pool_b2 if c.id.endswith("-rest")), None)
        e_b2 = kernel.evaluate(w_b2, rest_b2) if rest_b2 else None
        u_b2 = e_b2.utility if e_b2 else 0.0
        known_b2 = {m.event_id for m in w_b2.memory_state.memories.values()
                    if m.owner_id == cid}
        win_b2 = [e.id for e in [e for e in reversed(w_b2.event_log)
                                  if e.id in known_b2 and e.participants
                                  and e.participants[0] == cid][:3]]
        print(f"  B2 MATCHED detach of M16's 3 links, rows kept:")
        pen_b2 = DecisionKernel._repetition_penalty(w_b2, ch, rest_b2) if rest_b2 else 0.0
        print(f"     window = {win_b2}")
        print(f"     rest utility = {u_b2:+.6f}  penalty = {pen_b2}  "
              f"reasons = {e_b2.reasons if e_b2 else None}")
        w_b2s = copy.deepcopy(w_b2)
        before = len(w_b2s.event_log)
        res_b2 = SimulationEngine(seed=seed, use_arbitration=True).step(w_b2s)
        print(f"     step(): actions={[a.id for a in res_b2.actions]}  "
              f"new events={[e.id for e in w_b2s.event_log[before:]]}")
        print()

        # ---- B3: M17's ACTUAL table row: detach ALL of the actor's links ----
        w_b3 = copy.deepcopy(world)
        n = 0
        for m in w_b3.memory_state.memories.values():
            if m.owner_id == cid:
                m.event_id = "detached-" + m.id
                n += 1
        w_b3.characters[cid].memory_ids = [
            i for i in ch.memory_ids if i in w_b3.memory_state.memories]
        known_b3 = {m.event_id for m in w_b3.memory_state.memories.values()
                    if m.owner_id == cid}
        win_b3 = [e.id for e in [e for e in reversed(w_b3.event_log)
                                  if e.id in known_b3 and e.participants
                                  and e.participants[0] == cid][:3]]
        pool_b3 = generate_action_pool(w_b3, cid)
        rest_b3 = next((c for c in pool_b3 if c.id.endswith("-rest")), None)
        e_b3 = kernel.evaluate(w_b3, rest_b3) if rest_b3 else None
        u_b3 = e_b3.utility if e_b3 else 0.0
        print(f"  B3 M17's table row: detach ALL {n} links, rows kept")
        pen_b3 = DecisionKernel._repetition_penalty(w_b3, ch, rest_b3) if rest_b3 else 0.0
        print(f"     window = {win_b3}")
        print(f"     rest utility = {u_b3:+.6f}  penalty = {pen_b3}")
        w_b3s = copy.deepcopy(w_b3)
        before = len(w_b3s.event_log)
        res_b3 = SimulationEngine(seed=seed, use_arbitration=True).step(w_b3s)
        print(f"     step(): actions={[a.id for a in res_b3.actions]}  "
              f"new events={[e.id for e in w_b3s.event_log[before:]]}")
        print()

        print(f"  verdicts: B1(rest)={u_b1:+.6f}  B2(rest)={u_b2:+.6f}  "
              f"B3(rest)={u_b3:+.6f}  A(rest)={u_a:+.6f}")
        print(f"  B1==B2 match: {abs(u_b1-u_b2)<1e-9}")
        print()
    print("  Nothing modified. No recall wiring, no weights, no "
          "production/test change, no manufactured failure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
