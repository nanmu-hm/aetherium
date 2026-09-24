"""Schedule delayed callback opportunities without forcing them into prose."""

from __future__ import annotations

from .models import CallbackSchedule, ForeshadowingLink


class CallbackScheduler:
    def schedule(self, links:list[ForeshadowingLink]) -> list[CallbackSchedule]:
        result=[]
        for link in links:
            priority=min(1.0,0.55*link.confidence+0.35*float(link.causal)+0.10*float(bool(link.shared_keys)))
            minimum_gap=2 if link.causal else 1
            maximum_gap=12 if link.causal else 8
            result.append(CallbackSchedule(
                setup_event_id=link.setup_event_id,
                payoff_event_id=link.payoff_event_id,
                priority=priority,
                minimum_gap=minimum_gap,
                maximum_gap=maximum_gap,
                status="eligible",
                reason="The payoff is grounded in an already observed setup; timing remains flexible.",
            ))
        result.sort(key=lambda item:(-item.priority,item.setup_event_id,item.payoff_event_id))
        return result
