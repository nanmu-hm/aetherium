from engine.agents import (
    AgentContext,
    AgentStatus,
    CharacterAgent,
    ContinuityAgent,
    CriticAgent,
    DirectorOrchestrator,
    WriterAgent,
)
from engine.core.models import CharacterState, Consequence, Event, Goal, RelationshipState, WorldState
from engine.narrative.models import NarrativeScene, SceneExpressionPlan


def make_state():
    state = WorldState(world_id="writer-test", tick=5)
    state.locations.update({"town", "road"})
    state.add_character(
        CharacterState(
            id="a",
            name="A",
            location="town",
            goals=[Goal("g1", "leave town", priority=2.0)],
        )
    )
    state.add_character(CharacterState(id="b", name="B", location="town"))
    state.add_relationship(RelationshipState("a", "b", trust=60))
    state.event_log.append(
        Event(
            "e1",
            2,
            "t2",
            "town",
            ["a", "b"],
            ["action-2-a"],
            ["A speaks with B."],
            consequences=[Consequence("relationship", "a:b", "trust", 50, 60, "meeting")],
        )
    )
    state.event_log.append(
        Event(
            "e2",
            2,
            "t2",
            "town",
            ["a"],
            ["action-2-a"],
            ["A prepares to leave town."],
        )
    )
    return state


def make_context():
    return AgentContext.from_world(
        make_state(),
        narrative_state={
            "scenes": [
                {
                    "id": "scene-1",
                    "event_ids": ["e1", "e2"],
                    "participants": ["a", "b"],
                    "start_tick": 2,
                    "end_tick": 2,
                }
            ],
            "scene_expression": [
                {
                    "scene_id": "scene-1",
                    "viewpoint_character_id": "a",
                    "emphasis_mode": "dramatize",
                }
            ],
        },
    )


def test_writer_agent_generates_grounded_scene_draft():
    result = WriterAgent("scene-1").inspect(make_context())
    assert result.status == AgentStatus.OK
    assert "A speaks with B." in result.response
    assert "A prepares to leave town." in result.response
    assert result.proposals[0].kind.value == "narrative_edit"


def test_writer_draft_is_backed_by_source_event_ids():
    result = WriterAgent("scene-1").inspect(make_context())
    proposal = result.proposals[0]
    assert proposal.source_event_ids == ("e1", "e2")
    assert proposal.payload["source_event_ids"] == ["e1", "e2"]


def test_writer_uses_narrative_expression_plan():
    result = WriterAgent("scene-1").inspect(make_context())
    draft = result.proposals[0].payload
    assert draft["viewpoint_character_id"] == "a"
    assert draft["expression_mode"] == "dramatize"


def test_writer_does_not_modify_world_state():
    state = make_state()
    context = AgentContext.from_world(
        state,
        narrative_state={
            "scenes": [
                {"id": "scene-1", "event_ids": ["e1"], "participants": ["a", "b"]}
            ],
            "scene_expression": [],
        },
    )
    before = state.characters["a"].location
    WriterAgent("scene-1").respond(context, "keep the facts unchanged")
    assert state.characters["a"].location == before


def test_writer_requires_a_scene_selection():
    context = make_context()
    context.selected_event_ids = ()
    result = WriterAgent().inspect(context)
    assert result.status == AgentStatus.BLOCKED
    assert "No narrative scene selected" in result.diagnostics[0]


def test_writer_can_select_by_event_ids():
    context = make_context()
    result = WriterAgent().inspect(
        AgentContext(
            world_snapshot=context.world_snapshot,
            narrative_snapshot=context.narrative_snapshot,
            branch_id=context.branch_id,
            tick=context.tick,
            selected_event_ids=("e2",),
        )
    )
    assert result.status == AgentStatus.OK
    assert result.proposals[0].payload["scene_id"] == "scene-1"


def test_writer_blocks_unknown_event_reference():
    state = make_state()
    context = AgentContext.from_world(
        state,
        narrative_state={"scenes": [{"id": "bad", "event_ids": ["missing"]}]},
    )
    result = WriterAgent("bad").inspect(context)
    assert result.status == AgentStatus.BLOCKED
    assert "unknown event" in result.diagnostics[0].lower()


def test_writer_blocks_unknown_viewpoint():
    context = make_context()
    context.narrative_snapshot["scene_expression"][0]["viewpoint_character_id"] = "ghost"
    result = WriterAgent("scene-1").inspect(context)
    assert result.status == AgentStatus.BLOCKED
    assert "Viewpoint character does not exist" in result.diagnostics


def test_writer_result_passes_director_authority():
    director = DirectorOrchestrator()
    director.register(WriterAgent("scene-1"))
    run = director.inspect_one("writer", make_context())
    assert run.status == AgentStatus.OK
    assert run.result.proposals[0].kind.value == "narrative_edit"


def test_writer_chat_remains_non_authoritative():
    director = DirectorOrchestrator()
    writer = WriterAgent("scene-1")
    director.register(writer)
    run = director.respond_to("writer", make_context(), "Do not invent dialogue.")
    assert run.status == AgentStatus.OK
    assert "Do not invent dialogue." in run.result.response


def test_scene_quality_is_tracked():
    result = WriterAgent("scene-1").inspect(make_context())
    assert result.proposals[0].payload["quality_score"] == 1.0
