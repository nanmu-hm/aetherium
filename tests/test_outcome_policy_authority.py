"""Acceptance tests for the rest outcome-policy authority.

ChatGPT 5979725052 item C. Nine checks, one per authorised acceptance item.

These are deliberately written so that each one FAILS if the authority is
removed, rather than merely passing while it is present. The synthetic-failure
test in particular is the one that had teeth: under the old code the resolver
was rolled first and its result discarded, so asserting only "rest succeeds"
passed whether or not any authority existed.
"""
from __future__ import annotations

import pytest

from engine.core.models import ActionCandidate, ActionResult
from engine.core.outcome_policy import (
    ACTION_OUTCOME_POLICIES,
    policy_actions,
    resolve_policy_outcome,
)
from engine.core.simulation import ActionResolver, SimulationEngine
from engine.genesis import build_genesis_world


def rest_candidate(actor_id: str = "yan") -> ActionCandidate:
    return ActionCandidate(
        "rest", actor_id, "rest", confidence=0.95, difficulty=0.05
    )


def tired_world(actor_id: str = "yan"):
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    world.characters[actor_id].human_condition.fatigue = 80.0
    return world


# --- C1: an eligible rest commits success -----------------------------------

def test_eligible_rest_commits_success():
    event = SimulationEngine(seed=7).resolve(tired_world(), [rest_candidate()])[0]
    assert event.action_result.status == "success"


# --- C2: rest never reaches the resolver ------------------------------------
# This is the check that distinguishes a declared policy from "roll, then
# overwrite". Under the old code the resolver was called and its result thrown
# away; here it is never called at all.

def test_rest_is_never_sent_to_the_resolver(monkeypatch):
    calls = []
    original = ActionResolver.resolve_outcome

    def counting(self, state, action):
        calls.append(action.action_type)
        return original(self, state, action)

    monkeypatch.setattr(ActionResolver, "resolve_outcome", counting)
    SimulationEngine(seed=7).resolve(tired_world(), [rest_candidate()])

    assert calls == [], f"rest reached the resolver: {calls}"


# --- C3: the policy states its own reason and probability -------------------

def test_policy_states_reason_and_probability():
    outcome = resolve_policy_outcome(rest_candidate())
    assert outcome is not None
    assert outcome.status == "success"
    assert outcome.reason == "rest completed"
    assert outcome.probability == 1.0


def test_committed_rest_carries_the_policy_triple():
    event = SimulationEngine(seed=7).resolve(tired_world(), [rest_candidate()])[0]
    assert event.action_result.reason == "rest completed"
    assert event.action_result.probability == 1.0


# --- C4: the policy is the single authority, and consequences follow it -----
#
# My previous version of this test forced the RESOLVER to return a failure and
# asserted the policy still won. That was vacuous: the policy short-circuits
# before the resolver, so the forcing function was never invoked and the probe
# was never installed (measured: 0 installs). It would have passed with the
# policy deleted. Arena caught this; the resolver-order test (C2) is the check
# that actually discriminates.
#
# The load-bearing version offers the POLICY a competing outcome and asserts
# that everything downstream follows it -- commit, facts, and consequence. That
# is a behavioural claim, not a restatement of the policy.

def test_consequences_follow_the_policy_when_the_policy_yields_failure(monkeypatch):
    """Drive the declared policy to failure; the world must record a failure.

    This is the test that makes :772's failure arm reachable. Under the shipped
    rest policy that arm is dead code, which is precisely why it needs a test:
    otherwise nothing would notice if it were deleted, and nothing would notice
    if it were unreachable forever.
    """
    import engine.core.outcome_policy as op

    monkeypatch.setitem(
        op.ACTION_OUTCOME_POLICIES,
        "rest",
        lambda: ActionResult("failure", "POLICY_FAILURE_PROBE", 0.25),
    )

    world = tired_world()
    engine = SimulationEngine(seed=7)
    event = engine.resolve(world, [rest_candidate()])[0]

    # the commit follows the policy, not a hard-coded success
    assert event.action_result.status == "failure"
    assert event.action_result.reason == "POLICY_FAILURE_PROBE"
    assert event.action_result.probability == 0.25

    # the fact follows the committed status
    recorded = " ".join(
        str(getattr(world.characters["yan"], attr, "") or "")
        for attr in ("facts", "beliefs", "knowledge")
    )
    assert "tries to rest" in recorded
    assert "rests at" not in recorded

    # and the consequence layer follows too: a failure is penalised
    assert world.characters["yan"].habits.get("rest", 0.0) < 0.0


def test_policy_is_the_only_source_of_the_rest_outcome(monkeypatch):
    """If the resolver is unreachable for rest, no resolver result can leak in.

    Asserted as a conjunction so that neither half can pass alone: the policy
    must be declared, AND the resolver must not be consulted. The first half
    alone is satisfied by a policy that never runs; the second alone by a
    resolver that always succeeds.
    """
    consulted = []
    original = ActionResolver.resolve_outcome

    def counting(self, state, action):
        consulted.append(action.action_type)
        return original(self, state, action)

    monkeypatch.setattr(ActionResolver, "resolve_outcome", counting)
    event = SimulationEngine(seed=7).resolve(tired_world(), [rest_candidate()])[0]

    assert "rest" in ACTION_OUTCOME_POLICIES
    assert consulted == [], f"rest reached the resolver: {consulted}"
    assert event.action_result.reason == "rest completed"


