from __future__ import annotations

from typing import Protocol

from .models import AgentContext, AgentContract, AgentResult, AgentRole


class Agent(Protocol):
    contract: AgentContract

    def inspect(self, context: AgentContext) -> AgentResult:
        """Inspect an explicit snapshot and return a structured result."""

    def respond(self, context: AgentContext, message: str) -> AgentResult:
        """Respond to a user conversation without mutating authoritative state."""


def standard_contracts() -> dict[AgentRole, AgentContract]:
    all_read = frozenset(
        {
            "world.read",
            "history.read",
            "character.read",
            "relationship.read",
            "memory.read",
            "narrative.read",
        }
    )
    return {
        AgentRole.DIRECTOR: AgentContract(
            "director",
            AgentRole.DIRECTOR,
            "Coordinates simulation, narrative, agents, and human decisions.",
            read_scopes=all_read,
            write_scopes=frozenset({"orchestration.plan", "intervention.propose"}),
            can_propose_intervention=True,
        ),
        AgentRole.CHARACTER: AgentContract(
            "character",
            AgentRole.CHARACTER,
            "Reasons about one character's goals, values, knowledge, memory, and choices.",
            read_scopes=frozenset(
                {"world.read", "history.read", "character.read", "relationship.read", "memory.read"}
            ),
            write_scopes=frozenset({"recommendation.propose"}),
        ),
        AgentRole.RELATIONSHIP: AgentContract(
            "relationship",
            AgentRole.RELATIONSHIP,
            "Analyzes relationship state and its causal changes.",
            read_scopes=frozenset({"world.read", "history.read", "character.read", "relationship.read"}),
            write_scopes=frozenset({"recommendation.propose"}),
        ),
        AgentRole.ACTION: AgentContract(
            "action",
            AgentRole.ACTION,
            "Builds and evaluates behaviorally plausible action candidates.",
            read_scopes=frozenset({"world.read", "character.read", "relationship.read", "memory.read"}),
            write_scopes=frozenset({"recommendation.propose"}),
        ),
        AgentRole.EVENT: AgentContract(
            "event",
            AgentRole.EVENT,
            "Analyzes action interactions, outcomes, and consequence candidates.",
            read_scopes=frozenset({"world.read", "history.read", "character.read", "relationship.read"}),
            write_scopes=frozenset({"recommendation.propose"}),
        ),
        AgentRole.WORLD: AgentContract(
            "world",
            AgentRole.WORLD,
            "Analyzes world-scale conditions without directly changing canon.",
            read_scopes=frozenset({"world.read", "history.read", "character.read", "faction.read"}),
            write_scopes=frozenset({"recommendation.propose"}),
        ),
        AgentRole.KNOWLEDGE: AgentContract(
            "knowledge",
            AgentRole.KNOWLEDGE,
            "Separates actor knowledge, belief, rumor, and misinformation.",
            read_scopes=frozenset({"world.read", "history.read", "character.read", "memory.read"}),
            write_scopes=frozenset({"recommendation.propose"}),
        ),
        AgentRole.FACTION: AgentContract(
            "faction",
            AgentRole.FACTION,
            "Analyzes organizations, collective goals, resources, and conflicts.",
            read_scopes=frozenset({"world.read", "history.read", "character.read", "faction.read"}),
            write_scopes=frozenset({"recommendation.propose"}),
        ),
        AgentRole.NARRATIVE: AgentContract(
            "narrative",
            AgentRole.NARRATIVE,
            "Observes history and discovers threads, arcs, dilemmas, and boundaries.",
            read_scopes=frozenset({"world.read", "history.read", "character.read", "narrative.read"}),
            write_scopes=frozenset({"recommendation.propose"}),
        ),
        AgentRole.CONTINUITY: AgentContract(
            "continuity",
            AgentRole.CONTINUITY,
            "Checks chronology, knowledge, location, relationships, and canon consistency.",
            read_scopes=all_read,
        ),
        AgentRole.WRITER: AgentContract(
            "writer",
            AgentRole.WRITER,
            "Turns approved narrative structures into non-authoritative prose drafts.",
            read_scopes=frozenset(
                {"world.read", "history.read", "character.read", "relationship.read", "narrative.read"}
            ),
            write_scopes=frozenset({"narrative.draft"}),
        ),
        AgentRole.CRITIC: AgentContract(
            "critic",
            AgentRole.CRITIC,
            "Performs independent checks for causality, characterization, pacing, and contradictions.",
            read_scopes=all_read,
            write_scopes=frozenset({"recommendation.propose"}),
        ),
    }
