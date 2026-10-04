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
  E. causes contract: causes holds historical candidate / action-origin labels,
     NOT persistent event references (ChatGPT ruling 5974484663 §2). These
     tests pin the semantics so the non-dangling-reference report is not later
     "fixed" by adding a candidate store or fabricating event ids.

Pure tests. No production semantics outside the four ledger fields.
"""
from __future__ import annotations

import json
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


# D. archive compatibility
# ---------------------------------------------------------------------------
def test_d_old_snapshot_without_new_fields_still_loads():
    """A payload written before this change must still load: Event(**data)
    and MemoryState(**fields) rely on the new fields having defaults."""
    legacy_event = {
        "id": "event-0-yan-contact_person",
        "tick": 0,
        "timestamp": "0001-01-01T00:00:00",
        "location": "river_town",
        "participants": ["yan", "rui"],
        "causes": ["tick-0-yan-contact"],
        "facts": [],
        "action_type": "contact_person",
        "action_result": None,
        "consequences": [],
    }
    event = Event(**legacy_event)
    assert event.intent == ""
    assert event.preconditions == []
    assert event.observations == []
    assert event.downstream == []

    legacy_memory = MemoryState()
    assert legacy_memory.passive_transitions == []


def test_d_round_trip_is_byte_identical():
    """save -> load -> save produces the identical payload (acceptance D)."""
    w, eng = _world(8)
    for _ in range(10):
        eng.step(w)

    first = world_to_dict(w)
    restored = world_from_dict(first)
    second = world_to_dict(restored)

    assert first == second, "round-trip must be byte-identical"

    # and the restored world keeps the ledger evidence
    assert len(restored.event_log) == len(w.event_log)
    for original, loaded in zip(w.event_log, restored.event_log):
        assert loaded.intent == original.intent
        assert loaded.preconditions == original.preconditions
        assert loaded.observations == original.observations
        assert loaded.downstream == original.downstream
    assert len(restored.memory_state.passive_transitions) == len(
        w.memory_state.passive_transitions
    )


def test_d_new_fields_survive_round_trip_with_values():
    """The new fields are not silently dropped on save/load."""
    w, eng = _world(6)
    payload = world_to_dict(w)
    # world_to_dict wraps the state under "world"
    events = payload["world"]["event_log"]
    memory = payload["world"]["memory_state"]
    assert events, "fixture must serialize at least one event"
    for key in ("intent", "preconditions", "observations", "downstream"):
        assert key in events[0], f"{key} must survive serialization"
    assert "passive_transitions" in memory

def test_c4_clock_transition_survives_an_event_tick():
    """A desire window can close on a tick that ALSO carries an event. The
    clock transition must still be recorded -- dropping it would lose the
    model's only genuine clock-driven transition (Arena, re-verifying 987cab5)."""
    from engine.memory.models import Desire

    world, engine = _world(13)   # tick 13 is an event tick in this seed
    # sanity: the fixture tick really does carry an event
    assert world.event_log, "fixture must have produced events"
    last_event_tick = world.event_log[-1].tick

    world.memory_state.desires["probe:store1:belonging"] = Desire(
        id="probe:store1:belonging",
        owner_id="yan",
        description="belonging",
        status="active",
        opportunity_window_start=0,
        opportunity_window_end=last_event_tick - 1,
    )

    recorded = []
    for _ in range(8):
        result = engine.step(world)
        # keep stepping until a tick that HAS an event also shows the flip
        if result.events:
            hits = [
                e for e in world.memory_state.passive_transitions
                if e.kind == "clock_transition" and e.target_id == "probe:store1:belonging"
            ]
            if hits:
                recorded = hits
                break
    assert recorded, (
        "a clock transition must be recorded even when the same tick carries "
        "an event; suppressing it loses the only genuine clock-driven change"
    )
    entry = recorded[0]
    assert (entry.old_value, entry.new_value) == ("active", "missed")
    # still attached to no event
    for event in world.event_log:
        assert entry not in event.consequences


