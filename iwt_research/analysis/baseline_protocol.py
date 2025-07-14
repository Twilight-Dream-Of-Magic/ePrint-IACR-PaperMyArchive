from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol


@dataclass(frozen=True, slots=True)
class BaselineSample:
    seed: int
    trace_count: int
    diagnostics: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BaselineSummary:
    name: str
    sample_count: int
    diagnostics: Dict[str, Any] = field(default_factory=dict)


class BaselineRunner(Protocol):
    name: str

    def run_once(self, seed: int, trace_count: int) -> BaselineSample:
        ...

    def summarize(self, samples: List[BaselineSample]) -> BaselineSummary:
        ...

