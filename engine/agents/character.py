from __future__ import annotations

from ..persistence.codec import world_from_dict
from .contracts import standard_contracts
from .models import (
    AgentContext,
    AgentContract,
    AgentProposal,
    AgentResult,
    AgentRole,
    AgentStatus,
    ProposalKind,
)


class CharacterAgent:
    """Deterministic character-state analyst for one character."""

    def __init__(self, character_id: str) -> None:
        base = standard_contracts()[AgentRole.CHARACTER]
        self.character_id = character_id
        self.contract = AgentContract(
            agent_id=f"character:{character_id}",
            role=base.role,
            description=f"Analyzes character {character_id} from the authoritative snapshot.",
            read_scopes=base.read_scopes,
            write_scopes=base.write_scopes,
            chat_enabled=base.chat_enabled,
            autonomous_enabled=False,
            can_propose_intervention=False,
        )

    def inspect(self, context: AgentContext) -> AgentResult:
        state = world_from_dict(context.world_snapshot)
        character = state.characters.get(self.character_id)
        if character is None:
            return AgentResult(
                status=AgentStatus.BLOCKED,
                diagnostics=[f"Unknown character: {self.character_id}"],
            )

        active_goals = [goal for goal in character.goals if goal.status == "active"]
        top_goal = max(active_goals, key=lambda goal: goal.priority, default=None)
        dominant_emotion = max(character.emotions.items(), key=lambda item: item[1], default=None)
        strongest_desire = max(
            character.human_condition.desires.items(),
            key=lambda item: item[1],
            default=None,
        )

        relationship_count = sum(
            1
            for relationship in state.relationships.values()
            if relationship.source_id == self.character_id or relationship.target_id == self.character_id
        )

        facts = [
            f"{character.name} is {character.status} at {character.location or 'an unspecified location'}.",
            f"{len(active_goals)} active goal(s), {len(character.knowledge)} known fact(s), "
            f"{len(character.memory_ids)} recorded memory reference(s).",
            f"{relationship_count} relationship edge(s) involve this character.",
        ]
        if top_goal is not None:
            facts.append(
                f"Highest-priority active goal: {top_goal.description} "
                f"(priority {top_goal.priority:.1f})."
            )
        if dominant_emotion:
            facts.append(f"Strongest current emotion: {dominant_emotion[0]} ({dominant_emotion[1]:.1f}).")
        if strongest_desire:
            facts.append(f"Strongest current desire pressure: {strongest_desire[0]} ({strongest_desire[1]:.1f}).")

        proposals: list[AgentProposal] = []
        if top_goal is not None:
            proposals.append(
                AgentProposal(
                    id=f"{self.contract.agent_id}:goal-focus:{top_goal.id}",
                    agent_id=self.contract.agent_id,
                    kind=ProposalKind.RECOMMENDATION,
                    summary=f"Keep character attention centered on active goal: {top_goal.description}.",
                    payload={
                        "character_id": self.character_id,
                        "goal_id": top_goal.id,
                        "goal": top_goal.description,
                        "reason": "highest-priority active goal",
                    },
                    confidence=0.90,
                )
            )

        return AgentResult(
            status=AgentStatus.OK,
            response=" ".join(facts),
            proposals=proposals,
        )

    def respond(self, context: AgentContext, message: str) -> AgentResult:
        result = self.inspect(context)
        if result.status != AgentStatus.OK:
            return result
        return AgentResult(
            status=AgentStatus.OK,
            response=f"{result.response} User question: {message}",
            proposals=result.proposals,
        )
