# Reference Project Architecture Audit

This document records external implementations that Aetherium studies so we do not
rebuild solved engineering ideas unnecessarily. Reference projects are evidence and
inspiration, not authorities: any borrowed mechanism must still satisfy
`docs/DESIGN-PRINCIPLES.md`.

## 1. AI Town

Repository: https://github.com/a16z-infra/ai-town
Architecture: https://github.com/a16z-infra/ai-town/blob/main/ARCHITECTURE.md

Useful implementation ideas:
- Separate the simulation/game engine from agent behavior.
- Treat player/agent behavior as inputs processed by the engine rather than allowing
  an agent to mutate the world arbitrarily.
- Use explicit simulation ticks/steps and serialize world state between steps.
- Keep agent-specific state separate from core game state.
- Memory can be retrieved separately from the core world state.

What Aetherium should borrow:
- Strong engine/agent boundary.
- Explicit input/action boundary.
- Clear persistence boundary.
- A similar separation between simulation truth and higher-level agent cognition.

What Aetherium should not blindly copy:
- AI Town is optimized for an interactive multiplayer application and uses Convex.
  Aetherium's deterministic offline simulation, replay, causal audit, and story
  archaeology have different requirements.
- Its LLM conversation memory is useful for social dialogue, but should not become
  the authoritative source of world facts.

## 2. Generative Agents

Repository: https://github.com/joonspk-research/generative_agents

Useful implementation ideas:
- A persistent memory stream is a first-class component of agent cognition.
- Retrieved memories are used by planning and behavior rather than merely displayed.
- Hierarchical planning can decompose a durable goal into daily/stage/current-action steps.
- Agent history can be initialized and persisted as simulation data.
- The simulation has an explicit server/state layer and supports replaying saved
  simulations.

What Aetherium should borrow:
- Memory as an active input to future decisions **(planned in Aetherium; `MemoryKernel.recall()` is not yet wired into `DecisionKernel`)**.
- Separation of memory retrieval from the simulation loop.
- Explicit persistence of simulation state.
- The idea that accumulated experience changes future behavior.

What Aetherium should improve:
- Generative Agents relies heavily on LLM-generated cognition and prompt outputs.
  Aetherium must retain a deterministic, auditable causal core.
- A retrieved memory must never silently become objective world truth.
- Aetherium needs a stronger explicit chain from perceived facts to beliefs,
  desires/goals, decisions, consequences, and historical events.

## 3. Cataclysm: Dark Days Ahead

Repository: https://github.com/CleverRaven/Cataclysm-DDA

Useful implementation ideas:
- NPC state contains explicit personality dimensions, attitudes, missions,
  relationships and behavior-related state.
- The project has evolved from simple need ranking toward behavior-tree based
  behavior for some immediate survival needs.
- NPC behavior is represented by structured state and actions rather than one
  monolithic LLM prompt.

What Aetherium should borrow:
- Personality should be structured state, not prose decoration.
- Needs/personality/relationships can independently contribute to behavior.
- Behavior mechanisms should be replaceable as the simulation grows.
- Long-lived simulation systems benefit from explicit, inspectable state.

What Aetherium should improve:
- Aetherium needs personality to affect interpretation of events and formation of
  beliefs/goals, not merely select from cosmetic behavior traits.
- The causal history of a decision must remain inspectable.

## 4. Dwarf Fortress and Kenshi

These are design references rather than source-code references for the core engine.

Study targets:
- world history generated before the player observes it;
- faction and character interactions producing unintended consequences;
- persistent consequences of actions;
- emergent narrative discovered from simulation rather than authored as a fixed plot.

They are useful for validating the design direction, but we should not claim
source-level reuse where the relevant implementation is not openly available.

## 5. Aetherium comparison

| Concern | External lesson | Aetherium decision |
|---|---|---|
| World authority | Engine owns state changes | Keep SimulationEngine authoritative |
| Agent/world boundary | Agents submit/process inputs | Keep action candidates separate from resolution |
| Memory | Memory changes later cognition | Make memory actor-local and causally relevant |
| Personality | Structured state affects behavior | Extend toward interpretation -> belief -> goal -> action |
| Needs | Needs can drive behavior | Human-condition pressures are pressures, not mandatory plots |
| Information | Agents need not know all world state | Preserve information asymmetry |
| Persistence | State must be serializable/replayable | Persist RNG and decision seed as well as world state |
| Long history | Emergent systems need persistent consequences | Validate long runs and causal threads |
| Narrative | Emergent history can become story | Story Archaeology observes history only |
| Literary output | Should not rewrite simulation truth | Prose remains downstream |

## 6. Engineering rule

Before inventing a new subsystem, check whether a mature reference project already
solves the same engineering problem.

The comparison must answer four questions:
1. What problem did the reference project solve?
2. What data model and mechanism did it use?
3. Which part is transferable to Aetherium?
4. Which part conflicts with Aetherium's determinism, information asymmetry, or
   world-first constitution?

Borrow mechanisms when they solve a real Aetherium problem. Do not add dependencies,
LLM calls, abstractions, or complexity merely because a reference project has them.

## 7. Current priority

The audit does **not** justify jumping directly to prose generation.

The next simulation work remains:
1. use staged goals to preserve long-lived intention while advancing through observable steps;
2. replace hard pressure gates with continuous pressure and causally motivated affordances;
3. make failed searches update actor-local knowledge and future destination choice;
4. strengthen personality/history/values/relationship interpretation;
5. validate long-run autonomous history across multiple seeds;
6. only then deepen Story Archaeology and literary planning.

Current implementation status:
- `MemoryKernel.recall()` exists but is **not yet a decision-loop input**; this is deliberately marked as planned rather than claimed as implemented.
- Staged goals are now implemented in the Genesis world; the next work should validate whether they produce sustained, varied history rather than merely more repeated actions.

The central test remains:

> Does this make the world more capable of genuinely living, changing, and producing
> history — or are we merely making it better at pretending to tell a story?
