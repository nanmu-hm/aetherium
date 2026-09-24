# Aetherium Agent System

## Agent philosophy
Agents are specialized decision and transformation components operating on shared state. They do not own hidden, authoritative versions of the world.

## Core agents

### Character Agent
Models an individual character's goals, values, traits, current emotional state, memory, knowledge, constraints, and candidate decisions.

### Relationship Agent
Tracks directed and mutual relationship state and computes changes caused by events.

### Action Agent
Builds an action pool from character state and current circumstances, then evaluates feasibility and behavioral fit. It must not select actions solely because they advance a predefined plot.

### Event Agent
Resolves interacting actions into concrete events, including success, failure, partial success, side effects, and causal consequences.

### World Agent
Maintains global simulation state and applies world-level transitions such as time, resources, geography, institutions, and environmental conditions.

### Knowledge Agent
Maintains actor-specific knowledge. It separates observed facts, communicated information, rumors, beliefs, and misinformation.

### Faction Agent
Models organizations and collective behavior: goals, resources, leadership, membership, alliances, rivalries, and internal conflicts.

### Narrative Agent
Observes event history and identifies persistent conflicts, causal chains, character arcs, reversals, unresolved questions, and candidate story boundaries.

### Continuity Agent
Checks chronology, location, actor availability, knowledge, inventory, relationships, injuries, abilities, and canon provenance.

### Writer Agent
Converts approved narrative structures into scenes and prose while respecting the current story state.

### Critic Agent
Performs independent quality checks for characterization, causality, pacing, style, emotional credibility, and contradictions.

### Director Agent
Coordinates agent execution, chooses when to simulate, when to ask the user, and when to advance an autonomous run. It should orchestrate rather than become the sole source of creative decisions.

## Communication contract
Each agent should receive explicit state and return structured proposals or results. Important mutations happen through a state manager, not arbitrary agent-to-agent hidden memory.

## Failure handling
An agent may return uncertain, blocked, or conflict rather than fabricating an answer. Conflicts should be routed to Continuity, Director, or the user according to operating mode.
