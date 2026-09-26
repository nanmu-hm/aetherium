# Aetherium Design Principles

This document is a **binding design constitution** for Aetherium. It exists to prevent implementation work, optimization, testing, or narrative features from drifting away from the original purpose of the project.

## 1. The world comes first

Aetherium is first and foremost a **self-evolving small world simulation**, not an AI novel-writing application.

The primary object is a world that can exist and evolve coherently even when nobody is asking it to tell a story.

The system must therefore follow:

'World State → Character State → Experience/Memory → Beliefs/Values → Desires/Goals → Candidate Actions → Decision → Action Resolution → Event → Consequences → World/Character/Relationship Changes → next action'

Narrative output is downstream of this process.

## 2. The world must not be written to serve the story

The simulation is the source of truth.

- Characters act because of their state, motivations, relationships, knowledge, constraints, and opportunities.
- Events arise from resolved actions and world conditions.
- Consequences change the world.
- The narrative layer may observe, interpret, organize, and describe history.
- The narrative layer must **never inject facts, causes, relationships, outcomes, conflicts, revelations, or character changes into the simulated world merely to improve a story**.

If a world produces no compelling story for a period of time, that is a valid result. The system must not manufacture drama merely because a story is expected.

## 3. Character choice is the engine of history

The project is not a plot generator with characters placed inside a predetermined sequence.

Characters must have meaningful agency.

A useful causal loop is:

'人物 → 行动池 → 世界状态 → 冲突/机会 → 事件 → 人物改变 → 新行动池 → 新冲突/机会 → 新事件 → 历史'

Events should therefore be explainable through preceding state, character choice, constraints, chance, and consequences.

Avoid hard-coded plot rails unless they are explicitly part of the world's constitution.

## 4. Personality must eventually become causal, not decorative

When the personality layer is implemented, personality cannot merely change dialogue style or attach labels to characters.

The intended chain is:

'客观事件 → 人物实际可知信息 → 性格/经历/价值观/关系的解释 → 情绪与心理反应 → 记忆 → 信念变化 → 欲望/目标变化 → 行动选择'

The same objective event may therefore produce different interpretations and later actions in different characters, while the underlying world fact remains unchanged.

Personality traits should be relatively stable, but they may evolve gradually through experience rather than changing arbitrarily for plot convenience.

## 5. Human life is not reducible to plot devices

The world should be capable of containing the full range of human conditions:

- 生老病死
- 爱别离
- 怨憎会
- 求不得
- 五阴炽盛
- affection, loyalty, responsibility, fear, hope, loss, compassion, resentment, ambition, duty, and conflicting values

These are **pressures and affordances**, not mandatory plot beats.

The system must not force every human-condition element into a story. They should influence what characters can perceive, desire, choose, endure, lose, or change when the simulated circumstances make them relevant.

## 6. Conflict must emerge from incompatible realities

Good stories should not depend on endless victories, humiliation, or artificial escalation.

Conflict can arise from:

- incompatible goals;
- limited resources;
- conflicting duties and values;
- asymmetric information;
- relationships;
- fear and attachment;
- timing;
- irreversible consequences;
- missed opportunities;
- separation and loss;
- failure;
- unintended consequences;
- '求不得' and other forms of genuine constraint.

The system should allow characters to fail, misunderstand, miss each other, choose wrongly, sacrifice something, or achieve only part of what they wanted.

## 7. Story discovery follows history

The narrative subsystem should behave like an archaeologist, not a playwright.

The intended high-level pipeline is:

'世界运行 → 历史积累 → Story Archaeology → causal/story threads → chapter candidates → literary planning → prose'

Narrative structure may identify:

- causal threads;
- turning points;
- character arcs;
- unresolved tensions;
- revelations;
- convergence;
- foreshadowing;
- meaningful patterns across long history.

But these are discoveries and interpretations of simulated history. They are not permission to rewrite that history.

## 8. Literary style is a later expression layer

Prose style is important, but it comes after story facts and causal structure.

The order is:

'世界事实 → 历史/因果 → 故事发现 → 结构 → 文学表达'

A style layer must never alter:

- who did what;
- why an event happened;
- what a character knew;
- whether an action succeeded;
- relationships;
- consequences;
- chronology;
- causality.

Different literary styles may describe the same underlying history, but they must not create a different history.

## 9. Determinism and auditability are foundations

Given the same initial world and random seed, the simulation should produce the same sequence of events.

Important state transitions must be inspectable and testable.

When randomness is used, it must be part of the explicit simulation state so that:

- snapshots can be restored faithfully;
- replay is possible;
- bugs can be reproduced;
- competing implementations can be compared;
- historical causality can be audited.

A snapshot that restores visible world state but changes future random decisions is not a faithful simulation checkpoint.

## 10. Do not fix symptoms by suppressing behavior

When a test exposes repetitive or implausible behavior, prefer fixing the causal model over adding arbitrary cooldowns, caps, or suppression rules.

Examples:

- If a character repeatedly travels without meaningful reason, improve destination motivation and action selection rather than merely forbidding travel for one tick.
- If narrative pressure saturates, improve the pressure model rather than hiding saturation.
- If threads never close, define and implement causal closure rather than relabeling them.
- If checkpoint replay diverges, restore the complete simulation state rather than special-casing event sequences.

A local guard is acceptable only when it represents a genuine world rule, not when it conceals an incorrect model.

## 11. No false complexity

New subsystems must earn their place by improving the simulation's causal fidelity or the ability to understand its history.

Do not add agents, LLM calls, databases, orchestration layers, or abstraction merely because they sound sophisticated.

The core simulation should remain understandable, deterministic, testable, and independently runnable.

Complexity should follow demonstrated requirements.

## 12. Tests must protect behavior, not implementation accidents

Tests should verify the intended semantics of the world.

Prefer tests that demonstrate:

- objective facts remain unchanged by narrative analysis;
- goals match actions semantically rather than by substring accidents;
- different character states produce different decisions where appropriate;
- failures and consequences are represented honestly;
- relationships actually affect later behavior;
- memory and belief changes persist appropriately;
- snapshots replay exactly;
- long histories form meaningful causal chains;
- multiple seeds produce variation without destroying determinism.

Do not weaken a test merely to make an implementation pass. If the model is wrong, change the model.

## 13. Validation must include long-run behavior

Passing a small fixture is necessary but not sufficient.

Important simulation changes should be checked across:

- the canonical Genesis seed;
- multiple random seeds;
- longer runs;
- action distributions;
- movement patterns;
- relationship variance;
- causal-thread lengths and closure;
- narrative-pressure distribution;
- checkpoint/replay equivalence.

The purpose is to detect systems that technically pass unit tests while behaving unnaturally over time.

## 14. The canonical Genesis scenario is a regression anchor, not the whole world

Genesis (seed=7) is a reproducible fixture for testing.

It must remain stable unless a deliberate design change explicitly changes its expected behavior.

However, Genesis must not become an excuse to overfit the simulation to one story.

A behavior that only works for Genesis is not necessarily a correct world rule.

## 15. Design priority when principles conflict

When implementation convenience conflicts with these principles, use this order:

1. **World integrity and causal consistency**
2. **Character agency and meaningful state-driven behavior**
3. **Determinism and reproducibility**
4. **Faithful history and auditability**
5. **Story discovery from history**
6. **Literary structure and expression**
7. **Implementation convenience**

The system should never sacrifice world truth merely to produce a more convenient or more entertaining narrative.

## 16. The central question

Before accepting a major feature or architectural change, ask:

> **“Does this make the world more capable of genuinely living, changing, and producing history — or are we merely making it better at pretending to tell a story?”**

If the change mainly serves the latter, stop and reconsider the design.

---

**Status:** Binding design constitution for Aetherium.  
**Scope:** Simulation, character systems, memory, narrative discovery, testing, and future literary layers.  
**Change rule:** Changes to these principles should be deliberate, documented, and reviewed; implementation should adapt to the principles rather than silently redefining them.