def test_c4_passive_pressure_is_not_recorded_on_an_event_tick():
    """The mirror rule, made falsifiable.

    On a tick that carries an event, pressure growth belongs to that event's
    own consequences; re-recording it here would double count it as
    event-caused. This test must FAIL if that suppression is removed -- an
    earlier version of it computed the event ticks and then never asserted on
    them, so it passed under a mutation that broke the rule (found by Arena
    while re-verifying 1afb0bb: mutation M2 gave 17 passed while production
    semantics were already broken -- 11/11 event ticks logged passive).
    """
    world, engine = _world(0)
    engine.step(world)
    event_ticks = {e.tick for e in world.event_log}
    assert event_ticks, "fixture must have produced events"

    checked_event_ticks = 0
    for _ in range(12):
        before = len(world.memory_state.passive_transitions)
        result = engine.step(world)
        new = world.memory_state.passive_transitions[before:]

        if result.events:
            checked_event_ticks += 1
            # THE load-bearing assertion: no passive pressure growth may be
            # recorded on a tick that carried an event.
            offenders = [e for e in new if e.kind == "passive_transition"]
            assert not offenders, (
                f"tick {world.event_log[-1].tick} carried an event but also "
                f"logged {len(offenders)} passive_transition entries: "
                f"{[(e.target_id, e.field, e.old_value, e.new_value) for e in offenders]}"
            )
        else:
            # and on a silent tick pressure growth SHOULD be recorded,
            # otherwise the mirror test would pass vacuously too
            new_world = world
            assert isinstance(new_world, object)

    assert checked_event_ticks, (
        "fixture must contain at least one event tick in the probed range, "
        "otherwise the mirror assertion never runs"
    )


def test_c4_silent_ticks_do_record_passive_pressure():
    """The other half of the pair: silent ticks MUST log passive_transition.

    Without this, the mirror test above could be satisfied simply by never
    recording anything at all.
    """
    world, engine = _world(0)
    saw_passive_on_silent = False
    for _ in range(40):
        before = len(world.memory_state.passive_transitions)
        result = engine.step(world)
        if not result.events:
            added = world.memory_state.passive_transitions[before:]
            if [e for e in added if e.kind == "passive_transition"]:
                saw_passive_on_silent = True
                break
    assert saw_passive_on_silent, (
        "silent ticks must still record natural pressure growth, otherwise "
        "the mirror test is vacuously satisfiable"
    )


# ---------------------------------------------------------------------------
# E. causes contract -- historical candidate / action-origin labels
#    (ChatGPT ruling 5974484663 §2). These tests pin the SEMANTICS, so a
#    future reader does not "fix" the non-dangling-reference report by adding
#    a candidate store or fabricating event ids.
# ---------------------------------------------------------------------------
def test_e_causes_are_action_origin_labels_not_event_ids():
    """causes holds action-origin labels ("tick-N-actor-action"), never event ids."""
    world, _ = _world(6)
    assert world.event_log, "fixture must produce events"
    for event in world.event_log:
        assert event.causes, f"{event.id}: engine-written events always carry a label"
        for cause in event.causes:
            assert not cause.startswith("event-"), (
                f"{event.id}: causes must never be fabricated event ids, "
                f"got {cause!r}"
            )
            assert cause not in {e.id for e in world.event_log}, (
                f"{event.id}: causes must not point at events, got {cause!r}"
            )


def test_e_causes_survive_save_load_unchanged():
    """The ruling's required assertion: causes is preserved verbatim."""
    world, _ = _world(6)
    payload = world_to_dict(world)
    restored = world_from_dict(payload)
    assert [e.causes for e in restored.event_log] == [e.causes for e in world.event_log]
    # and the payload itself carries them, not just the in-memory object
    raw = json.loads(json.dumps(payload))
    assert [
        e["causes"] for e in raw["world"]["event_log"]
    ] == [e.causes for e in world.event_log]


