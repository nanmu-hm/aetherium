"""AF production-acceptance regression for the desire-consumption gate.

AF-3/AF-3R shadow evidence (PR #9) authorized a minimal production
port: the interpretation owner stamps consumed_at / consumed_evidence
on the DesireCarrier when a satisfaction Consequence settles on the
desire; candidate generation reads that stamp to keep a consumed
belonging from re-opening contact eligibility through passively
regrown float values. These tests pin the two counterfactuals the
shadow validated, without touching params, thresholds or the +3
maintenance.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.genesis import build_genesis_world
from engine.core.simulation import SimulationEngine
from engine.core.action_types import event_action_type


def _contact_events(results, actor):
    out = []
    for r in results:
        for e in r.events:
            if e.participants and e.participants[0] == actor \
                    and event_action_type(e) == "contact_person" \
                    and e.action_result is not None \
                    and e.action_result.status == "success":
                out.append(e)
    return out


def _run(seed, ticks=40):
    world = build_genesis_world()
    world.characters["rui"].human_condition.desires["reconciliation"] = 40.0
    engine = SimulationEngine(seed=seed, use_arbitration=False)
    results = [engine.step(world) for _ in range(ticks)]
    return results, world


def _with_belonging_carrier(world, char, consumed=False, value=80.0):
    """Give `char` an explicit belonging carrier (the lifecycle reader
    needs one; genesis carriers are only materialized at interpretation)."""
    from engine.core.models import DesireCarrier
    char.human_condition.desires["belonging"] = value
    carrier = char.desire_carriers.get("belonging")
    if carrier is None:
        carrier = DesireCarrier(
            carrier_id=f"{char.id}:DESIRE:belonging",
            subject_id=char.id,
            desire="belonging",
            source="GENESIS",
            created_at="GENESIS",
            strength=value,
        )
        char.desire_carriers["belonging"] = carrier
    if consumed:
        carrier.lifecycle = "CONSUMED"
        carrier.consumed_at = 0
        carrier.consumed_evidence = "test-fixture"
    else:
        carrier.lifecycle = "ACTIVE"
        carrier.consumed_at = None
        carrier.consumed_evidence = ""
    return carrier


def test_af_post_matrix_counts():
    """Post-AF production counts (seeds 1/7/42 x 200, rui recon=40).
    The consumption gate collapses contact volume; pre-AF baseline was
    153/158/156, shadow arm B (design target) 109/112/111, and the
    full lifecycle-stamp port measures 10/8/8 here."""
    from collections import Counter
    contacts = {}
    for seed in (1, 7, 42):
        world = build_genesis_world()
        world.characters["rui"].human_condition.desires["reconciliation"] = 40.0
        engine = SimulationEngine(seed=seed, use_arbitration=False)
        counter = Counter()
        for _ in range(200):
            for e in engine.step(world).events:
                if e.participants:
                    counter[event_action_type(e)] += 1
        total = sum(counter.values())
        contacts[seed] = (counter.get("contact_person", 0),
                          round(max(counter.values()) / total, 3))
    assert contacts[1] == (10, 0.364), contacts[1]
    assert contacts[7] == (8, 0.381), contacts[7]
    assert contacts[42] == (8, 0.36), contacts[42]


def test_af_gate_suppresses_consumed_belonging():
    """R1 shape: a CONSUMED belonging carrier must keep the gate closed
    even while the float passively regrows past the 20.0 threshold."""
    from engine.core.actions import generate_action_pool
    _, world = _run(7, ticks=0)
    char = world.characters["rui"]
    _with_belonging_carrier(world, char, consumed=True)
    pool = generate_action_pool(world, "rui")
    assert not any(c.action_type == "contact_person" for c in pool)


def test_af_new_evidence_reopens_gate():
    """R2 shape: clearing the CONSUMED stamp restores eligibility. The
    lifecycle writer clears the stamps when a new evidence-gated
    interpretation arrives (search_PERSON success births/updates the
    belonging carrier); the gate reader then re-qualifies on the
    current float - never by tick elapsed."""
    from engine.core.actions import generate_action_pool
    _, world = _run(7, ticks=0)
    char = world.characters["rui"]
    _with_belonging_carrier(world, char, consumed=True)
    pool = generate_action_pool(world, "rui")
    assert not any(c.action_type == "contact_person" for c in pool)
    # Simulate the interpretation writer's reactivation: a new
    # belonging-domain interpretation (e.g. from a failed contact's
    # evidence) clears the stamps.
    carrier = char.desire_carriers["belonging"]
    carrier.lifecycle = "ACTIVE"
    carrier.consumed_at = None
    carrier.consumed_evidence = ""
    pool = generate_action_pool(world, "rui")
    assert any(c.action_type == "contact_person" for c in pool)


def test_af_stamp_written_on_satisfaction():
    """The interpretation owner, and only it, stamps CONSUMED with
    event provenance; the float keeps its maintenance-silent growth."""
    world2 = build_genesis_world()
    world2.characters["rui"].human_condition.desires["reconciliation"] = 40.0
    engine = SimulationEngine(seed=7, use_arbitration=False)
    saw_consumed = None
    for i in range(120):
        engine.step(world2)
        c = world2.characters["rui"].desire_carriers.get("belonging")
        if c is not None and c.lifecycle == "CONSUMED" and saw_consumed is None:
            saw_consumed = (i, c.consumed_at, c.consumed_evidence)
    assert saw_consumed is not None, "no CONSUMED stamp observed in 120 ticks"
    tick, at, ev = saw_consumed
    assert at == tick, (at, tick)
    assert ev and ev != "test-fixture", ev


def test_af_replay_round_trip_with_stamps():
    """Consumption stamps survive checkpoint/restore round-trips."""
    from engine.persistence.codec import world_to_dict, world_from_dict
    from engine.persistence.replay import ReplayVerifier
    initial = build_genesis_world()
    initial.characters["rui"].human_condition.desires["reconciliation"] = 40.0
    continuous = world_from_dict(world_to_dict(initial))
    e1 = SimulationEngine(seed=7, use_arbitration=False)
    for _ in range(40):
        e1.step(continuous)
    split = world_from_dict(world_to_dict(initial))
    e2 = SimulationEngine(seed=7, use_arbitration=False)
    for _ in range(20):
        e2.step(split)
    restored = world_from_dict(world_to_dict(split))
    e3 = SimulationEngine(seed=999, use_arbitration=False)
    for _ in range(20):
        e3.step(restored)
    sigs = lambda log: [ReplayVerifier.event_signature(e) for e in log]
    assert sigs(restored.event_log) == sigs(continuous.event_log)
    assert world_to_dict(restored) == world_to_dict(continuous)
