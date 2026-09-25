from __future__ import annotations

from collections import Counter

from ..persistence.codec import world_from_dict
from .contracts import standard_contracts
from .models import AgentContext, AgentProposal, AgentResult, AgentRole, AgentStatus, ProposalKind


class CriticAgent:
    """Independent, non-authoritative quality critic for history and narrative signals."""

    def __init__(self) -> None:
        self.contract = standard_contracts()[AgentRole.CRITIC]

    def inspect(self, context: AgentContext) -> AgentResult:
        state = world_from_dict(context.world_snapshot)
        diagnostics: list[str] = []
        proposals: list[AgentProposal] = []

        recent_events = state.event_log[-8:]
        actor_counts = Counter(
            event.participants[0]
            for event in recent_events
            if event.participants
        )
        for actor_id, count in actor_counts.items():
            if count >= 4:
                diagnostics.append(
                    f"Possible behavioral concentration: actor {actor_id} appears as lead participant in {count} of the last {len(recent_events)} event(s)."
                )
                proposals.append(
                    AgentProposal(
                        id=f"critic:concentration:{actor_id}",
                        agent_id=self.contract.agent_id,
                        kind=ProposalKind.RECOMMENDATION,
                        summary="Review whether recent history is over-concentrated on one character.",
                        payload={
                            "character_id": actor_id,
                            "recent_event_count": count,
                            "window": len(recent_events),
                        },
                        confidence=0.65,
                    )
                )

        locations = [event.location for event in recent_events if event.location]
        if locations and len(set(locations)) == 1 and len(locations) >= 5:
            diagnostics.append(
                f"Recent events are spatially concentrated at {locations[0]}."
            )
            proposals.append(
                AgentProposal(
                    id="critic:location-concentration",
                    agent_id=self.contract.agent_id,
                    kind=ProposalKind.RECOMMENDATION,
                    summary="Review whether the current story phase benefits from remaining in one location.",
                    payload={"location": locations[0], "window": len(locations)},
                    confidence=0.55,
                )
            )

        narrative = context.narrative_snapshot
        unresolved = narrative.get("narrative_threads", [])
        open_threads = [
            item for item in unresolved
            if isinstance(item, dict) and item.get("status") == "open"
        ]
        if open_threads:
            diagnostics.append(f"{len(open_threads)} narrative thread(s) remain open in the supplied narrative snapshot.")

        if not diagnostics:
            response = "Critic found no obvious concentration or unresolved-pressure warning in the supplied snapshot."
        else:
            response = f"Critic identified {len(diagnostics)} review point(s); these are observations, not authoritative defects."

        return AgentResult(
            status=AgentStatus.OK,
            response=response,
            proposals=proposals,
            diagnostics=diagnostics,
        )

    def respond(self, context: AgentContext, message: str) -> AgentResult:
        result = self.inspect(context)
        result.response = f"{result.response} User question: {message}"
        return result
