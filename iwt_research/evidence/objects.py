from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .schema_version import EVIDENCE_SCHEMA_VERSION


def _infer_value_type(value: Any) -> str:
    if isinstance(value, (int, float)):
        return "scalar"
    if isinstance(value, dict):
        return "mapping"
    if isinstance(value, list):
        return "sequence"
    return "opaque"


@dataclass(frozen=True, slots=True)
class RawTraceObject:
    observations: List[int]
    projection_spec: str
    schema_version: str = EVIDENCE_SCHEMA_VERSION

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": str(self.schema_version),
            "projection_spec": str(self.projection_spec),
            "time_step_count": int(max(0, len(self.observations) - 1)),
            "observations": [int(y) for y in self.observations],
        }


@dataclass(frozen=True, slots=True)
class EvidenceObject:
    identifier: str
    summary: str
    value: Any
    p_value: Optional[float]
    witness: Dict[str, Any]
    metadata: Dict[str, Any]
    value_type: str | None = None
    witness_type: str = "generic_witness"
    schema_version: str = EVIDENCE_SCHEMA_VERSION

    def as_dict(self) -> Dict[str, Any]:
        value_type = str(self.value_type) if self.value_type else _infer_value_type(self.value)
        return {
            "schema_version": str(self.schema_version),
            "identifier": str(self.identifier),
            "summary": str(self.summary),
            "value_type": value_type,
            "witness_type": str(self.witness_type),
            "value": self.value,
            "p_value": self.p_value,
            "witness": dict(self.witness),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class WitnessObject:
    config: Dict[str, Any]
    E: Any
    Z: Any
    evidence_map: Dict[str, Any]
    witness_type: str = "structural_witness"
    schema_version: str = EVIDENCE_SCHEMA_VERSION

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": str(self.schema_version),
            "witness_type": str(self.witness_type),
            "config": dict(self.config),
            "E": self.E,
            "Z": self.Z,
            "evidence-map": dict(self.evidence_map),
        }
