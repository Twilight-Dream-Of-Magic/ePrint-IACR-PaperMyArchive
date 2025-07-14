from __future__ import annotations


def normalize_scalar_state(value: int, modulus_q: int) -> int:
    q = int(modulus_q)
    if q <= 0:
        raise ValueError("modulus_q must be positive")
    return int(value) % q


def scalar_state_to_index(value: int, modulus_q: int) -> int:
    return normalize_scalar_state(value=value, modulus_q=modulus_q)


def index_to_scalar_state(state_index: int, modulus_q: int) -> int:
    return normalize_scalar_state(value=state_index, modulus_q=modulus_q)

