"""Build causally connected narrative threads from observed world history."""

from __future__ import annotations

from ..core.models import Event, WorldState
from .models import NarrativeThread
from .pressure import NarrativePressureAnalyzer


class CausalThreadEngine:
    """Trace connected consequences without inventing hidden causes."""

    def __init__(self, pressure: NarrativePressureAnalyzer | None = None, max_tick_gap: int = 6) -> None:
        self.pressure = pressure or NarrativePressureAnalyzer()
        self.max_tick_gap = max(0, max_tick_gap)

    @staticmethod
    def _keys(event: Event) -> set[str]:
        keys = {f"participant:{item}" for item in event.participants}
        for consequence in event.consequences:
            keys.add(f"{consequence.target_type}:{consequence.target_id}:{consequence.field}")
            keys.add(f"{consequence.target_type}:{consequence.target_id}")
        return keys

    @staticmethod
    def _thread_type(events: list[Event]) -> str:
        fields = {consequence.field for event in events for consequence in event.consequences}
        if any(field.startswith("identity_beliefs.") for field in fields):
            return "character_change"
        if any(field.startswith("emotions.") for field in fields):
            return "emotional"
        if any(event.action_result is not None and event.action_result.status in {"failure", "blocked"} for event in events):
            return "obstacle"
        if any(consequence.target_type == "relationship" for event in events for consequence in event.consequences):
            return "relationship"
        if any(consequence.target_type == "goal" for event in events for consequence in event.consequences):
            return "goal"
        return "causal"

    @staticmethod
    def _question(events: list[Event]) -> str:
        last = events[-1]
        status = last.action_result.status if last.action_result else "unknown"
        actor = last.participants[0] if last.participants else "the actors"
        if status == "failure":
            return f"What will {actor} do after the failure?"
        if status == "blocked":
            return f"How will {actor} respond to the remaining obstacle?"
        if status == "success":
            return "What new consequences will follow from this success?"
        return "What consequence will emerge next?"

    def _connected(self, event: Event, thread: list[Event]) -> bool:
        if not thread:
            return False
        distance = event.tick - thread[-1].tick
        if distance < 0 or distance > self.max_tick_gap:
            return False
        return bool(self._keys(event).intersection(self._keys(thread[-1])))

    def discover(self, state: WorldState, events: list[Event] | None = None) -> list[NarrativeThread]:
        history = list(state.event_log)
        seen = {event.id for event in history}
        for event in events or []:
            if event.id not in seen:
                history.append(event)
        history.sort(key=lambda event: (event.tick, event.id))
        chains: list[list[Event]] = []
        for event in history:
            candidates = [thread for thread in chains if self._connected(event, thread)]
            if not candidates:
                chains.append([event])
                continue
            selected = min(candidates, key=lambda thread: (event.tick - thread[-1].tick, thread[-1].id))
            selected.append(event)

        threads: list[NarrativeThread] = []
        for index, chain in enumerate(chains, start=1):
            if len(chain) == 1 and not chain[0].consequences:
                continue
            scores = [self.pressure.score_event(state, event) for event in chain]
            participants = sorted({participant for event in chain for participant in event.participants})
            thread_type = self._thread_type(chain)
            threads.append(
                NarrativeThread(
                    id=f"thread-{index}-{chain[0].id}",
                    thread_type=thread_type,
                    title=f"{thread_type}: {chain[0].facts[0] if chain[0].facts else chain[0].id}",
                    participants=participants,
                    event_ids=[event.id for event in chain],
                    tension=sum(scores) / len(scores),
                    status="open",
                    unresolved_question=self._question(chain),
                )
            )
        threads.sort(key=lambda item: (-item.tension, item.id))
        return threads
