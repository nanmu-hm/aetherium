from __future__ import annotations

from dataclasses import replace

from .models import LiteraryMechanismProfile


class LiteraryResearchRegistry:
    """Store abstract literary mechanisms, never prose imitation presets."""

    def __init__(self, profiles: list[LiteraryMechanismProfile] | None = None) -> None:
        self._profiles = profiles or self._default_profiles()

    @staticmethod
    def _default_profiles() -> list[LiteraryMechanismProfile]:
        return [
            LiteraryMechanismProfile(
                id="causal_foreshadowing",
                title="Causal Foreshadowing",
                mechanisms=["seed from existing state", "delay interpretation", "payoff through consequence"],
                constraints=["never invent prior evidence", "payoff remains optional"],
                intended_effects=["anticipation", "retrospective coherence"],
                compatible_dimensions=["pacing", "subtext", "motif"],
            ),
            LiteraryMechanismProfile(
                id="relationship_subtext",
                title="Relationship Subtext",
                mechanisms=["indirect intention", "knowledge asymmetry", "emotional restraint"],
                constraints=["dialogue cannot reveal unknown facts", "character voice remains stable"],
                intended_effects=["tension", "ambiguity", "characterization"],
                compatible_dimensions=["dialogue", "viewpoint", "subtext"],
            ),
            LiteraryMechanismProfile(
                id="multi_thread_interleaving",
                title="Multi-Thread Interleaving",
                mechanisms=["alternate active arcs", "cross-thread pressure", "delayed return"],
                constraints=["do not switch solely for artificial cliffhangers", "preserve causal continuity"],
                intended_effects=["breadth", "anticipation", "convergence"],
                compatible_dimensions=["pacing", "scene order", "information"],
            ),
            LiteraryMechanismProfile(
                id="jianghu_classic_mechanics",
                title="Jianghu Classic Mechanisms",
                mechanisms=["loyalty-versus-freedom tension", "reciprocal debt", "martial/social hierarchy pressure", "encounter consequence chains"],
                constraints=["mechanisms are abstract", "no author imitation", "character agency remains primary"],
                intended_effects=["relationship tension", "stakes", "earned reversals"],
                compatible_dimensions=["character", "relationship", "action", "foreshadowing"],
            ),
        ]

    def list(self) -> list[LiteraryMechanismProfile]:
        return [replace(profile, mechanisms=list(profile.mechanisms), constraints=list(profile.constraints), intended_effects=list(profile.intended_effects), compatible_dimensions=list(profile.compatible_dimensions)) for profile in self._profiles]

    def get(self, profile_id: str) -> LiteraryMechanismProfile | None:
        for profile in self._profiles:
            if profile.id == profile_id:
                return replace(profile, mechanisms=list(profile.mechanisms), constraints=list(profile.constraints), intended_effects=list(profile.intended_effects), compatible_dimensions=list(profile.compatible_dimensions))
        return None
