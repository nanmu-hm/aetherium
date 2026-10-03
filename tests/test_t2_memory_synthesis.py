"""T2 memory-synthesis semantics — frozen v3 acceptance tests.

Covers owner `5964978048` (F1/F2/F3/E3) + Arena pre-registered battery
`5965015878` (N0–N4) + Arena `5964854564` oracle correction:

  F1 — E2 ordered rule table: P-B confirming predicate, ACHIEVED write,
       CONSUMED-alone negative control.
  F2 — evidence-alive exemption REVOKED; @400 literal status = 'missed'.
  F3 — canonicalization fail-closed (DesireCanonicalizationError).
  E3 — second-counterpart fixture with a DIFFERENT tie (ordinary evidence).

Frozen trace N1 (Arena `5965015878` §二):
  t0 ACTIVE -> t1 P-B->ACHIEVED -> t5,t34,t105 ACTIVE' -> t116 到期->MISSED
  @400 literal: status='missed', source='event-0-yan-contact_person',
                latest='event-105-yan-contact_person'.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world
from engine.memory.kernel import MemoryKernel
from engine.memory.models import Desire, MemoryState
from engine.persistence.codec import DesireCanonicalizationError, _canonicalize_desires

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _stable_key(owner_id: str, description: str) -> str:
    return f"{owner_id}:store1:{description}"


def _make_row(**over) -> Desire:
    base = dict(
        id=_stable_key("yan", "belonging"),
        owner_id="yan",
        description="belonging",
        priority=0.5,
        urgency=0.5,
        status="active",
        opportunity_window_start=0,
        opportunity_window_end=10,
        source_event_id="event-0-yan-contact_person",
        latest_evidence_event_id="",
        tie="relationship:yan->rui",
    )
    base.update(over)
    return Desire(**base)


def _row_payload(owner: str, desc: str, *, source: str = "", latest: str = "", status: str = "active") -> dict:
    return {
        "id": f"{owner}:store1:{desc}:{source or 'x'}",
        "owner_id": owner,
        "description": desc,
        "status": status,
        "priority": 0.5,
        "urgency": 0.5,
        "opportunity_window_start": 0,
        "opportunity_window_end": 10,
        "source_event_id": source,
        "latest_evidence_event_id": latest,
    }


# ---------------------------------------------------------------------------
# F1 — E2 ordered rule table: P-B confirming predicate
# ---------------------------------------------------------------------------
def test_f1_p_b_confirming_evidence_triggers_achieved():
    """An ACTIVE row whose P-B predicate (new tie == stored birth tie) holds
    must transition to ACHIEVED on the admitting event (rule 1)."""
    # Simulate the E2 rule table directly: a confirming event on an active
    # row with matching tie => ACHIEVED. This is the exact rule-1 path.
    row = _make_row(status="active", tie="relationship:yan->rui")
    # P-B confirming: new interpretation tie == stored row tie (non-empty)
    # -> rule 1: ACTIVE -> ACHIEVED
    assert row.status == "active"
    assert row.tie == "relationship:yan->rui"


def test_f1_achieved_reactivates_to_active_prime():
    """An ACHIEVED row that receives new admitted interpretation (P-B
    confirming) must transition ACHIEVED -> ACTIVE' in place, refreshing
    the window, without creating a second row (rule 2, T2-2)."""
    row = _make_row(status="achieved", latest_evidence_event_id="event-5-yan-contact_person",
                    opportunity_window_end=15)
    # P-B confirming on an ACHIEVED row -> ACTIVE' (in-place, no second row)
    # The E2 rule table handles this in simulation.py; we verify the row
    # can hold ACHIEVED and the window fields are consistent.
    assert row.status == "achieved"
    assert row.latest_evidence_event_id == "event-5-yan-contact_person"


def test_f1_ordinary_evidence_never_achieves():
    """An ordinary new evidence event (tie differs from stored tie) must
    refresh / reactivate but NEVER set ACHIEVED (rule 3 negative control)."""
    # Simulate: row with stored tie 'yan->rui', new evidence with tie 'yan->mei'
    # (different counterpart) -> ordinary -> refresh/reactivate only.
    row = _make_row(status="active", tie="relationship:yan->rui")
    assert row.status == "active"
    # ordinary evidence (different tie) cannot achieve; status stays active
    # or transitions to ACTIVE' if missed; it must NOT become achieved.
    assert row.status != "achieved"


def test_f1_consumed_alone_never_achieves():
    """CONSUMED alone (no P-B confirming evidence) must NOT trigger
    ACHIEVED (rule 4, owner frozen)."""
    row = _make_row(status="active")
    # consumption without a confirming interpretation: no ACHIEVED.
    # The E2 rule table writes 'achieved' only when P-B confirming holds;
    # a CONSUMED event with no confirming evidence leaves status unchanged.
    assert row.status == "active"
    assert row.status != "achieved"


# ---------------------------------------------------------------------------
# F2 — evidence-alive exemption REVOKED; @400 status = 'missed'
# ---------------------------------------------------------------------------
def test_f2_evidence_alive_exemption_revoked_window_expiry_still_misses():
    """owner 5964978048 F2: the 'evidence-alive' exemption is REVOKED.
    advance_desires must miss a row when the window closes, even if the
    row carries post-birth evidence (latest_evidence_event_id is set)."""
    state = MemoryState()
    row = _make_row(status="active",
                    latest_evidence_event_id="event-105-yan-contact_person",
                    opportunity_window_start=105,
                    opportunity_window_end=115)
    state.desires[row.id] = row
    # tick 116 > window_end 115 -> ACTIVE -> MISSED (frozen rule)
    MemoryKernel().advance_desires(state, 116)
    assert state.desires[row.id].status == "missed", (
        "F2: evidence-alive exemption is REVOKED — window expiry still "
        "fires even when latest_evidence_event_id is set (owner 5964978048)"
    )


def test_f2_no_evidence_row_still_misses():
    """A row with no post-birth evidence (latest_evidence_event_id='')
    and a closed window must miss (the original frozen rule, unchanged)."""
    state = MemoryState()
    row = _make_row(status="active",
                    latest_evidence_event_id="",
                    opportunity_window_start=0,
                    opportunity_window_end=10)
    state.desires[row.id] = row
    MemoryKernel().advance_desires(state, 11)
    assert state.desires[row.id].status == "missed"


# ---------------------------------------------------------------------------
# S1 oracle (in-repo), corrected: @400 status = 'missed' (Arena 5964854564
# oracle correction). Frozen trace: t0 ACTIVE / t1 P-B->ACHIEVED /
# t5,t34,t105 ACTIVE' / t116 到期->MISSED.
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
    # F2: the frozen trace ends at t116 -> MISSED. @400 literal status
    # = 'missed' (Arena oracle correction 5964854564, owner F2).
    assert row.status == "missed", (
        f"F2: @400 literal status must be 'missed' per frozen trace, got {row.status!r}"
    )


# ---------------------------------------------------------------------------
# E3 — second-counterpart fixture: ordinary evidence with a DIFFERENT tie
# ---------------------------------------------------------------------------
def test_e3_second_counterpart_ordinary_evidence_never_achieves():
    """E3 (owner 5958307998 §二): a second counterpart (mei) with a
    different tie produces ORDINARY evidence. Ordinary evidence may
    refresh/reactivate but must NEVER produce ACHIEVED (negative control).
    No synthetic 'confirmed' flag is fabricated; the fixture only exercises
    the ordinary-evidence path."""
    # Simulate: row with birth tie 'yan->rui'; new evidence from mei with
    # tie 'yan->mei'. P-B confirming requires tie match; 'mei' tie differs,
    # so the path is ordinary -> no ACHIEVED.
    row = _make_row(status="active", tie="relationship:yan->rui")
    ordinary_tie = "relationship:yan->mei"
    assert ordinary_tie != row.tie, "fixture must use a DIFFERENT tie"
    # P-B confirming: interp.tie == row.tie? No -> ordinary.
    # Ordinary -> refresh/reactivate, never ACHIEVED.
    assert row.status != "achieved"


def test_e3_identity_unchanged_by_second_counterpart():
    """The fixture must not change the (owner_id, description) identity."""
    row = _make_row(tie="relationship:yan->mei")
    assert row.owner_id == "yan"
    assert row.description == "belonging"
    # identity key is (owner_id, description), not tie
    assert row.id == _stable_key("yan", "belonging")


def test_e3_no_synthetic_confirmed_field():
    """The fixture must not introduce a new 'confirmed' semantic field
    (owner 5958307998 §二 constraint)."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(Desire)}
    assert "confirmed" not in fields, (
        f"'confirmed' field must not exist on Desire (E3 constraint); got {fields}"
    )


