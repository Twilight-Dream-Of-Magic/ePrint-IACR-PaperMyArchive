from __future__ import annotations

from typing import Any, Dict

from ..analysis.threat_model import ThreatModelLevel
from ..analysis.tm1_scan import run_tm1_multi_projection_scan
from ..evidence.extractor_family import default_threat_model_1_extractor_family
from ..evidence.objects import RawTraceObject
from .config import RunConfig


def attach_tm1_observation_evidence(
    *,
    result: Dict[str, Any],
    primary_projection_spec: str,
) -> None:
    example = result.get("example_trace", None)
    if not isinstance(example, dict) or not example:
        return
    raw_trace_object = RawTraceObject(
        observations=list(int(y) for y in example.get("observations_head", []) or []),
        projection_spec=str(primary_projection_spec),
    )
    extractor_family = default_threat_model_1_extractor_family()
    tm1_objs = [extractor.extract(raw_trace_object).as_dict() for extractor in extractor_family]
    result["threat_model_1_evidence_objects"] = tm1_objs
    if isinstance(result.get("evidence_objects"), list):
        result["evidence_objects"].extend(tm1_objs)


def attach_tm1_multi_projection_scan(
    *,
    run_config: RunConfig,
    result: Dict[str, Any],
    threat_model_level: ThreatModelLevel,
    cipher: Any,
    registered_projections: list[tuple[str, Any]],
    state_indices: list[int],
    total_steps: int,
) -> None:
    if threat_model_level != ThreatModelLevel.threat_model_1_black_box:
        return
    scan, scan_evidence_objects, scan_witnesses = run_tm1_multi_projection_scan(
        run_config=run_config,
        cipher=cipher,
        registered_projections=list(registered_projections),
        seeds=list(state_indices),
        total_steps=int(total_steps),
        threat_model_level=str(threat_model_level.value),
    )
    result["threat_model_1_multi_projection_scan"] = scan
    if "threat_model_1_evidence_objects" not in result or not isinstance(
        result.get("threat_model_1_evidence_objects"),
        list,
    ):
        result["threat_model_1_evidence_objects"] = []
    result["threat_model_1_evidence_objects"].extend(scan_evidence_objects)
    result["threat_model_1_witnesses"] = scan_witnesses
    if isinstance(result.get("evidence_objects"), list):
        result["evidence_objects"].extend(scan_evidence_objects)
    if isinstance(result.get("witnesses"), list):
        result["witnesses"].extend(scan_witnesses)


__all__ = ["attach_tm1_observation_evidence", "attach_tm1_multi_projection_scan"]
