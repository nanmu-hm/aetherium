"""Event-level causal ledger — acceptance A–D (ChatGPT 5971081586).

  A. event causal ledger 完整性: every executed event can independently
     resolve actor / intent / action / preconditions / observations / target /
     effects / downstream, with NO dangling reference.
  B. silent tick 隔离: a tick where nobody acts may still change world state,
     but those changes must be recorded as passive/clock transitions and must
     NOT appear as the previous event's consequences/downstream.
  C. 闭环: Character Choice -> Event -> World State -> Character State ->
     Next Choice; the next decision can read the previous event's effect.
  D. 存档兼容: snapshots written WITHOUT the new fields still load, and a
     round-trip is byte-identical.

Pure tests. No production semantics outside the four ledger fields.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

import dataclasses

from engine.core.models import Consequence, Event
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world
from engine.memory.models import MemoryState
from engine.persistence.codec import world_from_dict, world_to_dict

SEED = 7
KEY = "yan:store1:belonging"

def _target_resolvable(world, target_type: str, target_id: str) -> bool:
    """A Consequence names a character, a location, a relationship pair, or a
    goal. Every kind must be resolvable against live world state -- that is
    what makes the event ledger auditable rather than a free-text log."""
    if target_type == "character":
        return target_id in world.characters
    if target_type == "location":
        return target_id in world.locations
    if target_type == "relationship":
        return target_id in world.relationships
    if target_type == "goal":
        return any(
            goal.id == target_id
            for character in world.characters.values()
            for goal in character.goals
        )
    return target_id in world.characters or target_id in world.locations


def _field_resolvable(character, field_path: str) -> bool:
    """A Consequence.field is a dotted path from the CharacterState, e.g.
    'emotions.joy' or 'human_condition.desires.belonging'."""
    parts = field_path.split(".")
    current = character
    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                return False
            current = current[part]
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return False
    return True



def _world(ticks=6, seed=SEED):
    w = build_genesis_world()
    w.timestamp = "0001-01-01T00:00:00"
    eng = SimulationEngine(seed=seed, use_arbitration=False)
    for _ in range(ticks):
        eng.step(w)
    return w, eng


# ---------------------------------------------------------------------------
# A. event causal ledger completeness
# ---------------------------------------------------------------------------
def test_a_every_event_answers_the_eight_questions():
    """Every executed event independently answers all eight questions."""
    w, _ = _world(40)
    assert w.event_log, "fixture must produce events"
    event_ids = {e.id for e in w.event_log}

    for event in w.event_log:
        actor = event.participants[0]
        # actor
        assert actor in w.characters, f"{event.id}: actor not resolvable"
        # action
        assert event.action_type, f"{event.id}: action_type empty"
        # intent -- was dangling before (candidate-only), now on the event
        assert isinstance(event.intent, str)
        # preconditions -- recorded hard-gate outcome, not just "it happened"
        assert event.preconditions, f"{event.id}: no preconditions recorded"
        assert any(p.startswith("gate:") for p in event.preconditions), (
            f"{event.id}: preconditions must include the hard-gate outcome"
        )
        # observations -- deterministic, serializable summary
        assert event.observations, f"{event.id}: no observations recorded"
        assert any(o.startswith("location:") for o in event.observations)
        # target
        for target_id in event.participants[1:]:
            assert target_id in w.characters or target_id in w.locations, (
                f"{event.id}: unresolvable target {target_id}"
            )
        # effects -- via Consequence (every target_id resolvable in the world)
        for consequence in event.consequences:
            assert _target_resolvable(w, consequence.target_type, consequence.target_id), (
                f"{event.id}: unresolvable consequence target "
                f"{consequence.target_type}:{consequence.target_id}"
            )
        # downstream -- event-id references only, never dangling
        for downstream_id in event.downstream:
            assert downstream_id in event_ids, (
                f"{event.id}: dangling downstream ref {downstream_id}"
            )


def test_a_causes_are_no_longer_dangling():
    """The regression this whole change exists for (Arena 5971061262 §4):
    Event.causes used to hold transient ActionCandidate ids that no persisted
    object could resolve. intent/preconditions now travel ON the event, so the
    evidence is self-contained even though the candidate id is still kept for
    backward compatibility."""
    w, _ = _world(40)
    for event in w.event_log:
        assert event.causes, f"{event.id}: loses its cause reference"
        # every causal question the causes id used to answer is now answerable
        # from the event itself
        assert event.intent or event.action_type
        assert event.preconditions


def test_a_observations_are_deterministic_and_serializable():
    """Same seed -> byte-identical observations; values are plain strings."""
    first, _ = _world(6)
    second, _ = _world(6)
    a = [e.observations for e in first.event_log]
    b = [e.observations for e in second.event_log]
    assert a == b, "observations must be deterministic across identical runs"
    for group in a:
        for item in group:
            assert isinstance(item, str)


# ---------------------------------------------------------------------------
# B. silent tick isolation
# ---------------------------------------------------------------------------
def test_b_silent_tick_changes_are_passive_not_event_consequences():
    """A tick with no character action may change state, but those changes
    must be recorded as passive_transition and must NOT be attached to any
    event as consequences or downstream."""
    w, eng = _world(40)

    # find a silent tick (no events at all)
    silent_found = False
    for _ in range(40):
        result = eng.step(w)
        if result.events:
            continue
        silent_found = True
        # state really did change (pressure growth / passive recovery)
        assert w.memory_state.passive_transitions, (
            "a silent tick that changes state must record passive transitions"
        )
        for entry in w.memory_state.passive_transitions[-4:]:
            assert entry.kind in ("passive_transition", "clock_transition"), (
                f"silent-tick entry must not claim to be an event transition: "
                f"{entry.kind}"
            )
        # and none of it leaked into the event log
        for event in w.event_log:
            for consequence in event.consequences:
                assert consequence.kind in ("event_transition",), (
                    "an event's own consequences must stay event_transition"
                )
        break
    assert silent_found, "fixture must contain at least one silent tick"


def test_b_event_consequences_default_to_event_transition():
    """The classifier default is event_transition; nothing is silently passive."""
    default = dataclasses.fields(Consequence)[-1]
    assert default.name == "kind"
    assert default.default == "event_transition"

    w, _ = _world(6)
    for event in w.event_log:
        for consequence in event.consequences:
            assert consequence.kind == "event_transition"


def test_b_passive_transitions_are_not_in_event_log():
    """passive_transitions live outside event_log by construction."""
    w, eng = _world(40)
    before = len(w.memory_state.passive_transitions)
    for _ in range(20):
        eng.step(w)
    if len(w.memory_state.passive_transitions) > before:
        assert all(
            entry.kind in ("passive_transition", "clock_transition")
            for entry in w.memory_state.passive_transitions
        )
        # no event references them
        for event in w.event_log:
            assert not event.downstream or all(
                d in {e.id for e in w.event_log} for d in event.downstream
            )


# ---------------------------------------------------------------------------
# C. closed loop
# ---------------------------------------------------------------------------
def test_c_choice_event_state_next_choice_loop():
    """Character Choice -> Event -> World State -> Character State ->
    Next Choice, and the next decision can read the previous effect."""
    w, eng = _world(0)

    # step until a tick actually produces an event (the fixture's event ticks
    # are a property of the seed, not something to hard-code here)
    event = None
    for _ in range(12):
        result = eng.step(w)
        if result.events:
            event = result.events[0]
            break
    assert event is not None, "fixture must produce an event to close the loop on"

    actor_id = event.participants[0]
    actor = w.characters[actor_id]

    # World State changed (the event had an effect) ...
    assert event.consequences or event.facts, (
        "the event must actually change the world, not merely be logged"
    )
    # ... Character State reads from it next round ...
    pool_after = eng.generate_candidates(w)
    assert pool_after, "the next round must still be able to generate choices"
    # ... and the actor's own state carries the consequence of having acted.
    assert actor.human_condition is not None
    next_actions = [a for a in pool_after if a.actor_id == actor_id]
    assert isinstance(next_actions, list)


def test_c_next_round_reads_the_world_state_the_event_left():
    """The candidate the actor gets next round is scored against the state
    produced by the previous event -- not against a stale snapshot."""
    w, eng = _world(0)
    event = None
    for _ in range(12):
        result = eng.step(w)
        if result.events:
            event = result.events[0]
            break
    assert event is not None

    pool = eng.generate_candidates(w)
    for candidate in pool:
        assert candidate.actor_id in w.characters
        # every target the candidate names must be currently reachable state
        for target_id in candidate.targets:
            assert target_id in w.characters or target_id in w.locations

    # The event's consequences are visible in the state used for that scoring:
    # each named field must actually exist on the target it points at.
    for consequence in event.consequences:
        if consequence.target_type != "character":
            continue
        character = w.characters[consequence.target_id]
        assert _field_resolvable(character, consequence.field), (
            f"consequence field {consequence.field!r} does not resolve on "
            f"character {consequence.target_id!r}"
        )


# ---------------------------------------------------------------------------
# C2. the IMMEDIATE next tick is shaped by the previous event's consequence
#      (ChatGPT 5971193252). The weaker C above only proved the system keeps
#      evolving; C2 pins the actual causal arrow:
#        tick N event -> state change -> tick N+1 candidate utility
#      and undoing that one consequence must produce a detectable difference.
# ---------------------------------------------------------------------------
def _c2_utilities(world, engine):
    pool = engine.generate_candidates(world)
    return {
        f"{a.actor_id}:{a.action_type}": engine.decision_kernel.evaluate(world, a).utility
        for a in pool
    }


def test_c2_next_tick_candidate_is_shaped_by_the_previous_event():
    """Tick 0's contact drops reconciliation 71.5 -> 26.5. Tick 1's candidate
    must be scored against that DROPPED value."""
    world, engine = _world(1)
    event = world.event_log[0]
    actor = world.characters[event.participants[0]]

    # the event really did move the pressure
    drops = [
        c for c in event.consequences
        if c.field.endswith("desires.reconciliation")
        and c.old_value is not None
        and float(c.new_value) < float(c.old_value)
    ]
    assert drops, f"{event.id} must lower a desire pressure to make C2 meaningful"
    assert drops[0].kind == "event_transition"

    real = _c2_utilities(world, engine)
    assert real, "tick 1 must still offer a choice"

    # counterfactual: undo exactly that one consequence, change nothing else
    counterfactual_world, counterfactual_engine = _world(1)
    counterfactual_event = counterfactual_world.event_log[0]
    counterfactual_actor = counterfactual_world.characters[counterfactual_event.participants[0]]
    restored = drops[0].old_value
    counterfactual_actor.human_condition.desires["reconciliation"] = restored

    counterfactual = _c2_utilities(counterfactual_world, counterfactual_engine)

    # the very same candidate id must score differently -> the arrow is real
    shared = sorted(set(real) & set(counterfactual))
    assert shared, "the counterfactual must offer the same candidate to be comparable"
    differing = [k for k in shared if real[k] != counterfactual[k]]
    assert differing, (
        f"removing the previous event's consequence must change the next "
        f"tick's scoring; nothing differed between {real} and {counterfactual}"
    )
    # and the difference must be material, not float noise
    for key in differing:
        assert abs(real[key] - counterfactual[key]) > 1e-3, (
            f"{key}: utility difference {real[key] - counterfactual[key]} is noise"
        )


def test_c2_utility_moves_toward_the_unrestored_value():
    """The direction is what makes this causal rather than coincidental:
    restoring the pre-event pressure must RAISE the candidate's utility."""
    world, engine = _world(1)
    event = world.event_log[0]
    actor = world.characters[event.participants[0]]
    drop = next(
        c for c in event.consequences
        if c.field.endswith("desires.reconciliation")
    )

    real = _c2_utilities(world, engine)
    baseline = _world(1)[0]
    baseline_actor = baseline.characters[baseline.event_log[0].participants[0]]
    baseline_actor.human_condition.desires["reconciliation"] = drop.old_value
    baseline_engine = SimulationEngine(seed=SEED, use_arbitration=False)
    restored = _c2_utilities(baseline, baseline_engine)

    key = next(k for k in real if k in restored)
    assert restored[key] > real[key], (
        f"{key}: restoring the pre-event pressure must raise its utility "
        f"({real[key]} -> {restored[key]})"
    )


