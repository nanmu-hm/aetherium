"""M17-R: repetition witness reconciliation.

The two M16 mechanism-B witnesses (rest -> quiet) were reported as
    rest utility A = -0.0155   B = -0.132167   delta = -0.116667 = 0.35/3
with the B-side utility coming from M16's kernel-only ablation helper,
while M16's PERSISTED-event counts (P3/P4 = 6) came from the real
engine.step().

This tool re-derives BOTH readings from the same persisted world log and
prints every layer, for each of the two witnesses, so the -0.116667
figure and the "rest -> quiet" crossing can each be traced to the exact
variable they came from.

READ-ONLY. No production/test/weight change, no recall wiring, no
manufactured failure.

Usage:  python3 tools/mb_m16_mechB_recheck.py
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


def main() -> int:
    kernel = DecisionKernel(seed=0)
    for seed, tick in ((1, 41), (42, 35)):
        # M16's main loop: `for _ in range(TICKS): engine.step(world)` then
        # measure at the END of that iteration, so "world.tick == tick" is
        # the exact state M16 saw when it logged these two witnesses.
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=False)
        for _ in range(tick):
            engine.step(world)
        assert world.tick == tick
        cid = "yan"
        ch = world.characters[cid]

        pool_a = generate_action_pool(world, cid)
        evs_a = [kernel.evaluate(world, c) for c in pool_a]
        byid_a = {e.action_id: e for e in evs_a}
        rest = next((c for c in pool_a if c.id.endswith("-rest")), None)
        u_a = byid_a[rest.id].utility if rest else 0.0

        print(f"=== seed{seed} t{tick} actor={cid}  (M16's exact snapshot)")
        print(f"  pool A = {[c.id for c in pool_a]}")
        if rest:
            print(f"  rest utility A = {u_a:+.6f}  reasons = {byid_a[rest.id].reasons}")
        print()

        # ---- B1: kernel-only, M16's exact method ----
        w_b1 = copy.deepcopy(world)
        recent3 = [e.id for e in [e for e in reversed(w_b1.event_log)
                                  if e.participants
                                  and e.participants[0] == cid][:3]]
        for m in [m for m in list(w_b1.memory_state.memories.values())
                  if m.owner_id == cid and m.event_id in set(recent3)]:
            w_b1.memory_state.memories.pop(m.id, None)
        w_b1.characters[cid].memory_ids = [
            i for i in ch.memory_ids if i in w_b1.memory_state.memories]
        pool_b1 = generate_action_pool(w_b1, cid)
        evs_b1 = [kernel.evaluate(w_b1, c) for c in pool_b1]
        byid_b1 = {e.action_id: e for e in evs_b1}
        print(f"  B1 kernel-only (M16's method), recent-3 = {recent3}")
        print(f"     pool B1 = {[c.id for c in pool_b1]}")
        if rest and rest.id in byid_b1:
            u_b1 = byid_b1[rest.id].utility
            print(f"     rest utility B1 = {u_b1:+.6f}  "
                  f"(delta vs A = {u_b1-u_a:+.6f})  "
                  f"reasons = {byid_b1[rest.id].reasons}")
            print(f"     M16 claimed -0.0155 -> -0.132167, delta -0.116667; "
                  f"{'MATCHES' if abs((u_b1-u_a)-(-0.116667))<1e-4 else 'DOES NOT match'}")
        else:
            print(f"     rest candidate NOT present in pool B1 "
                  f"(candidates: {[c.id for c in pool_b1]})")
        print()

        # ---- B2: REAL engine.step() on the B1 world (M16's P3/P4 method) ----
        w_a2 = copy.deepcopy(world)
        res_a2 = SimulationEngine(seed=seed, use_arbitration=True).step(w_a2)
        ev_a2 = [e.id for e in w_a2.event_log[-len(res_a2.actions):]
                 if cid in (e.participants or [])]
        w_b2 = copy.deepcopy(w_b1)
        res_b2 = SimulationEngine(seed=seed, use_arbitration=True).step(w_b2)
        ev_b2 = [e.id for e in w_b2.event_log[-len(res_b2.actions):]
                 if cid in (e.participants or [])]
        print(f"  B2 real engine.step() (M16's P3/P4 method):")
        print(f"     PERSISTED event A = {ev_a2}  actions = "
              f"{[a.id for a in res_a2.actions]}")
        print(f"     PERSISTED event B = {ev_b2}  actions = "
              f"{[a.id for a in res_b2.actions]}")
        print(f"     persisted-event change: {ev_a2 != ev_b2}")
        print()

        # ---- B3: targeted single-reader detach. M16's `ablate(...,
        # "all")` removed the *memory rows* whose event_id is in the
        # actor's most-recent three linked events; that set includes
        # event-13 (much older than the tick-41 boundary), which is why
        # B1's recent-3 list above differs from a plain
        # reversed(event_log)[:3]. Reproduce that exact detach here. ----
        w_b3 = copy.deepcopy(world)
        detach3 = [m.event_id for m in [
            m for m in w_b3.memory_state.memories.values()
            if m.owner_id == cid and m.event_id
            and m.event_id in {e.id for e in w_b3.event_log}][:3]]
        for m in w_b3.memory_state.memories.values():
            if m.owner_id == cid and m.event_id in set(detach3):
                m.event_id = "detached-" + m.id
        w_b3.characters[cid].memory_ids = [
            i for i in ch.memory_ids if i in w_b3.memory_state.memories]
        known = {m.event_id for m in w_b3.memory_state.memories.values()
                 if m.owner_id == cid}
        window_b3 = [e.id for e in [e for e in reversed(w_b3.event_log)
                                    if e.id in known
                                    and e.participants
                                    and e.participants[0] == cid][:3]]
        print(f"  B3 targeted single-reader detach (M17's counterfactual):")
        print(f"     repetition recent-3 window now = {window_b3}")
        pool_b3 = generate_action_pool(w_b3, cid)
        rest3 = next((c for c in pool_b3 if c.id.endswith("-rest")), None)
        if rest3:
            e3 = kernel.evaluate(w_b3, rest3)
            pen3 = DecisionKernel._repetition_penalty(w_b3, ch, rest3)
            print(f"     rest utility B3 = {e3.utility:+.6f}  "
                  f"penalty = {pen3}  reasons = {e3.reasons}")
        res_b3 = SimulationEngine(seed=seed, use_arbitration=True).step(
            copy.deepcopy(w_b3))
        ev_b3 = [e.id for e in w_b3.event_log[-len(res_b3.actions):]
                 if cid in (e.participants or [])]
        print(f"     PERSISTED event B3 = {ev_b3}")
        print()
    print("  Nothing modified. No recall wiring, no weights, no "
          "production/test change, no manufactured failure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
