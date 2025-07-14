from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


def compute_observation_self_loop_rate(*, observations: List[int]) -> float:
    """
    Observation-side self-loop rate:
      fraction of steps with y_{t+1} == y_t.
    """
    if len(observations) < 2:
        return 0.0
    steps = len(observations) - 1
    loops = sum(1 for i in range(steps) if int(observations[i + 1]) == int(observations[i]))
    return float(loops) / float(steps) if steps > 0 else 0.0


def compute_observation_self_intersection_rate(*, observations: List[int]) -> float:
    """
    Observation-side self-intersection / revisit rate on a single trace:
      fraction of t>0 with y_t seen before.
    """
    if len(observations) < 2:
        return 0.0
    seen: set[int] = set()
    hits = 0
    for time_index, value in enumerate(observations):
        y = int(value)
        if time_index == 0:
            seen.add(y)
            continue
        if y in seen:
            hits += 1
        seen.add(y)
    return float(hits) / float(max(1, (len(observations) - 1)))


@dataclass(frozen=True, slots=True)
class ObservationSideMetrics:
    observation_self_loop_rate: float
    observation_self_intersection_rate: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "observation_self_loop_rate": float(self.observation_self_loop_rate),
            "observation_self_intersection_rate": float(self.observation_self_intersection_rate),
        }


def compute_observation_side_metrics(*, observations: List[int]) -> ObservationSideMetrics:
    return ObservationSideMetrics(
        observation_self_loop_rate=compute_observation_self_loop_rate(observations=observations),
        observation_self_intersection_rate=compute_observation_self_intersection_rate(observations=observations),
    )


def compute_one_step_predictor_success_from_traces(*, traces: List[List[int]]) -> float:
    """
    One-step predictor attack class (paper running example):
    Given observation traces Y, estimate the best one-step predictor success rate:
      Succ_pred = sum_y P(Y_t=y) * max_{y'} P(Y_{t+1}=y' | Y_t=y)
    using empirical transition counts across all traces and time steps.
    """
    if not traces:
        return 0.0
    transition_counts: Dict[int, Dict[int, int]] = {}
    total_transitions = 0
    for obs in traces:
        if len(obs) < 2:
            continue
        for t in range(len(obs) - 1):
            y0 = int(obs[t])
            y1 = int(obs[t + 1])
            if y0 not in transition_counts:
                transition_counts[y0] = {}
            transition_counts[y0][y1] = int(transition_counts[y0].get(y1, 0)) + 1
            total_transitions += 1
    if total_transitions <= 0 or not transition_counts:
        return 0.0
    best_hits = 0
    for y0, next_counts in transition_counts.items():
        if not next_counts:
            continue
        best_hits += int(max(next_counts.values()))
    return float(best_hits) / float(total_transitions)

