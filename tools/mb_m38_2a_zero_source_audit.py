"""M38-2A — zero-source audit of memory_state.desires (read-only).

Anchored 0ba1699, executed on HEAD (ref pushed with this tool).
Spec: PR#10 6206873426 v1 + v2 per ChatGPT 6206900412 + Arena review.
Per-seed: two INDEPENDENT genesis worlds / engines (arm-N no probe,
arm-P read-only probe). Canonical semantic world-field +
SimulationResult comparison. PROBE-LEAKED on any unexplained
semantic diff. Static writer audit via grep output embedded.
No production/test/weight change.
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from dataclasses import asdict
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.decision import DecisionKernel
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEEDS = (1, 3, 7, 42, 99)
ACTOR = "rui"
TICKS = 40
SAMPLE = (1, 5, 10, 20, 40)

# -----------------------------------------------------------------
# canonical semantic projection (deterministic, no identity/refs)
# -----------------------------------------------------------------

def _char_canonical(c):
    hc = c.human_condition
    return {
        "id": c.id, "status": c.status,
        "location": c.location,
        "desires": {k: round(v, 9) for k, v in hc.desires.items()},
        "emotions": {k: round(v, 9) for k, v in c.emotions.items()},
        "mem_count": len(c.memory_ids),
        "habits": {k: round(v, 9) for k, v in c.habits.items()},
    }

def world_canonical(world):
    return {
        "tick": world.tick,
        "timestamp": world.timestamp,
        "n_memories": len(world.memory_state.memories),
        "n_desires": len(world.memory_state.desires),
        "desire_keys": sorted(world.memory_state.desires.keys()),
        "characters": {cid: _char_canonical(c)
                        for cid, c in sorted(world.characters.items())},
        "locations": frozenset(world.locations),
    }

def result_canonical(res):
    """Canonical semantic projection of SimulationResult.
    Includes landed-event semantic content (id/type/tick) so a
    reviewer can verify the full event trail, not just a count."""
    landed = [
        {"id": e.id, "type": e.action_type, "tick": e.tick}
        for e in res.events
    ]
    return {
        "tick": res.tick,
        "n_actions": len(res.actions),
        "action_ids": tuple(a.id for a in res.actions),
        "n_events": len(res.events),
        "landed_events": landed,
        "n_validation_errors": len(res.validation_errors),
    }

def probe_metrics(world, res, actor_id=ACTOR):
    """Read-only per-tick probe metrics (no world mutation)."""
    ms = world.memory_state
    actor = world.characters[actor_id]
    mem_urg = max(
        (d.urgency * d.priority for d in ms.desires.values()
         if d.owner_id == actor_id and d.status == "active"),
        default=0.0,
    )
    # per-candidate evaluate() utility (2A dynamic audit; read-only)
    dk = DecisionKernel(
        seed=world.simulation_seed
        if world.simulation_seed is not None else 1)
    per_cand = []
    for a in res.actions:
        ev = dk.evaluate(world, a)
        per_cand.append({
            "action_id": a.id,
            "action_type": a.action_type,
            "utility": round(ev.utility, 9),
        })
    return {
        "n_desires": len(ms.desires),
        "n_desires_active": sum(
            1 for d in ms.desires.values()
            if d.owner_id == actor_id and d.status == "active"),
        "memory_urgency": round(mem_urg, 9),
        "per_candidate_utility": per_cand,
        "actor_location": actor.location,
    }

def run_arm(seed, probe: bool):
    """Independent genesis world + engine. Returns per-tick records."""
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)
    records = []
    for t in range(TICKS):
        res = engine.step(world)
        rec = {
            "tick": t + 1,
            "world": world_canonical(world),
            "result": result_canonical(res),
        }
        if probe:
            rec["probe"] = probe_metrics(world, res)
        records.append(rec)
    return records

def compare_arms(off_recs, on_recs):
    """Canonical semantic diff arm-N vs arm-P. PROBE-LEAKED on any
    unexplained world-field / result-field difference."""
    leaked = []
    for ro, rp in zip(off_recs, on_recs):
        if ro["world"] != rp["world"]:
            leaked.append(("world", ro["tick"]))
        if ro["result"] != rp["result"]:
            leaked.append(("result", ro["tick"]))
    return leaked

def main():
    import subprocess, os
    out = {"seeds": {}, "flags": {"PROBE-LEAKED": []}}
    for seed in SEEDS:
        off = run_arm(seed, probe=False)
        on = run_arm(seed, probe=True)
        leaked = compare_arms(off, on)
        zero_source = all(
            r["world"]["n_desires"] == 0 for r in off
        )
        out["seeds"][str(seed)] = {
            "arm_N_n_desires_max": max(r["world"]["n_desires"] for r in off),
            "arm_P_n_desires_max": max(r["world"]["n_desires"] for r in on),
            "zero_source_confirmed": zero_source and not leaked,
            "PROBE_LEAKED": bool(leaked),
            "leaked_detail": leaked[:5],
            "sample_ticks": {
                str(t): {
                    "N": off[t-1]["result"],
                    "P": on[t-1]["result"],
                    "probe": on[t-1].get("probe"),
                } for t in SAMPLE
            },
        }
        if leaked:
            out["flags"]["PROBE-LEAKED"].append(seed)

    # Static audit: run grep in real time (not hardcoded summary),
    # record the exact commands and hits so an independent reviewer
    # can reproduce them verbatim.
    root = str(Path(__file__).resolve().parent.parent)
    static = {}

    def _grep(pattern, paths):
        cmd = ["grep", "-rn", pattern, *paths]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                                cwd=root, timeout=30)
            hits = [l for l in r.stdout.splitlines() if l.strip()]
        except Exception as e:
            hits = [f"grep-error: {e}"]
        return {"cmd": " ".join(cmd), "hits": hits, "count": len(hits)}

    static["add_desire_callers"] = _grep(
        "add_desire", ["engine/", "scripts/"])
    static["direct_dict_write"] = _grep(
        r"memory_state\.desires\[", ["engine/", "scripts/"])
    static["Desire_constructor"] = _grep(
        r"Desire(", ["engine/", "scripts/"])
    out["static_audit"] = static
    out["static_audit_note"] = (
        "Commands run in real time against repo root at run-start; "
        "hits are recorded verbatim. codec.py:120 is expected to "
        "appear in Desire_constructor (deserialize-only, not a "
        "runtime writer). advance_desires/mark_desire do not create "
        "new Desire objects — verified by reading kernel.py:269-283.")

    print(json.dumps(out, indent=2, default=str))

if __name__ == "__main__":
    main()
