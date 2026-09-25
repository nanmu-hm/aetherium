"""Storage interface for memory; deliberately independent from any vendor."""

from __future__ import annotations

from typing import Protocol

from .models import Memory, MemoryState


class MemoryStore(Protocol):
    def add(self, memory: Memory) -> None: ...
    def get(self, memory_id: str) -> Memory | None: ...
    def for_character(self, owner_id: str) -> list[Memory]: ...


class InMemoryStore:
    def __init__(self, state: MemoryState | None = None) -> None:
        self.state = state or MemoryState()

    def add(self, memory: Memory) -> None:
        self.state.add_memory(memory)

    def get(self, memory_id: str) -> Memory | None:
        return self.state.memories.get(memory_id)

    def for_character(self, owner_id: str) -> list[Memory]:
        return [m for m in self.state.memories.values() if m.owner_id == owner_id]
