# AGENTS.md

## What this repo is

Aetherium is a **deterministic world-simulation engine**. It advances a small fictional world tick-by-tick without plot injection; characters choose, events change state, memory persists, and story threads are *discovered* from accumulated history. No LLM calls, no external dependencies — pure Python dataclasses + random.Random seed for reproducibility.

## Binding design constitution

**Before changing architecture, simulation rules, character behavior, narrative systems, or tests, read docs/DESIGN-PRINCIPLES.md.**

The following principles are binding:

1. **World first.** Aetherium is a self-evolving small world, not an AI novel-writing application.
2. **Simulation is the source of truth.** Narrative observes and discovers history; it never injects facts, causes, outcomes, conflicts, revelations, or character changes into the world to make a story better.
3. **Character agency drives history.** The causal loop is: 人物 → 行动池 → 世界状态 → 冲突/机会 → 事件 → 人物改变 → 新行动池 → 新冲突/机会 → 新事件 → 历史.
4. **Personality must eventually be causal.** The intended chain is: 客观事件 → 可知信息 → 性格/经历/价值观/关系解释 → 情绪 → 记忆 → 信念 → 欲望/目标 → 行动. Personality is not merely dialogue decoration.
5. **Human-condition values are pressures/affordances, not mandatory plot beats.** The world must permit failure, loss, separation, misunderstanding, missed opportunities, and 求不得 without forcing them into every story.
6. **Story discovery follows history.** Story Archaeology, causal threads, arcs, revelations, convergence, and foreshadowing discover patterns in accumulated history; they do not rewrite history.
7. **Literary style is downstream.** 世界事实 → 历史/因果 → 故事发现 → 结构 → 文学表达. Style must not change facts, knowledge, success/failure, relationships, chronology, or causality.
8. **Determinism and auditability are foundational.** Random state must be restorable; checkpoints must reproduce future simulation exactly.
9. **Fix causes, not symptoms.** Do not hide an incorrect causal model with arbitrary cooldowns, caps, or suppression rules unless the restriction represents a genuine world rule.
10. **No false complexity.** New agents, LLM calls, orchestration, or abstractions must solve demonstrated problems and must not obscure the core simulation.
11. **Tests protect semantics.** Do not weaken tests to accommodate incorrect behavior. Test world integrity, agency, causality, replay, long-run behavior, and meaningful variation.
12. **Genesis is a regression anchor, not the whole world.** The canonical seed=7 scenario protects reproducibility but must not become a reason to overfit the simulation.

When principles conflict, prioritize:
**world integrity and causal consistency → character agency → determinism/reproducibility → faithful history/auditability → story discovery → literary expression → implementation convenience.**

The central review question is:

> Does this change make the world more capable of genuinely living, changing, and producing history — or merely better at pretending to tell a story?

## Commands

- Run all tests: python -m pytest -q
- Run a single test file: python -m pytest tests/test_genesis.py -q
- Run the demo smoke test: python -m engine.core.demo
- Run Genesis: python -c "from engine.genesis import discover_genesis_stories; w, c = discover_genesis_stories(ticks=12, seed=7); [print(e.facts[0]) for e in w.event_log]"

CI (GitHub Actions, .github/workflows/ci.yml): Python 3.12, pip install pytest, python -m pytest -q.

## Module layout

engine/
  core/       WorldState, CharacterState, SimulationEngine (tick loop, seed-driven)
  memory/     MemoryKernel (deterministic decay + cue-based recall), InMemoryStore
  narrative/  StoryArchaeologist (thread discovery), NarrativePressureAnalyzer, NarrativeObserver
  genesis.py  Deterministic 12-tick scenario; the primary reproducible test fixture

Tests mirror the module names under tests/.

## Design invariants

These are **binding constraints on what code may do**:

1. The narrative layer observes history — it never writes world facts.
2. Human-condition values are pressures/affordances, not mandatory plot beats.
3. SimulationEngine is the only authority that mutates WorldState.
4. Reproducibility: same seed → same event sequence. Tests assert this explicitly.
5. WorldState.timestamp advances 24 h per tick from 0001-01-01 (tick 12 → 0001-01-13).

## Key gotchas

- CharacterState.relationships (dict) is **deprecated** — authoritative relationship state is WorldState.relationships (list of RelationshipState).
- MemoryKernel.decay() computes effective decay as rate × (1 − protection) where protection blends salience, personal importance, relationship importance, and unresolved flag. Do not add a new protection factor without adjusting the cap (currently 0.9).
- StoryArchaeologist.discover() groups events into one thread per connected chain (events within 6 ticks sharing participants). It deliberately returns one candidate per chain, not one per event.
- engine/genesis.py hard-codes seed=7 for the canonical test scenario; changing the seed will break test_genesis.py reproducibility assertions.
- pyproject.toml sets pythonpath = ["."] — run pytest from the repo root; do not cd into engine/.
- No external runtime dependencies. Only pytest is needed to run tests.

## Docs worth reading before large changes

- docs/DESIGN-PRINCIPLES.md — **binding project design constitution; read this first**
- docs/ROADMAP.md — phase checklist and cross-cutting invariants
- docs/GENESIS-TEST.md — current test-phase spec and success criteria
- docs/WORLD-CONSTITUTION.md — world-simulation rules
