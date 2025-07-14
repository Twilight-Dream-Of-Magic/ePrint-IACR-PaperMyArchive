from __future__ import annotations

from typing import Any, Dict

from .baseline_runner import attach_baselines
from .block_runner import run_block_pipeline
from .config import RunConfig
from .exhaustive_runner import attach_exhaustive_analysis
from .lesion_runner import attach_lesions
from .report_assembler import assemble_report_payload, finalize_report_payload


def run_block_workflow(run_config: RunConfig) -> Dict[str, Any]:
    """
    Execute the full block-cipher workflow on top of pipeline stages.
    """
    artifacts = run_block_pipeline(run_config)
    artifacts = attach_exhaustive_analysis(artifacts)
    artifacts = attach_baselines(artifacts)
    artifacts = attach_lesions(artifacts)
    report = assemble_report_payload(artifacts)
    return finalize_report_payload(report=report, run_config=run_config)


__all__ = ["run_block_workflow"]
