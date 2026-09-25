from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from ..core.models import Event, WorldState
from ..core.simulation import SimulationEngine, SimulationResult
from ..narrative.models import NarrativeState, StoryDiscoveryCandidate
from ..narrative.observer import NarrativeObserver
from ..persistence.repository import WorldRepository


class AutonomousRunStatus(str, Enum):
    COMPLETED = "completed"
    PAUSED = "paused"
    STOPPED = "stopped"
    FAILED = "failed"
    MAX_TICKS = "max_ticks"
    VALIDATION_ERROR = "validation_error"
    STORY_DISCOVERED = "story_discovered"


@dataclass(frozen=True)
class AutonomousRunConfig:
    max_ticks: int = 20
    checkpoint_every: int = 5
    max_validation_errors: int = 1
    stop_on_story_discovery: bool = False
    story_score_threshold: float = 0.75
    checkpoint_before_run: bool = True

    def __post_init__(self) -> None:
        if self.max_ticks <= 0:
            raise ValueError("max_ticks must be positive")
        if self.checkpoint_every < 0:
            raise ValueError("checkpoint_every cannot be negative")
        if self.max_validation_errors < 0:
            raise ValueError("max_validation_errors cannot be negative")
        if not 0.0 <= self.story_score_threshold <= 1.0:
            raise ValueError("story_score_threshold must be between 0 and 1")


@dataclass
class AutonomousRunReport:
    status: AutonomousRunStatus
    start_tick: int
    end_tick: int
    ticks_run: int
    events: list[Event] = field(default_factory=list)
    narrative: NarrativeState | None = None
    story_discoveries: list[StoryDiscoveryCandidate] = field(default_factory=list)
    checkpoints: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    reason: str = ""


class AutonomousRunController:
    """Run the world forward without allowing narrative systems to author outcomes."""

    def __init__(
        self,
        simulation: SimulationEngine | None = None,
        observer: NarrativeObserver | None = None,
        repository: WorldRepository | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        self.simulation = simulation or SimulationEngine()
        self.observer = observer or NarrativeObserver()
        self.repository = repository
        self.should_stop = should_stop
        self._stop_requested = False

    def request_stop(self) -> None:
        """Request a clean stop at the next tick boundary."""
        self._stop_requested = True

    @staticmethod
    def _discovery_key(candidate: StoryDiscoveryCandidate) -> tuple[str, ...]:
        return tuple(candidate.event_ids)

    def _collect_discoveries(
        self,
        discoveries: list[StoryDiscoveryCandidate],
        collected: dict[tuple[str, ...], StoryDiscoveryCandidate],
        threshold: float,
    ) -> None:
        for candidate in discoveries:
            if candidate.score < threshold:
                continue
            key = self._discovery_key(candidate)
            if key and key not in collected:
                collected[key] = candidate

    def run(
        self,
        state: WorldState,
        config: AutonomousRunConfig | None = None,
    ) -> AutonomousRunReport:
        config = config or AutonomousRunConfig()
        self._stop_requested = False

        start_tick = state.tick
        all_events: list[Event] = []
        collected_discoveries: dict[tuple[str, ...], StoryDiscoveryCandidate] = {}
        checkpoints: list[str] = []
        validation_errors: list[str] = []
        narrative: NarrativeState | None = None

        if config.checkpoint_before_run and self.repository is not None:
            checkpoint = self.repository.save_checkpoint(
                state,
                state.active_branch,
                reason="autonomous-run-start",
            )
            checkpoints.append(checkpoint.id)

        for _ in range(config.max_ticks):
            if self._stop_requested or (self.should_stop is not None and self.should_stop()):
                return AutonomousRunReport(
                    status=AutonomousRunStatus.PAUSED,
                    start_tick=start_tick,
                    end_tick=state.tick,
                    ticks_run=state.tick - start_tick,
                    events=all_events,
                    narrative=narrative,
                    story_discoveries=list(collected_discoveries.values()),
                    checkpoints=checkpoints,
                    validation_errors=validation_errors,
                    reason="Autonomous run stopped at a tick boundary by the control signal.",
                )

            result: SimulationResult = self.simulation.step(state)
            all_events.extend(result.events)
            validation_errors.extend(result.validation_errors)

            narrative = self.observer.observe(state, result.events)
            self._collect_discoveries(
                narrative.story_discoveries,
                collected_discoveries,
                config.story_score_threshold,
            )

            if result.validation_errors and len(validation_errors) >= config.max_validation_errors:
                if self.repository is not None:
                    checkpoint = self.repository.save_checkpoint(
                        state,
                        state.active_branch,
                        reason="autonomous-run-validation-error",
                    )
                    checkpoints.append(checkpoint.id)
                return AutonomousRunReport(
                    status=AutonomousRunStatus.VALIDATION_ERROR,
                    start_tick=start_tick,
                    end_tick=state.tick,
                    ticks_run=state.tick - start_tick,
                    events=all_events,
                    narrative=narrative,
                    story_discoveries=list(collected_discoveries.values()),
                    checkpoints=checkpoints,
                    validation_errors=validation_errors,
                    reason="Simulation validation reported an error; autonomous run stopped.",
                )

            if config.stop_on_story_discovery and collected_discoveries:
                if self.repository is not None:
                    checkpoint = self.repository.save_checkpoint(
                        state,
                        state.active_branch,
                        reason="autonomous-run-story-discovery",
                    )
                    checkpoints.append(checkpoint.id)
                return AutonomousRunReport(
                    status=AutonomousRunStatus.STORY_DISCOVERED,
                    start_tick=start_tick,
                    end_tick=state.tick,
                    ticks_run=state.tick - start_tick,
                    events=all_events,
                    narrative=narrative,
                    story_discoveries=list(collected_discoveries.values()),
                    checkpoints=checkpoints,
                    validation_errors=validation_errors,
                    reason="Narrative observation found a story-bearing discovery above the configured threshold.",
                )

            ticks_run = state.tick - start_tick
            if (
                self.repository is not None
                and config.checkpoint_every > 0
                and ticks_run % config.checkpoint_every == 0
            ):
                checkpoint = self.repository.save_checkpoint(
                    state,
                    state.active_branch,
                    reason="autonomous-run-interval",
                )
                checkpoints.append(checkpoint.id)

        return AutonomousRunReport(
            status=AutonomousRunStatus.MAX_TICKS,
            start_tick=start_tick,
            end_tick=state.tick,
            ticks_run=state.tick - start_tick,
            events=all_events,
            narrative=narrative,
            story_discoveries=list(collected_discoveries.values()),
            checkpoints=checkpoints,
            validation_errors=validation_errors,
            reason="Autonomous run reached its configured tick limit.",
        )
