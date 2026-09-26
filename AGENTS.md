# AGENTS.md

## What this repo is

Aetherium is a **deterministic world-simulation engine**. It advances a small fictional world tick-by-tick without plot injection; characters choose, events change state, memory persists, and story threads are *discovered* from accumulated history. No LLM calls, no external dependencies — pure Python dataclasses + `random.Random` seed for reproducibility.

## Commands

```bash
# Run all tests (no deps beyond stdlib + pytest)
python -m pytest -q

# Run a single test file
python -m pytest tests/test_genesis.py -q

# Run the demo smoke test (prints events from 3 ticks)
python -m engine.core.demo

# Run the Genesis scenario manually
python -c "from engine.genesis import discover_genesis_stories; w, c = discover_genesis_stories(ticks=12, seed=7); [print(e.facts[0]) for e in w.event_log]"
```

CI (GitHub Actions, `.github/workflows/ci.yml`): Python 3.12, `pip install pytest`, `python -m pytest -q`.

## Module layout

```
engine/
  core/       WorldState, CharacterState, SimulationEngine (tick loop, seed-driven)
  memory/     MemoryKernel (deterministic decay + cue-based recall), InMemoryStore
  narrative/  StoryArchaeologist (thread discovery), NarrativePressureAnalyzer, NarrativeObserver
  genesis.py  Deterministic 12-tick scenario; the primary reproducible test fixture
```

Tests mirror the module names under `tests/`.

## Design invariants (from `docs/GENESIS-TEST.md` and `docs/ROADMAP.md`)

These are **binding constraints on what code may do**:

1. The narrative layer observes history — it never writes world facts.
2. Human-condition values are pressures/affordances, not mandatory plot beats.
3. `SimulationEngine` is the only authority that mutates `WorldState`.
4. Reproducibility: same seed → same event sequence. Tests assert this explicitly.
5. `WorldState.timestamp` advances 24 h per tick from `0001-01-01` (tick 12 → `0001-01-13`).

## Key gotchas

- `CharacterState.relationships` (dict) is **deprecated** — authoritative relationship state is `WorldState.relationships` (list of `RelationshipState`).
- `MemoryKernel.decay()` computes effective decay as `rate × (1 − protection)` where protection blends salience, personal importance, relationship importance, and unresolved flag. Do not add a new protection factor without adjusting the cap (currently 0.9).
- `StoryArchaeologist.discover()` groups events into one thread per connected chain (events within 6 ticks sharing participants). It deliberately returns one candidate per chain, not one per event.
- `engine/genesis.py` hard-codes `seed=7` for the canonical test scenario; changing the seed will break `test_genesis.py` reproducibility assertions.
- `pyproject.toml` sets `pythonpath = ["."]` — run pytest from the repo root; do not `cd` into `engine/`.
- No external runtime dependencies. Only `pytest` is needed to run tests.

## Docs worth reading before large changes

- `docs/ROADMAP.md` — phase checklist and cross-cutting invariants
- `docs/GENESIS-TEST.md` — current test-phase spec and success criteria
- `docs/WORLD-CONSTITUTION.md` — world-simulation rules
