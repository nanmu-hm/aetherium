# Aetherium Simulation Loop

## 1. Purpose

The Simulation Loop is the engine that makes the fictional world continue to exist when the user is not writing.

Aetherium must not begin with:
    What should the next chapter be?

It begins with:
    Given the current world state, what would its inhabitants naturally do next?

## 2. Core Causal Loop

    World State
         ↓
    Character Desires
         ↓
    Candidate Actions
         ↓
    Action Selection
         ↓
    Action Resolution
         ↓
    Event
         ↓
    Consequences
         ↓
    State Update
         ↓
    Character Change
         ↓
    New Desires
         ↓
       repeat

This loop is the heart of Aetherium.

## 3. Simulation Tick

Each tick follows these stages.

### Stage 1 — Observe

Collect relevant current state: time, location, nearby actors, relationships, resources, active goals, needs, emotions, knowledge, recent events, and environmental conditions.

Characters only receive information they could plausibly access.

### Stage 2 — Generate Action Candidates

For each active actor, generate plausible actions.

The action pool should be driven by:
    desires + values + personality + relationships + knowledge + constraints + circumstances

The system must not generate an action merely because a predefined plot requires it.

### Stage 3 — Score / Select

Candidate actions may be evaluated using goal alignment, value alignment, emotional pressure, relationship effects, risk, opportunity, information quality, personality consistency, and faction incentives.

The score is a decision aid, not a guarantee. High-impact agents may still choose surprising actions if the action is consistent with their character model.

### Stage 4 — Resolve Interactions

Actions from different actors may cooperate, conflict, interfere, remain independent, or trigger reactions.

The engine resolves their interaction before declaring historical facts.

### Stage 5 — Create Event

Successful or consequential interactions become events.

Failure is also a valid historical result.

Examples include a negotiation failing, a character refusing an order, a message never arriving, a faction discovering a resource, a relationship deteriorating, or an assassination attempt failing.

The world records what actually happened, not what an agent intended to happen.

### Stage 6 — Apply Consequences

Apply explicit consequences to authoritative state.

    location: A → B
    trust: 70 → 42
    gold: 100 → 65
    faction_stability: 80 → 62
    goal_status: active → blocked

### Stage 7 — Update Minds

Characters update memory, knowledge, beliefs, goals, needs, emotions, and relationships.

The update must be caused by events rather than arbitrary rewriting.

### Stage 8 — Advance Time

The world clock advances.

Time advancement must respect travel, communication, recovery, production, political processes, and environmental change.

No teleportation.

### Stage 9 — Validate

Continuity validation checks impossible locations, impossible timing, duplicate possessions, invalid knowledge, contradictory relationships, impossible injuries, dead/inactive actors taking actions, and broken causal references.

Invalid state transitions are rejected or flagged.

## 4. Autonomous Mode

In World Evolution Mode, the loop can continue without user decisions.

The Director Agent controls only orchestration. It should not invent authoritative facts outside the state transition pipeline.

A safe autonomous cycle is:

    simulate N ticks
       ↓
    validate
       ↓
    detect significant developments
       ↓
    checkpoint
       ↓
    continue

The system should periodically checkpoint so a long simulation never becomes an irreversible black box.

## 5. Stopping Conditions

Autonomous simulation can stop when a configured time horizon is reached, the world reaches a stable state, a major narrative phase emerges, resources or actors enter a configured terminal state, validation repeatedly fails, or user intervention is required.

A story completion condition is different from simulation completion. The world can continue after a novel ends.

## 6. Determinism and Seeds

Simulation runs should support a random seed.

Given identical initial state, identical model configuration, and identical seed, deterministic portions should produce reproducible results.

Example:
    Seed 101 → History A
    Seed 202 → History B
    Seed 303 → History C

The histories can then be compared or novelized separately.

## 7. LLM Boundary

LLMs are useful for generating action candidates, interpreting motives, proposing reactions, generating dialogue, detecting narrative patterns, and writing prose.

LLMs should not be the sole authority for time, location, inventory, relationship values, event existence, chronology, or branch identity.

Those belong to the state engine.

## 8. Simulation Philosophy

The system is not trying to predict what a human would really do.

It is maintaining a coherent fictional causal system.

> Given this world, these people, their history, their knowledge, and their pressures, what happens next?

That question should drive the engine.