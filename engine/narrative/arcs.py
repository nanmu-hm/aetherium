"""Detect character trajectories from persistent consequences."""

from __future__ import annotations

from ..core.models import Event, WorldState
from .models import CharacterArc


class CharacterArcDetector:
    """Turn accumulated state changes into inspectable character trajectories."""

    def detect(self, state: WorldState, events: list[Event] | None = None) -> list[CharacterArc]:
        history = list(state.event_log)
        seen = {event.id for event in history}
        for event in events or []:
            if event.id not in seen:
                history.append(event)
        history.sort(key=lambda event: (event.tick, event.id))

        results: list[CharacterArc] = []
        for character in state.characters.values():
            identity, emotions, goals, relationships = [], [], [], []
            event_ids = []
            score = 0.0
            for event in history:
                event_score = 0.0
                for consequence in event.consequences:
                    field = consequence.field
                    target = consequence.target_id
                    owned = target == character.id or target.startswith(f"{character.id}:") or target.endswith(f":{character.id}")
                    if not owned:
                        continue
                    old, new = consequence.old_value, consequence.new_value
                    if field.startswith("identity_beliefs."):
                        identity.append(f"{event.id}:{field}:{old}->{new}")
                        event_score += 1.5
                    elif field.startswith("emotions."):
                        emotions.append(f"{event.id}:{field}:{old}->{new}")
                        event_score += 0.5
                    elif consequence.target_type == "goal":
                        goals.append(f"{event.id}:{field}:{old}->{new}")
                        event_score += 1.4
                    elif consequence.target_type == "relationship":
                        relationships.append(f"{event.id}:{target}:{field}:{old}->{new}")
                        event_score += 0.8
                if event_score > 0:
                    event_ids.append(event.id)
                    score += event_score

            bounded = min(1.0, score / 6.0)
            if identity or goals:
                phase = "transforming" if bounded >= 0.30 else "emerging"
            elif relationships or emotions:
                phase = "pressured" if bounded >= 0.25 else "emerging"
            else:
                phase = "stable"

            description = {
                "transforming": f"{character.name} is undergoing a persistent change in goals or self-concept.",
                "pressured": f"{character.name} is experiencing accumulating relational or emotional pressure.",
                "emerging": f"{character.name} has begun a detectable trajectory.",
                "stable": f"{character.name} has no strong persistent arc signal yet.",
            }[phase]
            results.append(CharacterArc(
                id=f"arc-{character.id}",
                character_id=character.id,
                event_ids=event_ids,
                identity_changes=identity,
                emotional_changes=emotions,
                goal_changes=goals,
                relationship_changes=relationships,
                change_score=bounded,
                phase=phase,
                description=description,
            ))
        results.sort(key=lambda item: (-item.change_score, item.id))
        return results
