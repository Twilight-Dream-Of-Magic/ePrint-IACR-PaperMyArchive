from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Literal, Tuple

from ..core.ops_trace import (
    add,
    cross_domain,
    sub,
    rotl_bits,
    rotr_bits,
    xor,
)
from ..core.atomic_trace import AtomicEvent
from ..core.discrete_domain import Domain
from ..core.enhanced_state import DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, InformationHeight


RotMode = Literal["bits"]
RotDir = Literal["l", "r"]


@dataclass(frozen=True, slots=True)
class ToyARXConfig:
    word_bits: int = 8
    rounds: int = 16
    rot_mode: RotMode = "bits"
    rot_dir: RotDir = "l"
    seed: int = 0
    # Cross-domain ("cross-building") schedule for A: make floor/cross_building_event_count non-trivial.
    # When set, the cipher will periodically cross between q=2^word_bits and q=cross_domain_q.
    cross_domain_q: int | None = None
    cross_every_rounds: int = 4


class ToyARX:
    """
    Toy ARX-like primitive with auditable atomic steps:
      add(k_i) -> rot(r_i) -> xor(c_i)

    rot_mode: "bits" only (true bit-rotation, ARX-native).
    """

    def __init__(self, configuration: ToyARXConfig):
        self.configuration = configuration
        self.domain = Domain(modulus=1 << configuration.word_bits, representative=0)
        if configuration.rot_mode == "bits" and configuration.cross_domain_q is not None:
            # True bit-rotation semantics require power-of-two modulus.
            q2 = int(configuration.cross_domain_q)
            if q2 & (q2 - 1) != 0:
                raise ValueError("cross_domain_q must be power-of-two when rot_mode='bits'")
        self.cross_domain = Domain(modulus=configuration.cross_domain_q, representative=0) if configuration.cross_domain_q else None
        self.rng = random.Random(configuration.seed)

        self.ks = [self.rng.randrange(self.domain.q) for _ in range(configuration.rounds)]
        self.cs = [self.rng.randrange(self.domain.q) for _ in range(configuration.rounds)]
        self.rs = [self.rng.randrange(1, max(2, configuration.word_bits)) for _ in range(configuration.rounds)]

    def init_state(self, x0: int, *, floor: str = "R0") -> DiscreteHighdimensionalInformationSpace_TrackTrajectoryState:
        x0 = x0 % self.domain.q
        return DiscreteHighdimensionalInformationSpace_TrackTrajectoryState(floor=floor, domain=self.domain, x=x0, information_height=InformationHeight(), tc=0)

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
            raise RuntimeError("ToyARX.run_from_state returned empty state trajectory")
        return states[-1]

    def state_to_observation(
        self,
        state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    ) -> int:
        return int(state.x)

    def step_round(self, st: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, i: int) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        states: List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState] = []
        events: List[AtomicEvent] = []

        # A) Cross-domain (跨楼=跨表示/跨域) event injection.
        # We toggle representation between the two domains to ensure floor/cross_building_event_count are meaningful.
        if self.cross_domain and self.configuration.cross_every_rounds > 0 and (i % self.configuration.cross_every_rounds == 0) and i != 0:
            if st.domain.q == self.domain.q:
                st, ev = cross_domain(
                    st,
                    new_floor=f"Dom{self.cross_domain.q}",
                    new_domain=self.cross_domain,
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

        st, ev = add(st, int(self.ks[i]), op=f"add[r{i}]")
        events.append(ev)
        states.append(st)

        q = st.domain.q
        if q & (q - 1) != 0:
            raise ValueError("rot_mode=bits requires power-of-two q in the current domain")
        word_bits_now = q.bit_length() - 1
        if self.configuration.rot_dir == "l":
            st, ev = rotl_bits(st, int(self.rs[i]), word_bits=word_bits_now, op=f"rotl_bits[r{i}]")
        else:
            st, ev = rotr_bits(st, int(self.rs[i]), word_bits=word_bits_now, op=f"rotr_bits[r{i}]")
        events.append(ev)
        states.append(st)

        st, ev = xor(st, int(self.cs[i]), op=f"xor[r{i}]")
        events.append(ev)
        states.append(st)

        return states, events

    def encrypt(self, x0: int) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        """
        Forward execution (encryption direction).
        """
        return self.run(x0)

    def decrypt(self, final_state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        """
        Reverse execution (decryption direction) that should return to the original state,
        for the correct key/config.

        Requirements:
        - cross-domain schedule must match the encryption config; this function will invert it deterministically.
        """
        try:
            from ..native import iwt_core, available as _native_available
            if _native_available and iwt_core is not None:
                snap = iwt_core.StateSnapshot()
                snap.value_x = int(final_state.x)
                snap.time_counter = int(final_state.tc)
                snap.floor = str(final_state.floor)
                snap.current_building_side_depth = int(final_state.information_height.current_building_side_depth)
                snap.current_building_height = int(final_state.information_height.current_building_height)
                snap.cross_building_event_count = int(final_state.information_height.cross_building_event_count)
                snap.cross_domain_reencoding_quotient = int(final_state.information_height.cross_domain_reencoding_quotient)
                cross_q = int(self.cross_domain.q) if self.cross_domain else 0
                cross_every = int(self.configuration.cross_every_rounds) if self.cross_domain else 0
                cross_floor = f"Dom{self.cross_domain.q}" if self.cross_domain else "DomQ"
                state_snapshots, event_snapshots = iwt_core.run_toy_arx_decrypt(
                    final_state=snap,
                    final_modulus=int(final_state.domain.modulus),
                    final_representative=int(final_state.domain.representative),
                    rounds=int(self.configuration.rounds),
                    round_keys=[int(k) for k in self.ks],
                    round_constants=[int(c) for c in self.cs],
                    rotation_amounts=[int(r) for r in self.rs],
                    rotate_left=(self.configuration.rot_dir == "l"),
                    base_modulus=int(self.domain.modulus),
                    base_representative=int(self.domain.representative),
                    cross_domain_modulus=cross_q,
                    cross_domain_every_rounds=cross_every,
                    base_floor_label="R0",
                    cross_domain_floor_label=cross_floor,
                )
                states = []
                for s in state_snapshots:
                    dom = self._domain_for_floor(str(s.floor))
                    ih = InformationHeight(
                        current_building_side_depth=int(s.current_building_side_depth),
                        current_building_height=int(s.current_building_height),
                        cross_building_event_count=int(s.cross_building_event_count),
                        cross_domain_reencoding_quotient=int(s.cross_domain_reencoding_quotient),
                    )
                    states.append(DiscreteHighdimensionalInformationSpace_TrackTrajectoryState(
                        floor=str(s.floor),
                        domain=dom,
                        x=int(s.value_x),
                        information_height=ih,
                        tc=int(s.time_counter),
                    ))
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
            "iwt_core (C++ extension) is required for ToyARX.decrypt(). "
            "Build the native module from iwt_research/iwt_core or install with native support."
        )

    def _domain_for_floor(self, floor: str) -> Domain:
        """Domain for a state snapshot by floor label (for C++ ARX trace conversion)."""
        if self.cross_domain and floor == f"Dom{self.cross_domain.q}":
            return self.cross_domain
        return self.domain

    def run(self, x0: int) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        try:
            from ..native import iwt_core, available as _native_available
            if _native_available and iwt_core is not None:
                cross_q = int(self.cross_domain.q) if self.cross_domain else 0
                cross_every = int(self.configuration.cross_every_rounds) if self.cross_domain else 0
                cross_floor = f"Dom{self.cross_domain.q}" if self.cross_domain else "DomQ"
                state_snapshots, event_snapshots = iwt_core.run_toy_arx(
                    initial_value=int(x0),
                    rounds=int(self.configuration.rounds),
                    round_keys=[int(k) for k in self.ks],
                    round_constants=[int(c) for c in self.cs],
                    rotation_amounts=[int(r) for r in self.rs],
                    rotate_left=(self.configuration.rot_dir == "l"),
                    modulus=int(self.domain.modulus),
                    representative=int(self.domain.representative),
                    cross_domain_modulus=cross_q,
                    cross_domain_every_rounds=cross_every,
                    base_floor_label="R0",
                    cross_domain_floor_label=cross_floor,
                )
                states = []
                for snap in state_snapshots:
                    dom = self._domain_for_floor(str(snap.floor))
                    ih = InformationHeight(
                        current_building_side_depth=int(snap.current_building_side_depth),
                        current_building_height=int(snap.current_building_height),
                        cross_building_event_count=int(snap.cross_building_event_count),
                        cross_domain_reencoding_quotient=int(snap.cross_domain_reencoding_quotient),
                    )
                    st = DiscreteHighdimensionalInformationSpace_TrackTrajectoryState(
                        floor=str(snap.floor),
                        domain=dom,
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
            "iwt_core (C++ extension) is required for ToyARX.run(). "
            "Build the native module from iwt_research/iwt_core or install with native support."
        )
