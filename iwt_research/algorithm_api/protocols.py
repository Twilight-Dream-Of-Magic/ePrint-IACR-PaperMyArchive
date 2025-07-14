from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol


@dataclass(frozen=True, slots=True)
class AnalyzeRequest:
    impl: str
    crypto_type: str
    input_bits: int
    output_bits: int
    threat_model: str
    out_dir: str
    seed: int


class AnalyzeAdapter(Protocol):
    name: str
    execution_backend: str

    def analyze(self, request: AnalyzeRequest) -> Dict[str, Any]:
        ...

