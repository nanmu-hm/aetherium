from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from ..persistence.narrative import NarrativeCanonEntry, NarrativeCanonLedger
from .models import AgentProposal, ProposalKind


class DraftStatus(str, Enum):
    PENDING = "pending"
    SUPERSEDED = "superseded"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class NarrativeDraft:
    id: str
    version: int
    scene_id: str
    title: str
    prose: str
    source_event_ids: tuple[str, ...]
    participant_ids: tuple[str, ...]
    viewpoint_character_id: str | None
    branch_id: str
    tick: int
    status: DraftStatus = DraftStatus.PENDING
    created_by: str = "agent"
    parent_version: int | None = None


class NarrativeDraftStore:
    """Versioned draft store. Draft versions never mutate authoritative world state."""

    def __init__(self) -> None:
        self._drafts: dict[tuple[str, int], NarrativeDraft] = {}
        self._latest: dict[str, int] = {}

    def get(self, draft_id: str, version: int | None = None) -> NarrativeDraft:
        if version is None:
            version = self._latest[draft_id]
        return self._drafts[(draft_id, version)]

    def versions(self, draft_id: str) -> list[NarrativeDraft]:
        return [
            self._drafts[key]
            for key in sorted(self._drafts)
            if key[0] == draft_id
        ]

    def _put(self, draft: NarrativeDraft) -> NarrativeDraft:
        key = (draft.id, draft.version)
        self._drafts[key] = draft
        self._latest[draft.id] = draft.version
        return draft

    def create(
        self,
        *,
        draft_id: str,
        scene_id: str,
        title: str,
        prose: str,
        source_event_ids: tuple[str, ...],
        participant_ids: tuple[str, ...],
        viewpoint_character_id: str | None,
        branch_id: str,
        tick: int,
        created_by: str,
    ) -> NarrativeDraft:
        version = self._latest.get(draft_id, 0) + 1
        if version > 1:
            previous = self.get(draft_id)
            if previous.status != DraftStatus.PENDING:
                raise ValueError("Only a pending draft can receive a new version.")
            self._drafts[(draft_id, previous.version)] = replace(
                previous,
                status=DraftStatus.SUPERSEDED,
            )

        return self._put(
            NarrativeDraft(
                id=draft_id,
                version=version,
                scene_id=scene_id,
                title=title,
                prose=prose,
                source_event_ids=source_event_ids,
                participant_ids=participant_ids,
                viewpoint_character_id=viewpoint_character_id,
                branch_id=branch_id,
                tick=tick,
                created_by=created_by,
                parent_version=version - 1 if version > 1 else None,
            )
        )

    def revise(
        self,
        draft_id: str,
        *,
        prose: str,
        title: str | None = None,
        edited_by: str = "user",
    ) -> NarrativeDraft:
        current = self.get(draft_id)
        if current.status != DraftStatus.PENDING:
            raise ValueError("Only a pending draft can be revised.")

        return self.create(
            draft_id=draft_id,
            scene_id=current.scene_id,
            title=current.title if title is None else title,
            prose=prose,
            source_event_ids=current.source_event_ids,
            participant_ids=current.participant_ids,
            viewpoint_character_id=current.viewpoint_character_id,
            branch_id=current.branch_id,
            tick=current.tick,
            created_by=edited_by,
        )

    def reject(self, draft_id: str, version: int | None = None) -> NarrativeDraft:
        current = self.get(draft_id, version)
        if current.status != DraftStatus.PENDING:
            raise ValueError("Only a pending draft can be rejected.")
        rejected = replace(current, status=DraftStatus.REJECTED)
        self._drafts[(current.id, current.version)] = rejected
        return rejected

    def approve(self, draft_id: str, version: int | None = None) -> NarrativeDraft:
        current = self.get(draft_id, version)
        latest = self.get(draft_id)
        if current.version != latest.version:
            raise ValueError("Only the latest draft version can be approved.")
        if current.status != DraftStatus.PENDING:
            raise ValueError("Only a pending draft can be approved.")
        approved = replace(current, status=DraftStatus.APPROVED)
        self._drafts[(current.id, current.version)] = approved
        return approved


@dataclass(frozen=True)
class ApprovalDecision:
    approved: bool
    draft: NarrativeDraft
    canon_entry: NarrativeCanonEntry | None = None
    reason: str = ""


class HumanApprovalService:
    """Human gate between narrative drafts and narrative canon."""

    def __init__(
        self,
        store: NarrativeDraftStore | None = None,
        canon_ledger: NarrativeCanonLedger | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self.store = store or NarrativeDraftStore()
        self.canon_ledger = canon_ledger
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())

    def submit_proposal(
        self,
        proposal: AgentProposal,
        *,
        branch_id: str,
        tick: int,
    ) -> NarrativeDraft:
        if proposal.kind != ProposalKind.NARRATIVE_EDIT:
            raise ValueError("Only NARRATIVE_EDIT proposals can become narrative drafts.")

        payload = proposal.payload
        source_event_ids = tuple(payload.get("source_event_ids", []))
        participant_ids = tuple(payload.get("participant_ids", []))
        if source_event_ids != proposal.source_event_ids:
            raise ValueError("Proposal and draft source_event_ids do not match.")
        if not payload.get("scene_id"):
            raise ValueError("Narrative draft requires scene_id.")
        if "prose" not in payload:
            raise ValueError("Narrative draft requires prose.")

        return self.store.create(
            draft_id=proposal.id,
            scene_id=str(payload["scene_id"]),
            title=str(payload.get("title", "")),
            prose=str(payload["prose"]),
            source_event_ids=source_event_ids,
            participant_ids=participant_ids,
            viewpoint_character_id=payload.get("viewpoint_character_id"),
            branch_id=branch_id,
            tick=tick,
            created_by=proposal.agent_id,
        )

    def revise(
        self,
        draft_id: str,
        *,
        prose: str,
        title: str | None = None,
        edited_by: str = "user",
    ) -> NarrativeDraft:
        return self.store.revise(
            draft_id,
            prose=prose,
            title=title,
            edited_by=edited_by,
        )

    def reject(self, draft_id: str, version: int | None = None) -> ApprovalDecision:
        draft = self.store.reject(draft_id, version)
        return ApprovalDecision(
            approved=False,
            draft=draft,
            reason="Narrative draft rejected; authoritative world state is unchanged.",
        )

    def approve(
        self,
        draft_id: str,
        *,
        approved_by: str = "user",
        version: int | None = None,
    ) -> ApprovalDecision:
        draft = self.store.approve(draft_id, version)
        approved_at = self._clock()
        entry = NarrativeCanonEntry(
            id=f"{draft.id}:v{draft.version}",
            draft_id=draft.id,
            version=draft.version,
            scene_id=draft.scene_id,
            title=draft.title,
            prose=draft.prose,
            source_event_ids=draft.source_event_ids,
            participant_ids=draft.participant_ids,
            viewpoint_character_id=draft.viewpoint_character_id,
            branch_id=draft.branch_id,
            tick=draft.tick,
            approved_by=approved_by,
            approved_at=approved_at,
            metadata={"created_by": draft.created_by},
        )
        if self.canon_ledger is not None:
            self.canon_ledger.append(entry)
        return ApprovalDecision(
            approved=True,
            draft=draft,
            canon_entry=entry,
            reason="Narrative draft approved into narrative canon; world state is unchanged.",
        )
