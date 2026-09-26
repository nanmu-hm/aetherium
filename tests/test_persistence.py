from engine.core.models import CharacterState, Event, Goal, WorldState
from engine.core.simulation import SimulationEngine
from engine.persistence.codec import load_world_json, save_world_json, world_from_dict, world_to_dict
from engine.persistence.events import JsonEventStore
from engine.persistence.ledger import CanonLedger
from engine.persistence.models import CanonEntry
from engine.persistence.replay import ReplayVerifier
from engine.persistence.repository import WorldRepository


def make_state():
    state = WorldState(world_id="persist", tick=2, timestamp="0001-01-03T00:00:00")
    state.locations.add("town")
    state.add_character(CharacterState(id="a", name="A", location="town", knowledge={"A knows"}, goals=[Goal("g1", "leave town", priority=1.0)]))
    return state


def test_world_json_roundtrip_preserves_core_state():
    state = make_state()
    restored = world_from_dict(world_to_dict(state))
    assert restored.world_id == state.world_id
    assert restored.tick == state.tick
    assert restored.timestamp == state.timestamp
    assert restored.locations == state.locations
    assert restored.characters["a"].knowledge == {"A knows"}


def test_world_json_file_roundtrip(tmp_path):
    state = make_state()
    path = tmp_path / "world.json"
    save_world_json(state, path)
    restored = load_world_json(path)
    assert restored.characters["a"].location == "town"


def test_json_event_store_is_append_only(tmp_path):
    state = make_state()
    event = Event("e1", 2, state.timestamp, "town", ["a"], [], ["A waits."])
    store = JsonEventStore(tmp_path / "events.jsonl")
    store.append(event)
    store.append(event)
    assert store.count() == 2
    assert [item.id for item in store.read_all()] == ["e1", "e1"]


def test_canon_ledger_filters_by_source_and_branch(tmp_path):
    ledger = CanonLedger(tmp_path / "canon.jsonl")
    ledger.append(CanonEntry("c1", "A exists", "SIMULATION_EVENT", "e1", "main", 1))
    ledger.append(CanonEntry("c2", "A leaves", "USER_DECISION", "u1", "branch-b", 2))
    assert len(ledger.by_source("e1")) == 1
    assert ledger.list(branch_id="branch-b")[0].statement == "A leaves"


def test_checkpoint_and_rollback_roundtrip(tmp_path):
    repo = WorldRepository(tmp_path)
    state = make_state()
    checkpoint = repo.save_checkpoint(state, "main", "before intervention")
    state.characters["a"].location = "elsewhere"
    restored = repo.rollback(checkpoint)
    assert restored.characters["a"].location == "town"
    assert restored.active_branch == "main"


def test_branch_fork_preserves_parent_and_child_identity(tmp_path):
    repo = WorldRepository(tmp_path)
    state = make_state()
    child = repo.fork(state, "branch-b", "user intervention")
    assert child.active_branch == "branch-b"
    assert repo.load_branch("branch-b").parent_branch_id == "main"
    assert child.world_id == state.world_id


def test_snapshot_hash_is_stable_for_same_state(tmp_path):
    repo = WorldRepository(tmp_path)
    state = make_state()
    assert repo.snapshot_hash(state) == repo.snapshot_hash(world_from_dict(world_to_dict(state)))


def test_deterministic_replay_matches_recorded_events():
    initial = make_state()
    state = world_from_dict(world_to_dict(initial))
    engine = SimulationEngine(seed=7)
    expected = []
    for _ in range(2):
        expected.extend(engine.step(state).events)
    verifier = ReplayVerifier()
    assert verifier.verify(initial, expected, seed=7, steps=2)


def test_replay_detects_tampered_history():
    initial = make_state()
    state = world_from_dict(world_to_dict(initial))
    engine = SimulationEngine(seed=7)
    expected = engine.step(state).events
    expected[0].facts.append("tampered history")
    verifier = ReplayVerifier()
    assert verifier.verify(initial, expected, seed=7, steps=1) is False


def test_checkpoint_replay_preserves_future_rng_sequence():
    initial = make_state()
    continuous = world_from_dict(world_to_dict(initial))
    continuous_engine = SimulationEngine(seed=19)
    for _ in range(12):
        continuous_engine.step(continuous)

    split = world_from_dict(world_to_dict(initial))
    first_engine = SimulationEngine(seed=19)
    for _ in range(6):
        first_engine.step(split)
    checkpoint_payload = world_to_dict(split)
    restored = world_from_dict(checkpoint_payload)
    second_engine = SimulationEngine(seed=999)
    for _ in range(6):
        second_engine.step(restored)

    assert [ReplayVerifier.event_signature(event) for event in restored.event_log] == [
        ReplayVerifier.event_signature(event) for event in continuous.event_log
    ]
    assert world_to_dict(restored) == world_to_dict(continuous)


def test_checkpoint_restores_decision_noise_seed_even_with_different_engine_seed():
    from engine.core.models import ActionCandidate
    from engine.core.decision import DecisionKernel

    state = make_state()
    state.simulation_seed = 19
    state.tick = 6
    state.characters["mei"].decision_noise = 1.0
    pool = [
        ActionCandidate("choice-a", "mei", "travel", targets=["town"], confidence=0.8, difficulty=0.4, score=0.5),
        ActionCandidate("choice-b", "mei", "pursue_goal", motivation="find a missing friend", confidence=0.8, difficulty=0.4, score=0.5),
    ]

    restored = world_from_dict(world_to_dict(state))
    first, first_evals = DecisionKernel(seed=19).choose(state, pool)
    second, second_evals = DecisionKernel(seed=999).choose(restored, pool)

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert [item.selection_score for item in first_evals] == [
        item.selection_score for item in second_evals
    ]
