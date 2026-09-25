from engine.agents import (
    AgentContext,
    AgentContract,
    AgentProposal,
    AgentRegistry,
    AgentResult,
    AgentRole,
    AgentStatus,
    DirectorOrchestrator,
    ProposalKind,
)
from engine.core.models import CharacterState, WorldState


class FakeAgent:
    def __init__(
        self,
        agent_id="fake",
        role=AgentRole.CHARACTER,
        chat_enabled=True,
        response="ok",
        proposals=None,
    ):
        self.contract = AgentContract(
            agent_id,
            role,
            "test agent",
            read_scopes=frozenset({"world.read"}),
            write_scopes=frozenset({"recommendation.propose"}),
            chat_enabled=chat_enabled,
        )
        self.response = response
        self.proposals = list(proposals or [])
        self.last_context = None
        self.last_message = None

    def inspect(self, context):
        self.last_context = context
        return AgentResult(
            AgentStatus.OK,
            response=self.response,
            proposals=list(self.proposals),
        )

    def respond(self, context, message):
        self.last_context = context
        self.last_message = message
        return AgentResult(
            AgentStatus.OK,
            response=f"{self.response}:{message}",
            proposals=list(self.proposals),
        )


def make_context():
    state = WorldState(world_id="director-test", tick=4)
    state.add_character(CharacterState(id="c1", name="C1", location="town"))
    return AgentContext.from_world(state, mode="chat")


def test_registry_rejects_duplicate_agent_id():
    registry = AgentRegistry()
    registry.register(FakeAgent("a"))
    try:
        registry.register(FakeAgent("a"))
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate registration must fail")


def test_director_registers_and_inspects_agent():
    director = DirectorOrchestrator()
    agent = FakeAgent("character-1")
    director.register(agent)

    run = director.inspect_one("character-1", make_context())

    assert run.status == AgentStatus.OK
    assert run.result.response == "ok"
    assert agent.last_context is not None


def test_director_can_chat_with_any_registered_agent():
    director = DirectorOrchestrator()
    agent = FakeAgent("character-1", response="reply")
    director.register(agent)

    run = director.respond_to("character-1", make_context(), "What changed?")

    assert run.status == AgentStatus.OK
    assert run.result.response == "reply:What changed?"
    assert agent.last_message == "What changed?"


def test_disabled_chat_agent_is_blocked():
    director = DirectorOrchestrator()
    director.register(FakeAgent("silent", chat_enabled=False))

    run = director.respond_to("silent", make_context(), "hello")

    assert run.status == AgentStatus.BLOCKED
    assert run.result.diagnostics


def test_many_agents_are_inspected_in_declared_order():
    director = DirectorOrchestrator()
    director.register(FakeAgent("first"))
    director.register(FakeAgent("second"))

    runs = director.inspect_many(["second", "first"], make_context())

    assert [run.agent_id for run in runs] == ["second", "first"]


def test_role_selection_uses_contract_role():
    director = DirectorOrchestrator()
    director.register(FakeAgent("character-1", role=AgentRole.CHARACTER))
    director.register(FakeAgent("critic-1", role=AgentRole.CRITIC))

    runs = director.inspect_by_role(AgentRole.CRITIC, make_context())

    assert [run.agent_id for run in runs] == ["critic-1"]


def test_director_gates_unauthorized_proposal():
    proposal = AgentProposal(
        "p1",
        "fake",
        ProposalKind.STATE_INTERVENTION,
        "mutate",
        requires_approval=True,
    )
    director = DirectorOrchestrator()
    director.register(FakeAgent("fake", proposals=[proposal]))

    run = director.inspect_one("fake", make_context())

    assert run.status == AgentStatus.BLOCKED
    assert not run.result.proposals
    assert run.result.diagnostics


def test_director_preserves_authoritative_world_state():
    director = DirectorOrchestrator()
    agent = FakeAgent("fake")
    director.register(agent)

    context = make_context()
    original_name = context.world_snapshot["world"]["characters"]["c1"]["name"]
    director.respond_to("fake", context, "change it")

    assert context.world_snapshot["world"]["characters"]["c1"]["name"] == original_name


def test_unknown_agent_is_explicitly_reported():
    director = DirectorOrchestrator()

    try:
        director.inspect_one("missing", make_context())
    except KeyError as exc:
        assert "Unknown agent" in str(exc)
    else:
        raise AssertionError("unknown agent must fail explicitly")


def test_registry_ids_are_stable():
    registry = AgentRegistry()
    registry.register(FakeAgent("a"))
    registry.register(FakeAgent("b"))

    assert registry.ids() == ("a", "b")
