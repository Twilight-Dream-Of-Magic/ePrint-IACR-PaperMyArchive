"""
Shared helpers for run_experiment: config parsing and state-space coverage.
"""
from __future__ import annotations

from typing import Any, List, Tuple

from .state_encoding.vector import index_to_lanes as index_to_lanes_encoding
from .utils.stats import deterministic_seed_pool


VECTOR_PRESETS = {
    "toy_spn_vector",
    "toy_substitution_permutation_network_vector",
}


def parse_int_csv(value: str | None) -> List[int]:
    """
    Parse a comma-separated string of integers (e.g. from CLI or config).
    """
    if value is None:
        return []
    parts = [p.strip() for p in str(value).split(",")]
    out: List[int] = []
    for p in parts:
        if not p:
            continue
        try:
            out.append(int(p, 0))
        except Exception:
            raise ValueError(f"invalid integer in csv: {p!r}") from None
    return out


def state_space_coverage_ratio(states: List[Any], omega_size: int) -> float:
    """
    Fraction of state space (size omega_size) visited by the given state sequence.
    States are compared by (domain.q, stable_value(x)) to support both scalar and vector x.
    """
    def stable_value(value: Any) -> Any:
        if isinstance(value, (tuple, list)):
            return tuple(value)
        return int(value)

    visited = set((int(st.domain.q), stable_value(st.x)) for st in states)
    return len(visited) / float(omega_size) if omega_size > 0 else float("nan")


def _config_get(config: Any, key: str, default: Any = None) -> Any:
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)


def is_vector_preset(preset: str) -> bool:
    return str(preset).strip().lower() in VECTOR_PRESETS


def supports_vector_index_interface(runner: Any) -> bool:
    return (
        callable(getattr(runner, "index_to_lanes", None))
        and callable(getattr(runner, "run_from_lanes", None))
    )


def runner_uses_vector_state_space(
    runner: Any,
    *,
    cipher_preset: str | None = None,
) -> bool:
    if supports_vector_index_interface(runner):
        return True
    if cipher_preset is None:
        return False
    return is_vector_preset(str(cipher_preset))


def state_index_space_size(
    *,
    runner: Any,
    lane_count: int,
    cipher_preset: str | None = None,
) -> int:
    modulus_q = int(runner.domain.q)
    if runner_uses_vector_state_space(runner, cipher_preset=cipher_preset):
        return int(modulus_q) ** int(lane_count)
    return int(modulus_q)


def build_trace_state_indices(
    *,
    runner: Any,
    run_config: Any,
    seed_xor: int = 0x5A17_9E3,
) -> List[int]:
    cipher_preset = str(_config_get(run_config, "cipher_preset", ""))
    lane_count = int(_config_get(run_config, "lane_count", 1) or 1)
    trace_count = int(_config_get(run_config, "trace_count", 0) or 0)
    exhaustive = bool(_config_get(run_config, "exhaustive", False))
    seed = int(_config_get(run_config, "seed", 0) or 0)
    modulus_q = int(runner.domain.q)
    max_exhaustive_modulus = int(_config_get(run_config, "max_exhaustive_modulus", 4096) or 4096)
    max_exhaustive_state_count = int(_config_get(run_config, "max_exhaustive_state_count", 65536) or 65536)
    max_empirical_trace_count = int(_config_get(run_config, "max_empirical_trace_count", 4096) or 4096)
    is_vector = runner_uses_vector_state_space(runner, cipher_preset=cipher_preset)
    space_size = state_index_space_size(
        runner=runner,
        lane_count=lane_count,
        cipher_preset=cipher_preset,
    )

    if exhaustive:
        if is_vector:
            if int(space_size) > int(max_exhaustive_state_count):
                raise ValueError(
                    f"exhaustive requested but q^n={space_size} exceeds max_exhaustive_state_count={max_exhaustive_state_count}"
                )
        else:
            if int(modulus_q) > int(max_exhaustive_modulus):
                raise ValueError(
                    f"exhaustive requested but q={modulus_q} exceeds max_exhaustive_modulus={max_exhaustive_modulus}"
                )
        return list(range(int(space_size)))

    if int(trace_count) > int(max_empirical_trace_count):
        raise ValueError(
            f"trace_count={trace_count} exceeds max_empirical_trace_count={max_empirical_trace_count}"
        )
    raw = deterministic_seed_pool(int(seed) ^ int(seed_xor), int(trace_count))
    return [int(s) % int(space_size) for s in raw]


def index_to_lanes_with_fallback(
    *,
    runner: Any,
    state_index: int,
    lane_count: int,
) -> Tuple[int, ...]:
    if callable(getattr(runner, "index_to_lanes", None)):
        lanes = runner.index_to_lanes(int(state_index))
        if isinstance(lanes, tuple):
            return tuple(int(v) for v in lanes)
        if isinstance(lanes, list):
            return tuple(int(v) for v in lanes)
        raise ValueError("index_to_lanes must return tuple/list")
    modulus_q = int(runner.domain.q)
    if int(lane_count) <= 0:
        raise ValueError("lane_count must be positive")
    max_states = int(modulus_q) ** int(lane_count)
    if int(state_index) < 0 or int(state_index) >= int(max_states):
        raise ValueError("state_index out of range")
    return index_to_lanes_encoding(
        int(state_index),
        modulus_q=int(modulus_q),
        lane_count=int(lane_count),
    )


def run_trace_from_state_index(
    *,
    runner: Any,
    state_index: int,
    run_config: Any | None = None,
    lane_count: int | None = None,
    cipher_preset: str | None = None,
) -> tuple[list[Any], list[Any]]:
    if lane_count is None:
        lane_count = int(_config_get(run_config, "lane_count", 1) or 1)
    if cipher_preset is None:
        cipher_preset = str(_config_get(run_config, "cipher_preset", ""))
    if runner_uses_vector_state_space(runner, cipher_preset=cipher_preset):
        if callable(getattr(runner, "run_from_index", None)):
            states, events = runner.run_from_index(int(state_index))
            return states, events
        if callable(getattr(runner, "run_from_lanes", None)):
            lanes = index_to_lanes_with_fallback(
                runner=runner,
                state_index=int(state_index),
                lane_count=int(lane_count),
            )
            states, events = runner.run_from_lanes(lanes)
            return states, events
    x0 = int(state_index) % int(runner.domain.q)
    states, events = runner.run(int(x0))
    return states, events
