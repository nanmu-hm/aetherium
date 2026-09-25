import pytest

from engine.agents.autonomous import (
    AutonomousRunConfig,
    AutonomousRunController,
    AutonomousRunStatus,
)
from engine.core.demo import build_demo_world
from engine.core.models import CharacterState, Goal, WorldState
from engine.core.simulation import SimulationEngine
from engine.persistence.repository import WorldRepository


def test_config_rejects_invalid_limits():
    with pytest.raises(ValueError):
        AutonomousRunConfig(max_ticks=0)
    with pytest.raises(ValueError):
        AutonomousRunConfig(checkpoint_every=-1)
    with pytest.raises(ValueError):
        AutonomousRunConfig(max_validation_errors=-1)
    with pytest.raises(ValueError):
        AutonomousRunConfig(story_score_threshold=1.1)


def test_run_advances_only_by_simulation_and_stops_at_max_ticks():
    state = build_demo_world()
    start_tick = state.tick
    controller = AutonomousRunController(simulation=SimulationEngine(seed=7))
    report = controller.run(state, AutonomousRunConfig(max_ticks=4, checkpoint_every=0, checkpoint_before_run=False))
    assert report.status == AutonomousRunStatus.MAX_TICKS
    assert report.end_tick == start_tick + 4
    assert report.ticks_run == 4
    assert state.tick == start_tick + 4
    assert len(report.events) == 4 * len(state.characters)


def test_controller_keeps_narrative_downstream_of_simulation():
    state = build_demo_world()
    controller = AutonomousRunController(simulation=SimulationEngine(seed=11))
    report = controller.run(state, AutonomousRunConfig(max_ticks=2, checkpoint_every=0, checkpoint_before_run=False))
    assert report.narrative is not None
    assert len(state.event_log) == len(report.events) == 2 * len(state.characters)
    assert state.tick == 2


def test_request_stop_pauses_cleanly_at_tick_boundary():
    state = build_demo_world()
    holder = {}

    def should_stop():
        holder["controller"].request_stop()
        return False

    controller = AutonomousRunController(simulation=SimulationEngine(seed=7), should_stop=should_stop)
    holder["controller"] = controller
    report = controller.run(state, AutonomousRunConfig(max_ticks=10, checkpoint_every=0, checkpoint_before_run=False))
    assert report.status == AutonomousRunStatus.PAUSED
    assert report.ticks_run == 1
    assert state.tick == 1


def test_checkpoints_are_created_at_start_and_intervals(tmp_path):
    state = build_demo_world()
    repository = WorldRepository(tmp_path / "repo")
    controller = AutonomousRunController(simulation=SimulationEngine(seed=7), repository=repository)
    report = controller.run(state, AutonomousRunConfig(max_ticks=6, checkpoint_every=2, checkpoint_before_run=True))
    assert report.status == AutonomousRunStatus.MAX_TICKS
    assert report.checkpoints == ["main-tick-0", "main-tick-2", "main-tick-4", "main-tick-6"]
    assert repository.rollback(repository.save_checkpoint(state, state.active_branch)) is not state


def test_run_stops_on_validation_error():
    state = build_demo_world()
    next(iter(state.characters.values())).location = "missing-location"
    controller = AutonomousRunController(simulation=SimulationEngine(seed=7))
    report = controller.run(state, AutonomousRunConfig(max_ticks=10, checkpoint_every=0, checkpoint_before_run=False, max_validation_errors=1))
    assert report.status == AutonomousRunStatus.VALIDATION_ERROR
    assert report.ticks_run == 1
    assert "missing-location" in report.validation_errors[0]


def test_story_discovery_can_stop_the_run():
    state = WorldState(world_id="autonomous-story")
    state.locations.add("town")
    state.add_character(CharacterState(id="a", name="A", location="town", goals=[Goal("g1", "help B", priority=1.0)]))
    state.add_character(CharacterState(id="b", name="B", location="town"))

    class FakeSimulation:
        def step(self, state):
            from engine.core.models import ActionResult, Consequence, Event
            from engine.core.simulation import SimulationResult
            event = Event(
                id=f"event-{state.tick}", tick=state.tick, timestamp=state.timestamp,
                location="town", participants=["a", "b"], causes=[f"tick-{state.tick}"],
                facts=["A helps B."], action_result=ActionResult("success"),
                consequences=[Consequence("character", "b", "status", "active", "injured", "test") for _ in range(3)],
            )
            state.event_log.append(event)
            state.tick += 1
            return SimulationResult(state.tick - 1, [], [event], [])

    class FakeObserver:
        def observe(self, state, events):
            from engine.narrative.models import NarrativeState, StoryDiscoveryCandidate
            narrative = NarrativeState()
            narrative.story_discoveries = [StoryDiscoveryCandidate(event_ids=[events[0].id], participants=["a", "b"], score=0.9, title="test", reason="test discovery")]
            return narrative

    controller = AutonomousRunController(simulation=FakeSimulation(), observer=FakeObserver())
    report = controller.run(state, AutonomousRunConfig(max_ticks=10, checkpoint_every=0, checkpoint_before_run=False, stop_on_story_discovery=True, story_score_threshold=0.8))
    assert report.status == AutonomousRunStatus.STORY_DISCOVERED
    assert report.ticks_run == 1
    assert len(report.story_discoveries) == 1


def test_discovery_collection_deduplicates_same_event_chain():
    state = build_demo_world()

    class FakeSimulation:
        def step(self, state):
            from engine.core.models import Event
            from engine.core.simulation import SimulationResult
            event = Event(id=f"event-{state.tick}", tick=state.tick, timestamp=state.timestamp, location="town", participants=["lin"], causes=[], facts=["Lin waits."])
            state.event_log.append(event)
            state.tick += 1
            return SimulationResult(state.tick - 1, [], [event], [])

    class FakeObserver:
        def observe(self, state, events):
            from engine.narrative.models import NarrativeState, StoryDiscoveryCandidate
            narrative = NarrativeState()
            narrative.story_discoveries = [StoryDiscoveryCandidate(event_ids=["same-event"], participants=["lin"], score=0.9, title="same", reason="same")]
            return narrative

    controller = AutonomousRunController(simulation=FakeSimulation(), observer=FakeObserver())
    report = controller.run(state, AutonomousRunConfig(max_ticks=3, checkpoint_every=0, checkpoint_before_run=False, stop_on_story_discovery=False, story_score_threshold=0.8))
    assert report.status == AutonomousRunStatus.MAX_TICKS
    assert len(report.story_discoveries) == 1
