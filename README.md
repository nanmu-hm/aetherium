# aetherium

chatgpt+胡明的小世界

Aetherium is a world simulation and narrative-emergence engine. Its core
principle is that the world generates history first; the novel is discovered
from that history rather than imposed on it.

## Current architecture

- **World simulation** — characters, relationships, factions, actions, events and consequences.
- **Human condition layer** — attachment, loss, desire, fear, virtue and mortality as pressures that shape choices without becoming plot triggers.
- **Memory layer** — persistent character/world memory for continuity.
- **Narrative pressure** — measures the difficulty and consequence of existing events without inventing events.
- **Story archaeology** — finds persistent, consequential historical threads that may deserve to become stories.
- **Narrative presentation** — intentionally kept separate from the simulated world so style can be selected after a story is discovered.

## Design rule

**Characters choose. Events change characters. The world remembers. History accumulates. Stories are discovered from history.**

The human-condition vocabulary is an affordance layer, not a checklist: Aetherium
must be free to produce joy, grief, love, friendship, conflict, sacrifice,
regret, separation and fulfillment through autonomous interaction rather than
being instructed to insert them on demand.

## Development status

The project is currently moving from the architecture prototype into the
first **Genesis Test**: run a small world forward, observe whether persistent
human pressure creates consequential chains, and only then extract candidate
stories.
