from engine.core.models import CharacterState, Consequence, Event, RelationshipState, WorldState
from engine.memory.kernel import MemoryKernel
from engine.narrative.arcs import CharacterArcDetector
from engine.narrative.information import KnowledgeAsymmetryAnalyzer, RevelationDetector
from engine.narrative.observer import NarrativeObserver
from engine.narrative.threads import CausalThreadEngine


def test_causal_thread_engine_groups_connected_consequences():
    state = WorldState(world_id="threads")
    state.add_character(CharacterState(id="a", name="A"))
    state.add_character(CharacterState(id="b", name="B"))
    for tick, field in [(1, "trust"), (2, "resentment"), (3, "affection")]:
        state.event_log.append(Event(
            f"e{tick}", tick, f"t{tick}", "town", ["a", "b"], [f"choice-{tick}"],
            [f"event {tick}"],
            consequences=[Consequence("relationship", "a:b", field, 50, 55, "change")],
        ))
    threads = CausalThreadEngine().discover(state)
    assert len(threads) == 1
    assert threads[0].event_ids == ["e1", "e2", "e3"]
    assert threads[0].thread_type == "relationship"
    assert threads[0].unresolved_question


def test_causal_thread_engine_separates_distant_history():
    state = WorldState(world_id="threads")
    state.add_character(CharacterState(id="a", name="A"))
    state.add_character(CharacterState(id="b", name="B"))
    state.event_log.extend([
        Event("e1", 1, "t", "town", ["a", "b"], ["c1"], ["first"], [Consequence("relationship", "a:b", "trust", 50, 60, "change")]),
        Event("e9", 20, "t", "town", ["a", "b"], ["c9"], ["later"], [Consequence("relationship", "a:b", "trust", 60, 70, "change")]),
    ])
    threads = CausalThreadEngine().discover(state)
    assert len(threads) == 2


def test_character_arc_detector_finds_persistent_change():
    state = WorldState(world_id="arcs")
    state.add_character(CharacterState(id="lin", name="Lin"))
    state.event_log.extend([
        Event("e1", 1, "t", "town", ["lin"], ["c1"], ["Lin tries."], consequences=[
            Consequence("character", "lin", "identity_beliefs.reliable", 0.0, 0.08, "evidence"),
            Consequence("character", "lin", "emotions.joy", 0.0, 5.0, "outcome"),
        ]),
        Event("e2", 2, "t", "town", ["lin"], ["c2"], ["Lin succeeds."], consequences=[
            Consequence("goal", "g1", "status", "active", "achieved", "goal"),
        ]),
    ])
    arcs = CharacterArcDetector().detect(state)
    arc = next(item for item in arcs if item.character_id == "lin")
    assert arc.phase == "transforming"
    assert arc.change_score > 0
    assert arc.identity_changes


def test_character_arc_detector_tracks_relationship_trajectory():
    state = WorldState(world_id="arcs")
    state.add_character(CharacterState(id="lin", name="Lin"))
    state.add_character(CharacterState(id="mei", name="Mei"))
    state.event_log.append(Event("e1", 1, "t", "town", ["lin", "mei"], ["c1"], ["loss"], consequences=[
        Consequence("relationship", "lin:mei", "trust", 50, 35, "loss"),
        Consequence("relationship", "mei:lin", "resentment", 0, 20, "loss"),
    ]))
    arcs = CharacterArcDetector().detect(state)
    assert next(item for item in arcs if item.character_id == "lin").relationship_changes
    assert next(item for item in arcs if item.character_id == "mei").relationship_changes


def test_knowledge_asymmetry_finds_partial_distribution():
    state = WorldState(world_id="info")
    for cid in ("lin", "mei", "rui"):
        state.add_character(CharacterState(id=cid, name=cid.title()))
    kernel = MemoryKernel()
    kernel.learn_fact(state.memory_state, "lin", "Mei left town.", 1, source_event_id="e1")
    kernel.learn_fact(state.memory_state, "mei", "Mei left town.", 2, source="heard", source_owner_id="lin", confidence=0.8)
    gaps = KnowledgeAsymmetryAnalyzer().analyze(state)
    gap = next(item for item in gaps if item.proposition == "Mei left town.")
    assert gap.known_by == ["lin", "mei"]
    assert gap.unknown_by == ["rui"]
    assert gap.source_event_ids == ["e1"]
    assert gap.confidence_range == (0.8, 1.0)


def test_revelation_detector_prefers_relationship_grounding():
    state = WorldState(world_id="info")
    for cid in ("lin", "mei", "rui"):
        state.add_character(CharacterState(id=cid, name=cid.title()))
    state.add_relationship(RelationshipState("lin", "rui", trust=80, affection=60, respect=70))
    state.add_relationship(RelationshipState("mei", "rui", trust=10, affection=10, respect=10))
    kernel = MemoryKernel()
    kernel.learn_fact(state.memory_state, "lin", "The bridge is broken.", 1, source_event_id="e7", confidence=1.0)
    gaps = KnowledgeAsymmetryAnalyzer().analyze(state)
    revelations = RevelationDetector().detect(state, gaps)
    target = next(item for item in revelations if item.target_character_id == "rui" and item.source_character_id == "lin")
    assert target.source_event_id == "e7"
    assert target.strength > 0.7


def test_observer_exposes_new_narrative_structure():
    state = WorldState(world_id="observer")
    state.add_character(CharacterState(id="lin", name="Lin"))
    state.add_character(CharacterState(id="mei", name="Mei"))
    state.add_relationship(RelationshipState("lin", "mei", trust=60))
    event = Event("e1", 1, "t", "town", ["lin", "mei"], ["choice"], ["Lin tells Mei something important."], consequences=[Consequence("relationship", "lin:mei", "trust", 60, 70, "honesty")])
    state.event_log.append(event)
    MemoryKernel().learn_fact(state.memory_state, "lin", "A secret exists.", 1, source_event_id="e1")
    before_tick = state.tick
    narrative = NarrativeObserver().observe(state, [event])
    assert narrative.threads
    assert narrative.arcs
    assert narrative.information_gaps
    assert narrative.revelations
    assert narrative.unresolved_threads == narrative.threads
    assert state.tick == before_tick
