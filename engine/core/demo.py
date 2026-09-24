"""Small living-world smoke test for the Aetherium MVP."""

from .models import CharacterState, Goal, WorldState
from .simulation import SimulationEngine


def build_demo_world() -> WorldState:
    world = WorldState(world_id="demo", locations={"town"})
    world.add_character(
        CharacterState(
            id="lin",
            name="Lin",
            location="town",
            values=["loyalty"],
            goals=[Goal(id="g1", description="find a missing friend", priority=1.0)],
        )
    )
    world.add_character(
        CharacterState(
            id="mei",
            name="Mei",
            location="town",
            values=["freedom"],
            goals=[Goal(id="g2", description="leave town before night", priority=0.9)],
        )
    )
    return world


def run_demo(ticks: int = 3) -> WorldState:
    world = build_demo_world()
    engine = SimulationEngine(seed=42)
    for _ in range(ticks):
        result = engine.step(world)
        if result.validation_errors:
            raise RuntimeError(result.validation_errors)
    return world


if __name__ == "__main__":
    result = run_demo()
    for event in result.event_log:
        print(event.facts[0])
