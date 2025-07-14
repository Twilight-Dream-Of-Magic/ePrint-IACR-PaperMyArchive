from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, List, Tuple

from ..core.ops_trace import (
    add,
    cross_domain,
    permute_bits,
    permute_values,
    rotl_bits,
    rotr_bits,
    substitute_box,
    xor,
)
from ..core.atomic_trace import AtomicEvent
from ..core.discrete_domain import Domain
from ..core.enhanced_state import DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, InformationHeight


def _snapshots_to_states_events(
    domain: Domain,
    state_snapshots: List[Any],
    event_snapshots: List[Any],
) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
    """Convert C++ state_snapshots/event_snapshots to Python states and events."""
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
            domain=domain,
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


class Baseline:
    name: str

    def run(self, x0: int) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class RandomPermutationBaseline(Baseline):
    domain: Domain
    steps: int
    seed: int
    name: str = "random_permutation"

    def __post_init__(self) -> None:
        if self.domain.w != 0:
            raise ValueError("random_permutation baseline assumes w=0 for toy")
        if self.domain.q > 1_000_000:
            raise ValueError("q too large for explicit permutation baseline")

    def run(self, x0: int) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        try:
            from ..native import iwt_core, available as _native_available
            if _native_available and iwt_core is not None:
                rng = random.Random(self.seed)
                perm = list(range(self.domain.q))
                rng.shuffle(perm)
                state_snapshots, event_snapshots = iwt_core.run_permutation_baseline(
                    int(x0), perm, int(self.steps), int(self.domain.q), int(self.domain.w),
                )
                return _snapshots_to_states_events(self.domain, state_snapshots, event_snapshots)
        except Exception:
            pass
        rng = random.Random(self.seed)
        perm = list(range(self.domain.q))
        rng.shuffle(perm)

        st = DiscreteHighdimensionalInformationSpace_TrackTrajectoryState(floor="B0", domain=self.domain, x=x0 % self.domain.q, information_height=InformationHeight(), tc=0)
        states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState] = [st]
        events: List[AtomicEvent] = []

        for i in range(self.steps):
            st, ev = permute_values(st, perm, op="perm_step")
            events.append(ev)
            states.append(st)
        return states, events


@dataclass(frozen=True, slots=True)
class RandomFunctionBaseline(Baseline):
    domain: Domain
    steps: int
    seed: int
    name: str = "random_function"

    def __post_init__(self) -> None:
        if self.domain.w != 0:
            raise ValueError("random_function baseline assumes w=0 for toy")
        if self.domain.q > 1_000_000:
            raise ValueError("q too large for explicit function baseline")

    def run(self, x0: int) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        try:
            from ..native import iwt_core, available as _native_available
            if _native_available and iwt_core is not None:
                rng = random.Random(self.seed)
                f = [rng.randrange(self.domain.q) for _ in range(self.domain.q)]
                state_snapshots, event_snapshots = iwt_core.run_function_baseline(
                    int(x0), f, int(self.steps), int(self.domain.q), int(self.domain.w),
                )
                return _snapshots_to_states_events(self.domain, state_snapshots, event_snapshots)
        except Exception:
            pass
        rng = random.Random(self.seed)
        f = [rng.randrange(self.domain.q) for _ in range(self.domain.q)]

        st = DiscreteHighdimensionalInformationSpace_TrackTrajectoryState(floor="B0", domain=self.domain, x=x0 % self.domain.q, information_height=InformationHeight(), tc=0)
        states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState] = [st]
        events: List[AtomicEvent] = []

        for i in range(self.steps):
            x = st.x
            raw = f[x]
            st1 = st.with_updates(x=int(raw), tc=st.tc + 1)
            ev = AtomicEvent(
                tc=st.tc,
                op="func_step",
                floor=st.floor,
                q=self.domain.q,
                w=self.domain.w,
                x0=int(x),
                x1=int(raw),
                raw=int(raw),
                delta=0,
                wrap=False,
                meta=(("i", int(i)),),
            )
            events.append(ev)
            states.append(st1)
            st = st1
        return states, events


