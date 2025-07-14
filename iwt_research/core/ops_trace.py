from __future__ import annotations

from typing import Callable, Optional

from .atomic_trace import AtomicEvent
from .discrete_domain import Domain, delta, is_power_of_two
from .enhanced_state import (
    DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    InformationHeight,
)
from .ops_kernel import (
    add_step,
    cross_domain_step,
    p_box_values_step,
    permute_bits_step,
    preflight_reduce,
    rotation_left_step,
    rotation_right_step,
    sbox_step,
    sub_step,
    xor_step,
)


def _next_information_height(
    information_height: InformationHeight,
    *,
    side_depth_delta: int = 0,
    building_height_delta: int = 0,
) -> InformationHeight:
    return InformationHeight(
        current_building_side_depth=(
            information_height.current_building_side_depth + int(side_depth_delta)
        ),
        current_building_height=(
            information_height.current_building_height + int(building_height_delta)
        ),
        cross_building_event_count=information_height.cross_building_event_count,
        cross_domain_reencoding_quotient=information_height.cross_domain_reencoding_quotient,
        building_exit_snapshots=information_height.building_exit_snapshots,
    )


def add(
    state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    k: int,
    op: str = "add",
) -> tuple[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, AtomicEvent]:
    x0 = int(state.x)
    step = add_step(state.domain, value_before=x0, constant=int(k))
    new_ih = _next_information_height(
        state.information_height,
        building_height_delta=step.boundary_quotient_delta,
    )
    state_after = state.with_updates(
        x=step.value_after_reduction,
        information_height=new_ih,
        tc=state.tc + 1,
    )
    event = AtomicEvent(
        tc=state.tc,
        op=op,
        floor=state.floor,
        q=state.domain.q,
        w=state.domain.w,
        x0=x0,
        x1=step.value_after_reduction,
        raw=x0 + int(k),
        delta=step.boundary_quotient_delta,
        wrap=step.wrap_occurred,
        carry=step.carry,
        meta=(("k", int(k)), ("wrap_dir", step.wrap_direction)),
    )
    return state_after, event


def sub(
    state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    k: int,
    op: str = "sub",
) -> tuple[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, AtomicEvent]:
    x0 = int(state.x)
    step = sub_step(state.domain, value_before=x0, constant=int(k))
    new_ih = _next_information_height(
        state.information_height,
        building_height_delta=step.boundary_quotient_delta,
    )
    state_after = state.with_updates(
        x=step.value_after_reduction,
        information_height=new_ih,
        tc=state.tc + 1,
    )
    event = AtomicEvent(
        tc=state.tc,
        op=op,
        floor=state.floor,
        q=state.domain.q,
        w=state.domain.w,
        x0=x0,
        x1=step.value_after_reduction,
        raw=x0 - int(k),
        delta=step.boundary_quotient_delta,
        wrap=step.wrap_occurred,
        borrow=step.borrow,
        meta=(("k", int(k)), ("wrap_dir", step.wrap_direction)),
    )
    return state_after, event


def xor(
    state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    k: int,
    op: str = "xor",
) -> tuple[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, AtomicEvent]:
    x0 = int(state.x)
    step = xor_step(state.domain, value_before=x0, constant=int(k))
    new_ih = _next_information_height(
        state.information_height,
        building_height_delta=step.boundary_quotient_delta,
    )
    state_after = state.with_updates(
        x=step.value_after_reduction,
        information_height=new_ih,
        tc=state.tc + 1,
    )
    event = AtomicEvent(
        tc=state.tc,
        op=op,
        floor=state.floor,
        q=state.domain.q,
        w=state.domain.w,
        x0=x0,
        x1=step.value_after_reduction,
        raw=x0 ^ int(k),
        delta=step.boundary_quotient_delta,
        wrap=step.wrap_occurred,
        meta=(("k", int(k)), ("wrap_dir", step.wrap_direction)),
    )
    return state_after, event


def substitute_box(
    state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    substitution_table: list[int],
    *,
    op: str = "s_box",
) -> tuple[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, AtomicEvent]:
    domain = state.domain
    if len(substitution_table) != int(domain.q):
        raise ValueError("substitution_table length must equal domain.q")

    x_before = int(state.x)
    index = x_before - int(domain.w)
    if not (0 <= index < int(domain.q)):
        raise ValueError("state.x is not in the representative interval [w, w+q)")

    step = sbox_step(
        domain,
        value_before=x_before,
        substitution_table=substitution_table,
    )
    updated_information_height = _next_information_height(
        state.information_height,
        building_height_delta=step.structure_delta,
    )
    state_after = state.with_updates(
        x=step.value_after,
        information_height=updated_information_height,
        tc=state.tc + 1,
    )
    event = AtomicEvent(
        tc=state.tc,
        op=op,
        floor=state.floor,
        q=domain.q,
        w=domain.w,
        x0=x_before,
        x1=step.value_after,
        raw=step.value_after,
        delta=step.structure_delta,
        wrap=False,
        meta=(
            ("table_size", int(domain.q)),
            ("delta_struct", step.structure_delta),
        ),
    )
    return state_after, event


