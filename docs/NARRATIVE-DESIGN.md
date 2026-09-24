# Narrative Design

Aetherium must optimize for a compelling novel without turning the simulator into a rigid plot generator.

## 1. Two loops

The simulation loop answers:

> What would happen in this world?

The narrative loop answers:

> Which consequences are becoming worth telling?

These loops must remain separate.

```
World -> Character Desire -> Choice -> Action -> Event -> Consequence
  ^                                                        |
  |--------------------------------------------------------|

History -> Narrative Observation -> Threads / Dilemmas / Pressure
        -> Beats -> Scenes -> Sequences -> Story Arcs -> Novel
```

The narrative layer observes and proposes. It does not silently rewrite authoritative world state.

## 2. Dramatic tension

Aetherium should prefer **meaningful choices** over arbitrary spectacle.

Important sources of pressure include:

- competing goals;
- conflicting values;
- relationship obligations;
- limited resources;
- incomplete or asymmetric information;
- time pressure;
- irreversible costs;
- external threats;
- secrets and misunderstandings.

A strong dilemma is not simply "good choice vs bad choice". It is often two desirable or necessary values in conflict.

Example:

```
protect a friend
       vs
protect a larger responsibility
```

The character decides according to their character model. The system must not force the "dramatic" answer.

## 3. Narrative pressure is not spectacle

Pressure should measure unresolved tension and consequence, not explosions or combat.

Useful signals include:

- persistent state changes;
- relationship changes;
- conflicting goals;
- unresolved questions;
- irreversible consequences;
- information asymmetry;
- character transformation;
- causal reach across multiple actors or factions.

A quiet conversation can therefore have high narrative value if it permanently changes trust.

## 4. Rhythm

A novel needs breathing room.

Aetherium should recognize patterns such as:

```
calm -> anomaly -> friction -> escalation
-> choice -> consequence -> release
-> new question -> renewed pressure
```

The system must not maximize pressure at every tick.

After a high-pressure sequence, it may prefer:

- recovery;
- reflection;
- relationship scenes;
- travel;
- ordinary life;
- information discovery.

These scenes can strengthen characterization and emotional investment even when they do not advance the main external plot.

## 5. Narrative threads

A thread is a persistent question, relationship, secret, promise, object, conflict, or consequence that can cross many events.

A thread should support:

```
seed -> development -> complication -> revelation -> payoff
```

A seed must be valid in the present world even if its future significance is unknown.

Do not manufacture an object or secret merely because a later chapter needs a twist.

## 6. Information and revelation

World truth, character knowledge, and reader knowledge are different layers.

For a fact F:

```
world truth(F)
character knows(F)
character believes(F)
reader knows(F)
```

These states must not be conflated.

Information asymmetry naturally creates mystery, misunderstanding, suspicion, and delayed reinterpretation.

## 7. Character agency

The narrative layer may increase pressure by changing circumstances, opportunities, risks, information flow, or time constraints.

It should not directly command:

> "Character X must betray Character Y."

Instead it creates a situation in which betrayal is one possible action among several. The character model determines the choice.

## 8. Narrative beats

The smallest useful narrative unit is a **beat**, not a chapter.

A beat can be:

- an action;
- a discovery;
- a decision;
- a refusal;
- a revelation;
- a relationship change;
- a meaningful silence.

Beats form scenes; scenes form sequences; sequences form arcs.

## 9. Story discovery

Aetherium should discover stories from history rather than pre-write a plot.

The emergence process is:

```
simulation history
-> recurring threads
-> unresolved tensions
-> character dilemmas
-> causal convergence
-> narrative beats
-> story arc
```

A story may become visible only after many simulation ticks.

## 10. Inspiration boundary

Aetherium may study narrative mechanisms from great fiction, including Jin Yong's handling of character motivation, foreshadowing, information, pacing, and interlocking plot threads.

It should learn **mechanisms**, not reproduce an author's prose, passages, characters, or distinctive expression.

The goal is not "write like Jin Yong".

The goal is:

> Build a world where strong characterization, causality, foreshadowing, dilemmas, and rhythm can naturally produce compelling stories.
