"""Deterministic Genesis scenario for the first autonomous-world test."""

from __future__ import annotations

from engine.core.human_condition import HumanCondition
from engine.core.models import CharacterState, Goal, RelationshipState, WorldState
from engine.core.simulation import SimulationEngine
from engine.narrative import StoryArchaeologist


def build_genesis_world() -> WorldState:
    world = WorldState(
        world_id="genesis-001",
        locations={"river_town", "old_road"},
    )

    world.add_character(
        CharacterState(
            id="yan",
            name="Yan",
            location="river_town",
            values=["loyalty", "responsibility"],
            goals=[Goal(
                "yan-1",
                "help an old friend",
                priority=0.75,
                stages=["find the old friend", "help the old friend"],
                stage_conditions=[
                    {"type": "successful_contact", "target_id": "rui", "action_types": ["contact_person"]},
                    {"type": "successful_help", "target_id": "rui", "action_types": ["help_person"]},
                ],
            )],
            human_condition=HumanCondition(
                attachments={"friendship": 85},
                desires={"reconciliation": 70},
                fears={"loss": 65},
                location_pressures={
                    "river_town": {"confinement": 0.0},
                    "old_road": {"confinement": 0.0},
                },
                virtues={"loyalty": 90, "compassion": 75},
            ),
        )
    )
    world.add_character(
        CharacterState(
            id="rui",
            name="Rui",
            location="river_town",
            values=["freedom"],
            goals=[Goal(
                "rui-1",
                "leave town",
                priority=0.65,
                stages=["leave town", "continue toward freedom"],
                stage_conditions=[
                    {"type": "location_not", "location": "river_town", "action_types": ["travel"]},
                    {"type": "location_not_and_action", "location": "river_town", "action_types": ["travel", "contact_person", "help_person"]},
                ],
            )],
            human_condition=HumanCondition(
                attachments={"friendship": 70},
                desires={"freedom": 80},
                fears={"confinement": 60},
                location_pressures={
                    "river_town": {"confinement": 1.0},
                    "old_road": {"confinement": 0.0},
                },
                virtues={"courage": 80},
            ),
        )
    )

    world.add_relationship(
        RelationshipState(
            source_id="yan",
            target_id="rui",
            trust=48,
            affection=72,
            loyalty=68,
        )
    )
    world.add_relationship(
        RelationshipState(
            source_id="rui",
            target_id="yan",
            trust=44,
            affection=65,
            loyalty=55,
        )
    )
    return world


def run_genesis(ticks: int = 12, seed: int = 7) -> WorldState:
    world = build_genesis_world()
    engine = SimulationEngine(seed=seed)

    for _ in range(ticks):
        result = engine.step(world)
        if result.validation_errors:
            raise RuntimeError(result.validation_errors)

    return world


def discover_genesis_stories(ticks: int = 12, seed: int = 7):
    world = run_genesis(ticks=ticks, seed=seed)
    return world, StoryArchaeologist().discover(world, min_score=0.15)


if __name__ == "__main__":
    world, candidates = discover_genesis_stories()
    print(f"ticks={world.tick}")
    print(f"events={len(world.event_log)}")
    print(f"memories={len(world.memory_state.memories)}")
    print(f"story_candidates={len(candidates)}")
    print(f"final_timestamp={world.timestamp}")
    print(f"beliefs={len(world.memory_state.beliefs)}")
    print("history:")
    for event in world.event_log:
        status = event.action_result.status if event.action_result else "unknown"
        fact = event.facts[0] if event.facts else "(no fact)"
        print(
            f"  tick={event.tick:02d} "
            f"status={status:<7} "
            f"participants={','.join(event.participants)} "
            f"fact={fact}"
        )

    print("story_threads:")
    for candidate in candidates[:5]:
        print(
            f"  score={candidate.score:.3f} "
            f"events={len(candidate.event_ids)} "
            f"participants={','.join(candidate.participants)} "
            f"event_ids={','.join(candidate.event_ids)}"
        )


    print("final_state:")
    for character_id in sorted(world.characters):
        character = world.characters[character_id]
        desires = ", ".join(
            f"{name}={value:.1f}"
            for name, value in sorted(character.human_condition.desires.items())
        )
        beliefs = [
            belief.proposition
            for belief in world.memory_state.beliefs.values()
            if belief.owner_id == character_id
        ]
        print(
            f"  {character.name}: location={character.location} "
            f"desires={desires or '(none)'} beliefs={len(beliefs)}"
        )