def permute_values(
    state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    permutation_table: list[int],
    *,
    op: str = "p_box_values",
) -> tuple[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, AtomicEvent]:
    domain = state.domain
    if len(permutation_table) != int(domain.q):
        raise ValueError("permutation_table length must equal domain.q")

    x_before = int(state.x)
    index = x_before - int(domain.w)
    if not (0 <= index < int(domain.q)):
        raise ValueError("state.x is not in the representative interval [w, w+q)")

    step = p_box_values_step(
        domain,
        value_before=x_before,
        permutation_table=permutation_table,
    )
    updated_information_height = _next_information_height(
        state.information_height,
        building_height_delta=step.structure_delta,
    )
    state_after = state.with_updates(
        x=step.value_after,
        information_height=updated_information_height,
        tc=state.tc + 1,
    )
    event = AtomicEvent(
        tc=state.tc,
        op=op,
        floor=state.floor,
        q=domain.q,
        w=domain.w,
        x0=x_before,
        x1=step.value_after,
        raw=step.value_after,
        delta=step.structure_delta,
        wrap=False,
        meta=(
            ("table_size", int(domain.q)),
            ("delta_struct", step.structure_delta),
        ),
    )
    return state_after, event


def permute_bits(
    state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    bit_permutation: list[int],
    *,
    op: str = "p_box_bits",
) -> tuple[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, AtomicEvent]:
    domain = state.domain
    if domain.w != 0:
        raise ValueError("permute_bits requires domain.w=0")
    if not is_power_of_two(int(domain.q)):
        raise ValueError("permute_bits requires power-of-two domain.q")

    word_bits = int(domain.q).bit_length() - 1
    x_before = int(state.x) & (int(domain.q) - 1)
    step = permute_bits_step(
        domain,
        value_before=x_before,
        bit_permutation=bit_permutation,
        word_bits=word_bits,
    )
    updated_information_height = _next_information_height(
        state.information_height,
        building_height_delta=step.structure_delta,
    )
    state_after = state.with_updates(
        x=step.value_after,
        information_height=updated_information_height,
        tc=state.tc + 1,
    )
    event = AtomicEvent(
        tc=state.tc,
        op=op,
        floor=state.floor,
        q=domain.q,
        w=domain.w,
        x0=x_before,
        x1=step.value_after,
        raw=step.value_after,
        delta=step.structure_delta,
        wrap=False,
        meta=(
            ("word_bits", int(word_bits)),
            ("delta_struct", step.structure_delta),
            ("inv_count", step.inv_count),
            ("inversion_norm", step.inversion_norm),
        ),
    )
    return state_after, event


def rotl_bits(
    state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    r: int,
    word_bits: int,
    op: str = "rotl_bits",
) -> tuple[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, AtomicEvent]:
    domain = state.domain
    if not (domain.w == 0 and domain.q == (1 << word_bits)):
        raise ValueError("rotl_bits requires domain q=2^word_bits and w=0")

    x_before = int(state.x) & (int(domain.q) - 1)
    rr = int(r) % int(word_bits)
    information_height = state.information_height
    step = rotation_left_step(
        domain,
        value_before=x_before,
        current_building_side_depth=information_height.current_building_side_depth,
        current_building_height=information_height.current_building_height,
        rotation_amount=rr,
        word_bits=word_bits,
    )
    raw_lift = (
        step.rotated_value - int(domain.q)
        if (rr != 0 and step.rotated_value > x_before)
        else step.rotated_value
    )
    updated_information_height = _next_information_height(
        information_height,
        side_depth_delta=step.side_depth_increment,
        building_height_delta=step.boundary_quotient_delta,
    )
    state_after = state.with_updates(
        x=step.value_after_preflight,
        information_height=updated_information_height,
        tc=state.tc + 1,
    )
    event = AtomicEvent(
        tc=state.tc,
        op=op,
        floor=state.floor,
        q=domain.q,
        w=domain.w,
        x0=x_before,
        x1=step.value_after_preflight,
        raw=raw_lift,
        delta=step.boundary_quotient_delta,
        wrap=step.wrap_occurred,
        meta=(
            ("r", rr),
            ("word_bits", word_bits),
            ("y_rot", step.rotated_value),
            ("lift_policy", "directional_left_boundary"),
            ("wrap_dir", step.wrap_direction),
        ),
    )
    return state_after, event


