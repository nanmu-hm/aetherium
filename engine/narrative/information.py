"""Analyze character-local information asymmetry and grounded revelation opportunities."""

from __future__ import annotations

import hashlib

from ..core.models import WorldState
from .models import InformationGap, RevelationCandidate


class KnowledgeAsymmetryAnalyzer:
    """Compare character-local knowledge without treating the world log as omniscience."""

    def analyze(self, state: WorldState) -> list[InformationGap]:
        active_ids = sorted(character.id for character in state.characters.values() if character.status == "active")
        propositions: dict[str, list] = {}
        for owner_id, facts in state.memory_state.knowledge.items():
            if owner_id not in active_ids:
                continue
            for proposition, fact in facts.items():
                propositions.setdefault(proposition, []).append(fact)

        gaps: list[InformationGap] = []
        for proposition, facts in propositions.items():
            known_by = sorted({fact.owner_id for fact in facts})
            unknown_by = sorted(set(active_ids) - set(known_by))
            if not unknown_by:
                continue
            confidences = [fact.confidence for fact in facts]
            source_event_ids = sorted({fact.source_event_id for fact in facts if fact.source_event_id is not None})
            spread = (min(confidences), max(confidences))
            digest = hashlib.sha1(proposition.encode("utf-8")).hexdigest()[:12]
            strength = min(1.0, 0.50 + 0.20 * float(bool(unknown_by)) + 0.20 * max(0.0, spread[1] - spread[0]) + 0.10 * float(len(known_by) == 1))
            gaps.append(InformationGap(
                id=f"gap-{digest}",
                proposition=proposition,
                source_event_ids=source_event_ids,
                known_by=known_by,
                unknown_by=unknown_by,
                confidence_range=spread,
                strength=strength,
                description=", ".join(known_by) + " know this proposition while " + ", ".join(unknown_by) + " do not.",
            ))
        gaps.sort(key=lambda item: (-item.strength, item.proposition))
        return gaps


class RevelationDetector:
    """Identify plausible, relationship-grounded learning opportunities."""

    def detect(self, state: WorldState, gaps: list[InformationGap]) -> list[RevelationCandidate]:
        candidates: list[RevelationCandidate] = []
        for gap in gaps:
            known_facts = [state.memory_state.get_knowledge(owner, gap.proposition) for owner in gap.known_by]
            known_facts = [fact for fact in known_facts if fact is not None]
            if not known_facts:
                continue
            best_fact = max(known_facts, key=lambda fact: (fact.confidence, -fact.transmission_depth))
            for target_id in gap.unknown_by:
                for source_id in gap.known_by:
                    relationship_score = 0.5
                    relationship = state.get_relationship(source_id, target_id)
                    if relationship is not None:
                        relationship_score = (relationship.trust + relationship.affection + relationship.respect) / 300.0
                    strength = min(1.0, 0.55 * best_fact.confidence + 0.45 * max(0.0, min(1.0, relationship_score)))
                    candidates.append(RevelationCandidate(
                        id=f"reveal-{source_id}-{target_id}-{best_fact.id}",
                        proposition=gap.proposition,
                        source_character_id=source_id,
                        target_character_id=target_id,
                        source_event_id=best_fact.source_event_id,
                        confidence=best_fact.confidence,
                        strength=strength,
                        reason="The target lacks the proposition, while another character already holds it and may plausibly transmit it.",
                    ))
        candidates.sort(key=lambda item: (-item.strength, item.source_character_id, item.target_character_id, item.proposition))
        return candidates
