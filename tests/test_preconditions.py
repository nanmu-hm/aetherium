from engine.core.models import ActionCandidate
from engine.core.demo import build_demo_world
from engine.core.preconditions import PreconditionEngine


def test_inactive_contact_target_is_blocked_before_resolution():
    world = build_demo_world()
    world.characters["mei"].status = "inactive"
    action = ActionCandidate("contact", "lin", "contact_person", targets=["mei"])

    result = PreconditionEngine().check(world, action)

    assert not result.satisfied
    assert "contact target is not active" in result.reasons


def test_same_location_travel_is_allowed_unless_explicitly_forbidden():
    world = build_demo_world()
    action = ActionCandidate("stay", "lin", "travel", targets=[world.characters["lin"].location])

    result = PreconditionEngine().check(world, action)

    assert result.satisfied


def test_destination_differs_precondition_can_forbid_same_location_travel():
    world = build_demo_world()
    action = ActionCandidate(
        "stay",
        "lin",
        "travel",
        targets=[world.characters["lin"].location],
        preconditions=["destination_differs"],
    )

    result = PreconditionEngine().check(world, action)

    assert not result.satisfied
    assert "destination must differ" in result.reasons[0]


def test_declared_ability_and_possession_preconditions_are_structured():
    world = build_demo_world()
    actor = world.characters["lin"]
    action = ActionCandidate(
        "open",
        "lin",
        "pursue_goal",
        preconditions=["requires_ability:lockpicking", "requires_possession:key:2"],
    )

    result = PreconditionEngine().check(world, action)
    assert not result.satisfied
    assert any("ability unavailable" in reason for reason in result.reasons)
    assert any("possession required" in reason for reason in result.reasons)

    actor.abilities["lockpicking"] = 0.8
    actor.possessions["key"] = 2
    result = PreconditionEngine().check(world, action)
    assert result.satisfied