@dataclass(frozen=True, slots=True)
class RandomARXLikeBaseline(Baseline):
    domain: Domain
    rounds: int
    seed: int
    word_bits: int
    rot_mode: str = "bits"
    rot_dir: str = "l"  # "l" | "r"
    cross_domain_q: int | None = None
    cross_every_rounds: int = 4
    name: str = "random_arx_like"

    def run(self, x0: int) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        if self.rot_mode == "bits" and self.cross_domain_q is not None:
            q2 = int(self.cross_domain_q)
            if q2 & (q2 - 1) != 0:
                raise ValueError("cross_domain_q must be power-of-two when rot_mode='bits'")
        try:
            from ..native import iwt_core, available as _native_available
            if _native_available and iwt_core is not None:
                rng = random.Random(self.seed ^ (x0 * 0x9E37))
                round_keys = [rng.randrange(self.domain.q) for _ in range(self.rounds)]
                round_constants = [rng.randrange(self.domain.q) for _ in range(self.rounds)]
                word_bits = max(1, self.domain.q.bit_length() - 1)
                rotation_amounts = [rng.randrange(1, max(2, word_bits)) for _ in range(self.rounds)]
                cross_mod = int(self.cross_domain_q) if self.cross_domain_q else 0
                state_snapshots, event_snapshots = iwt_core.run_toy_arx(
                    int(x0) % int(self.domain.q),
                    int(self.rounds),
                    round_keys,
                    round_constants,
                    rotation_amounts,
                    self.rot_dir == "l",
                    int(self.domain.q),
                    int(self.domain.w),
                    cross_mod,
                    int(self.cross_every_rounds),
                    "B0",
                    "DomQ",
                )
                return _snapshots_to_states_events(self.domain, state_snapshots, event_snapshots)
        except Exception:
            pass
        rng = random.Random(self.seed ^ (x0 * 0x9E37))
        st = DiscreteHighdimensionalInformationSpace_TrackTrajectoryState(floor="B0", domain=self.domain, x=x0 % self.domain.q, information_height=InformationHeight(), tc=0)
        cross_dom = Domain(modulus=self.cross_domain_q, representative=0) if self.cross_domain_q else None
        states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState] = [st]
        events: List[AtomicEvent] = []

        for i in range(self.rounds):
            if cross_dom and self.cross_every_rounds > 0 and (i % self.cross_every_rounds == 0) and i != 0:
                if st.domain.q == self.domain.q:
                    st, ev = cross_domain(
                        st,
                        new_floor=f"Dom{cross_dom.q}",
                        new_domain=cross_dom,
                        op=f"cross_domain[r{i}]",
                        cross_step=+1,
                    )
                else:
                    st, ev = cross_domain(
                        st,
                        new_floor=f"Dom{self.domain.q}",
                        new_domain=self.domain,
                        op=f"cross_domain[r{i}]",
                        cross_step=-1,
                    )
                events.append(ev)
                states.append(st)

            k = rng.randrange(self.domain.q)
            c = rng.randrange(self.domain.q)
            r = rng.randrange(1, max(2, self.word_bits))

            st, ev = add(st, int(k), op="add[rnd]")
            events.append(ev)
            states.append(st)

            q = st.domain.q
            if q & (q - 1) != 0:
                raise ValueError("ARX baseline requires power-of-two q in the current domain")
            word_bits_now = q.bit_length() - 1
            if self.rot_dir == "l":
                st, ev = rotl_bits(st, int(r), word_bits=word_bits_now, op="rotl_bits[rnd]")
            else:
                st, ev = rotr_bits(st, int(r), word_bits=word_bits_now, op="rotr_bits[rnd]")
            events.append(ev)
            states.append(st)

            st, ev = xor(st, int(c), op="xor[rnd]")
            events.append(ev)
            states.append(st)

        return states, events


