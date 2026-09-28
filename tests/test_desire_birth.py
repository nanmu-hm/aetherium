"""Focused AB tests for the AA-authorized Desire Birth minimal implementation.

Covers the mandatory acceptance items G asked for: birth / no-birth /
update / provenance / replay, plus the causal chain (A) and personality
dependence (C). Everything runs through real engine code; no threshold,
weight, or scheduler is involved in any birth.
"""

from copy import deepcopy

from engine.core.action_types import event_action_type
from engine.core.actions import generate_action_pool
from engine.core.desire_interpretation import (
    BIRTH_DOMAINS,
    interpret_desire_event,
)
from engine.core.models import ActionResult, CharacterState, Event, WorldState
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world, run_genesis
from engine.persistence.codec import world_from_dict, world_to_dict
from engine.persistence.replay import ReplayVerifier


def _contact_event(tick: int, participants: list[str]) -> Event:
    return Event(
        id=f"event-{tick}-{'-'.join(participants)}-contact_person",
        tick=tick,
        timestamp="0001-01-01T00:00:00",
        location="river_town",
        participants=participants,
        causes=[],
        facts=["A contact attempt happened."],
        action_type="contact_person",
        action_result=ActionResult("success"),
        consequences=[],
    )


def test_causal_birth_from_real_event_reaches_existing_eligibility() -> None:
    """Acceptance A: real event -> interpretation -> birth with provenance ->
    the existing gate opens because of the born key -> action executes."""
    world = build_genesis_world()
    engine = SimulationEngine(seed=7)

    first_admission_tick = None
    carrier = None
    for _ in range(60):
        engine.step(world)
        yan = world.characters["yan"]
        carrier = yan.desire_carriers.get("belonging")
        if carrier is None:
            continue
        value = yan.human_condition.desires.get("belonging", 0.0)
        if first_admission_tick is None and value >= 40.0:
            # Provenance: born from the real tick-0 contact, never fabricated.
            assert carrier.source == "event-0-yan-contact_person"
            assert carrier.created_at == 0
            assert carrier.family == "DESIRE"
            assert carrier.subject_id == "yan"
            assert carrier.evidence[0] == "event-0-yan-contact_person"
            assert carrier.tie == "relationship:yan->rui"
            assert carrier.lifecycle in {"ACTIVE", "WEAKENED", "SATISFIED"}
            # The born key alone is what admits contact: a counterfactual
            # copy without it loses the contact candidate.
            pool = generate_action_pool(world, "yan")
            assert any(a.action_type == "contact_person" for a in pool)
            counterfactual = deepcopy(world)
            del counterfactual.characters["yan"].human_condition.desires["belonging"]
            pool_without = generate_action_pool(counterfactual, "yan")
            assert not any(a.action_type == "contact_person" for a in pool_without)
            first_admission_tick = world.tick - 1

    assert first_admission_tick is not None, "born belonging never reached the gate"
    assert any(
        event.action_type == "contact_person"
        and event.participants
        and event.participants[0] == "yan"
        and event.tick > first_admission_tick
        for event in world.event_log
    ), "admitted contact never executed as a real event"
    assert carrier is not None and carrier.evidence, "updates must append evidence"


def test_no_interpretation_no_birth() -> None:
    """Acceptance B: without valid semantic evidence the world stays quiet."""

    # 1. blocked status -> prong 1 fails -> no interpretation.
    blocked = _contact_event(0, ["yan", "rui"])
    blocked.action_result = ActionResult("blocked", "target unreachable")
    world = build_genesis_world()
    assert interpret_desire_event(blocked, world) == []

    # 2. executed event but no observable tie -> prong 3 fails -> no birth.
    lonely = WorldState(world_id="lonely", locations={"town"})
    lonely.add_character(
        CharacterState(id="sol", name="Sol", location="town", values=["patience"])
    )
    engine = SimulationEngine(seed=7)
    for _ in range(30):
        engine.step(lonely)
    assert lonely.characters["sol"].desire_carriers == {}
    assert lonely.characters["sol"].human_condition.desires == {}

    # 3. rest events have no authored domain at all.
    assert interpret_desire_event(
        Event(
            id="event-0-sol-rest",
            tick=0,
            timestamp="0001-01-01T00:00:00",
            location="town",
            participants=["sol"],
            causes=[],
            facts=["Rested."],
            action_type="rest",
            action_result=ActionResult("success"),
            consequences=[],
        ),
        lonely,
    ) == []


def test_personality_and_history_decide_interpretation_not_rng() -> None:
    """Acceptance C: same event, different character state -> different
    interpretation, with no randomness anywhere in the decision."""
    world = build_genesis_world()
    event = Event(
        id="event-9-yan-help_person",
        tick=9,
        timestamp="0001-01-02T00:00:00",
        location="river_town",
        participants=["yan", "rui"],
        causes=[],
        facts=["Help happened."],
        action_type="help_person",
        action_result=ActionResult("success"),
        consequences=[],
    )

    yan_view = interpret_desire_event(event, world)
    assert [i.desire for i in yan_view] == ["responsibility"]
    assert yan_view[0].tie == "value:responsibility"

    # Same event, rui as subject: values=[freedom], traits=[proud,
    # adventurous, impulsive] -> no responsibility tie -> no interpretation.
    rui_event = _contact_event(9, ["rui", "bridge"])
    rui_event.action_type = "help_person"
    assert interpret_desire_event(rui_event, world) == []

    # Same subject, no relationship with the other participant -> no tie.
    assert interpret_desire_event(_contact_event(9, ["rui", "bridge"]), world) == []
    # With the real relationship partner it does interpret.
    assert [
        i.desire for i in interpret_desire_event(_contact_event(9, ["rui", "yan"]), world)
    ] == ["reconciliation", "belonging"]

    # Repeatable: identical inputs, identical outputs (pure function).
    assert interpret_desire_event(event, world) == yan_view


