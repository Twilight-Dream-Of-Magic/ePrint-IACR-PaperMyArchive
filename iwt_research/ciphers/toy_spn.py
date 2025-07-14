from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Tuple

from ..core.ops_trace import permute_bits, substitute_box, xor
from ..core.atomic_trace import AtomicEvent
from ..core.discrete_domain import Domain, is_power_of_two
from ..core.enhanced_state import DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, InformationHeight


def _make_bijection_table(*, modulus_q: int, seed: int) -> list[int]:
    if modulus_q < 2:
        raise ValueError("modulus_q must be >= 2")
    random_generator = random.Random(int(seed))
    table = list(range(int(modulus_q)))
    random_generator.shuffle(table)
    return table


def _make_bit_permutation(*, word_bits: int, seed: int) -> list[int]:
    if word_bits <= 0:
        raise ValueError("word_bits must be positive")
    random_generator = random.Random(int(seed))
    permutation = list(range(int(word_bits)))
    random_generator.shuffle(permutation)
    return permutation


@dataclass(frozen=True, slots=True)
class ToySubstitutionPermutationNetworkConfig:
    word_bits: int = 8
    rounds: int = 10
    seed: int = 0


class ToySubstitutionPermutationNetwork:
    """
    Toy Substitution-Permutation Network (SPN) with auditable atomic steps per round:
      xor(round_key) -> s_box(table) -> p_box(bit_permutation)

    Engineering policy:
    - S-box and P-box are within-domain structural operators.
    - S-box: structure increment δ^struct from value-domain unwinding (per-step, no fixed constant).
    - P-box: structure increment δ^struct ∈ {-1,0,+1} (bounded local lift); report has cycle metrics and inv(π).
    """

    def __init__(self, configuration: ToySubstitutionPermutationNetworkConfig):
        self.configuration = configuration
        self.domain = Domain(modulus=1 << int(configuration.word_bits), representative=0)
        if not is_power_of_two(int(self.domain.q)):
            raise ValueError("ToySubstitutionPermutationNetwork requires power-of-two modulus")

        random_generator = random.Random(int(configuration.seed))
        self.round_keys = [random_generator.randrange(int(self.domain.q)) for _ in range(int(configuration.rounds))]

        self.substitution_table = _make_bijection_table(
            modulus_q=int(self.domain.q),
            seed=int(configuration.seed) ^ 0x51B0_51B0,
        )
        self.bit_permutation = _make_bit_permutation(
            word_bits=int(configuration.word_bits),
            seed=int(configuration.seed) ^ 0x70B0_51B0,
        )

    def init_state(self, x0: int, *, building_label: str = "R0") -> DiscreteHighdimensionalInformationSpace_TrackTrajectoryState:
        initial_value = int(x0) % int(self.domain.q)
        return DiscreteHighdimensionalInformationSpace_TrackTrajectoryState(
            floor=str(building_label),
            domain=self.domain,
            x=int(initial_value),
            information_height=InformationHeight(),
            tc=0,
        )

    def run_from_state(
        self,
        state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    ) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        return self.run(int(state.x))

    def successor_of_state(
        self,
        state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    ) -> DiscreteHighdimensionalInformationSpace_TrackTrajectoryState:
        states, _ = self.run_from_state(state)
        if not states:
            raise RuntimeError("ToySubstitutionPermutationNetwork.run_from_state returned empty state trajectory")
        return states[-1]

    def state_to_observation(
        self,
        state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    ) -> int:
        return int(state.x)

    def run(self, x0: int) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        try:
            from ..native import iwt_core, available as _native_available
            if _native_available and iwt_core is not None:
                state_snapshots, event_snapshots = iwt_core.run_toy_spn(
                    int(x0),
                    int(self.configuration.rounds),
                    [int(k) for k in self.round_keys],
                    [int(s) for s in self.substitution_table],
                    [int(p) for p in self.bit_permutation],
                    int(self.domain.modulus),
                    int(self.domain.representative),
                    "R0",
                )
                states = []
                for snap in state_snapshots:
                    ih = InformationHeight(
                        current_building_side_depth=int(snap.current_building_side_depth),
                        current_building_height=int(snap.current_building_height),
                        cross_building_event_count=int(snap.cross_building_event_count),
                        cross_domain_reencoding_quotient=int(snap.cross_domain_reencoding_quotient),
                    )
                    st = DiscreteHighdimensionalInformationSpace_TrackTrajectoryState(
                        floor=str(snap.floor),
                        domain=self.domain,
                        x=int(snap.value_x),
                        information_height=ih,
                        tc=int(snap.time_counter),
                    )
                    states.append(st)
                events = []
                for ev in event_snapshots:
                    carry = int(ev.carry) if ev.carry is not None else None
                    borrow = int(ev.borrow) if ev.borrow is not None else None
                    events.append(AtomicEvent(
                        tc=int(ev.time_counter),
                        op=str(ev.operation),
                        floor=str(ev.floor),
                        q=int(ev.modulus),
                        w=int(ev.representative),
                        x0=int(ev.value_before),
                        x1=int(ev.value_after_reduction),
                        raw=int(ev.raw_value_before_reduction),
                        delta=int(ev.boundary_quotient_delta),
                        wrap=bool(ev.wrap_occurred),
                        carry=carry,
                        borrow=borrow,
                        meta=(),
                    ))
                return states, events
        except Exception:
            pass
        raise RuntimeError(
            "iwt_core (C++ extension) is required for ToySubstitutionPermutationNetwork.run(). "
            "Build the native module from iwt_research/iwt_core or install with native support."
        )

