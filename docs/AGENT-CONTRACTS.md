# Agent Contracts and Model Adapters

Aetherium now defines an explicit boundary between agents, models, and authoritative state.

## Agent contract

An AgentContract declares:

- agent identity and role
- permitted read scopes
- non-authoritative write scopes
- whether chat is enabled
- whether autonomous mode is enabled
- whether the agent may propose an intervention

Agents never receive the authoritative WorldState as a mutable working object. AgentContext.from_world() creates a detached snapshot for inspection and conversation.

## Proposal boundary

Agents return AgentResult objects containing observations, recommendations, narrative drafts, or state-intervention proposals.

A state-intervention proposal is not a mutation. It must:

1. be allowed by the agent contract;
2. require explicit approval;
3. enter the existing intervention planner;
4. pass conflict and impact analysis;
5. reach an execution layer before authoritative state changes.

Narrative drafts are explicitly non-authoritative.

## Model adapter

ModelAdapter is vendor-neutral. A model implementation only needs to accept ModelRequest and return ModelResponse.

This keeps the Aetherium agent layer independent of:

- OpenAI-compatible APIs
- local Ollama/vLLM servers
- hosted model providers
- future multi-model routing

NullModelAdapter is deterministic and blocked by design; it makes missing model connectivity visible in tests rather than silently inventing output.

## Standard agent roles

The initial contracts cover:

director, character, relationship, action, event, world, knowledge, faction, narrative, continuity, writer, critic.

The next layer will implement concrete agent behavior and orchestration. The contracts are intentionally established first so every later agent shares the same authority boundary.
