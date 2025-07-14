from __future__ import annotations

from typing import Iterable, Tuple


def lanes_to_index(lanes: Iterable[int], *, modulus_q: int) -> int:
    q = int(modulus_q)
    if q <= 0:
        raise ValueError("modulus_q must be positive")
    index = 0
    factor = 1
    for lane in lanes:
        index += (int(lane) % q) * factor
        factor *= q
    return int(index)


def index_to_lanes(state_index: int, *, modulus_q: int, lane_count: int) -> Tuple[int, ...]:
    q = int(modulus_q)
    n = int(lane_count)
    if q <= 0:
        raise ValueError("modulus_q must be positive")
    if n <= 0:
        raise ValueError("lane_count must be positive")
    value = int(state_index)
    lanes = []
    for _ in range(n):
        lanes.append(int(value % q))
        value //= q
    return tuple(lanes)


def seed_to_lanes(seed: int, *, modulus_q: int, lane_count: int) -> Tuple[int, ...]:
    return index_to_lanes(state_index=int(seed), modulus_q=modulus_q, lane_count=lane_count)

