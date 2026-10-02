"""AE 1-tick eligibility repair — minimal regression tests.

These tests pin the four properties authorized in AD/AE and required by the
AE-matrix review (PR comment 5861546675):

  1. the predicate is a strict no-op when no qualifying event exists;
  2. a successful contact_person at the immediately-prior tick that raised
     the subject's own emotion zeroes the gate's emotional term;
  3. the predicate is NOT a permanent latch: a contact-raise at tick-5
     does not fire at tick (the 1-tick window has closed);
  4. other actors' emotion-raises and non-contact sources do not fire the
     predicate for the subject.

All tests are pure WorldState constructions (no simulation step, no RNG),
so they are deterministic and cheap.
"""

from __future__ import annotations

from engine.core.actions import (
    _contact_just_expressed_emotion,
    generate_action_pool,
)
from engine.core.human_condition import HumanCondition
from engine.core.models import (
    ActionResult,
    CharacterState,
    Consequence,
    Event,
    RelationshipState,
    WorldState,
)


def _world_with(tick: int) -> WorldState:
    yan = CharacterState(
        id="yan", name="Yan",
        location="river_town",
        emotions={"love": 25.0},
        human_condition=HumanCondition(desires={"belonging": 0.0, "reconciliation": 0.0}),
    )
    rui = CharacterState(
        id="rui", name="Rui",
        location="river_town",
        human_condition=HumanCondition(desires={}),
    )
    world = WorldState(world_id="w", tick=tick, locations={"river_town"},
                       characters={"yan": yan, "rui": rui})
    world.relationships["yan:rui"] = RelationshipState(source_id="yan", target_id="rui", trust=40.0)
    world.relationships["rui:yan"] = RelationshipState(source_id="rui", target_id="yan", trust=40.0)
    return world


def _contact_event(event_id: str, tick: int, subject: str, target: str,
                   raise_emotion: bool = True, status: str = "success",
                   action_type: str = "contact_person") -> Event:
    consequences = []
    if raise_emotion:
        consequences.append(Consequence("character", subject, "emotions.love", 20.0, 25.0, "contact success"))
    return Event(id=event_id, tick=tick, timestamp="", location="river_town",
                 participants=[subject, target], causes=[], facts=[],
                 action_type=action_type,
                 action_result=ActionResult(status=status),
                 consequences=consequences)


def test_predicate_off_is_noop():
    """No qualifying event -> predicate False, gate unchanged."""
    world = _world_with(tick=10)
    assert _contact_just_expressed_emotion(world, world.characters["yan"]) is False
    pool = generate_action_pool(world, "yan")
    # with love=25 raw, the gate opens on emotional_pressure alone (25 >= 20)
    assert any(c.action_type == "contact_person" for c in pool)


def test_predicate_blocks_immediately_prior_contact():
    """A contact-raise at tick-1 zeroes the emotional term at tick."""
    world = _world_with(tick=10)
    world.event_log.append(_contact_event("e9", tick=9, subject="yan", target="rui"))
    assert _contact_just_expressed_emotion(world, world.characters["yan"]) is True
    # belonging=0, reconciliation=0, goal none -> only the emotional term
    # could clear the 20.0 gate; it is zeroed, so contact is excluded.
    pool = generate_action_pool(world, "yan")
    assert not any(c.action_type == "contact_person" for c in pool)


def test_predicate_does_not_permanent_latch():
    """A contact-raise at tick-5 does NOT fire at tick (window closed)."""
    world = _world_with(tick=10)
    world.event_log.append(_contact_event("e5", tick=5, subject="yan", target="rui"))
    assert _contact_just_expressed_emotion(world, world.characters["yan"]) is False
    pool = generate_action_pool(world, "yan")
    # raw love=25 re-opens the gate
    assert any(c.action_type == "contact_person" for c in pool)


def test_predicate_ignores_other_actors_and_noncontact():
    """Another actor's raise / a non-contact source never fire it."""
    world = _world_with(tick=10)
    world.event_log.append(_contact_event("e9other", tick=9, subject="rui", target="yan"))
    assert _contact_just_expressed_emotion(world, world.characters["yan"]) is False

    world2 = _world_with(tick=10)
    world2.event_log.append(_contact_event("e9help", tick=9, subject="yan",
                                           target="rui", action_type="help_person"))
    assert _contact_just_expressed_emotion(world2, world2.characters["yan"]) is False

    world3 = _world_with(tick=10)
    world3.event_log.append(_contact_event("e9fail", tick=9, subject="yan",
                                           target="rui", status="failure"))
    assert _contact_just_expressed_emotion(world3, world3.characters["yan"]) is False


def test_predicate_zero_tick_guard():
    """At tick 0 there is no immediately-prior tick -> always False."""
    world = _world_with(tick=0)
    world.event_log.append(_contact_event("e0", tick=0, subject="yan", target="rui"))
    assert _contact_just_expressed_emotion(world, world.characters["yan"]) is False
