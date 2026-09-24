from engine.core.models import Event
from engine.memory.kernel import MemoryKernel
from engine.memory.models import Belief, Desire, MemoryState


def test_memory_is_structured_and_can_decay_without_being_deleted() -> None:
    state = MemoryState()
    event = Event("e1", 0, "0001-01-01T00:00:00", "town", ["lin"], ["a1"], ["Lin sees a broken bridge."])
    kernel = MemoryKernel()
    memory = kernel.remember_event(state, "lin", event, "saw a broken bridge", emotional_salience=0.8)
    kernel.decay(state, 20)
    assert memory.id in state.memories
    assert 0.05 <= memory.recall_strength < 1.0


def test_character_belief_can_disagree_with_world_truth() -> None:
    state = MemoryState()
    state.add_belief(Belief("b1", "lin", "mei betrayed me", truth_status="false", confidence=0.9))
    assert state.beliefs["b1"].truth_status == "false"


def test_unresolved_desire_can_be_missed_when_window_closes() -> None:
    state = MemoryState()
    state.add_desire(Desire("d1", "lin", "meet Mei before departure", opportunity_window_end=3))
    MemoryKernel().advance_desires(state, 4)
    assert state.desires["d1"].status == "missed"


def test_recall_prefers_cued_memory() -> None:
    state = MemoryState()
    kernel = MemoryKernel()
    e1 = Event("e1", 0, "t", "town", ["lin"], [], ["Lin sees a bridge."])
    e2 = Event("e2", 1, "t", "town", ["lin"], [], ["Lin meets Mei."])
    kernel.remember_event(state, "lin", e1, "bridge collapsed", tags={"bridge"})
    kernel.remember_event(state, "lin", e2, "met Mei", tags={"mei"})
    assert kernel.recall(state, "lin", "mei", 1)[0].summary == "met Mei"


def test_lived_event_creates_owner_scoped_belief():
    state = MemoryState()
    event = Event(
        "e1",
        0,
        "0001-01-01T00:00:00",
        "town",
        ["lin", "mei"],
        ["tick-0-lin-contact"],
        ["Lin speaks with Mei."],
        action_result=__import__("engine.core.models", fromlist=["ActionResult"]).ActionResult("failure"),
    )
    kernel = MemoryKernel()
    memory = kernel.remember_event(state, "lin", event, "failed conversation")
    belief = kernel.record_event_belief(state, "lin", event, memory.id)
    assert belief.owner_id == "lin"
    assert belief.source_memory_ids == [memory.id]
    assert "failure" in belief.proposition


def test_event_belief_uses_canonical_action_type():
    state = MemoryState()
    event = Event(
        "e-contact",
        0,
        "0001-01-01T00:00:00",
        "town",
        ["lin", "mei"],
        ["tick-0-lin-contact"],
        ["Lin speaks with Mei."],
        action_result=__import__("engine.core.models", fromlist=["ActionResult"]).ActionResult("failure"),
    )
    kernel = MemoryKernel()
    memory = kernel.remember_event(state, "lin", event, "failed conversation")
    belief = kernel.record_event_belief(state, "lin", event, memory.id)
    assert belief.proposition.startswith("experience:contact_person:mei:failure")


def test_relationship_history_preserves_causal_changes():
    from engine.core.models import ActionCandidate, RelationshipState
    from engine.core.simulation import SimulationEngine

    from tests.test_simulation import build_demo_world

    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    world.add_relationship(RelationshipState("lin", "mei", trust=40.0))
    action = ActionCandidate(
        "contact", "lin", "contact_person", targets=["mei"], confidence=1.0, difficulty=0.1
    )
    event = SimulationEngine(seed=1).resolve(world, [action])[0]

    history = world.memory_state.relationship_history["lin:mei"]
    assert history
    assert history[0].event_id == event.id
    assert history[0].changes["trust"] == (40.0, 42.0)
    assert history[0].outcome == "success"


def test_memory_revision_preserves_old_interpretation():
    state = MemoryState()
    event = Event("e1", 0, "0001-01-01T00:00:00", "town", ["lin"], ["tick-0-lin-travel"], ["Lin failed to travel."])
    kernel = MemoryKernel()
    memory = kernel.remember_event(state, "lin", event, "I could not leave.", confidence=0.8)
    memory.interpretation = "I was blocked by circumstances."

    revision = kernel.revise_memory(
        state,
        memory.id,
        "I hesitated and chose not to leave.",
        tick=4,
        reason="Later evidence changed how Lin understood the event.",
        confidence=0.6,
    )

    assert revision.previous_interpretation == "I was blocked by circumstances."
    assert revision.new_interpretation == "I hesitated and chose not to leave."
    assert state.memories[memory.id].interpretation == revision.new_interpretation
    assert state.memories[memory.id].confidence == 0.6
    assert state.memory_revisions[memory.id] == [revision]


