from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Tuple

from ..core.enhanced_state import DiscreteHighdimensionalInformationSpace_TrackTrajectoryState


Projection = Callable[[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], int]

def _lane_from_state_value(state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, lane_index: int) -> int:
    """
    Vector-state compatible lane readout:
    - scalar x: lane 0 returns x; other lanes return 0
    - vector x (tuple/list): return x[lane_index] if in range else 0
    """
    x = state.x  # type: ignore[attr-defined]
    i = int(lane_index)
    if isinstance(x, (tuple, list)):
        if i < 0 or i >= len(x):
            return 0
        return int(x[i])
    return int(x) if i == 0 else 0


def _scalar_from_state_value(state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState) -> int:
    """
    Projection compatibility helper:
    - scalar x: use it directly
    - vector x (tuple/list): default to lane 0
    """
    x = state.x  # type: ignore[attr-defined]
    if isinstance(x, (tuple, list)):
        return int(x[0]) if x else 0
    return int(x)


def proj_core(state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState) -> int:
    return _scalar_from_state_value(state)


@dataclass(frozen=True, slots=True)
class Lane:
    i: int

    def __call__(self, state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState) -> int:
        return _lane_from_state_value(state, int(self.i))


@dataclass(frozen=True, slots=True)
class LowBits:
    k: int

    def __call__(self, state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState) -> int:
        if self.k <= 0:
            return 0
        mask = (1 << self.k) - 1
        return _scalar_from_state_value(state) & mask


@dataclass(frozen=True, slots=True)
class LaneLowBits:
    i: int
    k: int

    def __call__(self, state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState) -> int:
        if self.k <= 0:
            return 0
        mask = (1 << self.k) - 1
        return _lane_from_state_value(state, int(self.i)) & mask


@dataclass(frozen=True, slots=True)
class HighBits:
    word_bits: int
    k: int

    def __call__(self, state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState) -> int:
        if self.k <= 0:
            return 0
        shift = max(0, self.word_bits - self.k)
        return (_scalar_from_state_value(state) >> shift) & ((1 << self.k) - 1)


@dataclass(frozen=True, slots=True)
class LaneHighBits:
    word_bits: int
    i: int
    k: int

    def __call__(self, state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState) -> int:
        if self.k <= 0:
            return 0
        shift = max(0, self.word_bits - self.k)
        return (_lane_from_state_value(state, int(self.i)) >> shift) & ((1 << self.k) - 1)


@dataclass(frozen=True, slots=True)
class BitPlane:
    i: int

    def __call__(self, state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState) -> int:
        return (_scalar_from_state_value(state) >> self.i) & 1


@dataclass(frozen=True, slots=True)
class LaneBitPlane:
    lane: int
    bit: int

    def __call__(self, state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState) -> int:
        return (_lane_from_state_value(state, int(self.lane)) >> int(self.bit)) & 1


def parse_projection(spec: str, *, word_bits: int | None = None) -> Tuple[str, Projection]:
    """
    Parse a projection spec:
    - "core"
    - "lowbits:k"
    - "highbits:k" (requires word_bits)
    - "bit:i"

    Vector-state extensions (Omega^n):
    - "lane:i"
    - "lane_lowbits:i:k"
    - "lane_highbits:i:k" (requires word_bits)
    - "lane_bit:i:j"
    """
    s = spec.strip().lower()
    if s == "core":
        return "core", proj_core
    if s.startswith("lane:"):
        i = int(s.split(":", 1)[1])
        return f"lane:{i}", Lane(i=i)
    if s.startswith("lowbits:"):
        k = int(s.split(":", 1)[1])
        return f"lowbits:{k}", LowBits(k)
    if s.startswith("lane_lowbits:"):
        rest = s.split(":", 1)[1]
        i_str, k_str = rest.split(":", 1)
        i = int(i_str)
        k = int(k_str)
        return f"lane_lowbits:{i}:{k}", LaneLowBits(i=i, k=k)
    if s.startswith("highbits:"):
        if word_bits is None:
            raise ValueError("highbits requires word_bits")
        k = int(s.split(":", 1)[1])
        return f"highbits:{k}", HighBits(word_bits=word_bits, k=k)
    if s.startswith("lane_highbits:"):
        if word_bits is None:
            raise ValueError("lane_highbits requires word_bits")
        rest = s.split(":", 1)[1]
        i_str, k_str = rest.split(":", 1)
        i = int(i_str)
        k = int(k_str)
        return f"lane_highbits:{i}:{k}", LaneHighBits(word_bits=word_bits, i=i, k=k)
    if s.startswith("bit:"):
        i = int(s.split(":", 1)[1])
        return f"bit:{i}", BitPlane(i)
    if s.startswith("lane_bit:"):
        rest = s.split(":", 1)[1]
        lane_str, bit_str = rest.split(":", 1)
        lane = int(lane_str)
        bit = int(bit_str)
        return f"lane_bit:{lane}:{bit}", LaneBitPlane(lane=lane, bit=bit)
    raise ValueError(f"unknown projection spec: {spec!r}")

