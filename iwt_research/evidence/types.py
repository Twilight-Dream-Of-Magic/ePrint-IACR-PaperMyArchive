from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True, slots=True)
class EvidenceValueScalar:
    value: float

    def as_dict(self) -> Dict[str, Any]:
        return {"kind": "scalar", "value": float(self.value)}


@dataclass(frozen=True, slots=True)
class EvidenceValueHistogram:
    bins: List[float]
    counts: List[float]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "kind": "histogram",
            "bins": [float(x) for x in self.bins],
            "counts": [float(x) for x in self.counts],
        }


@dataclass(frozen=True, slots=True)
class WitnessConfig:
    mode: str
    source: str

    def as_dict(self) -> Dict[str, Any]:
        return {"mode": str(self.mode), "source": str(self.source)}


__all__ = [
    "EvidenceValueHistogram",
    "EvidenceValueScalar",
    "WitnessConfig",
]
