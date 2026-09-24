# Aetherium User Intervention

## 1. Principle

The user is allowed to intervene at any level without losing historical traceability.

Intervention must be versioned.

    User Command
        ↓
    Interpret Intent
        ↓
    Impact Analysis
        ↓
    Apply / Fork / Reject
        ↓
    Validate
        ↓
    Checkpoint

## 2. Chat With Any Agent

The user should be able to open a direct conversation with any specialized agent.

Examples:
- Character Agent: discuss a character's motives and behavior.
- Relationship Agent: inspect why two characters changed toward each other.
- World Agent: inspect geography, institutions, resources, or environmental rules.
- Continuity Agent: ask whether a proposed event is physically and chronologically possible.
- Narrative Agent: ask why a historical chain became a StoryArc.
- Writer Agent: revise scene presentation without changing canon.
- Director Agent: inspect what the system is currently simulating and why.

An agent conversation is an interface to the shared state, not a private alternate universe.

## 3. Intervention Types

### A. Future-only change

The user changes a rule or state from the current tick onward.

Example: a character decides to leave a city tomorrow.

Past history remains unchanged.

### B. Historical rewrite

The user explicitly changes a past fact.

This must normally create a new branch rather than silently rewriting the main history.

### C. Narrative-only change

The user changes how an existing history is interpreted or presented.

This does not alter world state.

### D. Character-model change

The user changes stable character traits, values, goals, or constraints.

The system must perform impact analysis because future behavior may change.

### E. World-rule change

The user changes a rule of the world.

Examples:
- travel time;
- inheritance rules;
- magic limitation;
- economic rule;
- political institution.

Major rule changes should normally fork the world.

## 4. Impact Analysis

Before a destructive or historical change, Aetherium should identify affected material.

Potential impact targets:
- events;
- characters;
- relationships;
- factions;
- locations;
- story arcs;
- chapters;
- derived canon.

Example:

    Change: Character A was never injured.
    Impact:
      → recovery event
      → later travel
      → battle participation
      → relationship changes
      → derived StoryArc

The user can then decide whether to branch or accept the consequences.

## 5. Branching

Branches preserve alternate histories.

    Main
      │
      ├── Branch A: original
      │
      └── Branch B: user intervention

Each branch has a parent, fork point, reason, and state snapshot.

Branches can later be compared or abandoned.

## 6. Rollback

Rollback means returning the working view to an earlier checkpoint.

Rollback must not destroy recorded history unless the user explicitly requests permanent deletion.

The preferred implementation is immutable event history plus branch pointers.

## 7. Conflict Resolution

If a user request conflicts with established canon, the system should not silently choose.

It should report:
- conflicting fact;
- source;
- affected material;
- possible resolutions.

Possible user choices:
- keep existing canon;
- create a branch;
- replace the historical fact;
- mark the statement as interpretation rather than canon.

## 8. Agent Chat and State Changes

Agents may explain and propose changes through chat.

Authoritative mutations should still pass through the same state manager used by autonomous simulation.

This prevents an agent chat from bypassing continuity controls.

## 9. User Control Levels

The system should expose at least:

- Observe: simulation continues and user only watches.
- Approve: significant changes pause for approval.
- Guide: user can steer goals and constraints.
- Direct: user explicitly commands state changes.
- Edit: user modifies historical or narrative material.

The same world can move between these modes.

## 10. Core Promise

Aetherium should never force the user to choose between creative freedom and continuity.

Intervention changes the world through explicit, traceable operations rather than hidden prompt edits.