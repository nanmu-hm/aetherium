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

The MVP keeps local knowledge separate from world state. A `KnowledgeFact` belongs to one character and records the proposition, source, source event, confidence, and learning/confirmation ticks. Directly experienced event facts are granted only to participants. Information learned later can use a different source such as `heard` or `confirmed` without changing the underlying world fact.

The existing `CharacterState.knowledge` set is a lightweight lookup mirror; `MemoryState.knowledge` is the authoritative local-knowledge record.

Knowledge may also travel between characters. A transmitted fact records the immediate source character, parent fact, transmission depth, and reduced confidence. The source character must actually know the proposition before it can be transmitted. Direct confirmation can later replace weaker hearsay provenance while preserving the same knowledge identity. Transmission changes what a character believes they know; it never creates or changes world truth.

### Relational memory

The accumulated history behind a relationship. A relationship score is only a derived summary; the causes remain inspectable.

### Emotional memory

Salience attached to experiences. Emotion can preserve memories that have little historical importance.

### Procedural memory

Habits and learned responses. These influence future action generation and decision utility without requiring conscious recall.

In the MVP, each character stores a small learned tendency per canonical action type:

- `+1` means a strong learned preference;
- `0` means no learned tendency;
- `-1` means a learned avoidance.

Successful lived actions move the tendency gradually toward preference; failed attempted actions move it gradually toward avoidance. Blocked actions do not create learning because the character did not actually experience the action outcome.

Procedural learning must remain gradual. One event should not rewrite personality. Repeated lived experience can accumulate into a durable behavioral pattern.

### Identity memory

Self-concept, values, commitments, shame, pride, feared identities, and promises to self.

The MVP represents the descriptive part of self-concept as small, gradual identity beliefs on each character. A value says what a character thinks matters; an identity belief says what the character currently thinks they are.

Identity evidence is experience-based and bounded:

- successful travel can strengthen `independent` / `capable`;
- successful contact can strengthen `loyal` / `reliable`;
- successful help can strengthen `compassionate` / `reliable`;
- failed attempts push the same dimensions gradually in the opposite direction;
- blocked actions create no identity evidence because no lived outcome occurred.

Identity changes are small and cumulative. A single event cannot rewrite the character, but repeated experience can make a self-concept durable. The decision kernel can use that self-concept as a modest compatibility signal, allowing character identity to become part of the causal loop without becoming destiny.

### Relationship history

Relationship scores are current summaries; relationship history preserves the concrete events and score changes that produced them. Each entry keeps the affected relationship, action, outcome, event, and field-level changes. This history is append-only in the MVP, so later analysis can explain why a relationship changed instead of inferring causes from the latest numbers alone.

### Memory revision / reinterpretation

A memory keeps its original experience while allowing later interpretations to be appended as explicit revisions. A revision records the previous interpretation, the new interpretation, why it changed, the supporting later memories, and the revised confidence. The original event and prior interpretation are never erased.

### Information asymmetry

The simulation never treats the global event log as universal character knowledge. A character can know an event because they experienced it or later learned it; another character can remain unaware. Decision logic that depends on remembered history must use owner-scoped memory/knowledge rather than the omniscient world log. This preserves the causal basis for misunderstanding, discovery, secrecy, and later revelation.

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
