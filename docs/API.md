# Aetherium Product API

The Phase 9 product layer exposes simulation, observation, persistence browsing, agent rooms, and narrative drafting without creating a second authoritative world-state path.

## Start the server

After installing the project:

    python3 -m pip install -e .
    python3 -m uvicorn engine.api:app --reload

Open the visual workbench at /dashboard/ and the interactive API reference at /docs.

## Authority boundary

    HTTP
      |
      +-- World API ------> read-only WorldState
      |
      +-- Simulation API -> SimulationEngine -> WorldState
      |
      +-- Branch Browser -> read-only WorldRepository
      |
      +-- Agent Room -----> DirectorOrchestrator -> detached AgentContext
      |
      +-- Novel Editor ---> Writer / Draft / Human Approval / Narrative Canon
      |
      +-- Dashboard ------> read-only view models

Agents receive detached snapshots. Narrative observation and writing do not mutate authoritative world state. The Branch Browser does not expose arbitrary branch mutation.

## Endpoint groups

### World and Dashboard

- GET /api/world
- GET /api/world/summary
- GET /api/world/characters
- GET /api/world/relationships
- GET /api/world/events?limit=50
- GET /api/dashboard
- GET /dashboard/

### Simulation

- POST /api/simulation/step
- POST /api/simulation/run

### Branch Browser

- GET /api/branches
- GET /api/branches/{branch_id}
- GET /api/branches/{branch_id}/checkpoints

Branch mutation remains behind the existing persistence/intervention mechanisms rather than being exposed as arbitrary UI writes.

### Agent Rooms

- GET /api/agents
- GET /api/agent-rooms
- POST /api/agents/{agent_id}/inspect
- POST /api/agents/{agent_id}/chat

The workbench keeps conversation local to the current browser session; each request is evaluated against a fresh detached world snapshot.

### Narrative and Novel Editor

- GET /api/narrative
- GET /api/narrative/scenes
- GET /api/narrative/discoveries
- GET /api/narrative/drafts
- POST /api/narrative/drafts
- GET /api/narrative/drafts/{draft_id}
- GET /api/narrative/drafts/{draft_id}/versions
- POST /api/narrative/drafts/{draft_id}/revise
- POST /api/narrative/drafts/{draft_id}/approve
- POST /api/narrative/drafts/{draft_id}/reject
- GET /api/narrative/canon

The editor preserves scene, participant, branch, tick, and source-event provenance while permitting prose/title revision before approval.
