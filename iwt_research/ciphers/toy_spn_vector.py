from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from ..core.atomic_trace import AtomicEvent
from ..core.discrete_domain import Domain, is_power_of_two
from ..core.enhanced_state import DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, InformationHeight
from ..state_encoding.vector import index_to_lanes as index_to_lanes_encoding
from ..state_encoding.vector import lanes_to_index as lanes_to_index_encoding


def _bit_count(value: int) -> int:
    return int(value).bit_count()


def _flatten_lanes_to_integer(lanes: Tuple[int, ...], *, word_bits: int) -> int:
    out = 0
    for lane_index, lane_value in enumerate(lanes):
        out |= (int(lane_value) & ((1 << int(word_bits)) - 1)) << (int(word_bits) * int(lane_index))
    return int(out)


def _unflatten_integer_to_lanes(value: int, *, word_bits: int, lane_count: int) -> Tuple[int, ...]:
    mask = (1 << int(word_bits)) - 1
    lanes: List[int] = []
    for lane_index in range(int(lane_count)):
        lanes.append((int(value) >> (int(word_bits) * int(lane_index))) & int(mask))
    return tuple(int(x) for x in lanes)


def _make_bijection_table(*, modulus_q: int, seed: int) -> list[int]:
    if modulus_q < 2:
        raise ValueError("modulus_q must be >= 2")
    random_generator = random.Random(int(seed))
    table = list(range(int(modulus_q)))
    random_generator.shuffle(table)
    return table


def _make_bit_permutation(*, bit_count_total: int, seed: int) -> list[int]:
    if bit_count_total <= 0:
        raise ValueError("bit_count_total must be positive")
    random_generator = random.Random(int(seed))
    permutation = list(range(int(bit_count_total)))
    random_generator.shuffle(permutation)
    return permutation


def _apply_s_box_to_lanes(lanes: Tuple[int, ...], substitution_table: list[int], *, modulus_q: int) -> Tuple[int, ...]:
    if len(substitution_table) != int(modulus_q):
        raise ValueError("substitution_table length must equal modulus_q")
    out: List[int] = []
    for x in lanes:
        v = int(x) % int(modulus_q)
        out.append(int(substitution_table[v]))
    return tuple(out)


def _apply_p_box_to_flat_bits(value: int, bit_permutation: list[int]) -> int:
    """
    Permute bits of a flattened integer according to a permutation on positions.
    Convention: output bit j is input bit bit_permutation[j].
    """
    if not bit_permutation:
        return 0
    if sorted(int(i) for i in bit_permutation) != list(range(len(bit_permutation))):
        raise ValueError("bit_permutation must be a permutation of [0..B-1]")
    out = 0
    for output_bit_index, input_bit_index in enumerate(bit_permutation):
        bit_value = (int(value) >> int(input_bit_index)) & 1
        out |= int(bit_value) << int(output_bit_index)
    return int(out)


@dataclass(frozen=True, slots=True)
class ToySubstitutionPermutationNetworkVectorConfig:
    word_bits: int = 8
    lane_count: int = 4
    rounds: int = 10
    seed: int = 0


