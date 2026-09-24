"""Detect convergence among independently tracked narrative threads."""

from __future__ import annotations

from itertools import combinations

from .models import NarrativeThread, ThreadConvergence


class ThreadConvergenceDetector:
    def __init__(self, max_event_gap:int=6) -> None:
        self.max_event_gap=max(0,max_event_gap)

    @staticmethod
    def _ticks(thread:NarrativeThread, event_ticks:dict[str,int]) -> tuple[int,int]:
        ticks=[event_ticks[event_id] for event_id in thread.event_ids if event_id in event_ticks]
        return (min(ticks),max(ticks)) if ticks else (0,0)

    def detect(self, threads:list[NarrativeThread], event_ticks:dict[str,int]) -> list[ThreadConvergence]:
        results=[]
        for left,right in combinations(threads,2):
            overlap=set(left.participants).intersection(right.participants)
            if not overlap:
                lt=self._ticks(left,event_ticks); rt=self._ticks(right,event_ticks)
                if min(abs(lt[1]-rt[0]),abs(rt[1]-lt[0]))>self.max_event_gap:
                    continue
            lt=self._ticks(left,event_ticks); rt=self._ticks(right,event_ticks)
            gap=max(0,max(lt[0],rt[0])-min(lt[1],rt[1]))
            strength=min(1.0,0.55*float(bool(overlap))+0.45*(1.0-min(1.0,gap/max(1,self.max_event_gap))))
            results.append(ThreadConvergence(
                id=f"convergence-{left.id}-{right.id}",
                thread_ids=sorted([left.id,right.id]),
                event_ids=sorted(set(left.event_ids+right.event_ids),key=lambda item:(event_ticks.get(item,0),item)),
                participants=sorted(set(left.participants+right.participants)),
                strength=strength,
                description="Two previously separate narrative threads now share actors or converge in time.",
            ))
        results.sort(key=lambda item:(-item.strength,item.id))
        return results