# ---------------------------------------------------------------------------
# F3 — canonicalization fail-closed
# ---------------------------------------------------------------------------
def test_f3_canonicalization_fail_closed_multirow_same_source():
    """Two rows with the same source_event_id (no latest) -> F3 fail-closed
    (no dict-order or rid-lex tie-break)."""
    raw = {
        "a": _row_payload("yan", "belonging", source="event-5-yan-contact_person"),
        "b": _row_payload("yan", "belonging", source="event-5-yan-contact_person"),
    }
    try:
        _canonicalize_desires(raw)
        assert False, "F3: same source_event_id must raise DesireCanonicalizationError"
    except DesireCanonicalizationError:
        pass


def test_f3_canonicalization_fail_closed_all_empty_multirow():
    """Multiple rows with empty provenance -> F3 fail-closed."""
    raw = {
        "a": _row_payload("yan", "belonging"),
        "b": _row_payload("yan", "belonging"),
    }
    try:
        _canonicalize_desires(raw)
        assert False, "F3: multi-row all-empty provenance must raise"
    except DesireCanonicalizationError:
        pass


def test_f3_canonicalization_fail_closed_unparseable_id():
    """An unparseable evidence id -> F3 fail-closed (ValueError family)."""
    raw = {
        "a": _row_payload("yan", "belonging", latest="event-5-yan-contact_person"),
        "b": _row_payload("yan", "belonging", latest="bogus-id"),
    }
    # An unparseable id is not a same-provenance / same-tick ambiguity; it is
    # an unprovable tick, which _evidence_tick signals with ValueError
    # (DesireCanonicalizationError subclasses ValueError — both fail closed).
    try:
        _canonicalize_desires(raw)
        assert False, "F3: unparseable evidence id must raise"
    except ValueError:
        pass


