"""Human-condition primitives for Aetherium.

These are world affordances, not plot commands. They describe pressures and
attachments that can arise in a human life without prescribing outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HumanCondition:
    """Persistent human-life dimensions that shape choices without forcing them."""

    attachments: dict[str, float] = field(default_factory=dict)
    losses: dict[str, float] = field(default_factory=dict)
    desires: dict[str, float] = field(default_factory=dict)
    fears: dict[str, float] = field(default_factory=dict)
    virtues: dict[str, float] = field(default_factory=dict)
    vices: dict[str, float] = field(default_factory=dict)
    # Actor-local associations between places and human pressures. These are
    # world/person state, not plot commands: a place can amplify or quiet a
    # pressure differently for different characters.
    location_pressures: dict[str, dict[str, float]] = field(default_factory=dict)
    life_stage: str = "adult"
    mortality_pressure: float = 0.0

    def pressure(self) -> float:
        """Return a bounded measure of unresolved human pressure."""
        values = list(self.desires.values()) + list(self.losses.values()) + list(self.fears.values())
        if not values:
            return 0.0
        return max(0.0, min(1.0, sum(values) / len(values) / 100.0))

    def attachment_strength(self) -> float:
        if not self.attachments:
            return 0.0
        return max(0.0, min(1.0, max(self.attachments.values()) / 100.0))

    def virtue_strength(self) -> float:
        if not self.virtues:
            return 0.0
        return max(0.0, min(1.0, max(self.virtues.values()) / 100.0))


# Canonical vocabulary. These names are descriptive rather than executable
# triggers; simulation may use any subset and may invent new values.
ROOT_CONDITIONS = (
    "birth",
    "aging",
    "illness",
    "death",
    "separation",
    "encounter_with_the_unwanted",
    "unfulfilled_desire",
    "inner_suffering",
)

EMOTIONS = (
    "joy",
    "sorrow",
    "anger",
    "fear",
    "love",
    "resentment",
    "longing",
    "hope",
    "regret",
)

VIRTUES = (
    "love",
    "loyalty",
    "courage",
    "compassion",
    "responsibility",
    "honor",
    "justice",
    "forgiveness",
    "friendship",
    "filial_duty",
    "self_sacrifice",
    "hope",
)
