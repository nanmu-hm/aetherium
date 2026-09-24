# Aetherium Roadmap

Aetherium is built around a **self-simulating fictional world**. The roadmap therefore prioritizes trustworthy world causality before autonomous storytelling, while bringing narrative intelligence and literary expression early enough that the simulator does not become a history generator with no compelling stories.

## Phase 1 — Living-world kernel
- [x] Core world and character state
- [x] Action pool
- [x] Deterministic simulation loop
- [x] Basic relationship consequence
- [x] CI workflow
- [x] Narrative observation prototype

## Phase 2 — Causal character simulation
- [x] Structured preconditions
- [x] Success / failure / blocked action resolution
- [x] Deterministic seeded outcomes
- [x] Time advancement
- [x] Local knowledge model
- [ ] Memory model
- [x] Rumor and information propagation
- [x] Authoritative relationship representation
- [ ] Character-state transitions caused by consequences
- [x] Decision errors, uncertainty, and bounded rationality


### Phase 2 character-life kernel detail

- [x] Structured episodic memory model
- [x] Character belief/misbelief model
- [x] Gradual identity self-concept model
- [x] Memory salience and recall decay
- [x] Cue-driven memory recall
- [x] Desire opportunity windows and missed chances
- [x] Vendor-neutral memory store interface
- [x] Integrate structured memory into authoritative simulation events
- [x] Relationship-history event model
- [x] Memory revision/reinterpretation events
- [ ] Persistent SQLite memory adapter
- [ ] Optional Graphiti/Mem0 adapter after the Aetherium memory contract stabilizes

## Phase 3 — Narrative intelligence
The narrative layer observes the autonomous world; it does not secretly write outcomes into the simulation.

- [ ] Dilemma detection and competing-value modeling
- [ ] Narrative pressure and unresolved-tension model
- [ ] Rhythm / breathing model
- [ ] Causal Thread Engine
- [ ] Narrative Thread Engine
- [ ] Information asymmetry / mystery / revelation
- [ ] Character arc detection
- [ ] Foreshadowing and payoff tracking
- [ ] Narrative importance vs historical importance
- [ ] Narrative resource allocation
- [ ] Multi-thread convergence
- [ ] Story completion criteria

## Phase 4 — Story structure and discovery
- [ ] Beat model
- [ ] Scene formation
- [ ] Sequence formation
- [ ] Story-arc formation
- [ ] Multi-arc interleaving
- [ ] Delayed callbacks and payoff scheduling
- [ ] Story boundary detection
- [ ] Story discovery from long simulation histories
- [ ] Reader-knowledge planning

## Phase 5 — Literary expression
Literary quality is a composable expression system, not a single author-style switch. See docs/LITERARY-MECHANICS.md.

- [ ] Literary expression state
- [ ] Character voice model
- [ ] Sentence / paragraph rhythm controls
- [ ] Viewpoint and narrative-distance controls
- [ ] Subtext and omission model
- [ ] Imagery / motif model
- [ ] Dynamic scene-level expression
- [ ] Narrative emphasis: summarize vs dramatize vs slow down
- [ ] Prose quality gates
- [ ] Literary research profiles expressed as abstract mechanisms

## Phase 6 — World evolution
- [ ] Faction evolution
- [ ] Economy and resource dynamics
- [ ] Political dynamics
- [ ] Population / ecology
- [ ] Dynamic character generation
- [ ] World-scale events
- [ ] Divergent world simulation
- [ ] Long-horizon stability / anti-collapse controls

## Phase 7 — Persistence and agency
- [ ] Event-sourced persistence
- [ ] Canon ledger / provenance
- [ ] Checkpoints
- [ ] Branch / fork / rollback
- [ ] Impact analysis for user edits
- [ ] Conflict resolution
- [ ] Simulation replay
- [ ] Deterministic reproducibility

## Phase 8 — Agents and novelization
- [ ] Agent contracts
- [ ] Model adapters
- [ ] Director / orchestrator
- [ ] Character agents
- [ ] Continuity agent
- [ ] Independent critic agents
- [ ] Writer / scene generation
- [ ] Human-in-the-loop approval
- [ ] Autonomous long-run mode
- [ ] User can converse with any agent without replacing authoritative world state

## Phase 9 — Product layer
- [ ] FastAPI
- [ ] World dashboard
- [ ] Timeline
- [ ] Character graph
- [ ] Narrative threads
- [ ] Branch browser
- [ ] Agent rooms
- [ ] Novel editor
- [ ] World / story / prose inspection and provenance

## Cross-cutting invariants

1. **The world can run without a novel.**
2. **Characters can make choices that do not serve a predefined plot.**
3. **Narrative systems observe and propose; they do not silently rewrite authoritative history.**
4. **Literary expression cannot contradict authoritative facts.**
5. **World truth, character belief, and reader knowledge remain separate.**
6. **Pressure is not spectacle; quiet scenes may matter.**
7. **Setups must be causally legitimate; twists cannot manufacture their own past.**
8. **Not every seed requires a payoff.**
9. **User interventions create explicit, recoverable history rather than erasing the old world.**
10. **The system must support autonomous evolution as a first-class operating mode.**

## Guiding milestone

The first real milestone is not "AI wrote a chapter".

It is:

> A deterministic world can evolve for a long time; characters make causally consistent but imperfect choices; consequences persist; information differs by actor; relationships change; narrative intelligence discovers dilemmas, threads, and emerging arcs; and the literary layer can turn an observed arc into readable prose without falsifying the world.

## Guiding rule

Do not add UI complexity faster than the underlying world, narrative, and literary models become trustworthy.