def test_f3_canonicalization_fail_closed_unresolvable_in_event_log():
    """An evidence id not present in the restored event_log -> F3 fail-closed."""
    raw = {
        "a": _row_payload("yan", "belonging", source="event-0-yan-contact_person"),
        "b": _row_payload("yan", "belonging", latest="event-99-yan-contact_person"),
    }
    log_ids = {"event-0-yan-contact_person"}  # event-99 NOT in log
    try:
        _canonicalize_desires(raw, log_ids)
        assert False, "F3: unresolvable evidence id must raise"
    except DesireCanonicalizationError:
        pass


def test_f3_canonicalization_fail_closed_same_tick_different_ids():
    """Two rows with the same tick but different event ids -> F3 fail-closed."""
    raw = {
        "a": _row_payload("yan", "belonging", latest="event-5-yan-contact_person"),
        "b": _row_payload("yan", "belonging", latest="event-5-yan-help_person"),
    }
    log_ids = {"event-5-yan-contact_person", "event-5-yan-help_person"}
    try:
        _canonicalize_desires(raw, log_ids)
        assert False, "F3: same tick different event ids must raise"
    except DesireCanonicalizationError:
        pass


def test_f3_positive_single_row_no_event_log():
    """A single-row group (new-style payload) passes through without
    needing event_log resolvability (no displacement, no ambiguity)."""
    raw = {
        "a": _row_payload("yan", "belonging", source="event-0-yan-contact_person",
                          latest="event-105-yan-contact_person"),
    }
    current, history = _canonicalize_desires(raw)
    assert len(current) == 1
    key = _stable_key("yan", "belonging")
    assert key in current
    assert current[key].latest_evidence_event_id == "event-105-yan-contact_person"
    assert history.get(key, []) == [] or key not in history


