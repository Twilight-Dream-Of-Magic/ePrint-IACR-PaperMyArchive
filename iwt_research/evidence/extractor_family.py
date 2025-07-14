from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol

from .objects import EvidenceObject, RawTraceObject


class TraceExtractor(Protocol):
    """
    Paper 6.E.1: extractor family element.
    """

    identifier: str

    def extract(self, raw_trace: RawTraceObject) -> EvidenceObject: ...


@dataclass(frozen=True, slots=True)
class ObservationSelfLoopExtractor:
    identifier: str = "observation_self_loop_rate"

    def extract(self, raw_trace: RawTraceObject) -> EvidenceObject:
        observations = list(int(y) for y in raw_trace.observations)
        if len(observations) < 2:
            rate = 0.0
        else:
            steps = len(observations) - 1
            loops = sum(1 for i in range(steps) if observations[i + 1] == observations[i])
            rate = float(loops) / float(steps) if steps > 0 else 0.0
        return EvidenceObject(
            identifier=self.identifier,
            summary="Observation-side self-loop rate: fraction of steps with y[t+1]==y[t].",
            value=float(rate),
            p_value=None,
            witness={"loops": int(round(float(rate) * max(1, len(observations) - 1))), "steps": int(max(0, len(observations) - 1))},
            metadata={"projection_spec": raw_trace.projection_spec},
        )


@dataclass(frozen=True, slots=True)
class ObservationSelfIntersectionExtractor:
    identifier: str = "observation_self_intersection_rate"

    def extract(self, raw_trace: RawTraceObject) -> EvidenceObject:
        observations = list(int(y) for y in raw_trace.observations)
        seen: set[int] = set()
        hits = 0
        for time_index, y in enumerate(observations):
            if time_index == 0:
                seen.add(y)
                continue
            if y in seen:
                hits += 1
            seen.add(y)
        denom = max(1, len(observations) - 1)
        rate = float(hits) / float(denom)
        return EvidenceObject(
            identifier=self.identifier,
            summary="Observation-side self-intersection rate: fraction of t>0 with y[t] seen before.",
            value=float(rate),
            p_value=None,
            witness={"revisit_count": int(hits), "time_step_count": int(max(0, len(observations) - 1))},
            metadata={"projection_spec": raw_trace.projection_spec},
        )


def default_threat_model_1_extractor_family() -> List[TraceExtractor]:
    return [
        ObservationSelfLoopExtractor(),
        ObservationSelfIntersectionExtractor(),
    ]

