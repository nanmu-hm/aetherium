from engine.core.actions import ActionCandidate
from engine.core.decision import DecisionKernel
from engine.core.demo import build_demo_world


def test_default_decision_remains_fully_deterministic():
    world = build_demo_world()
    world.characters["lin"].goals.clear()
    pool = [
        ActionCandidate("a", "lin", "rest", confidence=1.0),
        ActionCandidate("b", "lin", "rest", confidence=0.5),
    ]

    first, evaluations = DecisionKernel(seed=7).choose(world, pool)
    second, repeat = DecisionKernel(seed=7).choose(world, pool)

    assert first is not None and second is not None
    assert first.id == second.id
    assert [item.selection_score for item in evaluations] == [item.selection_score for item in repeat]
    assert all(item.selection_score == item.utility for item in evaluations)


def test_decision_noise_is_seed_reproducible_and_bounded():
    world = build_demo_world()
    world.characters["lin"].decision_noise = 0.35
    world.characters["lin"].goals.clear()
    pool = [
        ActionCandidate("a", "lin", "rest", confidence=1.0),
        ActionCandidate("b", "lin", "rest", confidence=0.5),
    ]

    first, evaluations = DecisionKernel(seed=11).choose(world, pool)
    second, repeat = DecisionKernel(seed=11).choose(world, pool)

    assert first is not None and second is not None
    assert first.id == second.id
    for before, after in zip(evaluations, repeat):
        assert before.selection_score == after.selection_score
        assert abs(before.selection_score - before.utility) <= 0.35


def test_bounded_rationality_can_choose_a_non_optimal_action():
    world = build_demo_world()
    world.characters["lin"].decision_noise = 1.0
    world.characters["lin"].goals.clear()
    pool = [
        ActionCandidate("a", "lin", "rest", confidence=1.0),
        ActionCandidate("b", "lin", "rest", confidence=0.2),
    ]

    found = False
    for seed in range(1, 100):
        chosen, evaluations = DecisionKernel(seed=seed).choose(world, pool)
        utilities = {item.action_id: item.utility for item in evaluations}
        if chosen is not None and utilities[chosen.id] < max(utilities.values()):
            found = True
            break

    assert found


def test_risk_tolerance_reduces_perceived_risk_cost():
    world = build_demo_world()
    world.characters["lin"].goals.clear()
    action = ActionCandidate(
        "risky", "lin", "rest", confidence=0.8, risks=["social cost", "delay"]
    )

    cautious = DecisionKernel(seed=1).evaluate(world, action)
    world.characters["lin"].risk_tolerance = 1.0
    tolerant = DecisionKernel(seed=1).evaluate(world, action)

    assert tolerant.utility > cautious.utility
    assert "perceived risk" in tolerant.reasons
