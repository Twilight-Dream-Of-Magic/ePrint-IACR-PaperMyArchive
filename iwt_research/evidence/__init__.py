"""Paper 6.E evidence interface: objects, extractor family, map utilities."""

from .objects import EvidenceObject, RawTraceObject, WitnessObject
from .schema_version import EVIDENCE_SCHEMA_VERSION
from .types import EvidenceValueHistogram, EvidenceValueScalar, WitnessConfig

__all__ = [
    "EVIDENCE_SCHEMA_VERSION",
    "EvidenceObject",
    "EvidenceValueHistogram",
    "EvidenceValueScalar",
    "RawTraceObject",
    "WitnessConfig",
    "WitnessObject",
]
