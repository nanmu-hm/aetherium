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
            goals=[Goal("yan-1", "help an old friend", priority=0.75)],
            human_condition=HumanCondition(
                attachments={"friendship": 85},
                desires={"reconciliation": 70},
                fears={"loss": 65},
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
            goals=[Goal("rui-1", "leave town", priority=0.65)],
            human_condition=HumanCondition(
                attachments={"friendship": 70},
                desires={"freedom": 80},
                fears={"confinement": 60},
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
    for candidate in candidates[:5]:
        print(
            f"score={candidate.score:.3f} "
            f"events={len(candidate.event_ids)} "
            f"participants={','.join(candidate.participants)}"
        )