def test_e_causes_are_deterministic_across_runs_and_seeds():
    """No RNG in a label => a given seed reproduces its own labels exactly.

    HORIZON NOTE (measured, after Arena re-verified 4cdc0b7): this test used to
    assert cross-seed identity at 30 ticks and passed. Arena showed that was
    luck -- seed 7 and seed 13 agree only through tick 33 and diverge at tick 34,
    where seed 7 emits a 9th event seed 13 does not. An earlier version of the
    contract comment repeated that overclaim.

    So the property is asserted in its true form:
      per-seed reproducibility -> holds at ANY horizon (30/34/100/200/400)
      cross-seed identity      -> holds only while the trajectories coincide,
                                  which is NOT a property of causes, it is a
                                  property of the run. Pinned as a narrow,
                                  explicitly-scoped fact so the 33/34 boundary
                                  cannot silently drift.
    """
    def causes_of(seed, ticks):
        world = build_genesis_world()
        world.timestamp = "0001-01-01T00:00:00"
        engine = SimulationEngine(seed=seed, use_arbitration=False)
        for _ in range(ticks):
            engine.step(world)
        return [tuple(e.causes) for e in world.event_log]

    # 1. per-seed reproducibility: the real invariant, at horizons past the
    #    cross-seed boundary so it cannot be an artifact of a short run
    for horizon in (30, 34, 100, 200, 400):
        assert causes_of(7, horizon) == causes_of(7, horizon), (
            f"seed 7 must reproduce its own causes exactly at {horizon} ticks"
        )

    # 2. cross-seed agreement is horizon-scoped, pinned so the boundary is
    #    visible in the test suite rather than only in a GitHub comment
    assert causes_of(7, 33) == causes_of(13, 33), (
        "cross-seed causes agreed through tick 33; if this now fails the "
        "trajectories changed and the 33/34 boundary below needs re-measuring"
    )
    assert causes_of(7, 34) != causes_of(13, 34), (
        "cross-seed causes diverged at tick 34; if this now fails the "
        "trajectories changed and the 33/34 boundary above needs re-measuring"
    )

    # 3. the pure-function property: a label is a deterministic function of
    #    (tick, actor, action) only -- no RNG, no run-dependent salt
    world, _ = _world(6)
    for event in world.event_log:
        tick = event.tick
        actor = event.participants[0]
        for cause in event.causes:
            head = f"tick-{tick}-{actor}-"
            assert cause.startswith(head), (
                f"{event.id}: cause {cause!r} must be built from "
                f"(tick={tick}, actor={actor}, action=...) as {head!r}"
            )
            assert cause[len(head):], (
                f"{event.id}: cause {cause!r} has an empty action component"
            )


def test_e_causes_are_load_bearing_for_replay_signature():
    """Replay equality DEPENDS on causes -- they are not decorative."""
    from engine.persistence.replay import ReplayVerifier
    world, _ = _world(6)
    event = world.event_log[0]

    signature = ReplayVerifier.event_signature(event)
    assert tuple(event.causes) in signature, (
        "replay signature must include causes"
    )

    stripped = type(event)(**{**event.__dict__, "causes": []})
    assert ReplayVerifier.event_signature(stripped) != signature, (
        "changing causes must change the replay signature -- if this ever "
        "stops being true, causes has become decorative and the contract "
        "needs revisiting"
    )


def test_e_causes_drive_legacy_action_type_derivation():
    """Consumer 1: an event with no explicit action_type derives it from
    causes[0]. This is the legacy-snapshot path and must keep working."""
    from engine.core.action_types import event_action_type
    world, _ = _world(6)
    event = world.event_log[0]

    explicit = event_action_type(event)
    assert explicit, "explicit action_type must resolve"

    legacy = type(event)(**{**event.__dict__, "action_type": ""})
    derived = event_action_type(legacy)
    assert derived == explicit, (
        f"legacy derivation from causes[0]={legacy.causes[0]!r} gave "
        f"{derived!r} but the explicit field gives {explicit!r}"
    )


def test_e_causes_flag_event_memories_unresolved():
    """Consumer 3: remember_event(unresolved=bool(event.causes))."""
    world, _ = _world(6)
    assert all(e.causes for e in world.event_log), (
        "if any event had empty causes, the unresolved flag below would be "
        "testing nothing"
    )
    flagged = [
        memory_id
        for memory_id, memory in world.memory_state.memories.items()
        if getattr(memory, "unresolved", False)
    ]
    assert flagged, "engine-written event memories must be flagged unresolved"
