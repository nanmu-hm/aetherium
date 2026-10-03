"""T2 memory-synthesis semantics (branch t2-memory-synthesis-semantics).

Acceptance tests for the v3 T2 union provisions, self-contained in the repo
(mirrors Arena's S1 oracle, no external read-only verifier needed):

- Stable in-place row identity: one current Store-1 row per
  (owner_id, description); no per-event suffix in `desires`.
- E2 post-birth evidence: a carrier's latest admitted event is mirrored into
  the row's `latest_evidence_event_id`.
- P-B reactivation: a newly admitted post-birth evidence event revives a
  'missed' row back to 'active'; 'achieved' stays terminal.
- P-B evidence-alive: a row carrying post-birth evidence is not re-missed by
  the opportunity-window fallback (state-based, no tick timer).
- Codec canonicalization: an old multi-row payload collapses to one current
  row plus an independent `desire_history` provenance container.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world
from engine.memory.kernel import MemoryKernel
from engine.memory.models import Desire, MemoryState
from engine.persistence.codec import _canonicalize_desires


def _stable_key(owner_id: str, description: str) -> str:
    return f"{owner_id}:store1:{description}"


# ---------------------------------------------------------------------------
# 1. Codec canonicalization: multi-row old payload -> one current + history.
# ---------------------------------------------------------------------------
def test_canonicalize_multirow_payload_to_one_current_plus_history():
    raw = {
        # old-style per-event row: earliest evidence
        "yan:store1:belonging:event-0-yan-contact_person": {
            "id": "yan:store1:belonging:event-0-yan-contact_person",
            "owner_id": "yan",
            "description": "belonging",
            "status": "active",
            "priority": 0.5,
            "urgency": 0.04,
            "source_event_id": "event-0-yan-contact_person",
            "latest_evidence_event_id": "",
        },
        # old-style per-event row: most-recent evidence wins as current
        "yan:store1:belonging:event-105-yan-contact_person": {
            "id": "yan:store1:belonging:event-105-yan-contact_person",
            "owner_id": "yan",
            "description": "belonging",
            "status": "active",
            "priority": 0.5,
            "urgency": 0.04,
            "source_event_id": "event-0-yan-contact_person",
            "latest_evidence_event_id": "event-105-yan-contact_person",
        },
    }
    current, history = _canonicalize_desires(raw)

    # Exactly one current row, re-keyed to the STABLE identity key.
    assert list(current) == ["yan:store1:belonging"]
    cur = current["yan:store1:belonging"]
    assert cur.id == "yan:store1:belonging"
    # Most-recent-evidence row survives as the current row.
    assert cur.latest_evidence_event_id == "event-105-yan-contact_person"
    # The displaced older row migrates to the independent provenance container.
    assert len(history["yan:store1:belonging"]) == 1
    assert history["yan:store1:belonging"][0].latest_evidence_event_id == ""
    assert history["yan:store1:belonging"][0].status == "active"


def test_canonicalize_single_newstyle_payload_is_noop():
    # A new-style payload already holds one row per stable identity.
    raw = {
        "yan:store1:belonging": {
            "id": "yan:store1:belonging",
            "owner_id": "yan",
            "description": "belonging",
            "status": "active",
            "priority": 0.5,
            "urgency": 0.04,
            "source_event_id": "event-0-yan-contact_person",
            "latest_evidence_event_id": "event-105-yan-contact_person",
        },
    }
    current, history = _canonicalize_desires(raw)
    assert list(current) == ["yan:store1:belonging"]
    assert current["yan:store1:belonging"].latest_evidence_event_id == "event-105-yan-contact_person"
    assert history.get("yan:store1:belonging", []) == []


# ---------------------------------------------------------------------------
# 2. P-B evidence-alive: rows with post-birth evidence are not re-missed.
# ---------------------------------------------------------------------------
def test_advance_desires_evidence_alive_not_remissed():
    state = MemoryState()
    state.add_desire(
        Desire(
            id=_stable_key("yan", "belonging"),
            owner_id="yan",
            description="belonging",
            status="active",
            opportunity_window_end=10,
            # post-birth evidence present -> evidence-alive
            latest_evidence_event_id="event-105-yan-contact_person",
        )
    )
    MemoryKernel().advance_desires(state, 11)  # window closed, but evidence present
    assert state.desires[_stable_key("yan", "belonging")].status == "active"


def test_advance_desires_no_evidence_still_remisses():
    # D-scope behavior preserved: a row with NO post-birth evidence auto-misses.
    state = MemoryState()
    state.add_desire(
        Desire(
            id=_stable_key("yan", "belonging"),
            owner_id="yan",
            description="belonging",
            status="active",
            opportunity_window_end=10,
            latest_evidence_event_id="",
        )
    )
    MemoryKernel().advance_desires(state, 11)
    assert state.desires[_stable_key("yan", "belonging")].status == "missed"


# ---------------------------------------------------------------------------
# 3. S1 oracle (in-repo): stable identity + E2 evidence + P-B active @400.
# ---------------------------------------------------------------------------
def test_belonging_row_s1_oracle_at_400():
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    eng = SimulationEngine(seed=7, use_arbitration=False)
    for _ in range(400):
        eng.step(world)

    # Every Store-1 row uses the stable in-place key (no per-event suffix).
    for row in world.memory_state.desires.values():
        assert row.id == _stable_key(row.owner_id, row.description)

    row = world.memory_state.desires[_stable_key("yan", "belonging")]
    assert row.source_event_id == "event-0-yan-contact_person"
    assert row.latest_evidence_event_id == "event-105-yan-contact_person"
    # P-B reactivation: the row was missed at window close, then revived by
    # the post-birth evidence at tick 105, and stays active (evidence-alive).
    # CONSUMED alone never marks it achieved.
    assert row.status == "active"
    assert row.status != "achieved"
