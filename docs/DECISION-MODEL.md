# Decision Model

Aetherium uses bounded rationality rather than assuming every character is a perfectly consistent optimizer.

## Character controls

- decision_noise ranges from 0 to 1. It adds a reproducible, character-specific perturbation to action selection. Zero preserves deterministic utility-only selection; higher values allow a lower-utility action to win sometimes.
- risk_tolerance ranges from 0 to 1. It reduces how strongly perceived action risk lowers utility.

The perturbation is seeded from the simulation seed, tick, character, and action ID. The same world, seed, and action pool therefore remain reproducible.

The important boundary is:

WORLD STATE -> PERCEIVED UTILITY -> BOUNDED DECISION -> ACTION

The decision kernel never sees narrative signals, future events, or the reader's needs.

## Preconditions

Preconditions answer whether an action can be attempted. They are distinct from outcome probability.

precondition failure -> blocked

preconditions satisfied -> success/failure roll

The structured checks currently cover actor/target activity, locations, required abilities, possessions, and declared action conditions. A blocked action creates history but does not create success/failure learning.
