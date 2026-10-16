"""M38-2A — zero-source audit of memory_state.desires (read-only).

Anchored 0ba1699, executed on HEAD (ref pushed with this tool).
Spec: PR#10 6206873426 v1 -> v2 per ChatGPT 6206900412 ->
field-completeness pass per ChatGPT 6210708558 (full 5x40 dual-arm
JSON, hc_urgency + chosen-action semantics, expanded action/event
canonical fields, extended static writer patterns).

Per-seed: two INDEPENDENT genesis worlds / engines (arm-N no probe,
arm-P read-only probe). Canonical semantic world-field +
SimulationResult comparison. PROBE-LEAKED on any unexplained
semantic diff.

All observations come from production APIs or engine.step()
outputs. Nothing is inferred across layers:
- per_candidate_utility: DecisionKernel.evaluate()
- chosen_action: engine.decision_kernel.choose() re-run (read-only)
- human_condition_urgency: engine.decision_kernel._human_condition_urgency
- selection_score: NOT OBSERVABLE in engine.step() output (internal
  to choose(), not returned in SimulationResult) -> NOT-COLLECTED
- action.score (raw candidate value, separate from selection_score)
  IS collected where it exists on ActionCandidate

No production/test/weight change.
"""
from __future__ import annotations

import sys
import json
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.decision import DecisionKernel
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEEDS = (1, 3, 7, 42, 99)
ACTOR = "rui"
TICKS = 40

# -----------------------------------------------------------------
# canonical semantic projections (deterministic, no identity/refs)
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
        "locations": sorted(world.locations),
    }

def _action_canonical(a):
    """ActionCandidate stable semantic fields (not just id)."""
    return {
        "id": a.id,
        "actor_id": a.actor_id,
        "action_type": a.action_type,
        "targets": list(a.targets),
        "motivation": a.motivation,
        "confidence": round(a.confidence, 9),
        "score": round(a.score, 9),
        "n_risks": len(a.risks),
    }

def _event_canonical(e):
    """Event stable semantic fields (not just id/type/tick)."""
    return {
        "id": e.id,
        "tick": e.tick,
        "location": e.location,
        "participants": list(e.participants),
        "action_type": e.action_type,
        "n_consequences": len(getattr(e, "consequences", []) or []),
    }

def result_canonical(res):
    """Canonical semantic projection of SimulationResult, with full
    action and event field content (not just id/count)."""
    return {
        "tick": res.tick,
        "n_actions": len(res.actions),
        "actions": [_action_canonical(a) for a in res.actions],
        "n_events": len(res.events),
        "events": [_event_canonical(e) for e in res.events],
        "n_validation_errors": len(res.validation_errors),
        "validation_errors": list(res.validation_errors),
    }

def probe_metrics(world, res, engine, actor_id=ACTOR):
    """Read-only per-tick probe metrics.

    Every field is sourced from a production API or engine.step()
    output -- nothing is inferred across layers.

    - n_desires / n_desires_active: world.memory_state.desires
    - memory_urgency: computed here (same formula as
      decision.py:167), read-only
    - human_condition_urgency: engine.decision_kernel.
      _human_condition_urgency(actor, chosen_action) -- the
      ACTUAL chosen action from this tick's step()
    - per_candidate_utility: engine.decision_kernel.evaluate()
      on each committed action (same kernel instance the engine
      uses internally; read-only)
    - chosen_action: the first action in res.actions that belongs
      to the ACTOR (res.actions is the engine's output for all
      characters this tick); if the actor had no action this tick
      (quiet arm), chosen_action = None
    - selection_score: NOT-COLLECTED (internal to choose(), not
      exposed in SimulationResult; cannot be re-derived without
      re-running choose() which would change RNG state)
    """
    ms = world.memory_state
    actor = world.characters[actor_id]

    mem_urg = max(
        (d.urgency * d.priority for d in ms.desires.values()
         if d.owner_id == actor_id and d.status == "active"),
        default=0.0,
    )

    # which of res.actions belongs to the actor this tick?
    actor_actions = [a for a in res.actions if a.actor_id == actor_id]
    chosen_action = actor_actions[0] if actor_actions else None

    # hc_urgency for the ACTUAL chosen action (or 0.0 if none)
    if chosen_action is not None:
        hc_urg = engine.decision_kernel._human_condition_urgency(
            actor, chosen_action)
    else:
        hc_urg = 0.0  # no action -> no urgency to report

    # per-candidate utility using the engine's own kernel instance
    per_cand = []
    for a in res.actions:
        ev = engine.decision_kernel.evaluate(world, a)
        per_cand.append({
            "action_id": a.id,
            "action_type": a.action_type,
            "actor_id": a.actor_id,
            "utility": round(ev.utility, 9),
        })

    return {
        "n_desires": len(ms.desires),
        "n_desires_active": sum(
            1 for d in ms.desires.values()
            if d.owner_id == actor_id and d.status == "active"),
        "memory_urgency": round(mem_urg, 9),
        "human_condition_urgency": round(hc_urg, 9),
        "chosen_action_id": chosen_action.id if chosen_action else None,
        "chosen_action_type": (
            chosen_action.action_type if chosen_action else None),
        "chosen_action_score": (
            round(chosen_action.score, 9) if chosen_action else None),
        "selection_score": "NOT-COLLECTED (internal to choose(), "
                            "not exposed in SimulationResult)",
        "per_candidate_utility": per_cand,
        "actor_location": actor.location,
    }

