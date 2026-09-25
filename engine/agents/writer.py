from __future__ import annotations

from dataclasses import asdict, dataclass

from ..narrative.quality import ProseQualityGate
from ..persistence.codec import world_from_dict
from .contracts import standard_contracts
from .models import (
    AgentContext,
    AgentProposal,
    AgentResult,
    AgentRole,
    AgentStatus,
    ProposalKind,
)


@dataclass(frozen=True)
class SceneDraft:
    scene_id: str
    title: str
    prose: str
    source_event_ids: tuple[str, ...]
    participant_ids: tuple[str, ...]
    viewpoint_character_id: str | None
    expression_mode: str = "summarize"
    quality_score: float = 1.0


class WriterAgent:
    """Generate a non-authoritative scene draft from already observed history."""

    def __init__(self, scene_id: str | None = None) -> None:
        self.scene_id = scene_id
        self.contract = standard_contracts()[AgentRole.WRITER]

    @staticmethod
    def _scene_expression(narrative: dict, scene_id: str) -> dict:
        for item in narrative.get("scene_expression", []):
            if isinstance(item, dict) and item.get("scene_id") == scene_id:
                return item
        return {}

    def _select_scene(self, context: AgentContext) -> dict | None:
        scenes = [
            item
            for item in context.narrative_snapshot.get("scenes", [])
            if isinstance(item, dict)
        ]
        if self.scene_id:
            return next((item for item in scenes if item.get("id") == self.scene_id), None)

        selected = set(context.selected_event_ids)
        if selected:
            matches = [
                item
                for item in scenes
                if selected.intersection(item.get("event_ids", []))
            ]
            if matches:
                return matches[0]

        return None

    @staticmethod
    def _event_index(state) -> dict[str, object]:
        return {event.id: event for event in state.event_log}

    @staticmethod
    def _display_names(state, participant_ids: list[str]) -> list[str]:
        return [
            state.characters[character_id].name
            for character_id in participant_ids
            if character_id in state.characters
        ]

    def _build_draft(self, context: AgentContext) -> tuple[SceneDraft | None, list[str]]:
        state = world_from_dict(context.world_snapshot)
        scene = self._select_scene(context)
        if scene is None:
            return None, ["No narrative scene selected; provide a scene_id or selected_event_ids."]

        event_ids = tuple(scene.get("event_ids", []))
        events = self._event_index(state)
        missing = [event_id for event_id in event_ids if event_id not in events]
        if missing:
            return None, [f"Scene references unknown event(s): {', '.join(missing)}."]

        event_list = [events[event_id] for event_id in event_ids]
        participant_ids = sorted(
            {
                participant
                for event in event_list
                for participant in event.participants
            }
        )
        expression = self._scene_expression(context.narrative_snapshot, scene.get("id", ""))
        viewpoint = expression.get("viewpoint_character_id")
        quality = ProseQualityGate().validate(
            state,
            list(event_ids),
            viewpoint,
            participant_ids,
        )
        if not quality.factual_fidelity or not quality.participant_consistency or not quality.viewpoint_consistency:
            return None, quality.failures

        prose_parts: list[str] = []
        for event in event_list:
            names = self._display_names(state, event.participants)
            who = ", ".join(names) if names else "The people involved"
            location = event.location or "an unspecified place"
            facts = " ".join(event.facts).strip()
            prefix = f"At {event.timestamp}, {who} were at {location}."
            prose_parts.append(f"{prefix} {facts}".strip())

        paragraph_break = chr(10) + chr(10)
        prose = paragraph_break.join(prose_parts)
        title = (event_list[0].facts[0] if event_list[0].facts else scene.get("id", "Scene")).strip()
        if len(title) > 80:
            title = title[:77].rstrip() + "..."

        draft = SceneDraft(
            scene_id=scene.get("id", ""),
            title=title,
            prose=prose,
            source_event_ids=event_ids,
            participant_ids=tuple(participant_ids),
            viewpoint_character_id=viewpoint,
            expression_mode=expression.get("emphasis_mode", "summarize"),
            quality_score=quality.score,
        )
        return draft, []

    def inspect(self, context: AgentContext) -> AgentResult:
        draft, diagnostics = self._build_draft(context)
        if draft is None:
            return AgentResult(
                status=AgentStatus.BLOCKED,
                diagnostics=diagnostics,
            )

        payload = asdict(draft)
        payload["source_event_ids"] = list(draft.source_event_ids)
        payload["participant_ids"] = list(draft.participant_ids)
        proposal = AgentProposal(
            id=f"writer:scene:{draft.scene_id}",
            agent_id=self.contract.agent_id,
            kind=ProposalKind.NARRATIVE_EDIT,
            summary=f"Generate non-authoritative prose draft for {draft.scene_id}.",
            payload=payload,
            source_event_ids=draft.source_event_ids,
            confidence=draft.quality_score,
            requires_approval=False,
        )
        return AgentResult(
            status=AgentStatus.OK,
            response=draft.prose,
            proposals=[proposal],
        )

    def respond(self, context: AgentContext, message: str) -> AgentResult:
        result = self.inspect(context)
        if result.status != AgentStatus.OK:
            return result
        return AgentResult(
            status=AgentStatus.OK,
            response=f"{result.response}\n\nWriter note: {message}",
            proposals=result.proposals,
        )
