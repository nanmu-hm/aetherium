"""FastAPI product layer for the Aetherium world engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .agents import (
    AgentContext,
    AgentRegistry,
    AutonomousRunConfig,
    AutonomousRunController,
    CharacterAgent,
    ContinuityAgent,
    CriticAgent,
    DirectorOrchestrator,
    HumanApprovalService,
    WriterAgent,
)
from .core.demo import build_demo_world
from .core.models import WorldState
from .core.simulation import SimulationEngine, SimulationResult
from .narrative.observer import NarrativeObserver
from .persistence.codec import world_to_dict
from .persistence.narrative import NarrativeCanonLedger
from .persistence.repository import WorldRepository


def _jsonable(value: Any) -> Any:
    """Convert Aetherium dataclasses and enums into JSON-safe primitives."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset, tuple, list)):
        return [_jsonable(item) for item in value]
    return value


class TickRequest(BaseModel):
    ticks: int = Field(default=1, ge=1, le=100)


class RunRequest(BaseModel):
    max_ticks: int = Field(default=20, ge=1, le=1000)
    checkpoint_every: int = Field(default=5, ge=0, le=1000)
    max_validation_errors: int = Field(default=1, ge=0, le=100)
    stop_on_story_discovery: bool = False
    story_score_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    checkpoint_before_run: bool = True


class AgentContextRequest(BaseModel):
    selected_event_ids: list[str] = Field(default_factory=list)
    mode: str = "interactive"


class AgentChatRequest(AgentContextRequest):
    message: str = Field(min_length=1, max_length=4000)


class DraftRequest(BaseModel):
    scene_id: str | None = None
    selected_event_ids: list[str] = Field(default_factory=list)


class DraftRevisionRequest(BaseModel):
    prose: str = Field(min_length=1)
    title: str | None = None
    edited_by: str = "user"


class DraftDecisionRequest(BaseModel):
    version: int | None = Field(default=None, ge=1)
    approved_by: str = "user"


@dataclass
class AetheriumApplication:
    """Own the product-layer dependencies while preserving core authority boundaries."""

    state: WorldState
    simulation: SimulationEngine
    observer: NarrativeObserver
    director: DirectorOrchestrator
    approval: HumanApprovalService
    autonomous: AutonomousRunController
    narrative_state: Any | None = None

    @classmethod
    def create(
        cls,
        *,
        state: WorldState | None = None,
        seed: int = 42,
        data_dir: str | Path | None = ".aetherium",
        canon_path: str | Path | None = None,
    ) -> "AetheriumApplication":
        state = state or build_demo_world()
        simulation = SimulationEngine(seed=seed)
        observer = NarrativeObserver()
        registry = AgentRegistry()
        director = DirectorOrchestrator(registry=registry)

        director.register(ContinuityAgent())
        director.register(CriticAgent())
        director.register(WriterAgent())
        for character_id in sorted(state.characters):
            director.register(CharacterAgent(character_id))

        repository = WorldRepository(data_dir) if data_dir is not None else None
        resolved_canon = canon_path
        if resolved_canon is None and data_dir is not None:
            resolved_canon = Path(data_dir) / "narrative-canon.jsonl"
        canon_ledger = NarrativeCanonLedger(resolved_canon) if resolved_canon is not None else None
        approval = HumanApprovalService(canon_ledger=canon_ledger)
        autonomous = AutonomousRunController(
            simulation=simulation,
            observer=observer,
            repository=repository,
        )

        application = cls(
            state=state,
            simulation=simulation,
            observer=observer,
            director=director,
            approval=approval,
            autonomous=autonomous,
        )
        application.refresh_narrative([])
        return application

    def refresh_agents(self) -> None:
        for character_id in sorted(self.state.characters):
            agent_id = f"character:{character_id}"
            if agent_id not in self.director.registry.agents:
                self.director.register(CharacterAgent(character_id))

    def refresh_narrative(self, events: list[Any]) -> Any:
        self.narrative_state = self.observer.observe(self.state, events)
        return self.narrative_state

    def context(
        self,
        *,
        selected_event_ids: list[str] | tuple[str, ...] = (),
        mode: str = "interactive",
        user_message: str = "",
    ) -> AgentContext:
        self.refresh_agents()
        return AgentContext.from_world(
            self.state,
            narrative_state=self.narrative_state,
            selected_event_ids=selected_event_ids,
            mode=mode,
            user_message=user_message,
        )

    def step(self, ticks: int) -> list[Any]:
        events: list[Any] = []
        for _ in range(ticks):
            result: SimulationResult = self.simulation.step(self.state)
            events.extend(result.events)
            if result.validation_errors:
                raise ValueError("; ".join(result.validation_errors))
        self.refresh_narrative(events)
        self.refresh_agents()
        return events

    def run(self, request: RunRequest) -> Any:
        config = AutonomousRunConfig(
            max_ticks=request.max_ticks,
            checkpoint_every=request.checkpoint_every,
            max_validation_errors=request.max_validation_errors,
            stop_on_story_discovery=request.stop_on_story_discovery,
            story_score_threshold=request.story_score_threshold,
            checkpoint_before_run=request.checkpoint_before_run,
        )
        report = self.autonomous.run(self.state, config)
        self.refresh_narrative(report.events)
        self.refresh_agents()
        return report


