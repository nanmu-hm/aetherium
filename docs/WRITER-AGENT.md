# Writer Agent and Scene Generation

Aetherium now has a deterministic WriterAgent above the narrative structure layer.

The Writer consumes:

- authoritative world snapshot;
- selected NarrativeScene or selected event IDs;
- scene expression plan when available;
- existing event facts and participants.

The Writer produces a SceneDraft and a non-authoritative NARRATIVE_EDIT proposal.

## Guardrails

The Writer does not create new world facts, mutate characters, alter event history, or silently invent dialogue.

Every generated scene records its source event IDs and participant IDs. Before generation, ProseQualityGate checks that the referenced events and characters exist.

The first implementation is intentionally deterministic. A model-backed Writer can later replace only the prose generation step while retaining the same source-event, viewpoint, and authority contracts.

## Flow

Simulation -> NarrativeObserver -> NarrativeScene -> WriterAgent -> SceneDraft

The generated prose is a draft. It does not become canon until a later approval/publishing layer explicitly accepts it.
