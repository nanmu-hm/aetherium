from engine.core.actions import generate_action_pool
from engine.core.models import ActionCandidate, CharacterState, RelationshipState, WorldState
from engine.core.human_condition import HumanCondition
from engine.core.preconditions import PreconditionEngine
from engine.core.simulation import SimulationEngine
from engine.genesis import run_genesis


def test_reconciliation_pressure_depends_on_relationship_state():
    def pool_for(trust: float, resentment: float) -> list[ActionCandidate]:
        world = WorldState(world_id="relationship-pressure", locations={"town"})
        world.add_character(
            CharacterState(
                id="a",
                name="A",
                location="town",
                human_condition=HumanCondition(desires={"reconciliation": 60.0}),
            )
        )
        world.add_character(CharacterState(id="b", name="B", location="town"))
        world.add_relationship(RelationshipState("a", "b", trust=trust, resentment=resentment))
        return generate_action_pool(world, "a")

    unresolved = pool_for(25.0, 35.0)
    settled = pool_for(95.0, 0.0)

    assert any(action.action_type == "contact_person" for action in unresolved)
    assert not any(action.action_type == "contact_person" for action in settled)


def test_help_is_physically_local_at_generation_and_authority_layers():
    world = WorldState(world_id="help-locality", locations={"town", "road"})
    world.add_character(
        CharacterState(
            id="a",
            name="A",
            location="town",
            values=["loyalty"],
            human_condition=HumanCondition(),
        )
    )
    world.add_character(
        CharacterState(
            id="b",
            name="B",
            location="road",
            emotions={"sorrow": 30.0},
        )
    )
    world.add_relationship(RelationshipState("a", "b", trust=40.0, loyalty=60.0))

    pool = generate_action_pool(world, "a")
    assert not any(action.action_type == "help_person" for action in pool)

    action = ActionCandidate("help", "a", "help_person", targets=["b"], confidence=1.0)
    result = PreconditionEngine().check(world, action)
    assert not result.satisfied
    assert "help target does not exist" not in result.reasons
    assert any("same location" in reason for reason in result.reasons)


def test_emotions_do_not_saturate_from_decay_alone():
    world = WorldState(world_id="emotion-decay", locations={"town"})
    world.add_character(CharacterState(id="a", name="A", location="town"))
    world.characters["a"].emotions.update(
        {"anger": 100.0, "resentment": 100.0, "fear": 100.0, "joy": 100.0}
    )

    engine = SimulationEngine(seed=7)
    for _ in range(50):
        engine.step(world)

    assert all(value < 100.0 for value in world.characters["a"].emotions.values())


def test_genesis_long_run_has_no_single_action_majority():
    for seed in (1, 2, 3, 7, 42):
        world = run_genesis(ticks=200, seed=seed)
        counts: dict[str, int] = {}
        for event in world.event_log:
            if not event.participants:
                continue
            action_type = event.action_type
            counts[action_type] = counts.get(action_type, 0) + 1
        total = sum(counts.values())
        assert total > 0
        assert max(counts.values()) / total <= 0.60


def test_reconciliation_growth_tracks_relationship_tension():
    def desire_after_one_tick(trust: float, resentment: float) -> float:
        world = WorldState(world_id="reconciliation-growth", locations={"town"})
        world.add_character(
            CharacterState(
                id="a",
                name="A",
                location="town",
                human_condition=HumanCondition(desires={"reconciliation": 50.0}),
            )
        )
        world.add_character(CharacterState(id="b", name="B", location="town"))
        world.add_relationship(RelationshipState("a", "b", trust=trust, resentment=resentment))
        engine = SimulationEngine(seed=1)
        engine._advance_human_pressures(world, [])
        return world.characters["a"].human_condition.desires["reconciliation"]

    unresolved = desire_after_one_tick(25.0, 35.0)
    settled = desire_after_one_tick(95.0, 0.0)
    assert unresolved > settled


def test_help_addresses_the_condition_that_triggered_it():
    world = WorldState(world_id="help-effect", locations={"town"})
    world.add_character(
        CharacterState(
            id="a",
            name="A",
            location="town",
            values=["loyalty"],
            human_condition=HumanCondition(),
        )
    )
    world.add_character(
        CharacterState(
            id="b",
            name="B",
            location="town",
            emotions={"sorrow": 30.0, "fear": 20.0},
            human_condition=HumanCondition(fatigue=20.0),
        )
    )
    world.add_relationship(RelationshipState("a", "b", trust=40.0, loyalty=60.0))
    engine = SimulationEngine(seed=1)
    action = ActionCandidate("help", "a", "help_person", targets=["b"], confidence=1.0)
    engine.resolve(world, [action])
    target = world.characters["b"]
    assert target.human_condition.fatigue == 5.0
    assert target.emotions["sorrow"] == 20.0
    assert target.emotions["fear"] == 10.0
