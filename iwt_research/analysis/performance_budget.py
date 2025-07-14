from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


VECTOR_PRESETS = {
    "toy_spn_vector",
    "toy_substitution_permutation_network_vector",
}


@dataclass(frozen=True, slots=True)
class PerformanceBudgetReport:
    branch: str
    within_budget: bool
    trace_count_effective: int
    empirical_trace_threshold: int
    exhaustive_state_count_estimate: int
    exhaustive_threshold: int
    overrun_amount: int
    budget_assertion: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "branch": str(self.branch),
            "within_budget": bool(self.within_budget),
            "trace_count_effective": int(self.trace_count_effective),
            "empirical_trace_threshold": int(self.empirical_trace_threshold),
            "exhaustive_state_count_estimate": int(self.exhaustive_state_count_estimate),
            "exhaustive_threshold": int(self.exhaustive_threshold),
            "overrun_amount": int(self.overrun_amount),
            "budget_assertion": str(self.budget_assertion),
        }


def compute_block_performance_budget_report(
    *,
    run_config: Any,
    sampling_mode: str,
    trace_count_effective: int,
) -> PerformanceBudgetReport:
    preset = str(getattr(run_config, "cipher_preset", "toy_arx")).strip().lower()
    word_bits = int(getattr(run_config, "word_bits", 8))
    lane_count = int(getattr(run_config, "lane_count", 4))
    q = 1 << word_bits

    if preset in VECTOR_PRESETS:
        exhaustive_state_count_estimate = int(q) ** int(lane_count)
        exhaustive_threshold = int(getattr(run_config, "max_exhaustive_state_count", 65536))
    else:
        exhaustive_state_count_estimate = int(q)
        exhaustive_threshold = int(getattr(run_config, "max_exhaustive_modulus", 4096))

    empirical_trace_threshold = int(getattr(run_config, "max_empirical_trace_count", 4096))

    mode = str(sampling_mode).strip().lower()
    if mode == "exhaustive":
        within_budget = exhaustive_state_count_estimate <= exhaustive_threshold
        overrun_amount = max(0, exhaustive_state_count_estimate - exhaustive_threshold)
        return PerformanceBudgetReport(
            branch="strict_exhaustive",
            within_budget=bool(within_budget),
            trace_count_effective=int(trace_count_effective),
            empirical_trace_threshold=int(empirical_trace_threshold),
            exhaustive_state_count_estimate=int(exhaustive_state_count_estimate),
            exhaustive_threshold=int(exhaustive_threshold),
            overrun_amount=int(overrun_amount),
            budget_assertion="exhaustive_state_count_estimate <= exhaustive_threshold",
        )

    within_budget = int(trace_count_effective) <= empirical_trace_threshold
    overrun_amount = max(0, int(trace_count_effective) - empirical_trace_threshold)
    return PerformanceBudgetReport(
        branch="empirical_sampling",
        within_budget=bool(within_budget),
        trace_count_effective=int(trace_count_effective),
        empirical_trace_threshold=int(empirical_trace_threshold),
        exhaustive_state_count_estimate=int(exhaustive_state_count_estimate),
        exhaustive_threshold=int(exhaustive_threshold),
        overrun_amount=int(overrun_amount),
        budget_assertion="trace_count_effective <= empirical_trace_threshold",
    )

