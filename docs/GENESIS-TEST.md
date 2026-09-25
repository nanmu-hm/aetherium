# Genesis Test

The world-element design is frozen for this phase. This document defines the
first implementation test of autonomous emergence.

## Objective

Run a small Aetherium world without user plot intervention and determine
whether it produces persistent, consequential human history from character
choices.

## Invariants

1. The simulator may create events, but the narrative layer must not create
   world facts.
2. Human-condition values are pressures and affordances, never mandatory plot
   beats.
3. Character choice remains the primary local driver of action.
4. Events update state, relationships and memory.
5. Story archaeology observes accumulated history and may rank candidate
   threads, but it must not rewrite history.
6. Literary style is outside the world simulation.

## First experiment

Start with a small population and a short horizon. Record for every tick:

- character state and location;
- candidate actions and selected actions;
- events and consequences;
- relationship changes;
- memory writes;
- human-condition pressure;
- narrative-pressure measurements;
- discovered story candidates.

The first success criterion is **not** "a novel was generated". It is:

> the world produces at least one persistent chain of choices and consequences
> whose participants, pressure and unresolved state make it distinguishable
> from an isolated random event.

## Next implementation step

Connect `StoryArchaeologist` to the simulation loop and add a deterministic
seeded Genesis scenario. Then use the resulting event log as the input to the
future story-structure and literary layers.
