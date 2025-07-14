from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class ThreatModelLevel(str, Enum):
    """
    Visibility levels (paper: Threat Model 1 / 2 / 3).

    - Threat Model 1: black-box observation only. No mechanism-side annotations are allowed to be used for decisions.
    - Threat Model 2: instrumented / white-box diagnostics allowed (mechanism-side events and enhanced state).
    - Threat Model 3: intervention / chosen-input extensions (closed-loop TM1 -> TM2 flow).
    """

    threat_model_1_black_box = "threat_model_1_black_box"
    threat_model_2_instrumented = "threat_model_2_instrumented"
    threat_model_3_intervention = "threat_model_3_intervention"


THREAT_MODEL_SEMANTICS: Dict[str, Dict[str, str]] = {
    ThreatModelLevel.threat_model_1_black_box.value: {
        "name": "TM-1 Black-box Observation",
        "zh_cn": "仅允许观测层输出轨迹与投影统计，禁止机制侧字段参与判定。",
        "en": "Observation-only mode; mechanism-side annotations are excluded from decisions.",
    },
    ThreatModelLevel.threat_model_2_instrumented.value: {
        "name": "TM-2 Instrumented Diagnostics",
        "zh_cn": "允许插桩事件与增强状态用于机制解释，但不回灌 TM-1 判定。",
        "en": "Instrumented events/state are allowed for mechanism diagnosis without feeding TM-1 decisions.",
    },
    ThreatModelLevel.threat_model_3_intervention.value: {
        "name": "TM-3 Hybrid Closed-loop",
        "zh_cn": "先 TM-1 筛查，再生成干预计划，再执行 TM-2 聚焦探针形成闭环证据。",
        "en": "TM-1 screening -> intervention planning -> TM-2 focused probes for closed-loop evidence.",
    },
}


def parse_threat_model_level(value: str | None) -> ThreatModelLevel:
    if value is None:
        return ThreatModelLevel.threat_model_2_instrumented
    normalized = str(value).strip().lower()
    aliases = {
        "tm1": ThreatModelLevel.threat_model_1_black_box,
        "tm1_black_box": ThreatModelLevel.threat_model_1_black_box,
        "threat_model_1_black_box": ThreatModelLevel.threat_model_1_black_box,
        "black_box": ThreatModelLevel.threat_model_1_black_box,
        "tm2": ThreatModelLevel.threat_model_2_instrumented,
        "tm2_instrumented": ThreatModelLevel.threat_model_2_instrumented,
        "threat_model_2_instrumented": ThreatModelLevel.threat_model_2_instrumented,
        "instrumented": ThreatModelLevel.threat_model_2_instrumented,
        "white_box": ThreatModelLevel.threat_model_2_instrumented,
        "tm3": ThreatModelLevel.threat_model_3_intervention,
        "tm3_intervention": ThreatModelLevel.threat_model_3_intervention,
        "threat_model_3_intervention": ThreatModelLevel.threat_model_3_intervention,
        "intervention": ThreatModelLevel.threat_model_3_intervention,
    }
    if normalized in aliases:
        return aliases[normalized]
    raise ValueError(f"unknown threat model level: {value!r}")


@dataclass(frozen=True, slots=True)
class VisibilityPolicy:
    """
    Defines which report sections may be emitted at a given threat model level.
    """

    allow_mechanism_side: bool
    allow_instrumented_example_trace: bool
    allow_lesions: bool
    allow_high_dimensional_internals: bool


def visibility_policy_for_level(level: ThreatModelLevel) -> VisibilityPolicy:
    if level == ThreatModelLevel.threat_model_1_black_box:
        return VisibilityPolicy(
            allow_mechanism_side=False,
            allow_instrumented_example_trace=False,
            allow_lesions=False,
            allow_high_dimensional_internals=False,
        )
    if level == ThreatModelLevel.threat_model_2_instrumented:
        return VisibilityPolicy(
            allow_mechanism_side=True,
            allow_instrumented_example_trace=True,
            allow_lesions=True,
            allow_high_dimensional_internals=True,
        )
    return VisibilityPolicy(
        allow_mechanism_side=True,
        allow_instrumented_example_trace=True,
        allow_lesions=True,
        allow_high_dimensional_internals=True,
    )


def apply_visibility_filter_to_report(report: Dict[str, Any], *, level: ThreatModelLevel) -> Dict[str, Any]:
    """
    Remove report sections that are not allowed under the given visibility level.

    This is a defense-in-depth measure: computation is also gated upstream.
    """
    policy = visibility_policy_for_level(level)
    filtered: Dict[str, Any] = dict(report)

    filtered["visibility"] = {
        "threat_model_level": str(level.value),
        "policy": {
            "allow_mechanism_side": bool(policy.allow_mechanism_side),
            "allow_instrumented_example_trace": bool(policy.allow_instrumented_example_trace),
            "allow_lesions": bool(policy.allow_lesions),
            "allow_high_dimensional_internals": bool(policy.allow_high_dimensional_internals),
        },
    }

    if not policy.allow_mechanism_side:
        filtered.pop("mechanism_side_metrics", None)
        filtered.pop("mechanism_side", None)
        filtered.pop("pattern_side_metrics", None)
        filtered.pop("pattern_side", None)
        filtered.pop("cross_domain_audit", None)

    if not policy.allow_instrumented_example_trace and "example_trace" in filtered:
        example = filtered.get("example_trace", {})
        if isinstance(example, dict):
            filtered["example_trace"] = {
                "initial_state_value": example.get("initial_state_value"),
                "projection": example.get("projection"),
                "note": "Threat Model 1: instrumented state/event details are suppressed; observation-only outputs are provided elsewhere.",
                "observations_head": example.get("observations_head"),
            }

    if not policy.allow_lesions:
        filtered.pop("lesions", None)
        filtered.pop("thresholds", None)
        filtered.pop("calibration", None)

    if not policy.allow_high_dimensional_internals:
        filtered.pop("high_dimensional_metrics", None)

    return filtered


def threat_model_semantics_payload() -> Dict[str, Any]:
    return {
        "threat_models": {
            str(k): dict(v)
            for k, v in THREAT_MODEL_SEMANTICS.items()
        }
    }

