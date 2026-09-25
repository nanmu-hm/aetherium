from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ModelRequest:
    model: str
    system_prompt: str
    user_prompt: str
    metadata: dict[str, Any] = field(default_factory=dict)
    temperature: float = 0.0


@dataclass(frozen=True)
class ModelResponse:
    text: str
    model: str
    status: str = "ok"
    finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    raw: Any = None


class ModelAdapter(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse:
        """Vendor-neutral model invocation contract."""


@dataclass
class NullModelAdapter:
    """Deterministic placeholder until a real local/cloud adapter is connected."""

    model_name: str = "unconfigured"

    def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            text="",
            model=request.model or self.model_name,
            status="blocked",
            finish_reason="no_model_adapter",
        )
