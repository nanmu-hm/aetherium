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

## Draft and approval boundary

Writer output is always a **Narrative Draft** first.

The Human Approval Service then provides the explicit workflow:

Writer -> NARRATIVE_EDIT -> Draft v1 -> Human edit/revision -> Draft v2 -> Approve -> Narrative Canon

A human may change prose or title, but the draft workflow preserves the originating source event IDs, participant IDs, viewpoint, branch, and tick. A new draft version supersedes the previous pending version rather than rewriting it.

Approval publishes the exact approved prose into the append-only NarrativeCanonLedger. It does **not** mutate World State.

A real-world change such as changing a character's location, relationship, memory, event, or world rule remains an intervention and must use the existing intervention authority path.

See docs/HUMAN-APPROVAL.md for the boundary and provenance rules.

## Flow

Simulation -> NarrativeObserver -> NarrativeScene -> WriterAgent -> SceneDraft -> HumanApprovalService -> NarrativeCanon

The generated prose is not authoritative until a human explicitly approves it, and even approved narrative canon remains separate from authoritative simulation state.
