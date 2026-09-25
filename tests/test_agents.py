from dataclasses import dataclass

import pytest

from engine.agents import (
    AgentAuthority,
    AgentContext,
    AgentContract,
    AgentProposal,
    AgentResult,
    AgentRole,
    AgentStatus,
    ModelRequest,
    NullModelAdapter,
    ProposalKind,
    standard_contracts,
)
from engine.core.models import CharacterState, WorldState


def make_state():
    state = WorldState(world_id="agent-world", tick=7, active_branch="main")
    state.locations.add("town")
    state.add_character(CharacterState(id="c1", name="C1", location="town"))
    return state


def test_context_is_a_detached_snapshot():
    state = make_state()
    context = AgentContext.from_world(state)
    context.world_snapshot["world"]["characters"]["c1"]["name"] = "changed"
    assert state.characters["c1"].name == "C1"


def test_context_carries_branch_and_tick():
    state = make_state()
    state.active_branch = "branch-1"
    context = AgentContext.from_world(state, selected_event_ids=["e1"], mode="chat")
    assert context.branch_id == "branch-1"
    assert context.tick == 7
    assert context.selected_event_ids == ("e1",)
    assert context.mode == "chat"


def test_context_accepts_dataclass_narrative_snapshot():
    @dataclass
    class Snapshot:
        pressure: float
        phase: str

    context = AgentContext.from_world(make_state(), narrative_state=Snapshot(0.5, "rising"))
    assert context.narrative_snapshot == {"pressure": 0.5, "phase": "rising"}


def test_protected_write_scope_is_rejected():
    with pytest.raises(ValueError):
        AgentContract(
            "bad",
            AgentRole.DIRECTOR,
            "bad contract",
            write_scopes=frozenset({"world.write"}),
        )


def test_intervention_requires_explicit_capability_and_approval():
    authority = AgentAuthority()
    contract = AgentContract(
        "writer",
        AgentRole.WRITER,
        "writer",
        write_scopes=frozenset({"narrative.draft"}),
    )
    proposal = AgentProposal(
        "p1",
        "writer",
        ProposalKind.STATE_INTERVENTION,
        "change",
        payload={"target_path": "characters.c1.location"},
        requires_approval=True,
    )
    decision = authority.validate_proposal(contract, proposal)
    assert not decision.allowed

    director = standard_contracts()[AgentRole.DIRECTOR]
    allowed = authority.validate_proposal(
        director,
        AgentProposal(
            "p2",
            "director",
            ProposalKind.STATE_INTERVENTION,
            "change",
            payload={"target_path": "characters.c1.location"},
        ),
    )
    assert allowed.allowed


def test_intervention_cannot_skip_human_approval():
    authority = AgentAuthority()
    director = standard_contracts()[AgentRole.DIRECTOR]
    proposal = AgentProposal(
        "p3",
        "director",
        ProposalKind.STATE_INTERVENTION,
        "change",
        requires_approval=False,
    )
    decision = authority.validate_proposal(director, proposal)
    assert not decision.allowed


def test_narrative_edit_is_non_authoritative():
    authority = AgentAuthority()
    writer = standard_contracts()[AgentRole.WRITER]
    proposal = AgentProposal(
        "p4",
        "writer",
        ProposalKind.NARRATIVE_EDIT,
        "draft scene",
    )
    decision = authority.validate_proposal(writer, proposal)
    assert decision.allowed


def test_result_gate_removes_unauthorized_proposals():
    authority = AgentAuthority()
    writer = standard_contracts()[AgentRole.WRITER]
    result = AgentResult(
        AgentStatus.OK,
        response="draft",
        proposals=[
            AgentProposal("p5", "writer", ProposalKind.RECOMMENDATION, "ok"),
            AgentProposal("p6", "writer", ProposalKind.STATE_INTERVENTION, "bad"),
        ],
    )
    gated = authority.gate_result(writer, result)
    assert len(gated.proposals) == 1
    assert gated.proposals[0].id == "p5"
    assert gated.status == AgentStatus.BLOCKED


def test_null_model_adapter_is_explicitly_unconfigured():
    adapter = NullModelAdapter()
    response = adapter.generate(ModelRequest("demo", "system", "hello"))
    assert response.status == "blocked"
    assert response.finish_reason == "no_model_adapter"
    assert response.text == ""


def test_standard_contracts_cover_core_roles():
    contracts = standard_contracts()
    assert AgentRole.DIRECTOR in contracts
    assert AgentRole.CONTINUITY in contracts
    assert AgentRole.WRITER in contracts
    assert AgentRole.CRITIC in contracts
    assert all("world.write" not in item.write_scopes for item in contracts.values())


def test_writer_contract_has_no_authoritative_write():
    writer = standard_contracts()[AgentRole.WRITER]
    assert writer.write_scopes == frozenset({"narrative.draft"})
