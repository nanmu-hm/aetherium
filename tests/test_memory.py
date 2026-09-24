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