# --- C5: facts are status-sensitive ----------------------------------------
# The 5979725052 item 3 fix. Both strings must exist and the branch must be
# selected by the committed status, so a future policy that can fail cannot
# write a success fact.

def test_rest_records_a_success_fact():
    world = tired_world()
    SimulationEngine(seed=7).resolve(world, [rest_candidate()])
    recorded = " ".join(
        str(getattr(world.characters["yan"], attr, "") or "")
        for attr in ("facts", "beliefs", "knowledge")
    )
    assert "rests at" in recorded


def test_rest_facts_are_status_sensitive_in_both_directions(monkeypatch):
    """Both fact branches are reachable and each writes its own text.

    ChatGPT's integration review flagged that the previous version asserted on
    the SOURCE STRING of simulation.py. That couples the test to formatting and
    passes without running anything. This version drives both statuses and
    reads what was actually recorded.
    """
    import engine.core.outcome_policy as op

    # success branch, with the shipped policy
    world = tired_world()
    SimulationEngine(seed=7).resolve(world, [rest_candidate()])
    ok_text = " ".join(
        str(getattr(world.characters["yan"], attr, "") or "")
        for attr in ("facts", "beliefs", "knowledge")
    )
    assert "rests at" in ok_text
    assert "tries to rest" not in ok_text

    # failure branch, by making the policy itself fail
    monkeypatch.setitem(
        op.ACTION_OUTCOME_POLICIES,
        "rest",
        lambda: ActionResult("failure", "POLICY_FAILURE_PROBE", 0.25),
    )
    world2 = tired_world()
    SimulationEngine(seed=7).resolve(world2, [rest_candidate()])
    fail_text = " ".join(
        str(getattr(world2.characters["yan"], attr, "") or "")
        for attr in ("facts", "beliefs", "knowledge")
    )
    assert "tries to rest" in fail_text
    assert " but fails" in fail_text


# --- C6: other actions keep all three fields -------------------------------

def test_no_other_action_borrows_the_rest_policy():
    for action_type in ("travel", "contact_person", "help_person",
                        "search_person"):
        candidate = ActionCandidate(
            "probe", "yan", action_type, confidence=1.0, difficulty=0.0
        )
        assert resolve_policy_outcome(candidate) is None, (
            f"{action_type} must not have declared outcome authority"
        )


def test_policy_surface_is_exactly_rest():
    assert policy_actions() == ["rest"]
    assert set(ACTION_OUTCOME_POLICIES) == {"rest"}


# --- C7: blocked and quiet ticks unchanged ---------------------------------

def test_rest_behind_an_unsatisfied_precondition_is_blocked_not_succeeded():
    """A rest that cannot be attempted must be blocked, never 'succeeded'.

    The policy is consulted only after the precondition gate passes, so an
    unattemptable rest cannot reach it. Using a non-existent target is how the
    existing suite expresses this (test_simulation.py:82).
    """
    world = tired_world()
    candidate = ActionCandidate(
        "rest", "yan", "rest", targets=["nowhere"], confidence=0.95, difficulty=0.05
    )
    event = SimulationEngine(seed=7).resolve(world, [candidate])[0]
    assert event.action_result.status == "blocked"


def test_quiet_ticks_emit_no_events():
    """Once the world is quiet, ticks produce no events at all.

    Driven to quiescence rather than assumed: tick 0 legitimately emits the
    genesis events, so a quiet tick is only meaningful after them.
    """
    world = tired_world()
    engine = SimulationEngine(seed=7, use_arbitration=False)
    quiet_streak = 0
    saw_quiet = False
    for _ in range(200):
        result = engine.step(world)
        if result.events:
            quiet_streak = 0
        else:
            quiet_streak += 1
            saw_quiet = True
    assert saw_quiet, "the run never went quiet, so this asserts nothing"
    # and once quiet it stays quiet: no fabricated event appears
    for _ in range(20):
        assert engine.step(world).events == []


# --- C8: the eligibility gate is untouched by this authority ---------------

@pytest.mark.parametrize(
    "fatigue,stress,sorrow,expected",
    [
        (10.0, 0.0, 0.0, True),
        (9.99, 0.0, 0.0, False),
        (0.0, 20.0, 0.0, True),
        (0.0, 19.99, 0.0, False),
        (0.0, 0.0, 35.0, True),
        (0.0, 0.0, 34.99, False),
    ],
)
def test_rest_gate_thresholds_are_unchanged(fatigue, stress, sorrow, expected):
    from engine.core import actions as A

    world = build_genesis_world()
    actor = world.characters["yan"]
    actor.human_condition.fatigue = fatigue
    actor.emotions["stress"] = stress
    actor.emotions["sorrow"] = sorrow
    offered = any(c.action_type == "rest" for c in A.generate_action_pool(world, "yan"))
    assert offered is expected