class ToySubstitutionPermutationNetworkVector:
    """
    High-dimensional SPN toy over Omega^n with auditable atomic events.

    State is stored in DiscreteHighdimensionalInformationSpace_TrackTrajectoryState.x as a tuple of lanes (length lane_count).
    - within-domain only (no cross-building)
    - per round: xor_round_key -> s_box -> p_box_bits_all
    - height policy: S-box 維度>2 用解纏繞；P-box 維度=2 用有界符號 δ∈{-1,0,+1}，同層纏繞用 inv(π)。
    """

    def __init__(self, configuration: ToySubstitutionPermutationNetworkVectorConfig):
        if int(configuration.lane_count) <= 0:
            raise ValueError("lane_count must be positive")
        if int(configuration.word_bits) <= 0:
            raise ValueError("word_bits must be positive")
        self.configuration = configuration
        self.domain = Domain(modulus=1 << int(configuration.word_bits), representative=0)
        if not is_power_of_two(int(self.domain.q)):
            raise ValueError("ToySubstitutionPermutationNetworkVector requires power-of-two modulus")

        random_generator = random.Random(int(configuration.seed))
        self.round_keys = [
            tuple(random_generator.randrange(int(self.domain.q)) for _ in range(int(configuration.lane_count)))
            for _ in range(int(configuration.rounds))
        ]

        self.substitution_table = _make_bijection_table(
            modulus_q=int(self.domain.q),
            seed=int(configuration.seed) ^ 0x51B0_51B0,
        )
        total_bits = int(configuration.word_bits) * int(configuration.lane_count)
        self.bit_permutation_all = _make_bit_permutation(
            bit_count_total=total_bits,
            seed=int(configuration.seed) ^ 0x70B0_51B0,
        )

    def _seed_to_lanes(self, x0: int) -> Tuple[int, ...]:
        random_generator = random.Random(int(self.configuration.seed) ^ (int(x0) * 0x9E37_79B9))
        return tuple(
            int(random_generator.randrange(int(self.domain.q))) for _ in range(int(self.configuration.lane_count))
        )

    def index_to_lanes(self, index: int) -> Tuple[int, ...]:
        """
        Deterministic base-q decoding for exhaustive enumeration of Omega^n.

        index in [0, q^n) is mapped to lanes in (Z_q)^n by base-q expansion.
        """
        modulus_q = int(self.domain.q)
        lane_count = int(self.configuration.lane_count)
        if int(index) < 0 or int(index) >= (modulus_q**lane_count):
            raise ValueError("index out of range for Omega^n")
        return index_to_lanes_encoding(
            int(index),
            modulus_q=modulus_q,
            lane_count=lane_count,
        )

    def lanes_to_index(self, lanes: Tuple[int, ...]) -> int:
        modulus_q = int(self.domain.q)
        if len(lanes) != int(self.configuration.lane_count):
            raise ValueError("lanes length must equal lane_count")
        return lanes_to_index_encoding(
            tuple(int(v) for v in lanes),
            modulus_q=modulus_q,
        )

    def init_state(self, x0: int, *, building_label: str = "R0") -> DiscreteHighdimensionalInformationSpace_TrackTrajectoryState:
        lanes = self._seed_to_lanes(int(x0))
        return DiscreteHighdimensionalInformationSpace_TrackTrajectoryState(
            floor=str(building_label),
            domain=self.domain,
            x=lanes,  # type: ignore[arg-type]
            information_height=InformationHeight(),
            tc=0,
        )

    def run_from_state(
        self,
        state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    ) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        x = state.x
        if not isinstance(x, (tuple, list)):
            raise ValueError("ToySubstitutionPermutationNetworkVector.run_from_state expects tuple/list lane state")
        return self.run_from_lanes(tuple(int(v) for v in x))

    def successor_of_state(
        self,
        state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    ) -> DiscreteHighdimensionalInformationSpace_TrackTrajectoryState:
        states, _ = self.run_from_state(state)
        if not states:
            raise RuntimeError("ToySubstitutionPermutationNetworkVector.run_from_state returned empty state trajectory")
        return states[-1]

    def state_to_observation(
        self,
        state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    ) -> tuple[int, ...]:
        x = state.x
        if not isinstance(x, (tuple, list)):
            raise ValueError("ToySubstitutionPermutationNetworkVector.state_to_observation expects tuple/list lane state")
        return tuple(int(v) for v in x)

    def run(self, x0: int) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        return self.run_from_lanes(self._seed_to_lanes(int(x0)))

    def run_from_index(self, index: int) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        return self.run_from_lanes(self.index_to_lanes(int(index)))

    def run_from_lanes(self, lanes0: Tuple[int, ...]) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        if len(lanes0) != int(self.configuration.lane_count):
            raise ValueError("lanes0 length must equal lane_count")
        state = DiscreteHighdimensionalInformationSpace_TrackTrajectoryState(
            floor="R0",
            domain=self.domain,
            x=tuple(int(v) % int(self.domain.q) for v in lanes0),  # type: ignore[arg-type]
            information_height=InformationHeight(),
            tc=0,
        )
        states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState] = [state]
        events: List[AtomicEvent] = []

        word_bits = int(self.configuration.word_bits)
        modulus_q = int(self.domain.q)
        lane_count = int(self.configuration.lane_count)
        total_bits = int(word_bits) * int(lane_count)
        from ..metrics.structure_height import per_step_structure_increments_sbox, pbox_structure_increment_at
        sbox_output = [0 + int(self.substitution_table[t]) for t in range(modulus_q)]
        sbox_per_step = per_step_structure_increments_sbox(sbox_output, modulus_q, 0)
        pbox_q = 1 << total_bits  # flattened P-box 空間大小

        for round_index in range(int(self.configuration.rounds)):
            lanes_before = tuple(state.x)  # type: ignore[arg-type]
            key = self.round_keys[round_index]
            lanes_after_xor = tuple((int(a) ^ int(b)) % modulus_q for a, b in zip(lanes_before, key))
            state = state.with_updates(x=lanes_after_xor, tc=state.tc + 1)  # type: ignore[arg-type]
            events.append(
                AtomicEvent(
                    tc=states[-1].tc,
                    op=f"xor_round_key[r{round_index}]",
                    floor=state.floor,
                    q=modulus_q,
                    w=0,
                    x0=_flatten_lanes_to_integer(lanes_before, word_bits=word_bits),
                    x1=_flatten_lanes_to_integer(lanes_after_xor, word_bits=word_bits),
                    raw=_flatten_lanes_to_integer(lanes_after_xor, word_bits=word_bits),
                    delta=0,
                    wrap=False,
                    meta=(("lane_count", lane_count),),
                )
            )
            states.append(state)

            lanes_before = tuple(state.x)  # type: ignore[arg-type]
            lanes_after_s = _apply_s_box_to_lanes(lanes_before, self.substitution_table, modulus_q=modulus_q)
            delta_struct = sum(int(sbox_per_step[int(l)]) for l in lanes_before if 0 <= int(l) < len(sbox_per_step))
            ih = state.information_height
            new_ih = InformationHeight(
                current_building_height=ih.current_building_height + delta_struct,
                cross_building_event_count=ih.cross_building_event_count,
                cross_domain_reencoding_quotient=ih.cross_domain_reencoding_quotient,
                building_exit_snapshots=ih.building_exit_snapshots,
            )
            state = state.with_updates(
                x=lanes_after_s,  # type: ignore[arg-type]
                information_height=new_ih,
                tc=state.tc + 1,
            )
            events.append(
                AtomicEvent(
                    tc=states[-1].tc,
                    op=f"s_box[r{round_index}]",
                    floor=state.floor,
                    q=modulus_q,
                    w=0,
                    x0=_flatten_lanes_to_integer(lanes_before, word_bits=word_bits),
                    x1=_flatten_lanes_to_integer(lanes_after_s, word_bits=word_bits),
                    raw=_flatten_lanes_to_integer(lanes_after_s, word_bits=word_bits),
                    delta=delta_struct,
                    wrap=False,
                    meta=(("delta_struct", delta_struct),),
                )
            )
            states.append(state)

            lanes_before = tuple(state.x)  # type: ignore[arg-type]
            flat_before = _flatten_lanes_to_integer(lanes_before, word_bits=word_bits)
            flat_after = _apply_p_box_to_flat_bits(flat_before, self.bit_permutation_all)
            lanes_after_p = _unflatten_integer_to_lanes(flat_after, word_bits=word_bits, lane_count=lane_count)
            delta_struct_p = pbox_structure_increment_at(flat_before, flat_after, pbox_q, 0)
            ih = state.information_height
            new_ih = InformationHeight(
                current_building_height=ih.current_building_height + delta_struct_p,
                cross_building_event_count=ih.cross_building_event_count,
                cross_domain_reencoding_quotient=ih.cross_domain_reencoding_quotient,
                building_exit_snapshots=ih.building_exit_snapshots,
            )
            state = state.with_updates(
                x=lanes_after_p,  # type: ignore[arg-type]
                information_height=new_ih,
                tc=state.tc + 1,
            )
            events.append(
                AtomicEvent(
                    tc=states[-1].tc,
                    op=f"p_box_bits_all[r{round_index}]",
                    floor=state.floor,
                    q=modulus_q,
                    w=0,
                    x0=int(flat_before) & ((1 << total_bits) - 1),
                    x1=int(flat_after) & ((1 << total_bits) - 1),
                    raw=int(flat_after) & ((1 << total_bits) - 1),
                    delta=delta_struct_p,
                    wrap=False,
                    meta=(("total_bits", int(total_bits)), ("delta_struct", delta_struct_p)),
                )
            )
            states.append(state)

        return states, events

    def iter_neighbor_pairs(self, *, seed: int, pair_count: int) -> Iterable[Tuple[Tuple[int, ...], Tuple[int, ...]]]:
        """
        Generate pairs of neighboring initial states (differ by one bit in one lane).
        """
        random_generator = random.Random(int(seed))
        modulus_q = int(self.domain.q)
        word_bits = int(self.configuration.word_bits)
        lane_count = int(self.configuration.lane_count)
        for _ in range(int(pair_count)):
            lanes = tuple(random_generator.randrange(modulus_q) for _ in range(lane_count))
            lane_index = random_generator.randrange(lane_count)
            bit_index = random_generator.randrange(word_bits)
            flipped = list(lanes)
            flipped[lane_index] = int(flipped[lane_index]) ^ (1 << int(bit_index))
            flipped[lane_index] %= modulus_q
            yield lanes, tuple(int(x) for x in flipped)

    def bit_hamming_distance(self, a: Tuple[int, ...], b: Tuple[int, ...]) -> int:
        return sum(_bit_count(int(x) ^ int(y)) for x, y in zip(a, b))

    def lane_difference_count(self, a: Tuple[int, ...], b: Tuple[int, ...]) -> int:
        return sum(1 for x, y in zip(a, b) if int(x) != int(y))
