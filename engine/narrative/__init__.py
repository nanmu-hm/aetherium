"""Narrative observation and story-emergence components."""

from .archaeologist import StoryArchaeologist, StoryCandidate
from .arcs import CharacterArcDetector
from .convergence import ThreadConvergenceDetector
from .dilemma import DilemmaDetector
from .foreshadowing import ForeshadowingTracker
from .importance import NarrativeImportanceAnalyzer
from .information import KnowledgeAsymmetryAnalyzer, RevelationDetector
from .pressure import NarrativePressureAnalyzer
from .rhythm import NarrativeRhythmAnalyzer
from .threads import CausalThreadEngine
from .structure import NarrativeStructureBuilder
from .allocation import NarrativeResourceAllocator
from .callbacks import CallbackScheduler
from .completion import StoryCompletionDetector
from .interleave import MultiArcInterleaver

__all__ = [
    "CausalThreadEngine",
    "CharacterArcDetector",
    "DilemmaDetector",
    "ForeshadowingTracker",
    "KnowledgeAsymmetryAnalyzer",
    "NarrativeImportanceAnalyzer",
    "NarrativePressureAnalyzer",
    "NarrativeRhythmAnalyzer",
    "RevelationDetector",
    "StoryArchaeologist",
    "StoryCandidate",
    "NarrativeStructureBuilder",
    "NarrativeResourceAllocator",
    "CallbackScheduler",
    "StoryCompletionDetector",
    "MultiArcInterleaver",
    "ThreadConvergenceDetector",
]