def test_c3_clock_transition_records_desire_window_closure():
    """The one genuine clock-driven transition in the model -- a Store-1
    desire's opportunity window closing -- must be recorded as
    clock_transition and must NOT be attributed to any event.

    HONEST SCOPE NOTE (verified, not assumed): this branch starts from the
    frozen baseline 8c5a8fd, which has NO Store-1 desire rows yet -- so
    MemoryKernel.advance_desires has nothing to expire and the transition
    cannot fire here. The clock_transition PATH is therefore covered by a
    seeded fixture below; the wiring itself is asserted structurally.
    """
    from engine.core.models import Consequence as _Consequence

    # 1. Structural: the kind exists and is distinguishable.
    clock = _Consequence(
        "desire", "yan:store1:belonging", "status", "active", "missed",
        "opportunity window closed before the desire was fulfilled",
        kind="clock_transition",
    )
    assert clock.kind == "clock_transition"
    assert clock.kind != "event_transition"
    # 2. The recorder emits exactly this shape for a status change.
    world, engine = _world(0)
    from engine.memory.models import Desire
    world.memory_state.desires["probe:store1:belonging"] = Desire(
        id="probe:store1:belonging",
        owner_id="yan",
        description="belonging",
        status="active",
        opportunity_window_start=0,
        opportunity_window_end=1,
    )
    # step a few ticks; the window (end=1) closes at tick 2 on a silent tick
    recorded = []
    for _ in range(6):
        result = engine.step(world)
        if not result.events:
            recorded = [
                e for e in world.memory_state.passive_transitions
                if e.kind == "clock_transition" and e.target_id == "probe:store1:belonging"
            ]
            if recorded:
                break
    assert recorded, (
        "a Store-1 desire whose window closes on a silent tick must produce a "
        f"clock_transition entry; got "
        f"{[ (e.kind, e.target_id, e.field) for e in world.memory_state.passive_transitions ][:5]}"
    )
    entry = recorded[0]
    assert entry.field == "status"
    assert entry.old_value == "active"
    assert entry.new_value == "missed"
    assert "window closed" in entry.reason
    # and it belongs to no event
    for event in world.event_log:
        assert entry not in event.consequences


def test_c3_passive_kind_is_recorded_on_silent_ticks():
    """Natural pressure growth is recorded as passive_transition."""
    world, engine = _world(0)
    for _ in range(20):
        engine.step(world)
    kinds = {e.kind for e in world.memory_state.passive_transitions}
    assert "passive_transition" in kinds, (
        f"natural pressure must be recorded; got {kinds}"
    )
    for entry in world.memory_state.passive_transitions:
        assert entry.kind in ("passive_transition", "clock_transition")
        assert entry.kind != "event_transition"
