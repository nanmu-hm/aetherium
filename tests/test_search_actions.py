from engine.core.actions import generate_action_pool
from engine.core.demo import build_demo_world
from engine.core.models import RelationshipState


def test_search_is_not_generated_when_target_is_already_at_actor_location():
    world = build_demo_world()
    world.characters["lin"].goals[0].status = "achieved"
    world.characters["lin"].human_condition.desires["reconciliation"] = 90.0
    world.add_relationship(RelationshipState("lin", "mei", trust=20.0))
    world.locations.update({"harbor", "temple"})
    world.characters["lin"].location = "town"
    world.characters["mei"].location = "town"

    pool = generate_action_pool(world, "lin")

    assert not any(
        action.action_type == "travel"
        and action.id.endswith("-search-mei")
        for action in pool
    )
    assert any(
        action.action_type == "contact_person"
        and action.targets == ["mei"]
        for action in pool
    )
