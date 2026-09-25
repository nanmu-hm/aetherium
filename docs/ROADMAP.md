# Aetherium Roadmap

Aetherium is built around a self-simulating fictional world. The roadmap therefore prioritizes trustworthy world causality before autonomous storytelling, while bringing narrative intelligence and literary expression early enough that the simulator does not become a history generator with no compelling stories.

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

- [x] Dilemma detection and competing-value modeling
- [x] Narrative pressure and unresolved-tension model
- [x] Rhythm / breathing model
- [x] Causal Thread Engine
- [x] Narrative Thread Engine
- [x] Information asymmetry / mystery / revelation
- [x] Character arc detection
- [x] Foreshadowing and payoff tracking
- [x] Narrative importance vs historical importance
- [x] Narrative resource allocation
- [x] Multi-thread convergence
- [x] Story completion criteria

## Phase 4 — Story structure and discovery
- [x] Beat model
- [x] Scene formation
- [x] Sequence formation
- [x] Story-arc formation
- [x] Multi-arc interleaving
- [x] Delayed callbacks and payoff scheduling
- [x] Story boundary detection
- [x] Story discovery from long simulation histories
- [x] Reader-knowledge planning

## Phase 5 — Literary expression
Literary quality is a composable expression system, not a single author-style switch. See docs/LITERARY-MECHANICS.md.

- [x] Literary expression state
- [x] Character voice model
- [x] Sentence / paragraph rhythm controls
- [x] Viewpoint and narrative-distance controls
- [x] Subtext and omission model
- [x] Imagery / motif model
- [x] Dynamic scene-level expression
- [x] Narrative emphasis: summarize vs dramatize vs slow down
- [x] Prose quality gates
- [x] Literary research profiles expressed as abstract mechanisms

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
- [x] Event-sourced persistence
- [x] Canon ledger / provenance
- [x] Checkpoints
- [x] Branch / fork / rollback
- [x] Impact analysis for user edits
- [x] Conflict resolution
- [x] Simulation replay
- [x] Deterministic reproducibility

## Phase 8 — Agents and novelization
- [x] Agent contracts
- [x] Model adapters
- [x] Director / orchestrator
- [x] Character agents
- [x] Continuity agent
- [x] Independent critic agents
- [x] Writer / scene generation
- [ ] Human-in-the-loop approval
- [ ] Autonomous long-run mode
- [x] User can converse with any agent without replacing authoritative world state

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

1. The world can run without a novel.
2. Characters can make choices that do not serve a predefined plot.
3. Narrative systems observe and propose; they do not silently rewrite authoritative history.
4. Literary expression cannot contradict authoritative facts.
5. World truth, character belief, and reader knowledge remain separate.
6. Pressure is not spectacle; quiet scenes may matter.
7. Setups must be causally legitimate; twists cannot manufacture their own past.
8. Not every seed requires a payoff.
9. User interventions create explicit, recoverable history rather than erasing the old world.
10. The system must support autonomous evolution as a first-class operating mode.