def test_memory_revision_can_reference_later_evidence():
    state = MemoryState()
    kernel = MemoryKernel()
    e1 = Event("e1", 0, "t", "town", ["lin"], ["tick-0-lin-contact"], ["Lin speaks with Mei."])
    e2 = Event("e2", 2, "t", "town", ["lin"], ["tick-2-lin-contact"], ["Lin learns why Mei left."])
    m1 = kernel.remember_event(state, "lin", e1, "Mei refused to meet me.")
    m2 = kernel.remember_event(state, "lin", e2, "I learn the reason.")
    revision = kernel.revise_memory(
        state,
        m1.id,
        "Mei was protecting me rather than rejecting me.",
        tick=2,
        reason="Later explanation from Mei.",
        evidence_memory_ids=[m2.id],
    )

    assert revision.evidence_memory_ids == [m2.id]
    assert revision.id.startswith("revision-")


def test_local_knowledge_is_owner_scoped_and_tracks_source():
    state = MemoryState()
    kernel = MemoryKernel()
    event = Event(
        "e1",
        3,
        "0001-01-04T00:00:00",
        "town",
        ["lin", "mei"],
        ["tick-3-lin-contact"],
        ["Mei left town before dawn."],
    )

    lin_fact = kernel.record_event_knowledge(state, "lin", event)[0]

    assert lin_fact.proposition == "Mei left town before dawn."
    assert lin_fact.source == "direct_experience"
    assert lin_fact.source_event_id == "e1"
    assert state.get_knowledge("lin", lin_fact.proposition) == lin_fact
    assert state.get_knowledge("rui", lin_fact.proposition) is None


def test_non_participant_does_not_learn_an_event_automatically():
    state = MemoryState()
    kernel = MemoryKernel()
    event = Event(
        "secret",
        1,
        "t",
        "old_road",
        ["lin"],
        ["tick-1-lin-travel"],
        ["Lin found the hidden cache."],
    )

    assert kernel.record_event_knowledge(state, "mei", event) == []
    assert state.knowledge.get("mei", {}) == {}


def test_knowledge_confidence_is_updated_without_creating_duplicate_facts():
    state = MemoryState()
    kernel = MemoryKernel()

    first = kernel.learn_fact(
        state, "lin", "Mei left town.", tick=2, source="heard", confidence=0.4
    )
    second = kernel.learn_fact(
        state, "lin", "Mei left town.", tick=5, source="confirmed", confidence=0.9
    )

    assert first.id == second.id
    assert second.confidence == 0.9
    assert second.first_learned_tick == 2
    assert second.last_confirmed_tick == 5
    assert len(state.knowledge["lin"]) == 1


def test_knowledge_transmission_preserves_provenance_and_lowers_confidence():
    state = MemoryState()
    kernel = MemoryKernel()
    kernel.learn_fact(
        state,
        "lin",
        "Mei left town.",
        tick=1,
        source="direct_experience",
        source_event_id="departure",
        confidence=1.0,
    )

    heard_by_mei = kernel.transmit_knowledge(
        state, "lin", "mei", "Mei left town.", tick=2
    )
    heard_by_rui = kernel.transmit_knowledge(
        state, "mei", "rui", "Mei left town.", tick=3
    )

    assert heard_by_mei.source == "heard"
    assert heard_by_mei.source_owner_id == "lin"
    assert heard_by_mei.parent_fact_id == state.get_knowledge("lin", "Mei left town.").id
    assert heard_by_mei.transmission_depth == 1
    assert heard_by_mei.confidence == 0.8

    assert heard_by_rui.source == "heard"
    assert heard_by_rui.source_owner_id == "mei"
    assert heard_by_rui.parent_fact_id == heard_by_mei.id
    assert heard_by_rui.transmission_depth == 2
    assert heard_by_rui.confidence == 0.64


def test_knowledge_transmission_does_not_create_world_truth_or_source_knowledge():
    state = MemoryState()
    kernel = MemoryKernel()
    kernel.learn_fact(
        state, "lin", "A secret door exists.", tick=1, source="direct_experience", confidence=1.0
    )

    kernel.transmit_knowledge(state, "lin", "mei", "A secret door exists.", tick=2)

    assert state.get_knowledge("mei", "A secret door exists.") is not None
    assert state.get_knowledge("rui", "A secret door exists.") is None
    assert not hasattr(state, "world_facts")


def test_transmission_requires_the_source_to_know_the_proposition():
    state = MemoryState()
    kernel = MemoryKernel()

    import pytest

    with pytest.raises(KeyError):
        kernel.transmit_knowledge(
            state, "lin", "mei", "A secret door exists.", tick=1
        )


def test_direct_confirmation_can_raise_confidence_and_refresh_provenance():
    state = MemoryState()
    kernel = MemoryKernel()
    heard = kernel.learn_fact(
        state, "mei", "The bridge is broken.", tick=2, source="heard",
        source_owner_id="lin", parent_fact_id="knowledge-lin-1",
        transmission_depth=1, confidence=0.6,
    )

    confirmed = kernel.learn_fact(
        state, "mei", "The bridge is broken.", tick=5,
        source="confirmed", source_event_id="bridge-event", confidence=1.0,
    )

    assert confirmed.id == heard.id
    assert confirmed.confidence == 1.0
    assert confirmed.source == "confirmed"
    assert confirmed.source_event_id == "bridge-event"
    assert confirmed.transmission_depth == 0