def create_app(application: AetheriumApplication | None = None) -> FastAPI:
    application = application or AetheriumApplication.create()
    api = FastAPI(
        title="Aetherium API",
        version="0.1.0",
        description="Product-layer API for world simulation, agents, narrative observation, and draft approval.",
    )
    api.state.aetherium = application

    @api.get("/")
    def root() -> dict[str, Any]:
        return {
            "name": "aetherium",
            "api": "/api",
            "world_id": application.state.world_id,
            "tick": application.state.tick,
            "branch": application.state.active_branch,
        }

    @api.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "tick": application.state.tick}

    @api.get("/api/world")
    def get_world() -> dict[str, Any]:
        return _jsonable(world_to_dict(application.state))

    @api.get("/api/world/summary")
    def get_world_summary() -> dict[str, Any]:
        return {
            "world_id": application.state.world_id,
            "tick": application.state.tick,
            "timestamp": application.state.timestamp,
            "active_branch": application.state.active_branch,
            "locations": sorted(application.state.locations),
            "character_count": len(application.state.characters),
            "relationship_count": len(application.state.relationships),
            "faction_count": len(application.state.factions),
            "event_count": len(application.state.event_log),
        }

    @api.get("/api/world/characters")
    def get_characters() -> list[dict[str, Any]]:
        return [
            _jsonable(character)
            for character in application.state.characters.values()
        ]

    @api.get("/api/world/relationships")
    def get_relationships() -> list[dict[str, Any]]:
        return [
            _jsonable(relationship)
            for relationship in application.state.relationships.values()
        ]

    @api.get("/api/world/events")
    def get_events(limit: int = 50) -> list[dict[str, Any]]:
        if limit < 1 or limit > 500:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
        return [
            _jsonable(event)
            for event in application.state.event_log[-limit:]
        ]

    @api.post("/api/simulation/step")
    def simulation_step(request: TickRequest) -> dict[str, Any]:
        try:
            events = application.step(request.ticks)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "ticks_run": request.ticks,
            "tick": application.state.tick,
            "events": _jsonable(events),
            "narrative": _jsonable(application.narrative_state),
        }

    @api.post("/api/simulation/run")
    def simulation_run(request: RunRequest) -> dict[str, Any]:
        try:
            report = application.run(request)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _jsonable(report)

    @api.get("/api/agents")
    def list_agents() -> list[dict[str, Any]]:
        return [
            _jsonable(agent.contract)
            for agent in application.director.registry.agents.values()
        ]

    @api.post("/api/agents/{agent_id}/inspect")
    def inspect_agent(agent_id: str, request: AgentContextRequest) -> dict[str, Any]:
        if agent_id not in application.director.registry.agents:
            raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_id}")
        run = application.director.inspect_one(
            agent_id,
            application.context(
                selected_event_ids=request.selected_event_ids,
                mode=request.mode,
            ),
        )
        return _jsonable(run)

    @api.post("/api/agents/{agent_id}/chat")
    def chat_with_agent(agent_id: str, request: AgentChatRequest) -> dict[str, Any]:
        if agent_id not in application.director.registry.agents:
            raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_id}")
        run = application.director.respond_to(
            agent_id,
            application.context(
                selected_event_ids=request.selected_event_ids,
                mode=request.mode,
                user_message=request.message,
            ),
            request.message,
        )
        return _jsonable(run)

    @api.get("/api/narrative")
    def get_narrative() -> Any:
        if application.narrative_state is None:
            application.refresh_narrative([])
        return _jsonable(application.narrative_state)

    @api.get("/api/narrative/scenes")
    def get_narrative_scenes() -> list[dict[str, Any]]:
        if application.narrative_state is None:
            application.refresh_narrative([])
        return _jsonable(application.narrative_state.scenes)

    @api.get("/api/narrative/discoveries")
    def get_story_discoveries() -> list[dict[str, Any]]:
        if application.narrative_state is None:
            application.refresh_narrative([])
        return _jsonable(application.narrative_state.story_discoveries)

    @api.post("/api/narrative/drafts")
    def create_narrative_draft(request: DraftRequest) -> dict[str, Any]:
        scene_id = request.scene_id
        context = application.context(
            selected_event_ids=request.selected_event_ids,
            mode="draft",
        )
        writer_id = "writer"
        if scene_id:
            writer = WriterAgent(scene_id=scene_id)
            writer_id = writer.contract.agent_id
            if writer_id not in application.director.registry.agents:
                application.director.register(writer)
        run = application.director.inspect_one(writer_id, context)
        if run.status.value != "ok" or not run.result.proposals:
            raise HTTPException(
                status_code=409,
                detail=run.result.diagnostics or ["Writer did not produce a narrative proposal."],
            )
        proposal = next(
            (item for item in run.result.proposals if item.kind.value == "narrative_edit"),
            None,
        )
        if proposal is None:
            raise HTTPException(status_code=409, detail="Writer result did not contain a narrative draft.")
        draft = application.approval.submit_proposal(
            proposal,
            branch_id=application.state.active_branch,
            tick=application.state.tick,
        )
        return _jsonable(draft)

    @api.get("/api/narrative/drafts/{draft_id}")
    def get_narrative_draft(draft_id: str, version: int | None = None) -> dict[str, Any]:
        try:
            draft = application.approval.store.get(draft_id, version)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Narrative draft not found.") from exc
        return _jsonable(draft)

    @api.get("/api/narrative/drafts/{draft_id}/versions")
    def get_narrative_draft_versions(draft_id: str) -> list[dict[str, Any]]:
        try:
            versions = application.approval.store.versions(draft_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Narrative draft not found.") from exc
        if not versions:
            raise HTTPException(status_code=404, detail="Narrative draft not found.")
        return _jsonable(versions)

    @api.post("/api/narrative/drafts/{draft_id}/revise")
    def revise_narrative_draft(
        draft_id: str,
        request: DraftRevisionRequest,
    ) -> dict[str, Any]:
        try:
            draft = application.approval.revise(
                draft_id,
                prose=request.prose,
                title=request.title,
                edited_by=request.edited_by,
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _jsonable(draft)

    @api.post("/api/narrative/drafts/{draft_id}/approve")
    def approve_narrative_draft(
        draft_id: str,
        request: DraftDecisionRequest,
    ) -> dict[str, Any]:
        try:
            decision = application.approval.approve(
                draft_id,
                approved_by=request.approved_by,
                version=request.version,
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _jsonable(decision)

    @api.post("/api/narrative/drafts/{draft_id}/reject")
    def reject_narrative_draft(
        draft_id: str,
        request: DraftDecisionRequest,
    ) -> dict[str, Any]:
        try:
            decision = application.approval.reject(
                draft_id,
                version=request.version,
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _jsonable(decision)

    @api.get("/api/narrative/canon")
    def list_narrative_canon(branch: str | None = None) -> list[dict[str, Any]]:
        ledger = application.approval.canon_ledger
        if ledger is None:
            return []
        return _jsonable(ledger.list(branch_id=branch))

    return api


app = create_app()
