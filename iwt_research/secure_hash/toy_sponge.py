"""
Toy sponge / hash construction for compression analysis.

Two constructions:

1. Toy Sponge (rate/capacity split over an existing block-cipher permutation):
   - Absorb: XOR message block into rate portion, apply full-state permutation
   - Squeeze: extract rate portion as digest
   - Compression arises because capacity is hidden -> many-to-one on external view

2. Direct compression function f: Omega -> Omega (non-injective):
   - f(x) = sbox(x) XOR (x >> k)
   - Non-injective because XOR with shifted self destroys information
   - Useful for exhaustive rho-structure analysis on small domains
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Tuple

from ..ciphers.runner_factory import build_toy_cipher_from_config


@dataclass(frozen=True, slots=True)
class ToySpongeConfig:
    cipher_preset: str = "toy_spn"
    word_bits: int = 8
    rounds: int = 4
    cipher_seed: int = 0
    lane_count: int = 4
    rate_bits: int = 4
    capacity_bits: int = 4

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def state_bits(self) -> int:
        return self.rate_bits + self.capacity_bits


class ToySponge:
    """
    Minimal sponge: the internal permutation operates on state_bits = rate + capacity.
    Absorb XORs message blocks into the rate portion, then applies a permutation.
    Squeeze reads out the rate portion.

    The underlying permutation is built from the toy cipher operating on word_bits
    (we require word_bits >= state_bits for simplicity, and mask to state_bits).
    """

    def __init__(self, configuration: ToySpongeConfig):
        self.configuration = configuration
        self._state_bits = configuration.state_bits
        self._rate_bits = configuration.rate_bits
        self._capacity_bits = configuration.capacity_bits
        self._state_mask = (1 << self._state_bits) - 1
        self._rate_mask = (1 << self._rate_bits) - 1

        cipher_config: Dict[str, Any] = {
            "cipher_preset": configuration.cipher_preset,
            "word_bits": configuration.word_bits,
            "rounds": configuration.rounds,
            "cipher_seed": configuration.cipher_seed,
            "lane_count": configuration.lane_count,
        }
        self._cipher = build_toy_cipher_from_config(cipher_config)

    def _permute(self, state: int) -> int:
        states, _ = self._cipher.run(int(state) & self._state_mask)
        out_x = states[-1].x
        if isinstance(out_x, tuple):
            # Vector cipher: lanes -> single int (pack then mask)
            w = self.configuration.word_bits
            lane_mask = (1 << w) - 1
            r = 0
            for lane in out_x:
                r = (r << w) | (int(lane) & lane_mask)
            return r & self._state_mask
        return int(out_x) & self._state_mask

    def _build_permutation_table_cpp_toy_spn(self, state_space_size: int) -> List[int] | None:
        """When cipher is scalar toy_spn, build full permutation table in C++ and return it; else None."""
        try:
            cipher = self._cipher
            if not (
                hasattr(cipher, "round_keys")
                and hasattr(cipher, "substitution_table")
                and hasattr(cipher, "bit_permutation")
                and hasattr(cipher, "domain")
            ):
                return None
            from ..native import iwt_core, available as _native_available
            if not _native_available or iwt_core is None:
                return None
            rounds = int(getattr(cipher.configuration, "rounds", 4))
            return list(iwt_core.build_permutation_table_toy_spn(
                state_space_size,
                int(self._state_mask),
                rounds,
                [int(k) for k in cipher.round_keys],
                [int(s) for s in cipher.substitution_table],
                [int(p) for p in cipher.bit_permutation],
                int(cipher.domain.modulus),
                int(cipher.domain.representative),
                "R0",
            ))
        except Exception:
            return None

    def absorb_squeeze(self, message_blocks: List[int], iv: int = 0) -> int:
        """
        Absorb all message blocks, then squeeze one output block.
        Each message block is rate_bits wide.
        When cipher is scalar toy_spn, table build and absorb/squeeze run in C++23; otherwise Python fallback.
        """
        state_space_size = 1 << self._state_bits
        try:
            from ..native import iwt_core, available as _native_available
            if _native_available and iwt_core is not None:
                if not hasattr(self, "_sponge_permutation_table") or self._sponge_permutation_table is None:
                    cpp_table = self._build_permutation_table_cpp_toy_spn(state_space_size)
                    if cpp_table is not None:
                        self._sponge_permutation_table = cpp_table
                    else:
                        self._sponge_permutation_table = [
                            self._permute(s) for s in range(state_space_size)
                        ]
                table = self._sponge_permutation_table
                return int(iwt_core.absorb_squeeze_using_table(
                    int(iv) & self._state_mask,
                    [int(b) & self._rate_mask for b in message_blocks],
                    table,
                    int(self._rate_mask),
                    int(self._state_mask),
                ))
        except Exception:
            pass
        state = int(iv) & self._state_mask
        for block in message_blocks:
            rate_part = int(block) & self._rate_mask
            state = (state ^ rate_part) & self._state_mask
            state = self._permute(state)
        digest = state & self._rate_mask
        return int(digest)

    def compression_function(self, chaining_value: int, message_block: int) -> int:
        """
        Single-step compression: h' = squeeze(absorb(cv, msg)).
        This is the many-to-one mapping that creates winding convergence.
        Uses iwt_core when available (via absorb_squeeze with one block).
        """
        return self.absorb_squeeze([message_block], iv=chaining_value)

    @property
    def rate_space_size(self) -> int:
        return 1 << self._rate_bits

    @property
    def state_space_size(self) -> int:
        return 1 << self._state_bits


@dataclass(frozen=True, slots=True)
class DirectCompressionConfig:
    word_bits: int = 8
    shift_amount: int = 3
    sbox_seed: int = 42

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DirectCompression:
    """
    A simple non-injective function f: {0..q-1} -> {0..q-1}
    defined as f(x) = sbox[x] XOR (x >> shift).

    Non-injectivity is guaranteed because the XOR with a shifted copy
    of the input destroys information (different x values can map to the same output).
    """

    def __init__(self, configuration: DirectCompressionConfig):
        self.configuration = configuration
        q = 1 << int(configuration.word_bits)
        self._q = q
        self._mask = q - 1

        rng = random.Random(int(configuration.sbox_seed))
        table = list(range(q))
        rng.shuffle(table)
        self._sbox = table
        self._shift = int(configuration.shift_amount)

    def __call__(self, x: int) -> int:
        x = int(x) & self._mask
        return (self._sbox[x] ^ (x >> self._shift)) & self._mask

    @property
    def state_space_size(self) -> int:
        return self._q

    def as_successor(self) -> Callable[[int], int]:
        """Return self as a callable suitable for rho_analysis."""
        return self.__call__
