from engine.core.actions import generate_action_pool
from engine.core.human_condition import HumanCondition
from engine.core.models import ActionCandidate, CharacterState, Goal, RelationshipState, WorldState
from engine.core.simulation import SimulationEngine
from engine.memory.kernel import MemoryKernel


def test_staged_goal_advances_before_final_completion():
    world = WorldState(world_id="staged", locations={"town"})
    world.add_character(
        CharacterState(
            id="a",
            name="A",
            location="town",
            goals=[
                Goal(
                    "g1",
                    "help a friend",
                    stages=["find the friend", "help the friend"],
                    stage_conditions=[
                        {"type": "at_same_location", "target_id": "b"},
                        {"type": "successful_action", "action_type": "help_person"},
                    ],
                    preferred_actions=["help_person"],
                )
            ],
        )
    )
    world.add_character(CharacterState(id="b", name="B", location="town"))
    world.add_relationship(RelationshipState("a", "b", trust=50.0))
    action = ActionCandidate(
        "help-1", "a", "help_person", targets=["b"], confidence=1.0, difficulty=0.1
    )

    first = SimulationEngine(seed=1).resolve(world, [action])[0]
    goal = world.characters["a"].goals[0]
    assert first.action_result.status == "success"
    assert goal.status == "active"
    assert goal.current_stage == 1
    assert goal.progress == 0.5

    second = SimulationEngine(seed=1).resolve(
        world,
        [ActionCandidate(
            "contact-2", "a", "contact_person", targets=["b"], confidence=1.0, difficulty=0.1
        )],
    )[0]
    assert second.action_result.status == "success"
    assert goal.status == "achieved"
    assert goal.progress == 1.0
    assert any(item.field == "current_stage" for item in first.consequences)
    assert any(item.field == "status" for item in second.consequences)


def test_freedom_destination_uses_actor_history_not_lexical_first_place():
    world = WorldState(world_id="travel", locations={"town", "a_place", "b_place"})
    world.add_character(
        CharacterState(
            id="a",
            name="A",
            location="town",
            values=["freedom"],
            human_condition=HumanCondition(desires={"freedom": 1.0}),
        )
    )
    kernel = MemoryKernel()
    for tick in (0, 1, 2):
        event = type("MemoryEvent", (), {
            "id": f"e{tick}",
            "tick": tick,
            "location": "a_place",
            "participants": ["a"],
        })()
        kernel.remember_event(world.memory_state, "a", event, "A visited a_place")

    pool = generate_action_pool(world, "a")
    travel = next(item for item in pool if item.action_type == "travel")
    assert travel.targets == ["b_place"]
    assert travel.metadata["travel_reason"] == "freedom_exploration"


def test_search_pressure_is_continuous_and_failed_search_changes_future_destination():
    world = WorldState(world_id="search", locations={"town", "temple", "harbor"})
    world.add_character(
        CharacterState(
            id="a",
            name="A",
            location="town",
            human_condition=HumanCondition(desires={"reconciliation": 1.0}),
        )
    )
    world.add_character(CharacterState(id="b", name="B", location="harbor"))
    world.add_relationship(RelationshipState("a", "b", trust=50.0))
    MemoryKernel().learn_fact(
        world.memory_state,
        "a",
        "location_seen:b:temple",
        tick=0,
        confidence=1.0,
    )

    pool = generate_action_pool(world, "a")
    search = next(item for item in pool if item.metadata.get("search_target") == "b")
    assert search.targets == ["temple"]

    event = SimulationEngine(seed=1).resolve(world, [search])[0]
    assert event.action_result.status == "success"
    assert "location_absent:b:temple" in world.characters["a"].knowledge

    next_pool = generate_action_pool(world, "a")
    next_search = next(item for item in next_pool if item.metadata.get("search_target") == "b")
    assert next_search.targets == ["harbor"]


def test_low_pressure_rest_is_distinct_from_no_candidate_idle():
    world = WorldState(world_id="rest", locations={"town"})
    world.add_character(
        CharacterState(
            id="a",
            name="A",
            location="town",
            goals=[Goal("g1", "help a friend", status="achieved")],
            human_condition=HumanCondition(),
        )
    )
    pool = generate_action_pool(world, "a")
    assert any(item.action_type == "rest" for item in pool)

    event = SimulationEngine(seed=1).resolve(
        world,
        [next(item for item in pool if item.action_type == "rest")],
    )[0]
    assert event.action_type == "rest"
    assert event.action_result.status == "success"
    assert "rests at town" in event.facts[0]


def test_continuous_pressure_generates_travel_below_old_threshold():
    world = WorldState(world_id="continuous", locations={"town", "road"})
    world.add_character(
        CharacterState(
            id="a",
            name="A",
            location="town",
            values=["freedom"],
            human_condition=HumanCondition(desires={"freedom": 1.0}),
        )
    )
    pool = generate_action_pool(world, "a")
    assert any(item.action_type == "travel" for item in pool)
