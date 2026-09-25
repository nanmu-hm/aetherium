from __future__ import annotations

from dataclasses import dataclass, field

from .authority import AgentAuthority
from .contracts import Agent
from .models import AgentContext, AgentResult, AgentRole, AgentStatus


@dataclass(frozen=True)
class AgentRun:
    agent_id: str
    status: AgentStatus
    result: AgentResult


@dataclass
class AgentRegistry:
    agents: dict[str, Agent] = field(default_factory=dict)

    def register(self, agent: Agent) -> None:
        agent_id = agent.contract.agent_id
        if agent_id in self.agents:
            raise ValueError(f"Agent already registered: {agent_id}")
        self.agents[agent_id] = agent

    def get(self, agent_id: str) -> Agent:
        try:
            return self.agents[agent_id]
        except KeyError as exc:
            raise KeyError(f"Unknown agent: {agent_id}") from exc

    def ids(self) -> tuple[str, ...]:
        return tuple(self.agents)


class DirectorOrchestrator:
    """Coordinate agents without giving any agent direct authority over WorldState."""

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        authority: AgentAuthority | None = None,
    ) -> None:
        self.registry = registry or AgentRegistry()
        self.authority = authority or AgentAuthority()

    def register(self, agent: Agent) -> None:
        self.authority.validate_contract(agent.contract)
        self.registry.register(agent)

    def inspect_one(self, agent_id: str, context: AgentContext) -> AgentRun:
        agent = self.registry.get(agent_id)
        contract_decision = self.authority.validate_contract(agent.contract)
        if not contract_decision.allowed:
            result = AgentResult(
                status=AgentStatus.BLOCKED,
                diagnostics=[contract_decision.reason],
            )
            return AgentRun(agent_id, AgentStatus.BLOCKED, result)

        gated = self.authority.gate_result(agent.contract, agent.inspect(context))
        return AgentRun(agent_id, gated.status, gated)

    def respond_to(
        self,
        agent_id: str,
        context: AgentContext,
        message: str,
    ) -> AgentRun:
        agent = self.registry.get(agent_id)
        contract_decision = self.authority.validate_contract(agent.contract)
        if not contract_decision.allowed:
            result = AgentResult(
                status=AgentStatus.BLOCKED,
                diagnostics=[contract_decision.reason],
            )
            return AgentRun(agent_id, AgentStatus.BLOCKED, result)

        if not agent.contract.chat_enabled:
            result = AgentResult(
                status=AgentStatus.BLOCKED,
                diagnostics=["Agent conversation is disabled by contract."],
            )
            return AgentRun(agent_id, AgentStatus.BLOCKED, result)

        gated = self.authority.gate_result(agent.contract, agent.respond(context, message))
        return AgentRun(agent_id, gated.status, gated)

    def inspect_many(
        self,
        agent_ids: list[str] | tuple[str, ...],
        context: AgentContext,
    ) -> list[AgentRun]:
        return [self.inspect_one(agent_id, context) for agent_id in agent_ids]

    def inspect_by_role(
        self,
        role: AgentRole,
        context: AgentContext,
    ) -> list[AgentRun]:
        return [
            self.inspect_one(agent.contract.agent_id, context)
            for agent in self.registry.agents.values()
            if agent.contract.role == role
        ]
