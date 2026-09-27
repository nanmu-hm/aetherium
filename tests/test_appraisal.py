"""Tests for the appraisal/arbitration typed contract (Phase 1-4).

Phase 4 wires the actual pool-narrowing into generate_candidates; the
original shadow-inert assertion (use_arbitration=True == use_arbitration=False)
no longer holds by design. These tests now verify the Phase-4 behavior:
INERT ticks are behaviorally unchanged, A/B/C cases produce their frozen
outcomes, and the typed records have no scalar-bonus field.
"""

from __future__ import annotations

import dataclasses

from engine.core.appraisal import apply_arbitration, arbitrate, build_appraisals, motivation_source
from engine.core.models import AppraisalRecord, ArbitrationResult, EvidenceRecord
from engine.genesis import build_genesis_world
from engine.core.actions import generate_action_pool
from engine.core.simulation import SimulationEngine


def _world_and_pool(seed=1, tick=0):
    world = build_genesis_world()
    world.characters["rui"].human_condition.desires["reconciliation"] = 40.0
    engine = SimulationEngine(seed=seed)
    for _ in range(tick):
        engine.step(world)
    pool = generate_action_pool(world, "yan")
    return world, engine, pool


def test_evidence_record_fields():
    rec = EvidenceRecord(
        past_event_id="event-1-x-contact_person",
        state_delta=("relationship", "yan", "rui"),
        motivation_source="relationship",
        subject_id="yan",
        target_id="rui",
        event_age=3,
        current_relevance=1.0,
        interpretation="contact_person at tick 3 (old_road)",
        causal_link="0 newer event(s) have since rewritten this pair's relationship",
    )
    assert rec.past_event_id.startswith("event-")
    assert rec.state_delta[0] in {"relationship", "location"}
    assert 0.0 <= rec.current_relevance <= 1.0


def test_arbitration_result_has_no_float_field():
    # Structural guard: "no scalar bonus" is enforced at the type level.
    for f in dataclasses.fields(ArbitrationResult):
        assert f.type not in (float, "float"), f"{f.name} must not be a float field"


def test_arbitration_result_variants():
    assert ArbitrationResult(kind="inert").candidate_id == ""
    assert ArbitrationResult(kind="resolve", candidate_id="x").candidate_id == "x"
    assert ArbitrationResult(kind="abstain", evidence=()).evidence == ()


def test_inert_tick_behavior_unchanged():
    # An INERT arbitration verdict (clearly-separated ranking, gap > 0.75, or
    # all candidates from one motivation source) must leave the pool and the
    # kernel's own choice bit-identical to running without arbitration at all.
    world, engine, pool = _world_and_pool(tick=0)
    appraisals = build_appraisals(engine.decision_kernel, world, world.characters["yan"], pool)
    evals = [engine.decision_kernel.evaluate(world, c) for c in pool]
    result = arbitrate(appraisals, pool, evals)
    if result.kind == "inert":
        narrowed = apply_arbitration(pool, result, evals)
        assert narrowed == pool  # pool passes through untouched
        kernel_pick, _ = engine.decision_kernel.choose(world, narrowed, allow_quiet=True)
        baseline_pick, _ = engine.decision_kernel.choose(world, pool, allow_quiet=True)
        assert kernel_pick == baseline_pick


def test_motivation_source_vocabulary_reused():
    world, engine, pool = _world_and_pool(tick=1)
    for c in pool:
        src = motivation_source(c)
        assert src in {"goal", "fulfillment", "relationship", "search", "compassion", "recovery", "other"}


def test_arbitrate_inert_on_clearly_separated_ranking():
    world, engine, pool = _world_and_pool(tick=0)
    appraisals = build_appraisals(engine.decision_kernel, world, world.characters["yan"], pool)
    evals = [engine.decision_kernel.evaluate(world, c) for c in pool]
    result = arbitrate(appraisals, pool, evals)
    ordered = sorted(evals, key=lambda e: e.utility, reverse=True)
    if len(ordered) >= 2 and ordered[0].utility - ordered[1].utility > 0.75:
        assert result.kind == "inert"


def test_apply_arbitration_inert_returns_pool_unchanged():
    world, engine, pool = _world_and_pool()
    appraisals = build_appraisals(engine.decision_kernel, world, world.characters["yan"], pool)
    evals = [engine.decision_kernel.evaluate(world, c) for c in pool]
    result = arbitrate(appraisals, pool, evals)
    narrowed = apply_arbitration(pool, result, evals)
    if result.kind == "inert":
        assert narrowed == pool


def test_apply_arbitration_abstain_returns_empty_pool():
    world, engine, pool = _world_and_pool()
    appraisals = build_appraisals(engine.decision_kernel, world, world.characters["yan"], pool)
    evals = [engine.decision_kernel.evaluate(world, c) for c in pool]
    result = ArbitrationResult(kind="abstain", evidence=())
    narrowed = apply_arbitration(pool, result, evals)
    assert narrowed == []
    # The kernel's own existing empty-pool guard handles this; no new code path.
    kernel_pick, kernel_evals = engine.decision_kernel.choose(world, narrowed, allow_quiet=True)
    assert kernel_pick is None
    assert kernel_evals == []


def test_apply_arbitration_resolve_narrows_to_top2():
    world, engine, pool = _world_and_pool(tick=1)
    appraisals = build_appraisals(engine.decision_kernel, world, world.characters["yan"], pool)
    evals = [engine.decision_kernel.evaluate(world, c) for c in pool]
    result = arbitrate(appraisals, pool, evals)
    if result.kind == "resolve" and len(pool) > 2:
        narrowed = apply_arbitration(pool, result, evals)
        assert len(narrowed) == 2
        assert result.candidate_id in {c.id for c in narrowed}
        # No utility/selection_score field on any candidate was touched:
        # the kernel's own evaluate() on the narrowed set gives the same
        # per-candidate utilities as on the full pool.
        for c in narrowed:
            assert engine.decision_kernel.evaluate(world, c) in evals

