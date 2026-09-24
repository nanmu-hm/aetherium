# Aetherium Data Model

## 1. Purpose

This document defines the authoritative data structures used by Aetherium.

The core rule is simple:

> Agents may propose state changes, but the state model owns the truth.

The model must be explicit, serializable, auditable, versionable, branchable, and understandable by both humans and AI agents.

## 2. WorldState

WorldState is the complete snapshot of a fictional world at one simulation tick.

Conceptual structure:

    WorldState
    ├── world
    ├── time
    ├── locations
    ├── characters
    ├── relationships
    ├── factions
    ├── resources
    ├── knowledge
    ├── event_log
    ├── canon
    └── branches

Required fields:

| Field | Meaning |
|---|---|
| world_id | Stable world identifier |
| tick | Simulation tick number |
| timestamp | In-world date/time |
| locations | Known places and spatial state |
| characters | CharacterState registry |
| relationships | RelationshipState registry |
| factions | FactionState registry |
| resources | Important material/social resources |
| knowledge | Knowledge available to actors |
| event_log | Historical events |
| canon | Provenance-aware canon ledger |
| active_branch | Current history branch |

## 3. CharacterState

A character is not merely a prompt. CharacterState represents the current condition of an actor.

    CharacterState
    ├── identity
    ├── traits
    ├── values
    ├── goals
    ├── needs
    ├── emotions
    ├── location
    ├── knowledge
    ├── memory
    ├── relationships
    ├── possessions
    ├── abilities
    ├── constraints
    └── status

Core distinction:
- Values: what the character considers important.
- Goals: desired future states.
- Needs: immediate pressures.
- Emotion: current affective state.
- Knowledge: what the character believes/knows.
- Memory: what the character remembers from experience.
- Constraints: what limits possible behavior.

The system must not collapse these into one generic personality paragraph.

## 4. RelationshipState

Relationships are first-class state.

Example dimensions:
- trust
- affection
- loyalty
- fear
- respect
- resentment
- rivalry
- debt
- cooperation
- dependence

A relationship may be asymmetric. For example, A may trust B strongly while B trusts A weakly.
Relationship changes must have causes recorded in the event history.

## 5. FactionState

A faction represents an organization, political group, military force, family, guild, company, movement, or other collective actor.

Fields include:
- identity
- leadership
- members
- goals
- values
- resources
- territory
- allies
- enemies
- internal factions
- stability
- reputation
- institutional memory

Factions may create actions and events independently of individual characters.

## 6. ActionCandidate

Agents should normally propose actions before execution.

    ActionCandidate
    ├── id
    ├── actor_id
    ├── action_type
    ├── targets
    ├── motivation
    ├── preconditions
    ├── expected_outcomes
    ├── risks
    ├── confidence
    └── provenance

The action proposal is not automatically true. It must pass validation and resolution before changing WorldState.

## 7. Event

An Event is an authoritative historical occurrence.

    Event
    ├── id
    ├── timestamp
    ├── location
    ├── participants
    ├── causes
    ├── facts
    ├── consequences
    └── provenance

Events form the historical backbone of the world.

An event should answer:
1. What happened?
2. Who caused it?
3. Who participated?
4. Where did it happen?
5. When did it happen?
6. Why did it happen?
7. What changed because of it?

## 8. Consequence

Every important event produces explicit consequences.

Examples:
- character moved;
- relationship changed;
- resource changed;
- faction reputation changed;
- injury occurred;
- knowledge was acquired;
- rumor spread;
- goal changed;
- new conflict emerged.

A consequence should identify its target and before/after values whenever practical.

## 9. KnowledgeItem

Knowledge is local to an actor.

A KnowledgeItem should include:
- subject
- proposition
- source
- certainty
- acquired_at
- last_confirmed_at
- status

Possible status values: fact, belief, rumor, misinformation, unknown.

This prevents omniscient characters.

## 10. CanonEntry

Every important assertion should have provenance.

Types:
- CANON
- DERIVED
- INTERPRETATION
- PROPOSAL
- USER_DECISION
- SIMULATION_EVENT

Canon entries should reference their source event, user decision, or originating artifact.

## 11. StoryArc

StoryArc is downstream from history.

It contains:
- arc_id
- title
- premise
- participating_characters
- initiating_events
- causal_chain
- central_conflict
- turning_points
- character_changes
- unresolved_threads
- resolution
- status
- source_history_range

The StoryArc does not rewrite history merely because a narrative interpretation changes.

## 12. Branch

A Branch represents an alternate history.

Fields:
- branch_id
- parent_branch_id
- fork_tick
- reason
- created_by
- state_snapshot
- status

A user modification can create alternate histories. Branches must preserve their parent history.

## 13. SimulationTick

A SimulationTick is one atomic cycle of world evolution.

It records:
- tick number
- observations
- candidate actions
- selected actions
- resolved events
- consequences
- state changes
- validation results

This makes autonomous evolution inspectable.

## 14. State Mutation Rule

No agent should silently mutate authoritative state.

The preferred pipeline is:

    Proposal
       ↓
    Validation
       ↓
    Resolution
       ↓
    State Mutation
       ↓
    Event Record
       ↓
    Provenance

This is one of the most important architectural safeguards in Aetherium.

## 15. Future Implementation

The first implementation will use Python dataclasses/Pydantic models.

Persistence will initially support JSON snapshots and event logs.

A later production version can add PostgreSQL without changing the conceptual model.