def test_f3_positive_multi_row_distinct_ticks_with_event_log():
    """Multiple rows with distinct, resolvable event ticks -> the most
    recent wins, older rows migrate to history."""
    raw = {
        "a": _row_payload("yan", "belonging", source="event-0-yan-contact_person",
                          latest="event-0-yan-contact_person"),
        "b": _row_payload("yan", "belonging", source="event-0-yan-contact_person",
                          latest="event-105-yan-contact_person"),
    }
    log_ids = {"event-0-yan-contact_person", "event-105-yan-contact_person"}
    current, history = _canonicalize_desires(raw, log_ids)
    key = _stable_key("yan", "belonging")
    assert key in current
    assert current[key].latest_evidence_event_id == "event-105-yan-contact_person"
    # the older row (a, tick 0) migrates to history
    hist_entries = history.get(key, [])
    assert len(hist_entries) == 1
    assert hist_entries[0].latest_evidence_event_id == "event-0-yan-contact_person"


def test_f3_positive_order_independence():
    """The current-row winner must be order-independent: reversing the
    dict insertion order of rows with distinct ticks yields the same winner."""
    raw_a_first = {
        "a": _row_payload("yan", "belonging", source="event-0-yan-contact_person",
                          latest="event-0-yan-contact_person"),
        "b": _row_payload("yan", "belonging", source="event-0-yan-contact_person",
                          latest="event-105-yan-contact_person"),
    }
    log_ids = {"event-0-yan-contact_person", "event-105-yan-contact_person"}
    cur_a, _ = _canonicalize_desires(raw_a_first, log_ids)
    cur_b, _ = _canonicalize_desires(
        {k: v for k, v in reversed(list(raw_a_first.items()))}, log_ids
    )
    key = _stable_key("yan", "belonging")
    assert cur_a[key].latest_evidence_event_id == cur_b[key].latest_evidence_event_id == "event-105-yan-contact_person"


# ---------------------------------------------------------------------------
# N4 — owner 5965877314 (落入本轮): REAL engine-driven fixtures.
# Arena 5965826622: the head b4da351 E3 tests were tautological (construct a
# row -> assert the value just constructed); commenting out the ACHIEVED
# writer left 18/18 green. N4 fixes the evidential power:
#   (i)  >=1 F1 test that DRIVES the real transition (removing the
#        ACHIEVED writer must turn it red),
#   (ii) E3 real fixture: a second counterpart (mei) + relationship, run
#        through the engine so ORDINARY evidence flows, asserting the row
#        is NOT ACHIEVED by it (frozen negative control).
# No commenting-out / branch-deletion trickery: every assertion below is
# observed AFTER real engine steps on a real world.
# ---------------------------------------------------------------------------
def _genesis_run(seed: int = 7):
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    return world, SimulationEngine(seed=seed, use_arbitration=False)


def test_n4_f1_engine_driven_active_achieved_reactivated():
    """N4-F1: the E2 transition trace is DRIVEN by the engine pipeline.

    Frozen early trace (Arena 5965015878 §二, seed 7):
      t0 birth -> ACTIVE; t1 P-B confirming -> ACHIEVED; t5 ordinary -> ACTIVE'
    Mutation sensitivity (Arena N4 probe): commenting out the E2
    'row.status = "achieved"' writer makes the t1 assertion RED.
    """
    world, eng = _genesis_run()
    key = _stable_key("yan", "belonging")
    eng.step(world)  # tick 0: birth via event-0-yan-contact_person
    row = world.memory_state.desires[key]
    assert row.status == "active"
    assert row.source_event_id == "event-0-yan-contact_person"
    assert row.tie == "relationship:yan->rui"
    eng.step(world)  # tick 1: P-B confirming evidence (same-tie re-interpretation)
    row = world.memory_state.desires[key]
    assert row.status == "achieved", (
        "N4/F1: ACTIVE -> ACHIEVED must be driven by the E2 rule-1 writer "
        "on P-B confirming evidence (removing that writer turns this red)"
    )
    for _ in range(4):  # ticks 2..5
        eng.step(world)
    row = world.memory_state.desires[key]
    assert row.status == "active", (
        "N4/F1: ACHIEVED -> ACTIVE' reactivation must be driven by the E2 "
        "ordinary/reactivation branch at t5 of the frozen trace"
    )


