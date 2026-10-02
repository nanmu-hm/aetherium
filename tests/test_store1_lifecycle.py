"""Store-1 D-scope lifecycle tests (branch d-scope-store1-lifecycle).

Minimal closed loop: ④-admitted BIRTH mirrors a row into Store-1
(memory_state.desires) with structured provenance (source_event_id),
reused advance_desires lifecycle, codec round-trip, and a real
write->read->decision.utility delta. No fixture/param/test changes to
existing tests.
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

from engine.core.models import Event
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world
from engine.memory.models import Desire, MemoryState
from engine.persistence.codec import load_world_json, save_world_json


def _run_engine(world, seed=7, ticks=4):
    eng = SimulationEngine(seed=seed)
    for _ in range(ticks):
        eng.step(world)
    return eng, world


def _active_store1(world):
    return [d for d in world.memory_state.desires.values() if d.status == "active"]


def test_store1_birth_mirrors_with_source_event_id():
    """④-admitted birth writes a Store-1 row whose source_event_id is the
    admitting event, and the row is readable at the decision path."""
    world = build_genesis_world()
    _run_engine(world)
    rows = _active_store1(world)
    assert rows, "expected at least one active Store-1 desire after 4 ticks"
    log_ids = {e.id for e in world.event_log}
    for row in rows:
        # structured provenance only: reason is empty, source_event_id resolves
        assert row.reason == ""
        assert row.source_event_id in log_ids, f"{row.source_event_id} not in event_log"
        assert 0.0 <= row.urgency <= 1.0, "Store-1 urgency must stay on the 0-1 scale"
    # Every Store-1 row's owner has the matching hot-path float (birth
    # mirror, not drift). NOTE: the hot-path float may have drifted since
    # birth (passive +3/tick maintenance is AA-6 silent), so equality with
    # the *current* hot value is NOT asserted — only that the hot-path key
    # exists and the row's value is a plausible 0-1 sample of it.
    for row in rows:
        hot = world.characters[row.owner_id].human_condition.desires.get(row.description)
        assert hot is not None, "Store-1 row must correspond to a live hot-path desire"


def test_store1_codec_roundtrip_preserves_source_event_id():
    """save -> load round-trips the mirrored row with source_event_id intact,
    and the restored world still resolves it against the restored event_log."""
    world = build_genesis_world()
    _run_engine(world)
    rows = _active_store1(world)
    assert rows
    save_world_json(world, "/tmp/store1_probe_roundtrip.json")
    restored = load_world_json("/tmp/store1_probe_roundtrip.json")
    pre = {(d.owner_id, d.description): d for d in rows}
    post = {(d.owner_id, d.description): d for d in restored.memory_state.desires.values()}
    assert set(pre) == set(post), "Store-1 row set must survive round-trip"
    for key, d in pre.items():
        assert post[key].source_event_id == d.source_event_id
        assert post[key].status == d.status
        assert post[key].urgency == d.urgency
    log_ids = {e.id for e in restored.event_log}
    for key, d in post.items():
        assert d.source_event_id in log_ids, "restored row must resolve in restored log"


def test_store1_missed_boundary_via_advance_desires():
    """Reused lifecycle: a mirrored row with a closed opportunity window
    advances to 'missed' at end_of_step(window_end + 1) (P5 convention)."""
    world = build_genesis_world()
    _run_engine(world, ticks=1)
    row = _active_store1(world)[0]
    assert row.opportunity_window_end is not None, "mirrored row always carries a window"
    window_end = row.opportunity_window_end
    eng = SimulationEngine(seed=7)
    state_at_close = eng.memory_kernel.advance_desires(world.memory_state, window_end)
    assert next(d.status for d in world.memory_state.desires.values() if d.id == row.id) == "active"
    eng.memory_kernel.advance_desires(world.memory_state, window_end + 1)
    assert world.memory_state.desires[row.id].status == "missed"


def test_store1_read_path_delta_nonzero():
    """write->read: toggling a mirrored row changes evaluate.utility when
    the row is binding (same seed, same candidate). The natural-flow row is
    NOT binding (hot-path dominates the max), so this test drives a
    binding configuration directly: the read path decision.py:167 is
    proven live, not inert."""
    world = build_genesis_world()
    _run_engine(world, ticks=3)
    rows = _active_store1(world)
    assert rows, "need a mirrored row to toggle"
    row = rows[0]
    eng = SimulationEngine(seed=7)
    # Drive a candidate whose urgency mapping reads this owner's desires
    # (contact_person -> reconciliation/belonging), then make the row the
    # binding input by raising its urgency above the hot-path value.
    from engine.core.models import ActionCandidate
    cand = ActionCandidate(
        id=f"probe-{row.owner_id}-contact",
        actor_id=row.owner_id,
        action_type="contact_person",
        targets=[],
        motivation="reconciliation",
    )
    row.urgency = 0.9
    with_row = eng.decision_kernel.evaluate(world, cand)
    saved = world.memory_state.desires.pop(row.id)
    try:
        without_row = eng.decision_kernel.evaluate(world, cand)
    finally:
        row.urgency = saved.urgency
        world.memory_state.desires[row.id] = saved
    assert abs(with_row.utility - without_row.utility) > 0.0, \
        "decision.utility delta must be non-zero (write->read->decision live)"