@dataclass(frozen=True, slots=True)
class RandomSubstitutionPermutationNetworkBaseline(Baseline):
    domain: Domain
    rounds: int
    seed: int
    name: str = "random_substitution_permutation_network"

    def __post_init__(self) -> None:
        if self.domain.w != 0:
            raise ValueError("random_substitution_permutation_network baseline assumes w=0 for toy")
        if self.domain.q < 2:
            raise ValueError("q must be >= 2")

    def run(self, x0: int) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        word_bits = int(self.domain.q).bit_length() - 1
        if (1 << word_bits) != int(self.domain.q):
            raise ValueError("random_substitution_permutation_network baseline requires power-of-two domain.q")

        random_generator = random.Random(int(self.seed))
        round_keys = [random_generator.randrange(int(self.domain.q)) for _ in range(int(self.rounds))]
        substitution_table = list(range(int(self.domain.q)))
        random.Random(int(self.seed) ^ 0x51B0_51B0).shuffle(substitution_table)
        bit_permutation = list(range(int(word_bits)))
        random.Random(int(self.seed) ^ 0x70B0_51B0).shuffle(bit_permutation)

        try:
            from ..native import iwt_core, available as _native_available
            if _native_available and iwt_core is not None:
                state_snapshots, event_snapshots = iwt_core.run_toy_spn(
                    int(x0) % int(self.domain.q),
                    int(self.rounds),
                    round_keys,
                    substitution_table,
                    bit_permutation,
                    int(self.domain.q),
                    int(self.domain.w),
                    "B0",
                )
                return _snapshots_to_states_events(self.domain, state_snapshots, event_snapshots)
        except Exception:
            pass

        state = DiscreteHighdimensionalInformationSpace_TrackTrajectoryState(
            floor="B0",
            domain=self.domain,
            x=int(x0) % int(self.domain.q),
            information_height=InformationHeight(),
            tc=0,
        )
        states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState] = [state]
        events: List[AtomicEvent] = []

        for round_index in range(int(self.rounds)):
            state, event = xor(state, int(round_keys[round_index]), op="xor_round_key[rnd]")
            events.append(event)
            states.append(state)
            state, event = substitute_box(state, substitution_table, op="s_box[rnd]")
            events.append(event)
            states.append(state)
            state, event = permute_bits(state, bit_permutation, op="p_box_bits[rnd]")
            events.append(event)
            states.append(state)

        return states, events

    def get_pbox_inversion_norm(self) -> float:
        """同楼同层非越界缠绕：逆序对 inv(π) 归一化值，用于 P7 校準。仅 SPN 类 baseline 有 P-box。使用 C++ iwt_core 的 inversion_count_permutation + inversion_norm。"""
        from ..native import iwt_core
        q = int(self.domain.q)
        word_bits = q.bit_length() - 1
        if (1 << word_bits) != q or q < 2:
            return float("nan")
        bit_permutation = list(range(word_bits))
        random.Random(int(self.seed) ^ 0x70B0_51B0).shuffle(bit_permutation)

        def pbox_apply(x: int) -> int:
            x = int(x) & (q - 1)
            out = 0
            for j, pj in enumerate(bit_permutation):
                out |= ((x >> pj) & 1) << j
            return out

        pbox_out = [pbox_apply(t) for t in range(q)]
        inv_count = int(iwt_core.inversion_count_permutation([int(x) for x in pbox_out]))
        return float(iwt_core.inversion_norm(inv_count, q))