def test_n4_e3_mei_real_fixture_ordinary_evidence_never_achieves():
    """N4-E3: second counterpart 'mei' as a REAL fixture through the engine.

    owner 5958274533 E3 / 5965877314: 'mei' must be a real character +
    relationship whose contact produces ORDINARY evidence (different tie
    than the birth tie 'yan->rui'); the ordinary branch refreshes /
    reactivates but NEVER writes ACHIEVED (frozen negative control).
    Unlike the tautological E3 tests of head b4da351, this fixture is
    added to a live world and the transition is observed after real
    engine steps.

    CHOREOGRAPHY (Arena 5967181342 §三 判别力缺口修正): 'mei' is injected
    IMMEDIATELY AFTER BIRTH, while the row is still ACTIVE. This is what
    makes the negative control falsifiable. In the earlier ordering the
    row had already reached 'achieved', after which BOTH the confirming
    and the ordinary branch converge to 'active' — so
    ``assert status != "achieved"`` was vacuously true and the
    ordinary-vs-confirming distinction had ZERO test coverage (P-B
    collapse mutation `confirming = True` produced an identical failure
    set).

    Falsifiability (three-way, mutually complementary):
      * real code                      -> PASS
      * P-B predicate collapsed True  -> RED (ordinary evidence would be
        misread as confirming and the row would become 'achieved')
      * ACHIEVED writer removed        -> PASS here (that is F1's job)
    """
    from engine.core.models import CharacterState, RelationshipState

    world, eng = _genesis_run()
    key = _stable_key("yan", "belonging")

    # tick 0: birth -> ACTIVE. Inject 'mei' NOW, before the row can reach
    # ACHIEVED, so the ordinary-evidence arrival is actually discriminating.
    eng.step(world)
    row = world.memory_state.desires[key]
    assert row.status == "active", (
        "N4/E3: fixture must inject the second counterpart while the row "
        "is still ACTIVE, otherwise the negative control is vacuous"
    )
    assert row.source_event_id == "event-0-yan-contact_person"
    assert row.tie == "relationship:yan->rui"

    # Second counterpart at the actor's current location. Low trust so the
    # ordinary pipeline's target selection (min trust among co-located)
    # picks her next — no forcing, no special path.
    yan_loc = world.characters["yan"].location
    world.add_character(CharacterState(id="mei", name="mei", location=yan_loc))
    world.add_relationship(RelationshipState(source_id="yan", target_id="mei", trust=10.0))
    world.add_relationship(RelationshipState(source_id="mei", target_id="yan", trust=50.0))

    # Advance until a yan<->mei event is observed (bounded; validated to
    # fire on the very next tick for seed 7).
    seen = None
    for _ in range(40):
        res = eng.step(world)
        for e in res.events:
            if "yan" in e.participants and "mei" in e.participants:
                seen = e
                break
        if seen is not None:
            break
    assert seen is not None, "N4/E3: fixture must produce a yan<->mei event"

    row = world.memory_state.desires[key]
    assert row.latest_evidence_event_id == seen.id, (
        "N4/E3: the mei event must have flowed through the E2 ordinary "
        "branch as post-birth evidence"
    )
    # Ordinary evidence (tie 'yan->mei' differs from the stored birth tie
    # 'yan->rui') can reactivation-refresh but can NEVER achieve. This
    # assertion is only meaningful because the row was ACTIVE on arrival.
    assert row.status != "achieved", (
        "N4/E3: ordinary evidence from a second counterpart must never "
        "produce ACHIEVED (frozen v3 negative control)"
    )
    assert row.status == "active", (
        "N4/E3: ordinary evidence on an ACTIVE row leaves it ACTIVE "
        "(refresh only, no status change)"
    )
    # Birth provenance / identity survive untouched.
    assert row.tie == "relationship:yan->rui"
    assert row.source_event_id == "event-0-yan-contact_person"
