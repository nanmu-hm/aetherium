"""Measure narrative breathing and pressure trends from observed history."""

from __future__ import annotations

from ..core.models import Event, WorldState
from .models import RhythmState
from .pressure import NarrativePressureAnalyzer


class NarrativeRhythmAnalyzer:
    """Classify recent narrative pressure without optimizing for maximum intensity."""

    def __init__(self, pressure: NarrativePressureAnalyzer | None = None) -> None:
        self.pressure = pressure or NarrativePressureAnalyzer()

    @staticmethod
    def _trend(current: float, previous: float) -> str:
        if current > previous + 0.08:
            return "rising"
        if current < previous - 0.08:
            return "falling"
        return "flat"

    def analyze(self, state: WorldState, events: list[Event]) -> RhythmState:
        known = {event.id: event for event in state.event_log}
        for event in events:
            known[event.id] = event

        ordered = sorted(known.values(), key=lambda event: (event.tick, event.id))
        if not ordered:
            return RhythmState()

        pressures = [self.pressure.score_event(state, event) for event in ordered]
        current = pressures[-1]
        previous = pressures[-2] if len(pressures) > 1 else 0.0
        trend = self._trend(current, previous)
        recent = pressures[-5:]

        high_streak = 0
        for value in reversed(pressures):
            if value < 0.55:
                break
            high_streak += 1

        if current >= 0.70 and current >= previous:
            phase = "peak"
        elif previous >= 0.60 and current < previous - 0.12:
            phase = "release"
        elif current >= 0.30 and trend == "rising":
            phase = "build"
        elif current < 0.25 and high_streak == 0:
            phase = "calm"
        elif high_streak > 0 and current < 0.45:
            phase = "recovery"
        else:
            phase = "steady"

        avg_recent = sum(recent) / len(recent)
        breathing_needed = high_streak >= 3 or (len(recent) >= 3 and avg_recent >= 0.68)

        return RhythmState(
            phase=phase,
            pressure=current,
            previous_pressure=previous,
            trend=trend,
            breathing_needed=breathing_needed,
            high_pressure_streak=high_streak,
        )
