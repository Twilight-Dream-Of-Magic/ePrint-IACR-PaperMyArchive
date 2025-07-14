from __future__ import annotations

from typing import Any, Dict

from .analysis.threat_model import ThreatModelLevel, parse_threat_model_level
from .analysis.tm3_workflow import run_tm3_workflow as run_tm3_workflow_external
from .pipeline import (
    RunConfig,
    finalize_report_payload,
    run_block_workflow,
)
from .report import write_report


def run_tm3_workflow(run_config: RunConfig) -> Dict[str, Any]:
    return run_tm3_workflow_external(run_config=run_config, run_tm1=run_toy_iwt)


def run_toy_iwt(run_config: RunConfig) -> Dict[str, Any]:
    threat_model_level = parse_threat_model_level(run_config.threat_model_level)
    if threat_model_level == ThreatModelLevel.threat_model_3_intervention:
        return finalize_report_payload(report=run_tm3_workflow(run_config), run_config=run_config)
    return run_block_workflow(run_config)


__all__ = ["RunConfig", "run_toy_iwt", "run_tm3_workflow", "write_report"]
