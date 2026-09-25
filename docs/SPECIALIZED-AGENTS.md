# Specialized Agents

Aetherium now has three deterministic specialist agents above the Director layer.

## Character Agent

CharacterAgent(character_id) reads one character's goals, emotions, desires, knowledge, memories, and relationships from the detached world snapshot.

It can recommend keeping attention on a real active goal. It does not choose an action, rewrite the character, or change the world.

## Continuity Agent

ContinuityAgent validates structural continuity:

- character locations exist;
- relationship endpoints exist;
- event IDs are unique;
- event chronology is ordered;
- events do not lie beyond the current world tick;
- event locations exist;
- event participants exist.

A continuity failure is a diagnostic, not an automatic repair.

## Critic Agent

CriticAgent provides independent review signals. The current deterministic checks look for recent concentration on one lead character or one location and report open narrative pressure when such information is available.

Critic findings are recommendations, not authoritative defects.

## Authority

All three agents operate through AgentContext snapshots and return AgentResult. They never receive a mutable WorldState.

They can therefore be replaced or augmented later with model-backed reasoning without changing the authority boundary.
