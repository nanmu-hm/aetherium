"""Assess story completion from explicit evidence rather than arbitrary length."""

from __future__ import annotations

from .models import StoryArc, StoryCompletionAssessment, NarrativeSequence, NarrativeThread


class StoryCompletionDetector:
    def assess(self, arcs:list[StoryArc], sequences:list[NarrativeSequence], threads:list[NarrativeThread], callback_payoffs:set[str]|None=None) -> list[StoryCompletionAssessment]:
        callback_payoffs=callback_payoffs or set()
        sequence_by_id={item.id:item for item in sequences}
        thread_by_id={item.id:item for item in threads}
        result=[]
        for arc in arcs:
            arc_threads=[thread_by_id[item] for item in arc.thread_ids if item in thread_by_id]
            unresolved=sum(bool(thread.unresolved_question) and thread.status=="open" for thread in arc_threads)
            resolved=sum(thread.status!="open" for thread in arc_threads)
            payoff_events = {event_id for thread in arc_threads for event_id in thread.event_ids}
            payoffs = len(payoff_events.intersection(callback_payoffs))
            if unresolved==0 and resolved>0 and payoffs>0:
                status="complete"; confidence=0.90; reason="The arc has resolved threads and an observed payoff."
            elif unresolved==0 and arc.completion_signal>=0.75:
                status="resolving"; confidence=0.70; reason="No unresolved thread questions remain and completion evidence is accumulating."
            else:
                status="open"; confidence=max(0.0,1.0-0.25*unresolved); reason="The arc still carries unresolved questions or lacks a grounded payoff."
            result.append(StoryCompletionAssessment(arc.id,status,confidence,resolved,unresolved,payoffs,reason))
        return result