def rotr_bits(
    state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    r: int,
    word_bits: int,
    op: str = "rotr_bits",
) -> tuple[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, AtomicEvent]:
    domain = state.domain
    if not (domain.w == 0 and domain.q == (1 << word_bits)):
        raise ValueError("rotr_bits requires domain q=2^word_bits and w=0")

    x_before = int(state.x) & (int(domain.q) - 1)
    rr = int(r) % int(word_bits)
    information_height = state.information_height
    step = rotation_right_step(
        domain,
        value_before=x_before,
        current_building_side_depth=information_height.current_building_side_depth,
        current_building_height=information_height.current_building_height,
        rotation_amount=rr,
        word_bits=word_bits,
    )
    raw_lift = (
        step.rotated_value + int(domain.q)
        if (rr != 0 and step.rotated_value < x_before)
        else step.rotated_value
    )
    updated_information_height = _next_information_height(
        information_height,
        side_depth_delta=step.side_depth_increment,
        building_height_delta=step.boundary_quotient_delta,
    )
    state_after = state.with_updates(
        x=step.value_after_preflight,
        information_height=updated_information_height,
        tc=state.tc + 1,
    )
    event = AtomicEvent(
        tc=state.tc,
        op=op,
        floor=state.floor,
        q=domain.q,
        w=domain.w,
        x0=x_before,
        x1=step.value_after_preflight,
        raw=raw_lift,
        delta=step.boundary_quotient_delta,
        wrap=step.wrap_occurred,
        meta=(
            ("r", rr),
            ("word_bits", word_bits),
            ("y_rot", step.rotated_value),
            ("lift_policy", "directional_right_boundary"),
            ("wrap_dir", step.wrap_direction),
        ),
    )
    return state_after, event


def cross_domain(
    state: DiscreteHighdimensionalInformationSpace_TrackTrajectoryState,
    *,
    new_floor: str,
    new_domain: Domain,
    x_map: Optional[Callable[[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], int]] = None,
    op: str = "cross_domain",
    cross_step: int = 0,
) -> tuple[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, AtomicEvent]:
    x0 = state.x
    state = state.stash_in_floor_hist()
    information_height = state.information_height

    if x_map is not None:
        raw = int(x_map(state))
        policy = "custom_x_map"
        x1, boundary_quotient_delta, wrap_occurred, wrap_direction = preflight_reduce(new_domain, raw)
        new_cross_count = information_height.cross_building_event_count + int(cross_step)
        new_quotient = delta(new_domain, raw)
    else:
        step = cross_domain_step(
            state.domain,
            new_domain,
            value_before=int(x0),
            cross_domain_reencoding_quotient=int(information_height.cross_domain_reencoding_quotient),
            current_cross_building_event_count=int(information_height.cross_building_event_count),
            cross_step=int(cross_step),
        )
        x1 = step.value_after_reduction
        boundary_quotient_delta = step.boundary_quotient_delta
        wrap_occurred = step.wrap_occurred
        wrap_direction = step.wrap_direction
        new_cross_count = step.cross_building_event_count_after
        new_quotient = step.cross_domain_reencoding_quotient_after
        raw = x0 + information_height.cross_domain_reencoding_quotient * state.domain.q
        policy = "invertible_reencode"

    new_ih = InformationHeight(
        current_building_side_depth=0,
        current_building_height=0,
        cross_building_event_count=new_cross_count,
        cross_domain_reencoding_quotient=new_quotient,
        building_exit_snapshots=information_height.building_exit_snapshots,
    )
    state_after = DiscreteHighdimensionalInformationSpace_TrackTrajectoryState(
        floor=new_floor,
        domain=new_domain,
        x=x1,
        information_height=new_ih,
        tc=state.tc + 1,
    )
    event = AtomicEvent(
        tc=state.tc,
        op=op,
        floor=f"{state.floor}->{new_floor}",
        q=new_domain.q,
        w=new_domain.w,
        x0=x0,
        x1=x1,
        raw=raw,
        delta=boundary_quotient_delta,
        wrap=wrap_occurred,
        meta=(
            ("old_q", int(state.domain.q)),
            ("new_q", int(new_domain.q)),
            ("new_w", int(new_domain.w)),
            ("wrap_dir", wrap_direction),
            ("policy", policy),
            ("cross_step", int(cross_step)),
        ),
    )
    return state_after, event


cross_floor = cross_domain


__all__ = [
    "add",
    "cross_domain",
    "cross_floor",
    "permute_bits",
    "permute_values",
    "rotl_bits",
    "rotr_bits",
    "sub",
    "substitute_box",
    "xor",
]
