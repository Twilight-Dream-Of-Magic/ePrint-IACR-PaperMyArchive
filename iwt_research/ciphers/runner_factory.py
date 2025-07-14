from __future__ import annotations

from typing import Any

from .protocols import CipherRunner
from .toy_arx_cipher import ToyARX, ToyARXConfig
from .toy_spn import (
    ToySubstitutionPermutationNetwork,
    ToySubstitutionPermutationNetworkConfig,
)


def _config_get(config: Any, key: str, default: Any = None) -> Any:
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)


def build_toy_cipher_from_config(config: Any) -> CipherRunner:
    """
    Factory for the toy ciphers used by the runner + verifiers.
    Accepts either a dataclass-like object (attribute access) or a dict.
    """
    cipher_preset = str(_config_get(config, "cipher_preset", "")).strip().lower()
    word_bits = int(_config_get(config, "word_bits", 8) or 8)
    rounds = int(_config_get(config, "rounds", 16) or 16)
    seed = int(_config_get(config, "seed", 0) or _config_get(config, "cipher_seed", 0) or 0)

    if cipher_preset == "toy_arx":
        return ToyARX(
            ToyARXConfig(
                word_bits=int(word_bits),
                rounds=int(rounds),
                rot_mode="bits",
                rot_dir=str(_config_get(config, "rotation_direction", "l")),
                seed=int(seed),
                cross_domain_q=_config_get(config, "cross_domain_modulus", None),
                cross_every_rounds=int(_config_get(config, "cross_every_rounds", 4) or 4),
            )
        )

    if cipher_preset in ("toy_spn", "toy_substitution_permutation_network"):
        return ToySubstitutionPermutationNetwork(
            ToySubstitutionPermutationNetworkConfig(
                word_bits=int(word_bits),
                rounds=int(rounds),
                seed=int(seed),
            )
        )

    if cipher_preset in ("toy_spn_vector", "toy_substitution_permutation_network_vector"):
        from .toy_spn_vector import (
            ToySubstitutionPermutationNetworkVector,
            ToySubstitutionPermutationNetworkVectorConfig,
        )

        lane_count = int(_config_get(config, "lane_count", 4) or 4)
        return ToySubstitutionPermutationNetworkVector(
            ToySubstitutionPermutationNetworkVectorConfig(
                word_bits=int(word_bits),
                lane_count=int(lane_count),
                rounds=int(rounds),
                seed=int(seed),
            )
        )

    raise ValueError(f"unknown preset: {cipher_preset!r}")

