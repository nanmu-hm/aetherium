"""Track grounded setup/callback candidates without claiming authorial intent."""

from __future__ import annotations

from ..core.models import Event, WorldState
from .models import ForeshadowingLink


class ForeshadowingTracker:
    @staticmethod
    def _keys(event:Event)->set[str]:
        keys={f"participant:{item}" for item in event.participants}
        for consequence in event.consequences:
            keys.add(f"{consequence.target_type}:{consequence.target_id}")
            keys.add(f"{consequence.target_type}:{consequence.target_id}:{consequence.field}")
        return keys

    def detect(self,state:WorldState,max_tick_gap:int=12)->list[ForeshadowingLink]:
        history=sorted(state.event_log,key=lambda event:(event.tick,event.id))
        results=[]
        for index,setup in enumerate(history):
            setup_keys=self._keys(setup)
            if not setup_keys: continue
            for payoff in history[index+1:]:
                gap=payoff.tick-setup.tick
                if gap<=0: continue
                if gap>max_tick_gap: break
                shared=sorted(setup_keys.intersection(self._keys(payoff)))
                if not shared: continue
                causal=any(consequence.target_type=="relationship" for consequence in payoff.consequences) and any(key.startswith("relationship:") for key in shared)
                confidence=min(1.0,0.35+0.10*len(shared)+0.25*float(causal)+0.15*(1.0-gap/max_tick_gap))
                results.append(ForeshadowingLink(setup.id,payoff.id,shared,confidence,causal,
                    "Candidate setup/callback link grounded in facts already present in the simulation."))
        results.sort(key=lambda item:(-item.confidence,item.setup_event_id,item.payoff_event_id))
        return results
