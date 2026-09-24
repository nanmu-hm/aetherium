# Aetherium Memory Architecture

## Purpose

Aetherium characters must remember a lived world, not a transcript. Memory is part of character state and therefore part of causal simulation.

The authoritative world may contain facts a character has never learned. A character may remember an event incompletely, emotionally, or incorrectly. Later decisions use the character's internal knowledge and memory, not the omniscient world log.

Core boundary:

`WORLD TRUTH != CHARACTER KNOWLEDGE != CHARACTER MEMORY != READER KNOWLEDGE`

## Memory contract

Every memory should answer:

- who remembers it;
- what happened;
- when and where;
- who was involved;
- whether it was directly experienced, heard, inferred, or believed;
- emotional salience;
- importance;
- confidence;
- recall cues;
- whether later evidence can revise it.

Memory formation is caused by simulation events. The memory subsystem never creates world facts.

## Memory layers

### Episodic memory

A concrete lived episode: an argument, promise, betrayal, journey, loss, discovery, or ordinary encounter.

### Semantic knowledge

Facts the character believes to be true. These can become stale or false.

### Relational memory

The accumulated history behind a relationship. A relationship score is only a derived summary; the causes remain inspectable.

### Emotional memory

Salience attached to experiences. Emotion can preserve memories that have little historical importance.

### Procedural memory

Habits and learned responses. These influence future action generation without requiring conscious recall.

### Identity memory

Self-concept, values, commitments, shame, pride, feared identities, and promises to self.

### Belief / misbelief

Characters may hold incorrect interpretations. The simulation must preserve the distinction between an incorrect belief and an incorrect world fact.

## Salience and decay

Memory retention is not simple age-based deletion.

A memory's persistence depends on:

- emotional intensity;
- personal relevance;
- relationship relevance;
- novelty;
- unresolved consequences;
- repetition;
- recency;
- identity relevance.

Low-salience memories may become harder to recall without being deleted. High-salience memories can persist for years.

## Recall

Recall should be cue-driven. Current people, locations, goals, conflicts, objects, emotions, and related events can reactivate memories.

Recall returns memories with relevance and confidence, not a perfect chronological transcript.

## Revision

A character can reinterpret a memory when new evidence arrives. Prefer recording a new interpretation over silently rewriting the old experience.

This permits:

- misunderstanding;
- regret;
- changed feelings;
- unreliable testimony;
- contradictory memories;
- gradual realization.

## Opportunity and loss

The same causal model governs desire.

A desire is not guaranteed to be fulfilled. A character acts under:

`Desire + Need + Opportunity + Constraint + Cost + Timing + Other People's Agency`

Opportunity windows are first-class state. They may open, narrow, or close while a character is unaware.

Missed chances should emerge from:

- incompatible timing;
- lack of information;
- competing obligations;
- another person's choice;
- fear or hesitation;
- resource constraints;
- mistaken belief.

Loss must be irreversible when the world makes it irreversible. Do not manufacture failure merely to create drama.

## Implementation boundary

The MVP uses an in-process structured memory store. Future persistence adapters may target SQLite, a graph store, or systems such as Graphiti/Mem0 after the Aetherium memory contract is stable.

Third-party memory systems are storage/retrieval infrastructure, not the definition of character psychology.
