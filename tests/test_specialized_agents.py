from engine.agents import (
    AgentContext,
    AgentStatus,
    CharacterAgent,
    ContinuityAgent,
    CriticAgent,
    DirectorOrchestrator,
)
from engine.core.models import CharacterState, Event, Goal, RelationshipState, WorldState


def make_state():
    state = WorldState(world_id="specialized", tick=5)
    state.locations.update({"town", "road"})
    state.add_character(
        CharacterState(
            id="a",
            name="A",
            location="town",
            goals=[Goal("g1", "leave town", priority=2.0)],
            emotions={"hope": 8.0, "fear": 3.0},
        )
    )
    state.add_character(CharacterState(id="b", name="B", location="town"))
    state.add_relationship(RelationshipState("a", "b", trust=60))
    state.event_log.append(
        Event("e1", 2, "t2", "town", ["a", "b"], ["action-2-a"], ["A speaks with B."])
    )
    return state


def test_character_agent_has_unique_identity():
    agent = CharacterAgent("a")
    assert agent.contract.agent_id == "character:a"


def test_character_agent_reads_goal_and_emotion():
    result = CharacterAgent("a").inspect(AgentContext.from_world(make_state()))
    assert result.status == AgentStatus.OK
    assert "leave town" in result.response
    assert "hope" in result.response
    assert result.proposals[0].payload["goal_id"] == "g1"


def test_character_agent_does_not_mutate_world_snapshot():
    state = make_state()
    context = AgentContext.from_world(state)
    before = context.world_snapshot["world"]["characters"]["a"]["location"]
    CharacterAgent("a").respond(context, "Why are you staying?")
    assert context.world_snapshot["world"]["characters"]["a"]["location"] == before
    assert state.characters["a"].location == "town"


def test_character_agent_reports_highest_priority_goal_in_both_channels():
    result = CharacterAgent("a").inspect(AgentContext.from_world(make_state()))
    assert "Highest-priority active goal: leave town" in result.response
    assert result.proposals[0].summary.endswith("leave town.")


def test_unknown_character_agent_blocks():
    result = CharacterAgent("ghost").inspect(AgentContext.from_world(make_state()))
    assert result.status == AgentStatus.BLOCKED
    assert "Unknown character" in result.diagnostics[0]


def test_continuity_agent_accepts_valid_state():
    result = ContinuityAgent().inspect(AgentContext.from_world(make_state()))
    assert result.status == AgentStatus.OK


def test_continuity_agent_detects_missing_location():
    state = make_state()
    state.characters["a"].location = "missing-place"
    result = ContinuityAgent().inspect(AgentContext.from_world(state))
    assert result.status == AgentStatus.BLOCKED
    assert any("unknown location" in item for item in result.diagnostics)


def test_continuity_agent_detects_duplicate_event():
    state = make_state()
    state.event_log.append(state.event_log[0])
    result = ContinuityAgent().inspect(AgentContext.from_world(state))
    assert result.status == AgentStatus.BLOCKED
    assert any("Duplicate event id" in item for item in result.diagnostics)


def test_continuity_agent_detects_future_event():
    state = make_state()
    state.event_log.append(
        Event("future", 9, "future", "town", ["a"], [], ["future event"])
    )
    result = ContinuityAgent().inspect(AgentContext.from_world(state))
    assert result.status == AgentStatus.BLOCKED
    assert any("ahead of world tick" in item for item in result.diagnostics)


def test_critic_agent_returns_non_authoritative_review():
    result = CriticAgent().inspect(AgentContext.from_world(make_state()))
    assert result.status == AgentStatus.OK
    assert result.proposals == []


def test_critic_agent_flags_concentrated_history():
    state = make_state()
    for index in range(4):
        state.event_log.append(
            Event(
                f"e{index + 2}",
                index + 2,
                f"t{index + 2}",
                "town",
                ["a"],
                [],
                [f"A does thing {index}."],
            )
        )
    result = CriticAgent().inspect(AgentContext.from_world(state))
    assert result.status == AgentStatus.OK
    assert any("concentration" in item.lower() for item in result.diagnostics)
    assert result.proposals


def test_director_can_run_specialized_agents_together():
    director = DirectorOrchestrator()
    director.register(CharacterAgent("a"))
    director.register(ContinuityAgent())
    director.register(CriticAgent())

    runs = director.inspect_many(
        ["character:a", "continuity", "critic"],
        AgentContext.from_world(make_state()),
    )
    assert [run.status for run in runs] == [
        AgentStatus.OK,
        AgentStatus.OK,
        AgentStatus.OK,
    ]