@dataclass(frozen=True, slots=True)
class RandomSubstitutionPermutationNetworkVectorBaseline(Baseline):
    domain: Domain
    rounds: int
    lane_count: int
    seed: int
    name: str = "random_substitution_permutation_network_vector"

    def __post_init__(self) -> None:
        if self.domain.w != 0:
            raise ValueError("random_substitution_permutation_network_vector baseline assumes w=0 for toy")
        if int(self.lane_count) <= 0:
            raise ValueError("lane_count must be positive")

    def index_to_lanes(self, index: int) -> Tuple[int, ...]:
        modulus_q = int(self.domain.q)
        lane_count = int(self.lane_count)
        if int(index) < 0 or int(index) >= (modulus_q**lane_count):
            raise ValueError("index out of range for Omega^n")
        x = int(index)
        lanes: List[int] = []
        for _ in range(lane_count):
            lanes.append(int(x % modulus_q))
            x //= modulus_q
        return tuple(lanes)

    def run(self, x0: int) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        return self.run_from_index(int(x0))

    def run_from_index(self, state_index: int) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        from ..ciphers.toy_spn_vector import (
            _apply_p_box_to_flat_bits,
            _apply_s_box_to_lanes,
            _flatten_lanes_to_integer,
            _make_bijection_table,
            _make_bit_permutation,
            _unflatten_integer_to_lanes,
        )

        word_bits = int(int(self.domain.q).bit_length() - 1)
        if (1 << word_bits) != int(self.domain.q):
            raise ValueError("random_substitution_permutation_network_vector baseline requires power-of-two domain.q")

        lanes = self.index_to_lanes(int(state_index))

        random_generator_keys = random.Random(int(self.seed))
        round_keys = [
            tuple(random_generator_keys.randrange(int(self.domain.q)) for _ in range(int(self.lane_count)))
            for _ in range(int(self.rounds))
        ]

        substitution_table = _make_bijection_table(modulus_q=int(self.domain.q), seed=int(self.seed) ^ 0x51B0_51B0)
        total_bits = int(word_bits) * int(self.lane_count)
        bit_permutation_all = _make_bit_permutation(bit_count_total=total_bits, seed=int(self.seed) ^ 0x70B0_51B0)

        state = DiscreteHighdimensionalInformationSpace_TrackTrajectoryState(
            floor="B0",
            domain=self.domain,
            x=lanes,  # type: ignore[arg-type]
            information_height=InformationHeight(),
            tc=0,
        )
        states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState] = [state]
        events: List[AtomicEvent] = []

        from ..metrics.structure_height import per_step_structure_increments_sbox, pbox_structure_increment_at
        sbox_output = [0 + int(substitution_table[t]) for t in range(int(self.domain.q))]
        sbox_per_step = per_step_structure_increments_sbox(sbox_output, int(self.domain.q), 0)
        modulus_q = int(self.domain.q)
        lane_count = int(self.lane_count)
        pbox_q = 1 << (word_bits * lane_count)  # flattened P-box 空間大小

        for round_index in range(int(self.rounds)):
            lanes_before = tuple(state.x)  # type: ignore[arg-type]
            key = round_keys[round_index]
            lanes_after_xor = tuple((int(a) ^ int(b)) % modulus_q for a, b in zip(lanes_before, key))
            state = state.with_updates(x=lanes_after_xor, tc=state.tc + 1)  # type: ignore[arg-type]
            events.append(
                AtomicEvent(
                    tc=states[-1].tc,
                    op="xor_round_key[rnd]",
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
            lanes_after_s = _apply_s_box_to_lanes(lanes_before, substitution_table, modulus_q=modulus_q)
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
                    op="s_box[rnd]",
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
            flat_after = _apply_p_box_to_flat_bits(flat_before, bit_permutation_all)
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
                    op="p_box_bits_all[rnd]",
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

    def get_pbox_inversion_norm(self) -> float:
        """同楼同层非越界缠绕：逆序对 inv(π) 归一化值（扁平化 P-box），用于 P7 校準。使用 C++ iwt_core 的 inversion_count_permutation + inversion_norm。"""
        from ..native import iwt_core
        from ..ciphers.toy_spn_vector import _apply_p_box_to_flat_bits, _make_bit_permutation
        word_bits = int(int(self.domain.q).bit_length() - 1)
        if (1 << word_bits) != int(self.domain.q):
            return float("nan")
        total_bits = word_bits * int(self.lane_count)
        pbox_q = 1 << total_bits
        if pbox_q < 2:
            return float("nan")
        bit_permutation_all = _make_bit_permutation(bit_count_total=total_bits, seed=int(self.seed) ^ 0x70B0_51B0)
        pbox_out = [
            _apply_p_box_to_flat_bits(t, bit_permutation_all) & (pbox_q - 1)
            for t in range(pbox_q)
        ]
        inv_count = int(iwt_core.inversion_count_permutation([int(x) for x in pbox_out]))
        return float(iwt_core.inversion_norm(inv_count, pbox_q))
