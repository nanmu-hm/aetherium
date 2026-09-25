# Aetherium Architecture

## Layer 1 — World

The persistent simulation state: time, geography, resources, institutions, factions, population, and environmental conditions.

## Layer 2 — Agents

Specialized agents operate on bounded responsibilities:

- Character Agent: goals, values, personality, memory, decisions.
- Relationship Agent: interpersonal state and relationship transitions.
- Action Agent: candidate actions and feasibility.
- Event Agent: converts interacting actions into events and consequences.
- Faction Agent: organizations, interests, alliances, conflicts.
- Knowledge Agent: what each actor knows, believes, or falsely believes.
- World Agent: global state transitions.
- Narrative Agent: detects meaningful causal chains and emerging story arcs.
- Continuity Agent: validates chronology, location, knowledge, causality, and canon.
- Writer Agent: turns approved story material into prose.
- Critic Agent: evaluates coherence, style, pacing, characterization, and unresolved contradictions.
- Director Agent: coordinates the system without replacing specialist reasoning.

## Layer 3 — Simulation Loop

```text
observe state
  → generate candidate actions
  → evaluate decisions
  → execute actions
  → resolve interactions
  → create event
  → apply consequences
  → update memory/knowledge/relationships
  → advance world time
  → repeat
```

## Layer 4 — Narrative Emergence

The narrative layer observes simulation history rather than dictating every event. It identifies persistent goals, conflicts, reversals, character arcs, causal clusters, unresolved questions, and potential endings.

## Layer 5 — Novelization

Only after a story arc has sufficient causal and emotional structure does the novel layer convert events into scenes, chapters, volumes, and prose.

## Persistence

Every consequential simulation step should be represented as durable state and event history. The event log is the source of truth for reconstructing why the world reached its current state.

## Human control

The user may inspect or modify world state, character state, decisions, events, narrative arcs, or prose. Changes must be explicit and versioned so that alternate histories remain recoverable.
