from __future__ import annotations

from typing import Any, Dict, Iterable, List


TODO_MAINLINES: List[Dict[str, str]] = [
    {
        "id": "M1_theory_correctness_alignment",
        "title": "Paper-correct theory anchors are implemented as executable objects.",
    },
    {
        "id": "M2_misread_and_semantic_guardrails",
        "title": "Known semantic misreads are blocked by protocol-level guardrails.",
    },
    {
        "id": "M3_engineering_alignment_with_paper",
        "title": "Core implementation aligns with paper definitions and threat-model layering.",
    },
    {
        "id": "M4_engineering_extensions_and_risk_control",
        "title": "Engineering extensions, diagnostics, and added controls are explicit and auditable.",
    },
]


def _is_stream_or_hash(experiment_type: str) -> bool:
    et = str(experiment_type).strip().lower()
    return et in (
        "stream_cipher_prg",
        "secure_hash_sponge",
        "secure_hash_direct_compression",
    )


def _mapping_spec_for_experiment(experiment_type: str) -> Dict[str, List[str]]:
    common = {
        "config": ["M3_engineering_alignment_with_paper"],
        "evidence_objects": ["M3_engineering_alignment_with_paper"],
        "witnesses": ["M3_engineering_alignment_with_paper"],
        "todo_alignment": ["M4_engineering_extensions_and_risk_control"],
        "performance_budget": [
            "M2_misread_and_semantic_guardrails",
            "M4_engineering_extensions_and_risk_control",
        ],
    }

    if _is_stream_or_hash(experiment_type):
        spec = dict(common)
        spec.update(
            {
                "structural_diagnosis": ["M4_engineering_extensions_and_risk_control"],
                "theory_correspondence": ["M1_theory_correctness_alignment"],
                "winding_trajectory_profile": ["M4_engineering_extensions_and_risk_control"],
                "rho_structure": ["M1_theory_correctness_alignment"],
                "merge_depth": ["M1_theory_correctness_alignment"],
            }
        )
        return spec

    spec = dict(common)
    spec.update(
        {
            "visibility": ["M2_misread_and_semantic_guardrails"],
            "sampling": [
                "M1_theory_correctness_alignment",
                "M2_misread_and_semantic_guardrails",
            ],
            "threat_model_1_multi_projection_scan": [
                "M1_theory_correctness_alignment",
                "M3_engineering_alignment_with_paper",
            ],
            "threat_model_2_focused_probes": ["M3_engineering_alignment_with_paper"],
            "threat_model_3_workflow": ["M3_engineering_alignment_with_paper"],
            "high_dimensional_metrics": ["M1_theory_correctness_alignment"],
            "cross_domain_audit": ["M3_engineering_alignment_with_paper"],
            "winding_trajectory_profile": ["M4_engineering_extensions_and_risk_control"],
            "lesions": ["M4_engineering_extensions_and_risk_control"],
            "thresholds": ["M3_engineering_alignment_with_paper"],
            "baseline_comparison": ["M3_engineering_alignment_with_paper"],
        }
    )
    return spec


def build_todo_alignment_section(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a machine-readable field-to-mainline mapping for TODO charter tracking.
    """
    experiment_type = str(report.get("experiment_type", "block_cipher_run"))
    present_fields = sorted(str(k) for k in report.keys())
    spec = _mapping_spec_for_experiment(experiment_type)

    known_mainline_ids = {item["id"] for item in TODO_MAINLINES}
    field_to_mainline: List[Dict[str, str]] = []
    coverage_count = {mid: 0 for mid in known_mainline_ids}

    for field in present_fields:
        mainline_ids = spec.get(field, [])
        for mainline_id in mainline_ids:
            if mainline_id not in known_mainline_ids:
                continue
            field_to_mainline.append(
                {
                    "report_field": str(field),
                    "mainline_id": str(mainline_id),
                }
            )
            coverage_count[mainline_id] += 1

    mapped_fields = {entry["report_field"] for entry in field_to_mainline}
    unmapped_fields = [field for field in present_fields if field not in mapped_fields]
    missing_mainlines = [mid for mid, count in coverage_count.items() if int(count) == 0]

    return {
        "version": "todo-alignment-v1",
        "charter_file": "iwt_research/TODO.md",
        "paper_anchor_file": "Information Winding Theory/信息绕线理论与密码学基元关系研究 2.1 学术论文（简体中文+英语+GitHub公式版）.md",
        "experiment_type": experiment_type,
        "mainlines": list(TODO_MAINLINES),
        "present_top_level_fields": present_fields,
        "field_to_mainline": field_to_mainline,
        "coverage_count_by_mainline": coverage_count,
        "missing_mainlines": missing_mainlines,
        "unmapped_present_fields": unmapped_fields,
    }


def validate_todo_alignment_section(todo_alignment: Dict[str, Any], present_fields: Iterable[str]) -> List[str]:
    """
    Validate shape and referential integrity of todo_alignment section.
    Returns a list of validation failures.
    """
    failures: List[str] = []
    known_mainline_ids = {item["id"] for item in TODO_MAINLINES}
    present_set = {str(k) for k in present_fields}

    mainlines = todo_alignment.get("mainlines")
    if not isinstance(mainlines, list) or len(mainlines) < 4:
        failures.append("todo_alignment.mainlines missing or incomplete")
    else:
        ids = set()
        for item in mainlines:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                ids.add(str(item["id"]))
        if not known_mainline_ids.issubset(ids):
            failures.append("todo_alignment.mainlines does not contain all required mainline ids")

    mapping = todo_alignment.get("field_to_mainline")
    if not isinstance(mapping, list) or not mapping:
        failures.append("todo_alignment.field_to_mainline missing or empty")
    else:
        for i, entry in enumerate(mapping):
            if not isinstance(entry, dict):
                failures.append(f"todo_alignment.field_to_mainline[{i}] invalid entry")
                continue
            field = entry.get("report_field")
            mainline_id = entry.get("mainline_id")
            if not isinstance(field, str) or not field:
                failures.append(f"todo_alignment.field_to_mainline[{i}] missing report_field")
            elif field not in present_set and field != "todo_alignment":
                failures.append(
                    f"todo_alignment.field_to_mainline[{i}] references missing field '{field}'"
                )
            if not isinstance(mainline_id, str) or mainline_id not in known_mainline_ids:
                failures.append(
                    f"todo_alignment.field_to_mainline[{i}] invalid mainline_id '{mainline_id}'"
                )

    return failures

