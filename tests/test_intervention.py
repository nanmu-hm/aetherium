from engine.core.models import CharacterState, Event, Goal, RelationshipState, WorldState
from engine.intervention.models import InterventionRequest
from engine.intervention.planner import InterventionPlanner


def make_state():
    state = WorldState(world_id="agency", tick=10)
    state.locations.add("town")
    state.add_character(
        CharacterState(
            id="a",
            name="A",
            location="town",
            goals=[Goal("g1", "leave town", priority=1.0)],
        )
    )
    state.add_character(CharacterState(id="b", name="B", location="town"))
    state.add_relationship(RelationshipState("a", "b", trust=50))
    state.event_log.append(
        Event("e1", 3, "t3", "town", ["a", "b"], [], ["A meets B."])
    )
    return state


def test_historical_rewrite_requires_fork():
    request = InterventionRequest("i1", "historical_rewrite", "characters.a.location", "road", 3)
    plan = InterventionPlanner().plan(make_state(), request)
    assert plan.action == "fork"
    assert plan.impact.affected_count > 0


def test_future_only_change_can_apply():
    request = InterventionRequest("i2", "future_only", "characters.a.location", "road", 11)
    plan = InterventionPlanner().plan(make_state(), request)
    assert plan.action == "apply"
    assert not plan.conflicts


def test_narrative_only_change_does_not_require_world_fork():
    request = InterventionRequest("i3", "narrative_only", "world.presentation.title", "A New Title")
    plan = InterventionPlanner().plan(make_state(), request)
    assert plan.action == "apply"


def test_world_rule_change_requires_fork():
    request = InterventionRequest("i4", "world_rule", "world.travel_time", 4)
    plan = InterventionPlanner().plan(make_state(), request)
    assert plan.action == "fork"


def test_unknown_character_is_rejected():
    request = InterventionRequest("i5", "future_only", "characters.ghost.location", "road", 11)
    plan = InterventionPlanner().plan(make_state(), request)
    assert plan.action == "reject"
    assert plan.conflicts[0].category == "missing_target"


def test_future_only_past_tick_is_rejected():
    request = InterventionRequest("i6", "future_only", "characters.a.location", "road", 9)
    plan = InterventionPlanner().plan(make_state(), request)
    assert plan.action == "reject"


def test_historical_rewrite_without_tick_is_rejected():
    request = InterventionRequest("i7", "historical_rewrite", "characters.a.location", "road")
    plan = InterventionPlanner().plan(make_state(), request)
    assert plan.action == "reject"


def test_relationship_impact_is_reported():
    request = InterventionRequest("i8", "future_only", "relationships.a:b.trust", 80, 11)
    plan = InterventionPlanner().plan(make_state(), request)
    assert plan.action == "apply"
    assert any(item.category == "relationship" for item in plan.impact.items)
