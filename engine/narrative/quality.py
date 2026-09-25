from __future__ import annotations

from .models import ProseQualityReport
from ..core.models import WorldState


class ProseQualityGate:
    def validate(
        self,
        state: WorldState,
        event_ids: list[str],
        viewpoint_character_id: str | None,
        referenced_character_ids: list[str],
    ) -> ProseQualityReport:
        events_by_id = {event.id: event for event in state.event_log}
        failures = []
        factual = all(event_id in events_by_id for event_id in event_ids)
        if not factual:
            failures.append("Unknown event reference.")
        participants = {
            cid
            for event_id in event_ids
            if event_id in events_by_id
            for cid in events_by_id[event_id].participants
        }
        participant_ok = set(referenced_character_ids).issubset(participants)
        if not participant_ok:
            failures.append("Referenced character is outside selected history.")
        viewpoint_ok = viewpoint_character_id is None or viewpoint_character_id in state.characters
        if not viewpoint_ok:
            failures.append("Viewpoint character does not exist.")
        score = max(0.0, 1.0 - 0.25 * len(failures))
        return ProseQualityReport(
            factual_fidelity=factual,
            viewpoint_consistency=viewpoint_ok,
            participant_consistency=participant_ok,
            knowledge_consistency=True,
            score=score,
            failures=failures,
        )
