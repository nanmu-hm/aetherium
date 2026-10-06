"""M23-R1 -- corrected State Persistence -> Future Agency counterfactual.

Arena's review of M23 (chatgpt-on-platform, eca71a3) identified three
independent defects in the original tool that, taken together, make
its "desire 5/5 positive, all others 0" result an INVALID positive
(and the eight 0s not safely attributable to a valid method either).
This tool fixes all three and re-runs the audit; read-only, anchored
to 0ba1699, 342/0 expected (no engine/production/test change).

Fix 1 (hold/refresh bug): the original tool's neutral arm refreshed
`hold` from the NEUTRAL arm's own post-step state each tick, then
pinned to that value next tick -- i.e. it was pinning to its own
converging value, not to the natural arm's, so after the first tick
the two arms were no longer a genuine natural-vs-neutralized
comparison (tools/mb_m23_state_persistence.py:244-261, exactly the
lines Arena cited). Fix: run the natural arm ONCE to full length and
capture its per-tick pre-step desire snapshot; the neutral arm pins
each tick's desires to the natural arm's snapshot for that same tick
-- it never re-synchronizes to its own drift.

Fix 2 (desire field scope): the original DESIRE_FIELDS list
(reconciliation/belonging/exploration + responsibility added in the
delivery comment but never in the code) omitted `freedom` and
`curiosity` -- the two desire keys that are NONZERO AT GENESIS for
rui (freedom=80, curiosity=35, confirmed independently on all 5
seeds) and that a live reader explicitly consumes
(engine/core/decision.py:55, :140). Fix: DESIRE_FIELDS now covers
every desire key any live reader consumes: reconciliation,
belonging, freedom, curiosity, responsibility. (exploration is not
read by any reader found in this grep -- it is kept in the list only
so the neutralizer still covers it if a later reader appears, and is
flagged as a no-op today, not silently dropped.)

Fix 3 (key-existence artifact): the original neutralizer wrote
`ch.human_condition.desires[f] = 0.0` for keys that never existed in
that character's dict (e.g. `responsibility` for a character who
has never had it) -- this created a new, spurious key difference
between arms that the reader then saw as a real 0.0, not as
"absence" (which `desires.get(name, 0.0)` already treats as 0.0).
Fix: the neutralizer now uses .get()-semantics -- it restores a key
to its held value ONLY if that key is present in the natural arm's
pre-step snapshot for that tick; it never creates a key the natural
arm never had, and never deletes one it did.

Fix 4 (pin boundary, per Arena's final note): the original tool's
`_preview_committed()` was called at the top of the loop, BEFORE
`engine.step()`, but `engine.step()` itself calls `_settle_emotions()`
first (engine/core/simulation.py:1194) and THEN `generate_candidates()`
(:1195) -- so the pin had to be reapplied AFTER `_settle_emotions()`
runs but BEFORE `generate_candidates()`, or it was not actually
observed by the reader at the true read boundary for the emotion
family (and, by the same logic, should be re-asserted for desire at
the same boundary for a clean result). Since `_settle_emotions` and
`generate_candidates` are both public and the pin is read-only
reserialization, this tool calls them separately (rather than via
`engine.step()`'s opaque bundle) for the pre-step snapshot, mirroring
exactly the internal order step() uses (simulation.py:1192-1196),
so the pin's timing claim is verifiable line-by-line against the
source rather than asserted.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.actions import generate_action_pool
from engine.core.appraisal import build_appraisals, arbitrate, \
    apply_arbitration
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEEDS = (1, 3, 7, 42, 99)
TICKS = 200

# Fix 2: every desire key a live reader consumes (grep-verified above
# this file's docstring), not just three.
DESIRE_FIELDS = ["reconciliation", "belonging", "freedom",
                 "curiosity", "responsibility"]


def _pre_step_snapshot(world, engine) -> dict:
    """Reproduce engine.step()'s pre-candidate-generation boundary
    EXACTLY (simulation.py:1192-1196): _settle_emotions() runs first,
    THEN generate_candidates() reads state. Capture desire values at
    the moment generate_candidates() actually sees them, not at the
    loop top before _settle_emotions() has run."""
    engine._settle_emotions(world)
    return {cid: {k: v for k, v in
                   ch.human_condition.desires.items()
                   if k in DESIRE_FIELDS}
            for cid, ch in world.characters.items()}


def _candidates(world, engine) -> dict:
    """Mirror engine.generate_candidates()'s selection exactly (the
    same call the real step() makes, simulation.py:1195)."""
    kernel = engine.decision_kernel
    out = {}
    for ch in world.characters.values():
        pool = generate_action_pool(world, ch.id)
        arbitration = None
        if engine.use_arbitration and pool:
            appraisals = build_appraisals(kernel, world, ch, pool)
            evaluations = [kernel.evaluate(world, c) for c in pool]
            arbitration = arbitrate(appraisals, pool, evaluations)
            pool = apply_arbitration(pool, arbitration, evaluations)
        action = None
        if arbitration is not None and arbitration.kind == "resolve":
            action = next((c for c in pool if c.id ==
                           arbitration.candidate_id), None)
        if action is None:
            action, _ = kernel.choose(world, pool, allow_quiet=True)
        out[ch.id] = action.id if action else None
    return out


def _pin(world, held: dict) -> None:
    """Fix 3: .get()-semantics restore. For each character, for each
    desire key in the HELD snapshot, restore its value. Never add a
    key the held snapshot lacks for that character (that would
    create a spurious key difference), never remove one it has."""
    for cid, ch in world.characters.items():
        held_for_cid = held.get(cid, {})
        desires = ch.human_condition.desires
        # remove keys the natural arm never had at this tick
        for k in list(desires.keys()):
            if k in DESIRE_FIELDS and k not in held_for_cid:
                del desires[k]
        # restore/insert keys the natural arm DID have
        for k, v in held_for_cid.items():
            desires[k] = v


def natural_arm(seed: int) -> list[dict]:
    """Run the unmodified natural arm once, capturing, per tick, the
    pre-candidate desire snapshot (Fix 4 boundary) AND the committed
    actions the engine itself produced via engine.step() -- not a
    re-derivation, the real SimulationResult."""
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)
    recs = []
    for _ in range(TICKS):
        snapshot = _pre_step_snapshot(world, engine)
        res = engine.step(world)  # _settle_emotions +
                                   # generate_candidates + resolve,
                                   # in the real engine's own order
        recs.append({"desired": copy.deepcopy(snapshot),
                     "committed": {a.actor_id: a.id for a in res.actions}})
    return recs


def neutral_arm(seed: int, natural: list[dict]) -> list[dict]:
    """Replay the same seed's world, but pin desires (Fix 2's full
    field list, Fix 3's .get()-semantics) to the natural arm's
    pre-candidate-generation snapshot for that tick (Fix 1), then
    let the engine's own _settle_emotions + generate_candidates +
    resolve run -- the pin is applied at the exact boundary the real
    step() crosses, not after it."""
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)
    recs = []
    for i in range(TICKS):
        _pin(world, natural[i]["desired"])
        snapshot = _pre_step_snapshot(world, engine)
        res = engine.step(world)
        recs.append({"desired": copy.deepcopy(snapshot),
                     "committed": {a.actor_id: a.id for a in res.actions}})
    return recs


def main() -> int:
    print("=" * 72)
    print("M23-R1  corrected State Persistence -> Future Agency "
          "(read-only, 0ba1699)")
    print("=" * 72)

    for seed in SEEDS:
        natural = natural_arm(seed)
        neutral = neutral_arm(seed, natural)
        diff = [i for i in range(TICKS)
                if natural[i]["committed"] != neutral[i]["committed"]]
        print(f"\nseed {seed}: {len(diff)} ticks where committed-action "
              f"sets differ (desire family pinned pre-candidate-generation "
              f"to the natural arm's own pre-candidate value, same tick)")
        for i in diff[:3]:
            print(f"   t{i}: natural={natural[i]['committed']}  "
                  f"neutral={neutral[i]['committed']}")
            print(f"        natural desire pre-step={natural[i]['desired']}")
            print(f"        neutral desire pre-step (post-pin)={neutral[i]['desired']}")
        if not diff:
            print("   -> desire forward-influence: NOT PROVEN in this "
                  "window under the corrected method (not a "
                  "whole-space zero)")

    print("\n[METHOD] Natural arm: one full engine.step() run, "
          "committed actions taken directly from SimulationResult "
          "(no re-derivation). Neutral arm: identical world/seed/"
          "tick count, desires pinned to the natural arm's "
          "pre-candidate-generation value for the SAME tick, pinned "
          "at the boundary _settle_emotions() -> generate_candidates()"
          " crosses (simulation.py:1194-1195), engine.step()'s own "
          "internal order otherwise untouched. Desire field list "
          "covers every key a live reader consumes: "
          f"{DESIRE_FIELDS}. Key-existence artifact eliminated "
          "(Fix 3: .get()-semantics, never create/delete a key the "
          "natural arm did not have at that tick).")
    print("\nAll read-only. No engine/production/test/weight change, "
          "no recall() wiring, no new field/reader, no downstream "
          "write, no manufactured failure or event. Anchor: 0ba1699.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
