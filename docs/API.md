# Aetherium Product API

Phase 9 begins with a backend product layer. The API exposes simulation and observation systems without creating a second authoritative world-state path.

## Start the server

After installing the project:

    python3 -m pip install -e .
    python3 -m uvicorn engine.api:app --reload

The interactive OpenAPI page is available at /docs.

## Authority boundary

The API follows this direction:

    HTTP
      |
      +-- World API ------> read-only WorldState
      |
      +-- Simulation API -> SimulationEngine -> WorldState
      |
      +-- Agent API ------> DirectorOrchestrator -> detached AgentContext
      |
      +-- Narrative API --> NarrativeObserver / Writer / Approval

Agents do not receive direct access to the authoritative WorldState. They receive detached snapshots. Narrative observation and writing do not mutate the simulation state.

## Endpoint groups

### World

- GET /api/world
- GET /api/world/summary
- GET /api/world/characters
- GET /api/world/relationships
- GET /api/world/events?limit=50

### Simulation

- POST /api/simulation/step — advance the world through SimulationEngine.step().
- POST /api/simulation/run — execute the safe autonomous controller.

### Agents

- GET /api/agents
- POST /api/agents/{agent_id}/inspect
- POST /api/agents/{agent_id}/chat

### Narrative

- GET /api/narrative
- GET /api/narrative/scenes
- GET /api/narrative/discoveries
- POST /api/narrative/drafts
- GET /api/narrative/drafts/{draft_id}
- GET /api/narrative/drafts/{draft_id}/versions
- POST /api/narrative/drafts/{draft_id}/revise
- POST /api/narrative/drafts/{draft_id}/approve
- POST /api/narrative/drafts/{draft_id}/reject
- GET /api/narrative/canon

## Intentional limitation

This first API block is an orchestration layer, not a web editor. It does not expose arbitrary world editing or model-provider secrets. Branch mutation remains behind the existing intervention rules.
