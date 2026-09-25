from dataclasses import replace

import pytest

from engine.agents import AgentProposal, ProposalKind
from engine.agents.approval import DraftStatus, HumanApprovalService, NarrativeDraftStore
from engine.persistence import NarrativeCanonLedger
from engine.persistence.repository import WorldRepository
from engine.core.models import CharacterState, WorldState


def make_proposal() -> AgentProposal:
    return AgentProposal(
        id="writer:scene-1",
        agent_id="writer",
        kind=ProposalKind.NARRATIVE_EDIT,
        summary="draft scene",
        source_event_ids=("e1",),
        payload={
            "scene_id": "scene-1",
            "title": "The Meeting",
            "prose": "A met B.",
            "source_event_ids": ["e1"],
            "participant_ids": ["a", "b"],
            "viewpoint_character_id": "a",
            "quality_score": 1.0,
        },
        requires_approval=False,
    )


def make_state() -> WorldState:
    state = WorldState(world_id="approval-world", tick=7, active_branch="main")
    state.locations.add("town")
    state.add_character(CharacterState(id="a", name="A", location="town"))
    state.add_character(CharacterState(id="b", name="B", location="town"))
    return state


def test_submit_creates_pending_draft_without_world_mutation():
    state = make_state()
    before = WorldRepository("/tmp/aetherium-approval-test").snapshot_hash(state)
    service = HumanApprovalService()
    draft = service.submit_proposal(make_proposal(), branch_id=state.active_branch, tick=state.tick)

    after = WorldRepository("/tmp/aetherium-approval-test").snapshot_hash(state)
    assert draft.status == DraftStatus.PENDING
    assert draft.version == 1
    assert draft.source_event_ids == ("e1",)
    assert before == after
    assert state.characters["a"].name == "A"


def test_revision_creates_new_version_and_preserves_provenance():
    service = HumanApprovalService()
    first = service.submit_proposal(make_proposal(), branch_id="main", tick=7)
    second = service.revise(first.id, prose="A and B spoke quietly.", edited_by="user")

    assert first.status == DraftStatus.PENDING
    assert service.store.get(first.id, 1).status == DraftStatus.SUPERSEDED
    assert second.version == 2
    assert second.parent_version == 1
    assert second.source_event_ids == first.source_event_ids
    assert second.participant_ids == first.participant_ids
    assert second.prose == "A and B spoke quietly."


def test_only_latest_version_can_be_approved():
    service = HumanApprovalService()
    first = service.submit_proposal(make_proposal(), branch_id="main", tick=7)
    service.revise(first.id, prose="Revised.")
    with pytest.raises(ValueError, match="latest"):
        service.approve(first.id, version=1)


def test_reject_closes_pending_draft():
    service = HumanApprovalService()
    draft = service.submit_proposal(make_proposal(), branch_id="main", tick=7)
    decision = service.reject(draft.id)

    assert decision.approved is False
    assert decision.draft.status == DraftStatus.REJECTED
    with pytest.raises(ValueError, match="pending"):
        service.revise(draft.id, prose="Cannot edit after rejection.")


def test_approval_publishes_narrative_canon_without_world_write(tmp_path):
    state = make_state()
    ledger = NarrativeCanonLedger(tmp_path / "narrative-canon.jsonl")
    service = HumanApprovalService(canon_ledger=ledger, clock=lambda: "2030-01-01T00:00:00+00:00")
    before = WorldRepository(tmp_path / "repo").snapshot_hash(state)
    draft = service.submit_proposal(make_proposal(), branch_id=state.active_branch, tick=state.tick)

    decision = service.approve(draft.id, approved_by="human")
    after = WorldRepository(tmp_path / "repo").snapshot_hash(state)

    assert decision.approved is True
    assert decision.canon_entry is not None
    assert decision.canon_entry.prose == "A met B."
    assert decision.canon_entry.source_event_ids == ("e1",)
    assert before == after
    assert ledger.list(branch_id="main") == [decision.canon_entry]


def test_approved_draft_cannot_be_revised_or_approved_again():
    service = HumanApprovalService()
    draft = service.submit_proposal(make_proposal(), branch_id="main", tick=7)
    service.approve(draft.id)

    with pytest.raises(ValueError, match="pending"):
        service.revise(draft.id, prose="Another revision.")
    with pytest.raises(ValueError, match="pending"):
        service.approve(draft.id)


def test_only_narrative_edit_proposals_can_enter_draft_workflow():
    service = HumanApprovalService()
    proposal = replace(make_proposal(), kind=ProposalKind.RECOMMENDATION)
    with pytest.raises(ValueError, match="NARRATIVE_EDIT"):
        service.submit_proposal(proposal, branch_id="main", tick=7)


def test_source_event_provenance_is_not_user_editable():
    service = HumanApprovalService()
    draft = service.submit_proposal(make_proposal(), branch_id="main", tick=7)
    revised = service.revise(draft.id, prose="Edited by the user.", title="Edited")

    assert revised.source_event_ids == ("e1",)
    assert revised.participant_ids == ("a", "b")
    assert revised.viewpoint_character_id == "a"


def test_mismatched_proposal_provenance_is_rejected():
    service = HumanApprovalService()
    proposal = replace(
        make_proposal(),
        source_event_ids=("e2",),
    )
    with pytest.raises(ValueError, match="source_event_ids"):
        service.submit_proposal(proposal, branch_id="main", tick=7)


def test_narrative_canon_ledger_round_trips_versions(tmp_path):
    ledger = NarrativeCanonLedger(tmp_path / "canon.jsonl")
    service = HumanApprovalService(canon_ledger=ledger, clock=lambda: "2030-01-01T00:00:00+00:00")
    draft = service.submit_proposal(make_proposal(), branch_id="branch-2", tick=12)

    decision = service.approve(draft.id, approved_by="editor")
    entries = ledger.by_draft(draft.id)

    assert len(entries) == 1
    assert entries[0] == decision.canon_entry
    assert entries[0].branch_id == "branch-2"
    assert entries[0].tick == 12
