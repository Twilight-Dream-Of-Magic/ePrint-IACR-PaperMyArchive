from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True, slots=True)
class NonDegeneracyReport:
    """
    Minimal implementable version of paper 5.0.E1-style checks.

    These checks do not "prove" non-degeneracy; they provide auditable warnings that
    certain structural objects may lose information under current settings.
    """

    projection_is_near_injective: bool
    projection_is_near_constant: bool
    coverage_is_saturating: bool
    coverage_is_near_zero: bool
    notes: List[str]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "projection_is_near_injective": bool(self.projection_is_near_injective),
            "projection_is_near_constant": bool(self.projection_is_near_constant),
            "coverage_is_saturating": bool(self.coverage_is_saturating),
            "coverage_is_near_zero": bool(self.coverage_is_near_zero),
            "notes": list(self.notes),
        }


def compute_non_degeneracy_report(
    *,
    projection_unique_node_counts: List[int],
    projection_step_counts: List[int],
    coverage_rates: List[float],
    near_injective_threshold: float = 0.98,
    near_constant_threshold: float = 0.02,
    coverage_saturating_threshold: float = 0.98,
    coverage_near_zero_threshold: float = 0.02,
) -> NonDegeneracyReport:
    """
    Heuristic but auditable checks:
    - projection degeneracy: unique_nodes / (steps+1) near 1 (injective-ish) or near 0 (constant-ish)
    - coverage degeneracy: mean coverage near 1 (saturating) or near 0 (too small to be informative)
    """
    notes: List[str] = []

    ratios: List[float] = []
    for unique_nodes, steps in zip(projection_unique_node_counts, projection_step_counts):
        denom = max(1, int(steps) + 1)
        ratios.append(float(int(unique_nodes)) / float(denom))

    ratio_mean = sum(ratios) / float(len(ratios)) if ratios else 0.0
    projection_is_near_injective = bool(ratio_mean >= float(near_injective_threshold))
    projection_is_near_constant = bool(ratio_mean <= float(near_constant_threshold))
    if projection_is_near_injective:
        notes.append("projection near-injective: shadowing / intersections may be weak (low collapse).")
    if projection_is_near_constant:
        notes.append("projection near-constant: observations collapse too much; many metrics may saturate.")

    coverage_mean = sum(float(x) for x in coverage_rates) / float(len(coverage_rates)) if coverage_rates else 0.0
    coverage_is_saturating = bool(coverage_mean >= float(coverage_saturating_threshold))
    coverage_is_near_zero = bool(coverage_mean <= float(coverage_near_zero_threshold))
    if coverage_is_saturating:
        notes.append("coverage saturating: coverage-based anomalies may degenerate.")
    if coverage_is_near_zero:
        notes.append("coverage near zero: estimates may be too sparse to interpret globally.")

    return NonDegeneracyReport(
        projection_is_near_injective=projection_is_near_injective,
        projection_is_near_constant=projection_is_near_constant,
        coverage_is_saturating=coverage_is_saturating,
        coverage_is_near_zero=coverage_is_near_zero,
        notes=notes,
    )

