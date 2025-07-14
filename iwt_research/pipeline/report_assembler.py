from __future__ import annotations

from typing import Any, Dict

from ..alignment.todo_alignment import build_todo_alignment_section
from ..analysis.threat_model import apply_visibility_filter_to_report, parse_threat_model_level
from ..report import attach_report_contract_metadata
from .config import RunConfig
from .types import RunArtifacts


def assemble_report_payload(artifacts: RunArtifacts) -> Dict[str, Any]:
    """
    Assemble a mutable report payload from staged artifacts.

    Keeps the canonical report-shape assembly in one place for pipeline stages.
    """
    return dict(artifacts.result)


def finalize_report_payload(*, report: Dict[str, Any], run_config: RunConfig) -> Dict[str, Any]:
    """
    Apply visibility filter, TODO alignment mapping, and v2 report contracts.
    """
    level = parse_threat_model_level(run_config.threat_model_level)
    filtered = apply_visibility_filter_to_report(report, level=level)
    filtered["todo_alignment"] = build_todo_alignment_section(filtered)
    return attach_report_contract_metadata(filtered)


__all__ = ["assemble_report_payload", "finalize_report_payload"]