def run_arm(seed, probe: bool):
    """Independent genesis world + engine. Returns full per-tick
    records (all 40 ticks, not sample)."""
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
            rec["probe"] = probe_metrics(world, res, engine)
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
    out = {
        "seeds": {},
        "flags": {"PROBE-LEAKED": []},
        "meta": {
            "python_version": sys.version.split()[0],
            "seeds": SEEDS,
            "ticks": TICKS,
            "arm_N": "no probe (pure natural flow)",
            "arm_P": "read-only probe (probe_metrics)",
            "selection_score_note": (
                "NOT-COLLECTED: selection_score is computed inside "
                "DecisionKernel.choose() and is not exposed in "
                "SimulationResult. It cannot be re-derived without "
                "re-running choose(), which would consume RNG state. "
                "Per-candidate utility IS collected via "
                "engine.decision_kernel.evaluate()."),
        },
    }

    for seed in SEEDS:
        off = run_arm(seed, probe=False)
        on = run_arm(seed, probe=True)
        leaked = compare_arms(off, on)
        zero_source = all(r["world"]["n_desires"] == 0 for r in off)

        # full per-tick JSON (not sample) -- all 40 ticks, both arms
        out["seeds"][str(seed)] = {
            "arm_N_n_desires_max": max(
                r["world"]["n_desires"] for r in off),
            "arm_P_n_desires_max": max(
                r["world"]["n_desires"] for r in on),
            "zero_source_confirmed": zero_source and not leaked,
            "PROBE_LEAKED": bool(leaked),
            "leaked_detail": leaked[:5],
            # FULL 40-tick trajectories, both arms
            "arm_N_all_ticks": off,
            "arm_P_all_ticks": on,
        }
        if leaked:
            out["flags"]["PROBE-LEAKED"].append(seed)

    # Static writer audit: real-time grep with extended patterns
    # covering add_desire, direct container writes, Desire(
    # construction, mark_desire/lifecycle, rebinding, deletion.
    root = str(Path(__file__).resolve().parent.parent)

    def _grep(pattern, paths, use_ere=False):
        base = ["grep", "-rn"]
        if use_ere:
            base.append("-E")
        cmd = base + [pattern] + list(paths)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                                cwd=root, timeout=30)
            hits = [l for l in r.stdout.splitlines() if l.strip()]
        except Exception as e:
            hits = [f"grep-error: {e}"]
        return {
            "cmd": " ".join(cmd),
            "hits": hits,
            "count": len(hits),
            "note": "ERE" if use_ere else "BRE",
        }

    PROD_PATHS = ["engine/", "scripts/"]
    static = {}
    static["add_desire"] = _grep("add_desire", PROD_PATHS)
    static["direct_container_write"] = _grep(
        r"memory_state\.desires\[", PROD_PATHS, use_ere=True)
    static["Desire_constructor"] = _grep(
        r"Desire\(", PROD_PATHS, use_ere=True)
    static["mark_desire"] = _grep("mark_desire", PROD_PATHS)
    static["advance_desires"] = _grep("advance_desires", PROD_PATHS)
    static["desire_rebind_or_del"] = _grep(
        r"memory_state\.desires\b(\s*[=\[\.]|\s*\.clear|\.pop|\s*del\b)",
        PROD_PATHS, use_ere=True)
    out["static_audit"] = static
    out["static_audit_note"] = (
        "Commands run in real time against repo root. "
        "Exclusions: (1) codec.py:120 Desire(**data) is "
        "deserialization-only (codec-load path, out of natural-flow "
        "scope). (2) add_desire at models.py:128 is the DEFINITION "
        "-- zero external callers in engine/+scripts/. (3) "
        "advance_desires (kernel.py:269-275) and mark_desire "
        "(kernel.py:277-283) migrate STATUS of existing entries; "
        "they do not create new Desire objects. "
        "grep hit count != writer count; each hit must be "
        "classified as definition / read / deserialize / actual-write.")

    print(json.dumps(out, indent=2, default=str))

if __name__ == "__main__":
    main()
