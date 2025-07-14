from __future__ import annotations

import random
from typing import Any, List, Tuple

from .baseline_protocol import BaselineRunner, BaselineSample, BaselineSummary

from .baseline_models import (
    RandomARXLikeBaseline,
    RandomFunctionBaseline,
    RandomPermutationBaseline,
    RandomSubstitutionPermutationNetworkBaseline,
    RandomSubstitutionPermutationNetworkVectorBaseline,
)

TEMPLATE_BASELINE_NAMES = (
    "random_arx_like",
    "random_substitution_permutation_network",
    "random_substitution_permutation_network_vector",
)

_BASELINE_SEED_XOR = {
    "random_arx_like": 0xBADC0DD,
    "random_substitution_permutation_network": 0xBADC0E0,
    "random_substitution_permutation_network_vector": 0xBADC0E1,
    "random_permutation": 0xBADC0DE,
    "random_function": 0xBADC0DF,
}


def _config_get(config: Any, key: str, default: Any = None) -> Any:
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)


def _normalize_preset(cipher_preset: str) -> str:
    return str(cipher_preset).strip().lower()


def _normalize_baseline_name(baseline_name: str) -> str:
    return str(baseline_name).strip().lower()


def _baseline_seed(*, baseline_name: str, run_config: Any, ensemble_index: int = 0) -> int:
    seed = int(_config_get(run_config, "seed", 0) or 0)
    xor = int(_BASELINE_SEED_XOR[baseline_name])
    return int((seed ^ xor) + int(ensemble_index))


def default_baselines_for_preset(cipher_preset: str) -> Tuple[str, ...]:
    preset = _normalize_preset(cipher_preset)
    if preset in ("toy_spn_vector", "toy_substitution_permutation_network_vector"):
        template = "random_substitution_permutation_network_vector"
    elif preset in ("toy_spn", "toy_substitution_permutation_network"):
        template = "random_substitution_permutation_network"
    else:
        template = "random_arx_like"
    return (
        template,
        "random_permutation",
        "random_function",
    )


def select_calibration_baseline(baselines: Tuple[str, ...]) -> str | None:
    for name in baselines:
        normalized = _normalize_baseline_name(name)
        if normalized in TEMPLATE_BASELINE_NAMES:
            return normalized
    return None


def build_baseline_runner(
    *,
    baseline_name: str,
    domain: Any,
    run_config: Any,
    steps: int,
    ensemble_index: int = 0,
) -> Any:
    normalized = _normalize_baseline_name(baseline_name)
    if normalized == "random_arx_like":
        return RandomARXLikeBaseline(
            domain=domain,
            rounds=int(_config_get(run_config, "rounds", 16) or 16),
            seed=_baseline_seed(
                baseline_name=normalized,
                run_config=run_config,
                ensemble_index=ensemble_index,
            ),
            word_bits=int(_config_get(run_config, "word_bits", 8) or 8),
            rot_mode=str(_config_get(run_config, "rotation_mode", "bits")),
            rot_dir=str(_config_get(run_config, "rotation_direction", "l")),
            cross_domain_q=_config_get(run_config, "cross_domain_modulus", None),
            cross_every_rounds=int(_config_get(run_config, "cross_every_rounds", 4) or 4),
        )
    if normalized == "random_substitution_permutation_network":
        return RandomSubstitutionPermutationNetworkBaseline(
            domain=domain,
            rounds=int(_config_get(run_config, "rounds", 16) or 16),
            seed=_baseline_seed(
                baseline_name=normalized,
                run_config=run_config,
                ensemble_index=ensemble_index,
            ),
        )
    if normalized == "random_substitution_permutation_network_vector":
        return RandomSubstitutionPermutationNetworkVectorBaseline(
            domain=domain,
            rounds=int(_config_get(run_config, "rounds", 16) or 16),
            lane_count=int(_config_get(run_config, "lane_count", 4) or 4),
            seed=_baseline_seed(
                baseline_name=normalized,
                run_config=run_config,
                ensemble_index=ensemble_index,
            ),
        )
    if normalized == "random_permutation":
        return RandomPermutationBaseline(
            domain=domain,
            steps=int(steps),
            seed=_baseline_seed(
                baseline_name=normalized,
                run_config=run_config,
                ensemble_index=ensemble_index,
            ),
        )
    if normalized == "random_function":
        return RandomFunctionBaseline(
            domain=domain,
            steps=int(steps),
            seed=_baseline_seed(
                baseline_name=normalized,
                run_config=run_config,
                ensemble_index=ensemble_index,
            ),
        )
    raise ValueError(f"unknown baseline: {baseline_name}")


class BaselineRunnerAdapter:
    """
    Adapter that exposes run_once/summarize over baseline model implementations.
    """

    def __init__(self, *, name: str, baseline: Any, lane_count: int = 1) -> None:
        self.name = str(name)
        self._baseline = baseline
        self._lane_count = max(1, int(lane_count))

    def _sample_state_index(self, rng: random.Random) -> int:
        q = int(getattr(getattr(self._baseline, "domain", None), "q", 1))
        state_count = int(q ** self._lane_count)
        if state_count <= 1:
            return 0
        return int(rng.randrange(state_count))

    def run_once(self, seed: int, trace_count: int) -> BaselineSample:
        rng = random.Random(int(seed))
        event_counts: List[int] = []
        for _ in range(max(1, int(trace_count))):
            x0 = self._sample_state_index(rng)
            if hasattr(self._baseline, "run_from_index"):
                _, events = self._baseline.run_from_index(x0)
            else:
                _, events = self._baseline.run(x0)
            event_counts.append(int(len(events)))
        mean_event_count = (
            float(sum(event_counts)) / float(len(event_counts))
            if event_counts
            else 0.0
        )
        return BaselineSample(
            seed=int(seed),
            trace_count=max(1, int(trace_count)),
            diagnostics={
                "mean_event_count": mean_event_count,
                "min_event_count": int(min(event_counts) if event_counts else 0),
                "max_event_count": int(max(event_counts) if event_counts else 0),
            },
        )

    def summarize(self, samples: List[BaselineSample]) -> BaselineSummary:
        if not samples:
            return BaselineSummary(name=self.name, sample_count=0, diagnostics={})
        mean_events = sum(
            float(sample.diagnostics.get("mean_event_count", 0.0))
            for sample in samples
        ) / float(len(samples))
        return BaselineSummary(
            name=self.name,
            sample_count=len(samples),
            diagnostics={"mean_event_count": float(mean_events)},
        )


def build_baseline(
    *,
    baseline_name: str,
    domain: Any,
    run_config: Any,
    steps: int,
    ensemble_index: int = 0,
) -> BaselineRunner:
    baseline = build_baseline_runner(
        baseline_name=baseline_name,
        domain=domain,
        run_config=run_config,
        steps=steps,
        ensemble_index=ensemble_index,
    )
    lane_count = int(_config_get(run_config, "lane_count", 1) or 1)
    return BaselineRunnerAdapter(
        name=str(baseline_name),
        baseline=baseline,
        lane_count=lane_count,
    )


__all__ = [
    "TEMPLATE_BASELINE_NAMES",
    "default_baselines_for_preset",
    "select_calibration_baseline",
    "build_baseline_runner",
    "build_baseline",
    "BaselineRunnerAdapter",
]
