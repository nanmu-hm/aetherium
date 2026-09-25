# Autonomous Long-Run Mode

Aetherium's autonomous mode runs the **world simulation forward**. It does not ask narrative systems to manufacture events, and it does not let Writer output steer character choices.

## Responsibilities

`AutonomousRunController` only controls execution:

- repeat `SimulationEngine.step()`;
- observe the resulting events through `NarrativeObserver`;
- collect story discoveries without treating them as commands;
- enforce tick and validation safety limits;
- create optional filesystem checkpoints;
- allow a clean stop at tick boundaries.

## Stop conditions

A run can stop because:

- the configured maximum tick count was reached;
- a validation error exceeded the configured limit;
- a story discovery crossed the configured score threshold and `stop_on_story_discovery=True`;
- an external stop signal requested a pause.

The report records the reason and all events observed during the run.

## Checkpoints

When a `WorldRepository` is supplied, the controller can create:

- an initial checkpoint before the run;
- periodic checkpoints every N ticks;
- a diagnostic checkpoint when validation stops the run;
- a story-discovery checkpoint when configured to stop on a discovery.

Checkpoints preserve the current branch and world snapshot.

## Narrative boundary

`Simulation -> AutonomousRunController -> NarrativeObserver`

A `StoryDiscoveryCandidate` is an observation. It does not become an instruction to characters, the Director, or the Writer.

This maintains the core invariant:

**world evolution remains causally driven by character state and simulation rules, while story discovery remains downstream of history.**

## Future extension

A later autonomous loop can add a human-intervention threshold or model-backed Director consultation. That extension must remain outside the core world mutation path.
