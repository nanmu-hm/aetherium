# Agent Orchestration

Aetherium now has a DirectorOrchestrator and AgentRegistry above the agent contract layer.

## Registry

Agents are registered by their contract-defined agent_id. Duplicate IDs are rejected. The registry can select agents by explicit ID or by AgentRole.

## Director

The DirectorOrchestrator provides three non-authoritative operations:

- inspect_one() — ask one agent to inspect a detached context snapshot;
- respond_to() — converse with one registered agent;
- inspect_many() / inspect_by_role() — coordinate multiple agents over the same snapshot.

Every returned result passes through AgentAuthority before the Director exposes it.

## Authority boundary

The Director is an orchestrator, not a hidden world editor.

Agent execution never receives a mutable WorldState. AgentContext contains a detached snapshot, branch/tick metadata, selected events, and optional narrative state.

A proposal to alter authoritative state remains a proposal. It must enter the existing intervention pipeline and, where required, a human approval path before execution.

## Why this is important

This makes the requested interaction model possible without compromising the simulation:

User -> Director -> selected Agent -> structured Result

while authoritative world evolution remains:

Simulation / approved Intervention -> WorldState -> Event Log -> Narrative Observation

The two paths meet through explicit proposals, not hidden prompt-side mutation.
