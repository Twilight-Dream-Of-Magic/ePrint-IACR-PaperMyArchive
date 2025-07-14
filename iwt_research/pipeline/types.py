from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..analysis.threat_model import ThreatModelLevel
from .config import RunConfig


@dataclass(slots=True)
class TraceBatchArtifacts:
    metrics: Dict[str, Any] = field(default_factory=dict)
    example: Dict[str, Any] = field(default_factory=dict)
    state_indices: List[int] = field(default_factory=list)


@dataclass(slots=True)
class ExhaustiveArtifacts:
    high_dimensional: Dict[str, Any] = field(default_factory=dict)
    proof_evidence_objects: List[Dict[str, Any]] = field(default_factory=list)
    proof_witnesses: List[Dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class BaselineArtifacts:
    baseline_comparison: Dict[str, Any] = field(default_factory=dict)
    calibration: Dict[str, Any] = field(default_factory=dict)
    thresholds: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LesionArtifacts:
    lesions: List[Dict[str, Any]] = field(default_factory=list)
    tm2_focused_probes: Dict[str, Any] = field(default_factory=dict)
    tm2_witnesses: List[Dict[str, Any]] = field(default_factory=list)
    tm2_evidence_objects: List[Dict[str, Any]] = field(default_factory=list)
    binary_degenerate: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RunArtifacts:
    run_config: RunConfig
    threat_model_level: ThreatModelLevel
    result: Dict[str, Any]
    trace_batch: TraceBatchArtifacts = field(default_factory=TraceBatchArtifacts)
    exhaustive: ExhaustiveArtifacts = field(default_factory=ExhaustiveArtifacts)
    baseline: BaselineArtifacts = field(default_factory=BaselineArtifacts)
    lesion: LesionArtifacts = field(default_factory=LesionArtifacts)
    working: Dict[str, Any] = field(default_factory=dict)