def test_repeated_domain_events_update_one_carrier() -> None:
    """Acceptance D: repeated same-domain evidence updates a single carrier
    instead of creating duplicates; evidence only appends."""
    world = run_genesis(ticks=60, seed=7)
    yan = world.characters["yan"]
    assert "belonging" in yan.desire_carriers
    carrier_ids = [c.carrier_id for c in yan.desire_carriers.values()]
    assert len(carrier_ids) == len(set(carrier_ids))
    assert len(yan.desire_carriers) == len(set(yan.desire_carriers))
    belong = yan.desire_carriers["belonging"]
    assert len(belong.evidence) > 1, "domain updates must append evidence"
    assert len(belong.evidence) == len(set(belong.evidence)), (
        "one event must not be double counted for one carrier"
    )
    # Genesis desire first touched by the writer carries the sentinel.
    recon = yan.desire_carriers["reconciliation"]
    assert recon.source == "GENESIS" and recon.created_at == "GENESIS"
    assert recon.evidence and recon.evidence[0] != "GENESIS"


def test_satisfaction_leaves_causal_evidence() -> None:
    """Acceptance E: a satisfied desire mutates with a real event Consequence
    and carrier evidence - the W-style silent mutation is gone."""
    world = run_genesis(ticks=60, seed=7)
    drops = [
        (event, consequence)
        for event in world.event_log
        for consequence in event.consequences
        if consequence.field.startswith("human_condition.desires.")
        and "satisfies" in consequence.reason
    ]
    assert drops, "no satisfaction consequence was recorded"
    event, consequence = drops[0]
    assert consequence.old_value > consequence.new_value
    assert event.id  # the evidence IS the event carrying the consequence
    yan = world.characters["yan"]
    recon = yan.desire_carriers.get("reconciliation")
    if recon is not None:
        # The first contact both satisfied and updated the carrier.
        assert any(
            e.id in recon.evidence
            for e in world.event_log
            if e.action_type == "contact_person"
        )
    # Births are recorded on carriers, not as fabricated events.
    belong = yan.desire_carriers.get("belonging")
    assert belong is not None
    assert belong.source != "GENESIS"


def test_replay_is_bit_identical_including_carriers() -> None:
    """Acceptance F: two identical runs agree event-for-event and
    carrier-for-carrier."""
    first = run_genesis(ticks=40, seed=7)
    second = run_genesis(ticks=40, seed=7)
    verifier = ReplayVerifier()
    fresh = build_genesis_world()
    assert verifier.verify(fresh, first.event_log, seed=7, steps=40)
    assert [verifier.event_signature(e) for e in first.event_log] == [
        verifier.event_signature(e) for e in second.event_log
    ]
    assert [(e.id, e.tick) for e in first.event_log] == [
        (e.id, e.tick) for e in second.event_log
    ]
    for character_id, character in first.characters.items():
        other = second.characters[character_id]
        assert character.human_condition.desires == other.human_condition.desires
        assert character.desire_carriers == other.desire_carriers


def test_carrier_records_survive_checkpoint_roundtrip() -> None:
    world = run_genesis(ticks=20, seed=7)
    restored = world_from_dict(world_to_dict(world))
    for character_id, character in world.characters.items():
        assert (
            restored.characters[character_id].desire_carriers
            == character.desire_carriers
        )


def test_curiosity_never_births_without_authored_amount() -> None:
    """Declared gap G4 stays honest: curiosity has a pressure domain but no
    authored birth amount, so it is outside the birth vocabulary."""
    assert "curiosity" not in BIRTH_DOMAINS["travel"]
    assert BIRTH_DOMAINS["travel"] == ("freedom",)
    assert set(BIRTH_DOMAINS) == {
        "travel",
        "contact_person",
        "search_person",
        "help_person",
    }


def test_interpreter_failure_prong_is_rule_level_only() -> None:
    """Prong 1 accepts status in {success, failure} at the interpreter level.
    The production failure writer remains unreachable - this test never
    makes it reachable, it only pins the interpretation rule."""
    world = build_genesis_world()
    event = _contact_event(3, ["yan", "rui"])
    event.action_result = ActionResult("failure", "rejected")
    assert [i.desire for i in interpret_desire_event(event, world)] == [
        "reconciliation",
        "belonging",
    ]


def test_event_action_type_reader_is_used_consistently() -> None:
    world = run_genesis(ticks=6, seed=7)
    for event in world.event_log:
        # Every executed action is either in the birth vocabulary or has no
        # authored desire domain at all (rest).
        assert event_action_type(event) in set(BIRTH_DOMAINS) | {"rest"}
