"""Separate narrative importance from raw historical magnitude."""

from __future__ import annotations

from ..core.models import Event, WorldState
from .models import NarrativeImportance, NarrativeThread
from .pressure import NarrativePressureAnalyzer


class NarrativeImportanceAnalyzer:
    """Estimate why an event may matter to a story, not merely how large it was."""

    @staticmethod
    def _keys(event: Event) -> set[str]:
        keys={f"participant:{item}" for item in event.participants}
        for consequence in event.consequences:
            keys.add(f"{consequence.target_type}:{consequence.target_id}")
            keys.add(f"{consequence.target_type}:{consequence.target_id}:{consequence.field}")
        return keys

    def score(self, state: WorldState, events: list[Event] | None = None) -> list[NarrativeImportance]:
        history=list(state.event_log)
        seen={event.id for event in history}
        for event in events or []:
            if event.id not in seen: history.append(event)
        history.sort(key=lambda event:(event.tick,event.id))
        pressure=NarrativePressureAnalyzer()
        results=[]
        for index,event in enumerate(history):
            historical_size=min(1.0, 0.10*len(set(event.participants)) + 0.10*len(event.consequences))
            pressure_factor=pressure.score_event(state,event)
            relationship_factor=min(1.0, 0.20*sum(c.target_type=="relationship" for c in event.consequences))
            character_factor=min(1.0, 0.20*sum(c.field.startswith("identity_beliefs.") or c.field.startswith("emotions.") for c in event.consequences))
            later=history[index+1:]
            keys=self._keys(event)
            reach=sum(1 for future in later if keys.intersection(self._keys(future)))
            causal_reach=min(1.0, reach/4.0)
            information_factor=0.0
            for future in later:
                if future.participants and set(event.participants).intersection(future.participants):
                    information_factor=max(information_factor,0.15 if future.id != event.id else 0.0)
            narrative_score=min(1.0,0.25*pressure_factor + 0.20*relationship_factor + 0.20*character_factor + 0.15*information_factor + 0.20*causal_reach)
            description=("Narrative weight comes from pressure, persistent change, information, "
                         "and later causal reach rather than event size alone.")
            results.append(NarrativeImportance(event.id,historical_size,narrative_score,pressure_factor,relationship_factor,character_factor,information_factor,causal_reach,description))
        results.sort(key=lambda item:(-item.narrative_score,item.event_id))
        return results
