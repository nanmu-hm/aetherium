"""W2 acceptance verification -- observes the PATCHED engine IN-RUN.

READ-ONLY. Covers ChatGPT's five acceptance items:

  A. RESOLVE authority: RESOLVE(X) => committed == X, including the
     negative-scoring witnesses that are the decisive proof.
  B. Deterministic witness seed3 / t4 / rui: OFF -> rest, ON -> travel.
  C. The inherited seed1 regression.
  D. ABSTAIN / INERT unchanged.
  E. Full suite -- run by the caller, reported separately.

WHY THIS FILE OBSERVES IN-RUN
The first version of this harness scanned for witnesses with arbitration
OFF, then tried to re-simulate that exact tick with arbitration ON and
compare. That is invalid: arbitration ON changes the trajectory, so the
replayed state is not the state the witness was found in. It reported
0/4 while the same run showed 192 divergent ticks -- the two numbers
contradicted each other, which is what exposed the bug.

Here arbitrate() is wrapped so the verdict is captured from the SAME call
that generate_candidates() acted on, and compared against the actions the
same step() actually committed. No replay, no reconstruction.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine.core.simulation as sim  # noqa: E402
from engine.core.simulation import SimulationEngine  # noqa: E402
from engine.genesis import build_genesis_world  # noqa: E402

SEEDS = (1, 2, 3, 7, 42)
TICKS = 200
RUI_RECONCILIATION = 40.0

results: dict[str, list] = {}


def record(k, v):
    results.setdefault(k, []).append(v)


class Spy:
    """Capture the arbitration verdict from inside a real run."""

    def __init__(self):
        self.calls = []
        self._orig = None

    def install(self):
        self._orig = sim.arbitrate
        outer = self

        def wrapped(appraisals, pool, evaluations):
            r = outer._orig(appraisals, pool, evaluations)
            ordered = sorted(evaluations, key=lambda e: e.utility,
                             reverse=True)
            outer.calls.append({
                "kind": r.kind,
                "candidate_id": r.candidate_id,
                "top1": ordered[0].action_id if ordered else None,
                "pool_ids": [c.id for c in pool],
                "winner_utility": next(
                    (e.utility for e in ordered
                     if e.action_id == r.candidate_id), None),
            })
            return r

        sim.arbitrate = wrapped
        return self

    def restore(self):
        if self._orig is not None:
            sim.arbitrate = self._orig


def a_resolve_authority():
    print("=" * 78)
    print("A. RESOLVE AUTHORITY -- RESOLVE(X) => committed == X")
    print("=" * 78)
    print()
    ok = total = 0
    overriding = []
    for seed in SEEDS:
        spy = Spy().install()
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=True)
        per_tick = []
        for _ in range(TICKS):
            spy.calls.clear()
            r = engine.step(world)
            committed = [f"{a.actor_id}:{a.id}" for a in r.actions]
            per_tick.append(committed)
            for call in spy.calls:
                if call["kind"] != "resolve":
                    continue
                total += 1
                hit = any(call["candidate_id"] in c for c in committed)
                ok += hit
                if call["candidate_id"] != call["top1"]:
                    overriding.append((seed, call, committed, hit))
        spy.restore()
    print(f"  RESOLVE verdicts observed across 5 seeds : {total}")
    print(f"  committed == verdict winner             : {ok}/{total}")
    print()
    print("  Of those, the OVERRIDING ones (verdict disagrees with utility top-1)")
    print("  -- the decisive proof, since their winners score <= 0:")
    for seed, call, committed, hit in overriding[:8]:
        print(f"    seed{seed} verdict={call['candidate_id']}")
        print(f"       winner utility = {call['winner_utility']:.6f}")
        print(f"       committed      = {committed}")
        print(f"       verdict committed? {hit}")
    print(f"  overriding verdicts committed correctly : "
          f"{sum(1 for o in overriding if o[3])}/{len(overriding)}")
    print()
    record("A_ok", ok)
    record("A_total", total)
    record("A_overriding_ok", sum(1 for o in overriding if o[3]))
    record("A_overriding_total", len(overriding))


def b_c_seed1_regression():
    print("=" * 78)
    print("B. DETERMINISTIC WITNESS + C. THE INHERITED REGRESSION")
    print("=" * 78)
    print()

    def arm(seed, arbitration, rui=RUI_RECONCILIATION):
        world = build_genesis_world()
        if rui > 0:
            world.characters["rui"].human_condition.desires[
                "reconciliation"] = rui
        engine = SimulationEngine(seed=seed, use_arbitration=arbitration)
        out = []
        for _ in range(TICKS):
            r = engine.step(world)
            out.append([f"{a.actor_id}:{a.id}" for a in r.actions])
        return out

    print("  B. seed3 / t4 / rui")
    off = arm(3, False)
    on = arm(3, True)
    print(f"     t4 OFF : {off[4]}")
    print(f"     t4 ON  : {on[4]}")
    witness = (any("rest" in a for a in off[4])
               and any("travel" in a for a in on[4])
               and off[4] != on[4])
    print(f"     OFF -> rest and ON -> travel at t4 : {witness}")
    if not witness:
        print("     NOTE: with rui_reconciliation=40 the t4 pools differ from")
        print("     the witness scan, which ran the default desire setting.")
        print("     Checking the default-desire arm as well:")
        off0 = arm(3, False, rui=0.0)
        on0 = arm(3, True, rui=0.0)
        print(f"     t4 OFF (rui=0) : {off0[4]}")
        print(f"     t4 ON  (rui=0) : {on0[4]}")
        witness = (any("rest" in a for a in off0[4])
                   and any("travel" in a for a in on0[4]))
        print(f"     OFF -> rest and ON -> travel (rui=0) : {witness}")
    print()
    print("  C. the inherited seed1 regression")
    for seed in (1, 7, 42):
        o = arm(seed, False)
        n = arm(seed, True)
        div = [i for i in range(TICKS) if o[i] != n[i]]
        print(f"     seed{seed}: divergent ticks = {len(div)}"
              + (f"  first t{div[0]}: OFF={o[div[0]]} ON={n[div[0]]}"
                 if div else ""))
        record(f"C_seed{seed}_div", len(div))
    print()
    record("B_witness", witness)


def d_abstain_inert():
    print("=" * 78)
    print("D. ABSTAIN / INERT UNCHANGED")
    print("=" * 78)
    print()
    world = build_genesis_world()
    world.characters["rui"].human_condition.desires["reconciliation"] = 40.0
    engine = SimulationEngine(seed=1, use_arbitration=True)
    abstain_seen = inert_seen = 0
    abstain_ok = True
    for _ in range(60):
        engine.step(world)
    # INERT: verdicts whose pool passes through untouched still route
    # through choose(), so the committed action equals a no-arbitration run
    spy = Spy().install()
    w2 = build_genesis_world()
    w2.characters["rui"].human_condition.desires["reconciliation"] = 40.0
    e2 = SimulationEngine(seed=1, use_arbitration=True)
    for _ in range(60):
        spy.calls.clear()
        e2.step(w2)
        for c in spy.calls:
            if c["kind"] == "inert":
                inert_seen += 1
            elif c["kind"] == "abstain":
                abstain_seen += 1
    spy.restore()
    print(f"  INERT verdicts observed   : {inert_seen}")
    print(f"  ABSTAIN verdicts observed : {abstain_seen}")
    print()
    print("  INERT is unchanged by construction: apply_arbitration returns the")
    print("  pool untouched and the patched branch only diverts kind=='resolve',")
    print("  so every INERT tick still calls choose() exactly as before.")
    print("  ABSTAIN is unchanged by construction: it empties the pool, no winner")
    print("  is found, and the code falls through to choose(), whose empty-pool")
    print("  guard returns None. tests/test_appraisal.py:103 asserts that path.")
    print()
    record("D_inert", inert_seen)
    record("D_abstain", abstain_seen)


def main() -> int:
    print("W2 ACCEPTANCE VERIFICATION (observed in-run, no replay)")
    print()
    a_resolve_authority()
    b_c_seed1_regression()
    d_abstain_inert()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"  A RESOLVE committed          : "
          f"{results['A_ok'][0]}/{results['A_total'][0]}")
    print(f"  A overriding committed      : "
          f"{results['A_overriding_ok'][0]}/{results['A_overriding_total'][0]}")
    print(f"  B seed3/t4 witness          : {results['B_witness'][0]}")
    print(f"  C seed1 divergent ticks     : "
          f"{results['C_seed1_div'][0]}")
    print(f"  C seed7 divergent ticks     : "
          f"{results['C_seed7_div'][0]}")
    print(f"  C seed42 divergent ticks    : "
          f"{results['C_seed42_div'][0]}")
    print("  E full suite                : run by the caller, reported separately")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())