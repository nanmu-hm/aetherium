from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any

from ..core.models import WorldState


class AgentRole(str, Enum):
    DIRECTOR = "director"
    CHARACTER = "character"
    RELATIONSHIP = "relationship"
    ACTION = "action"
    EVENT = "event"
    WORLD = "world"
    KNOWLEDGE = "knowledge"
    FACTION = "faction"
    NARRATIVE = "narrative"
    CONTINUITY = "continuity"
    WRITER = "writer"
    CRITIC = "critic"


class AgentStatus(str, Enum):
    OK = "ok"
    BLOCKED = "blocked"
    UNCERTAIN = "uncertain"


class ProposalKind(str, Enum):
    OBSERVATION = "observation"
    RECOMMENDATION = "recommendation"
    STATE_INTERVENTION = "state_intervention"
    NARRATIVE_EDIT = "narrative_edit"


PROTECTED_WRITE_SCOPES = frozenset(
    {
        "world.write",
        "simulation.write",
        "canon.write",
        "persistence.write",
        "memory.write",
    }
)


@dataclass(frozen=True)
class AgentContract:
    agent_id: str
    role: AgentRole
    description: str
    read_scopes: frozenset[str] = frozenset()
    write_scopes: frozenset[str] = frozenset()
    chat_enabled: bool = True
    autonomous_enabled: bool = False
    can_propose_intervention: bool = False

    def __post_init__(self) -> None:
        protected = self.write_scopes & PROTECTED_WRITE_SCOPES
        if protected:
            names = ", ".join(sorted(protected))
            raise ValueError(f"Agents cannot own authoritative write scopes: {names}")


@dataclass
class AgentContext:
    world_snapshot: dict[str, Any]
    narrative_snapshot: dict[str, Any] = field(default_factory=dict)
    branch_id: str = "main"
    tick: int = 0
    selected_event_ids: tuple[str, ...] = ()
    mode: str = "interactive"
    user_message: str = ""

    @classmethod
    def from_world(
        cls,
        state: WorldState,
        *,
        narrative_state: Any | None = None,
        selected_event_ids: list[str] | tuple[str, ...] = (),
        mode: str = "interactive",
        user_message: str = "",
    ) -> "AgentContext":
        from ..persistence.codec import world_to_dict

        if narrative_state is None:
            narrative_snapshot: dict[str, Any] = {}
        elif is_dataclass(narrative_state):
            narrative_snapshot = asdict(narrative_state)
        elif isinstance(narrative_state, dict):
            narrative_snapshot = deepcopy(narrative_state)
        else:
            raise TypeError("narrative_state must be a dataclass, dict, or None")

        return cls(
            world_snapshot=deepcopy(world_to_dict(state)),
            narrative_snapshot=narrative_snapshot,
            branch_id=state.active_branch,
            tick=state.tick,
            selected_event_ids=tuple(selected_event_ids),
            mode=mode,
            user_message=user_message,
        )


@dataclass(frozen=True)
class AgentMessage:
    sender: str
    content: str
    turn: int = 0


@dataclass(frozen=True)
class AgentProposal:
    id: str
    agent_id: str
    kind: ProposalKind
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)
    source_event_ids: tuple[str, ...] = ()
    confidence: float = 0.0
    requires_approval: bool = True


@dataclass
class AgentResult:
    status: AgentStatus
    response: str = ""
    proposals: list[AgentProposal] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
