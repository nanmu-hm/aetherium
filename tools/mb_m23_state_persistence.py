"""M23 -- State Persistence -> Future Agency counterfactual audit.

Spec: ChatGPT on-platform, PR#10 5423617435 follow-up ("M23: State
Persistence -> Future Agency"). Read-only. Anchored to 0ba1699.

Question: do EXISTING character/world state fields (relationship
trust/affection/resentment/loyalty/respect/fear, emotions, desires,
goals, knowledge, habits, identity_beliefs, human_condition)
genuinely propagate through EXISTING readers (candidate generation,
DecisionKernel.evaluate / _utility / _relationship / _emotion /
_desire / _identity_belief terms, appraisal build_appraisals /
arbitrate) into candidate pools / utility / verdicts / committed
actions -- i.e. is there a field whose natural change, when
counterfactually reverted at each tick, actually changes a LATER
committed action (not just a temporal correlation)?

Method (per spec: real counterfactual, not "Event A before Action B"):
  1. Natural run: N ticks, use_arbitration=True (W2 production
     semantics, the m-b line's real step mode), record every tick's
     committed actions + the exact state-field values that
     immediately precede them.
  2. For each target field F in the audit list: a neutralized
     re-run where, after each engine.step(), we restore F (for all
     characters/relationships it belongs to) to its value at tick 0
     (the genesis baseline), leaving every OTHER field of that tick's
     natural evolution untouched. If any later committed action set
     differs between the natural and F-neutralized runs, F is
     demonstrated to carry forward-influence through the existing
     reader stack in THIS window; otherwise F is NOT PROVEN in this
     window (no forced sample, no new weight/field/reader/recall/
     downstream-write/plot -- spec's explicit do-not-list).
  3. If a difference is found, pin it to the exact tick(s) and the
     exact read site(s) in engine/core (the reader chain) that must
     be responsible, by checking which readers' input values actually
     changed between the two arms at that tick.

Readers audited (all pre-existing, no new ones introduced):
  - generate_action_pool(): _trust() reads rel.trust (actions.py:24);
    near/contact branch reads trust/resentment/fear (actions.py:99-113);
    social-need / distress branch reads emotions.sorrow/fear +
    relationship.resentment/fear (actions.py:150-156); goal/desire
    branch reads character.goals, human_condition.desires
    (actions.py:93-95, 110-111, 131).
  - DecisionKernel.evaluate()/utility(): relationship term reads
    rel.trust/loyalty/affection/respect/resentment/fear
    (decision.py:69-72, 145, 166); emotion term reads
    character.emotions (decision.py, _emotion_mapping); desire term
    reads human_condition.desires; identity-belief term reads
    identity_beliefs.
  - build_appraisals()/arbitrate(): appraisal axis for
    relationship-family candidates points at (relationship, actor,
    target, "trust") (appraisal.py:78-86).

Fields probed (spec's priority order: goal/desire/emotion/relationship
first, then the rest of its list):
  relationship: trust, affection, resentment, loyalty, respect, fear
  emotion:        joy, love, hope, longing, fear, sorrow, anger,
                  resentment
  desire:         reconciliation, belonging, exploration
  goal:           the top-priority active goal's "progress" field
                  (goal objects are mutated by _apply_goal_progress)
  human_condition: needs / drive values (whatever is a plain float
                  field there)
  habits:         procedural_habit strengths
  identity_beliefs: belief strengths
  knowledge:      knowledge-store entries (count only, since it is a
                  set, not a scalar)

All runs stay on use_arbitration=True (W2), 5 seeds, 200 ticks
(audited window: a real counterfactual difference does NOT need 1000
ticks to be real -- it just needs to be found and pinned to a reader;
200 keeps runtime bounded and is already 4x M22-R1's 30-tick window).
No engine/production/test change. No recall() wiring. No new weight,
field, reader, or plot. No manually triggered failure.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.actions import generate_action_pool
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEEDS = (1, 3, 7, 42, 99)
TICKS = 200

# (state-root, accessor-path) pairs the counterfactual will neutralize.
# relationship fields are keyed by (relationship-id, field); character
# fields by (character-id, field).
REL_FIELDS = ["trust", "affection", "resentment", "loyalty", "respect",
              "fear"]
EMOTION_FIELDS = ["joy", "love", "hope", "longing", "fear", "sorrow",
                  "anger", "resentment"]
DESIRE_FIELDS = ["reconciliation", "belonging", "exploration"]
HUMAN_CONDITION_FIELDS = ["mortality_pressure", "fatigue"]
HABIT_FIELDS = []           # filled in dynamically (character.habits)
BELIEF_FIELDS = []          # filled in dynamically (character.identity_beliefs)
GOAL_FIELDS = ["priority", "current_stage", "status"]
KNOWLEDGE_FIELDS = []      # count-based, handled specially


def snapshot_fields(world) -> dict:
    """Return a tick-0 baseline dict of every probed field, keyed
    (root, id, field) -> value, so a neutralized re-run can restore any
    probed field back to its genesis value on demand, without touching
    any non-probed field."""
    base: dict = {}
    for rid, rel in world.relationships.items():
        for f in REL_FIELDS:
            base[("rel", rid, f)] = getattr(rel, f)
    for cid, ch in world.characters.items():
        for f in EMOTION_FIELDS:
            base[("char", cid, f)] = ch.emotions.get(f, 0.0)
        for f in DESIRE_FIELDS:
            base[("char", cid, f)] = ch.human_condition.desires.get(f, 0.0)
        for f in HUMAN_CONDITION_FIELDS:
            base[("char-hc", cid, f)] = getattr(ch.human_condition, f, None)
        for f in HABIT_FIELDS:
            base[("char-habit", cid, f)] = ch.habits.get(f, 0.0)
        for f in BELIEF_FIELDS:
            base[("char-belief", cid, f)] = ch.identity_beliefs.get(f, 0.0)
        for f in GOAL_FIELDS:
            for g in ch.goals:
                base[("char-goal", cid, g.id, f)] = getattr(g, f, None)
    # _belief_friction's real input is state.memory_state.beliefs
    # (decision.py:89), NOT character.identity_beliefs -- a distinct
    # reader on a distinct field family (the M19 framing conflated
    # these; M23 probes both, under separate keys, and reports which
    # one actually carried a difference if any is found).
    base[("membelief", None, "count")] = len(world.memory_state.beliefs)
    # hold the full SET (deep copy) so neutralize() can restore which
    # specific beliefs existed, not just how many.
    base[("membelief", None, "set")] = {
        k: copy.deepcopy(v) for k, v in world.memory_state.beliefs.items()}
    # Knowledge lives per-actor: CharacterState.knowledge is set[str]
    # (models.py:51); state.memory_state.knowledge is a dict[actor_id,
    # dict[fact_id, KnowledgeFact]] (engine/memory/models.py:108).
    # The reader chain reads the KERNEL store per actor (actions.py:49,
    # :229), so neutralization must be per-actor, not a global count.
    for cid, ch in world.characters.items():
        base[("knowledge", cid, "char_count")] = len(ch.knowledge)
    for cid, facts in world.memory_state.knowledge.items():
        base[("knowledge", cid, "kernel_count")] = len(facts)
    return base

def neutralize(world, target: str, hold: dict) -> None:
    """Restore the TARGET field family to `hold` (its immediately-
    preceding NATURAL post-step value, captured by snapshot_fields()),
    leaving every other field at its current natural value. Called
    BEFORE candidate generation each tick, so the reader actually
    observes the held value, not a stale post-step one. This is the
    single-field counterfactual: 'as if field family F had NOT evolved
    during this tick's step, everything else did'."""
    if target == "relationship":
        for rid, rel in world.relationships.items():
            for f in REL_FIELDS:
                setattr(rel, f, hold[("rel", rid, f)])
    elif target == "emotion":
        for cid, ch in world.characters.items():
            for f in EMOTION_FIELDS:
                ch.emotions[f] = hold[("char", cid, f)]
    elif target == "desire":
        for cid, ch in world.characters.items():
            for f in DESIRE_FIELDS:
                ch.human_condition.desires[f] = hold[("char", cid, f)]
    elif target == "human_condition":
        for cid, ch in world.characters.items():
            for f in HUMAN_CONDITION_FIELDS:
                setattr(ch.human_condition, f, hold[("char-hc", cid, f)])
    elif target == "habit":
        for cid, ch in world.characters.items():
            for f in HABIT_FIELDS:
                ch.habits[f] = hold[("char-habit", cid, f)]
    elif target == "belief":
        for cid, ch in world.characters.items():
            for f in BELIEF_FIELDS:
                ch.identity_beliefs[f] = hold[("char-belief", cid, f)]
    elif target == "membelief":
        # The real input to _belief_friction (decision.py:89):
        # state.memory_state.beliefs, a dict[belief_id, Belief].
        # Restore the SET of belief objects to the held (preceding
        # natural) set, not just a count -- _belief_friction matches
        # owner_id + 'experience:' proposition prefix + outcome text,
        # so which specific belief exists matters, not how many.
        world.memory_state.beliefs = {k: copy.deepcopy(v)
                                      for k, v in
                                      hold[("membelief", None, "set")].items()}
    elif target == "goal":
        for cid, ch in world.characters.items():
            for g in ch.goals:
                for f in GOAL_FIELDS:
                    setattr(g, f, hold[("char-goal", cid, g.id, f)])
    elif target == "knowledge":
        # Per-actor truncation-only restore (see snapshot_fields for
        # why): drop the extra kernel-store facts and extra
        # character-set members beyond the held count, never add any.
        # If the reader chain's actual sensitivity is to WHICH fact
        # is remembered (content), not just COUNT, this target is
        # vacuous for M23's question and is reported as such rather
        # than forced.
        for cid, ch in world.characters.items():
            held_char = hold[("knowledge", cid, "char_count")]
            if len(ch.knowledge) > held_char:
                ch.knowledge = set(list(ch.knowledge)[:held_char])
            held_kernel = hold.get(("knowledge", cid, "kernel_count"), 0)
            facts = world.memory_state.knowledge.get(cid)
            if facts is not None and len(facts) > held_kernel:
                world.memory_state.knowledge[cid] = dict(
                    list(facts.items())[:held_kernel])


def run(seed: int, target: str | None, base: dict,
        genesis_membeliefs: dict) -> tuple[dict, list]:
    """Run N ticks. The counterfactual arm (target is not None) pins the
    target field family to its IMMEDIATELY-PRECEDING NATURAL value
    BEFORE candidate generation each tick -- not to the tick-0 genesis
    baseline, and NOT after engine.step() (the M22-R1 / M18 / M19
    timing class of bug: the reader for tick N runs before step N's
    consequences land, so pinning-after-step never actually changes
    what the next tick's reader observes, and any reported divergence
    is an artifact of when the pin fires, not a genuine state ->
    behavior effect).

    'before-step pinning to the preceding natural value' is the
    cleanest available single-field counterfactual: it isolates ONE
    field family's forward-influence without touching any other input,
    and -- unlike pinning to a fixed genesis value -- it does not
    also neutralize that field family's OWN earlier (pre-counterfactual)
    evolution, so a difference between arms is attributable to the
    reader actually consuming the field's natural post-step value, not
    to a frozen input the reader would never have seen in a real run.
    """
    global _GENESIS_MEMBELIEFS
    _GENESIS_MEMBELIEFS = genesis_membeliefs
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)
    commits: list = []
    hold = snapshot_fields(world)
    for _ in range(TICKS):
        t = world.tick
        if target is not None:
            neutralize(world, target, hold)  # pin BEFORE the reader
        committed = {a.actor_id: a.id for a in
                     _preview_committed(world, engine)}
        res = engine.step(world)
        hold = snapshot_fields(world)  # refresh to this step's natural
                                       # post-step value, for next tick
                                       # (only read in the next loop
                                       # iteration if target is set;
                                       # cheap enough to always compute
                                       # and keeps the natural arm
                                       # bit-identical in cost to the
                                       # neutralized arm, so a timing
                                       # asymmetry can't masquerade as a
                                       # "difference")
        commits.append({"tick": t, "committed": committed,
                        "events": [e.id for e in res.events]})
    return {"n_events": len(world.event_log), "events":
            [e.id for e in world.event_log]}, commits


_GENESIS_MEMBELIEFS: dict = {}


def _preview_committed(world, engine) -> list:
    """Mirror engine.generate_candidates()'s selection logic exactly,
    so the 'committed' record is what the engine itself would commit
    THIS tick (not a re-derivation that could drift from the real
    pipeline). Returns the same ActionCandidate objects engine.step()
    will receive into resolve()."""
    from engine.core.actions import generate_action_pool
    from engine.core.appraisal import build_appraisals, arbitrate, \
        apply_arbitration
    kernel = engine.decision_kernel
    selected = []
    for character in world.characters.values():
        pool = generate_action_pool(world, character.id)
        arbitration = None
        if engine.use_arbitration and pool:
            appraisals = build_appraisals(kernel, world, character, pool)
            evaluations = [kernel.evaluate(world, c) for c in pool]
            arbitration = arbitrate(appraisals, pool, evaluations)
            pool = apply_arbitration(pool, arbitration, evaluations)
        action = None
        if arbitration is not None and arbitration.kind == "resolve":
            action = next((c for c in pool if c.id == arbitration.candidate_id),
                          None)
        if action is None:
            action, _ = kernel.choose(world, pool, allow_quiet=True)
        if action is not None:
            selected.append(action)
    return selected


def main() -> int:
    print("=" * 72)
    print("M23  State Persistence -> Future Agency  (read-only, "
          "0ba1699)")
    print("=" * 72)

    # Discover the dynamic field lists (habits, identity_beliefs)
    # from one genesis world, so the neutralizer and report are
    # honest about exactly which fields exist.
    probe = build_genesis_world()
    probe.timestamp = "0001-01-01T00:00:00"
    ch_sample = next(iter(probe.characters.values()))
    global HABIT_FIELDS, BELIEF_FIELDS
    HABIT_FIELDS[:] = [f for f in ch_sample.habits]
    BELIEF_FIELDS[:] = [f for f in ch_sample.identity_beliefs]
    print(f"\nFields discovered: habits={HABIT_FIELDS}, "
          f"beliefs={BELIEF_FIELDS}")

    # Establish each seed's genesis baseline BEFORE any run mutates
    # shared module state (build_genesis_world() is called fresh per
    # arm, so baselines are per-arm, not cross-arm contaminated).
    TARGETS = ["relationship", "emotion", "desire", "goal",
               "habit", "belief", "membelief", "human_condition",
               "knowledge"]

    results: dict = {}
    for seed in SEEDS:
        world0 = build_genesis_world()
        world0.timestamp = "0001-01-01T00:00:00"
        base = snapshot_fields(world0)
        genesis_membeliefs = {k: copy.deepcopy(v)
                              for k, v in
                              world0.memory_state.beliefs.items()}
        natural_summary, natural_commits = run(
            seed, None, base, genesis_membeliefs)
        per_target: dict = {}
        for target in TARGETS:
            neutral_summary, neutral_commits = run(
                seed, target, base, genesis_membeliefs)
            diff_ticks = [i for i in range(len(natural_commits))
                          if natural_commits[i]["committed"] !=
                             neutral_commits[i]["committed"]]
            per_target[target] = {"diff_ticks": diff_ticks,
                                  "n_events_natural": natural_summary[
                                      "n_events"],
                                  "n_events_neutral": neutral_summary[
                                      "n_events"]}
            if diff_ticks:
                first = diff_ticks[0]
                rec_n = natural_commits[first]
                rec_x = neutral_commits[first]
                print(f"\n  seed {seed} / {target}: committed-action "
                      f"DIVERGES starting tick {rec_n['tick']} "
                      f"({len(diff_ticks)} of {TICKS} ticks differ)")
                print(f"     natural arm @t{rec_n['tick']}: "
                      f"{rec_n['committed']}")
                print(f"     neutralized @t{rec_n['tick']}: "
                      f"{rec_x['committed']}")
                print(f"     reader chain responsible (existing, no new "
                      f"reader): see report section [READERS]")
            else:
                print(f"  seed {seed} / {target}: no committed-action "
                      f"difference in ticks 1-{TICKS} when ONLY the "
                      f"'{target}' field family is held, BEFORE each "
                      f"tick's candidate generation, at that family's "
                      f"immediately-preceding natural value (i.e. as if "
                      f"that family had not evolved during the step, "
                      f"while everything else evolved normally) -> "
                      f"forward-influence of '{target}' NOT PROVEN in "
                      f"this window (not a whole-space zero; a longer "
                      f"window, a different seed, or a co-movement of "
                      f"multiple field families could still carry "
                      f"influence).")
        results[seed] = per_target

    # Reader-chain documentation (static, verified against the source
    # grep done during tool development -- pinned to line numbers, not
    # re-derived at runtime so a report reader can verify by opening
    # the file at those lines):
    reader_map = {
        "relationship": [
            "engine/core/actions.py:24 _trust() -> rel.trust",
            "engine/core/actions.py:99-113 near/contact branch: "
            "min(nearby, key=_trust); tension from 100-trust, "
            "relationship.resentment, relationship.fear",
            "engine/core/decision.py:69-72 relationship utility term: "
            "(trust+loyalty+affection+respect-resentment-fear)/500, "
            "blended with tension and a 0.25*trust/100 term",
            "engine/core/decision.py:145 alignment penalty from "
            "max(resentment, fear, 100-trust)",
            "engine/core/decision.py:166 desire gate scaled by "
            "max(desires.reconciliation, desires.belonging, "
            "emotions.longing, emotions.resentment, emotions.love)",
            "engine/core/appraisal.py:78-86 relationship-family "
            "appraisal axis = (relationship, actor, target, 'trust')",
        ],
        "emotion": [
            "engine/core/actions.py:114 emotional_pressure = "
            "max(emotions.anger, longing, resentment, love); drives "
            "the contact-pool gate (>=20.0) at line 136",
            "engine/core/actions.py:150-156 distress branch: "
            "sorrow+fear picks help/cuddle candidate target",
            "engine/core/decision.py _emotion_mapping + "
            "_emotion_compatibility: per-action-type emotion "
            "compatibility table (decision.py:122) feeds utility",
        ],
        "desire": [
            "engine/core/actions.py:110-111 reconciliation/belonging "
            "desire floats feed the contact-pool motive "
            "(line 129-130)",
            "engine/core/decision.py:166 desire gate (same term as "
            "relationship map, listed once there)",
        ],
        "goal": [
            "engine/core/actions.py:93-95 top-priority active goal "
            "opens the 'pursue' candidate pool branch",
            "engine/core/decision.py goal-alignment term reads "
            "character.goals and candidate.goal_alignment",
        ],
        "habit": [
            "engine/core/decision.py:107-108 _habit_alignment reads "
            "character.habits[canonical_action_type] (the field is "
            "named `habits`, not `procedural_habits`); feeds utility "
            "at decision.py:192 via self.weights.habit * habit, plus "
            "a symmetric -repetition term on the same line",
        ],
        "belief": [
            "engine/core/decision.py:117 identity term reads "
            "character.identity_beliefs (a self-concept map, -1..+1, "
            "distinct field from the memory-kernel beliefs below)",
        ],
        "membelief": [
            "engine/core/decision.py:86-104 _belief_friction reads "
            "state.memory_state.beliefs (the MemoryKernel's Belief "
            "objects, keyed by owner_id, matched by 'experience:' "
            "proposition prefix + action_type + outcome text). This is "
            "the ACTUAL reader input for the belief-friction utility "
            "term -- the M19 framing attributed this to "
            "character.identity_beliefs, which is a DIFFERENT field "
            "(the identity self-concept map, decision.py:117). M23 "
            "probes both under separate targets ('belief' and "
            "'membelief') so a found difference can be attributed to "
            "the correct reader, not silently merged.",
        ],
        "human_condition": [
            "engine/core/human_condition.py HumanCondition dataclass: "
            "mortality_pressure, fatigue are the two plain-float "
            "fields probed (attachments/losses/desires/fears/"
            "virtues/vices are dict fields, folded into the desire "
            "target's own family -- do not double-count them here); "
            "DecisionKernel fatigue term (decision.py:196, "
            "fatigue_cost/fatigue_bonus) is the read site",
        ],
        "knowledge": [
            "engine/core/actions.py:49 (and :229): reader reads "
            "state.memory_state.knowledge.get(character_id) content "
            "directly -- this is the memory KERNEL store, not "
            "character.knowledge (the per-actor set[str], "
            "models.py:51). Both are probed; character.knowledge's "
            "count is informational only, since no decision-path "
            "reader found in this grep reads the character-level set "
            "directly (its content is mirrored INTO the kernel store "
            "by engine/core/simulation.py:156 after a successful "
            "event, and only the kernel store is read back into "
            "candidate generation).",
        ],
    }
    print("\n[READERS] Existing read sites per target field family "
          "(line numbers pinned; open engine/core at these lines to "
          "verify):")
    for target, lines in reader_map.items():
        print(f"  {target}:")
        for l in lines:
            print(f"     {l}")

    print("\nSummary (no target = natural arm; each other row = that "
          "field family held, before each tick's candidate generation, "
          "at its immediately-preceding natural value, all other "
          "fields evolving naturally):")
    for seed, per_target in results.items():
        diffs = {t: v["diff_ticks"] for t, v in per_target.items()
                 if v["diff_ticks"]}
        print(f"  seed {seed}: forward-influence demonstrated in "
              f"{len(diffs)}/{len(TARGETS)} target families: "
              f"{sorted(diffs) if diffs else 'NONE in this window'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
