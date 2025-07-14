from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .discrete_domain import Domain


@dataclass(frozen=True, slots=True)
class ArithmeticStepResult:
    boundary_quotient_delta: int
    value_after_reduction: int
    wrap_occurred: bool
    wrap_direction: str
    carry: Optional[int] = None
    borrow: Optional[int] = None


@dataclass(frozen=True, slots=True)
class StructuralStepResult:
    value_after: int
    structure_delta: int


@dataclass(frozen=True, slots=True)
class BitPermutationStepResult:
    value_after: int
    structure_delta: int
    inv_count: int
    inversion_norm: float


@dataclass(frozen=True, slots=True)
class RotationStepResult:
    value_after_preflight: int
    boundary_quotient_delta: int
    wrap_occurred: bool
    wrap_direction: str
    side_depth_increment: int
    rotated_value: int


@dataclass(frozen=True, slots=True)
class CrossDomainStepResult:
    value_after_reduction: int
    boundary_quotient_delta: int
    wrap_occurred: bool
    wrap_direction: str
    cross_domain_reencoding_quotient_after: int
    cross_building_event_count_after: int


def _native_or_raise(native_api_name: str):
    from ..native import available as _native_available, iwt_core

    if _native_available and iwt_core is not None:
        return iwt_core
    raise RuntimeError(
        f"iwt_core (C++ extension) is required for {native_api_name}(). "
        "Build the native module from iwt_research/iwt_core or install with native support."
    )


def _cpp_domain(iwt_core, domain: Domain):
    return iwt_core.Domain(int(domain.modulus), int(domain.representative))


def preflight_reduce(domain: Domain, raw: int) -> tuple[int, int, bool, str]:
    iwt_core = _native_or_raise("preflight_reduce")
    representative_after_reduction, boundary_quotient_delta, wrap_occurred, wrap_direction = iwt_core.preflight_reduce(
        _cpp_domain(iwt_core, domain), int(raw)
    )
    return int(representative_after_reduction), int(boundary_quotient_delta), bool(wrap_occurred), str(wrap_direction)


def add_step(domain: Domain, *, value_before: int, constant: int) -> ArithmeticStepResult:
    iwt_core = _native_or_raise("add_step")
    result = iwt_core.add_step(
        _cpp_domain(iwt_core, domain),
        value_before=int(value_before),
        constant=int(constant),
    )
    return ArithmeticStepResult(
        boundary_quotient_delta=int(result.boundary_quotient_delta),
        value_after_reduction=int(result.value_after_reduction),
        wrap_occurred=bool(result.wrap_occurred),
        wrap_direction=str(result.wrap_direction),
        carry=(int(result.carry) if result.carry is not None else None),
    )


def sub_step(domain: Domain, *, value_before: int, constant: int) -> ArithmeticStepResult:
    iwt_core = _native_or_raise("sub_step")
    result = iwt_core.sub_step(
        _cpp_domain(iwt_core, domain),
        value_before=int(value_before),
        constant=int(constant),
    )
    return ArithmeticStepResult(
        boundary_quotient_delta=int(result.boundary_quotient_delta),
        value_after_reduction=int(result.value_after_reduction),
        wrap_occurred=bool(result.wrap_occurred),
        wrap_direction=str(result.wrap_direction),
        borrow=(int(result.borrow) if result.borrow is not None else None),
    )


def xor_step(domain: Domain, *, value_before: int, constant: int) -> ArithmeticStepResult:
    iwt_core = _native_or_raise("xor_step")
    result = iwt_core.xor_step(
        _cpp_domain(iwt_core, domain),
        value_before=int(value_before),
        constant=int(constant),
    )
    return ArithmeticStepResult(
        boundary_quotient_delta=int(result.boundary_quotient_delta),
        value_after_reduction=int(result.value_after_reduction),
        wrap_occurred=bool(result.wrap_occurred),
        wrap_direction=str(result.wrap_direction),
    )


def sbox_step(domain: Domain, *, value_before: int, substitution_table: list[int]) -> StructuralStepResult:
    iwt_core = _native_or_raise("sbox_step")
    result = iwt_core.sbox_step(
        _cpp_domain(iwt_core, domain),
        int(value_before),
        [int(x) for x in substitution_table],
    )
    return StructuralStepResult(
        value_after=int(result.value_after),
        structure_delta=int(result.structure_delta),
    )


def p_box_values_step(domain: Domain, *, value_before: int, permutation_table: list[int]) -> StructuralStepResult:
    iwt_core = _native_or_raise("p_box_values_step")
    result = iwt_core.p_box_values_step(
        _cpp_domain(iwt_core, domain),
        int(value_before),
        [int(x) for x in permutation_table],
    )
    return StructuralStepResult(
        value_after=int(result.value_after),
        structure_delta=int(result.structure_delta),
    )


def permute_bits_step(
    domain: Domain,
    *,
    value_before: int,
    bit_permutation: list[int],
    word_bits: int,
) -> BitPermutationStepResult:
    iwt_core = _native_or_raise("permute_bits_step")
    permutation_ints = [int(i) for i in bit_permutation]
    iwt_core.validate_bit_permutation(permutation_ints, int(word_bits))
    result = iwt_core.permute_bits_step(
        _cpp_domain(iwt_core, domain),
        int(value_before),
        permutation_ints,
        int(word_bits),
    )
    inv_count = int(iwt_core.inversion_count_permutation(permutation_ints))
    inversion_norm_val = float(iwt_core.inversion_norm(inv_count, int(domain.q)))
    return BitPermutationStepResult(
        value_after=int(result.value_after),
        structure_delta=int(result.structure_delta),
        inv_count=inv_count,
        inversion_norm=inversion_norm_val,
    )


def rotation_left_step(
    domain: Domain,
    *,
    value_before: int,
    current_building_side_depth: int,
    current_building_height: int,
    rotation_amount: int,
    word_bits: int,
) -> RotationStepResult:
    iwt_core = _native_or_raise("rotation_left_step")
    result = iwt_core.rotation_left_step(
        _cpp_domain(iwt_core, domain),
        value_before=int(value_before),
        current_building_side_depth=int(current_building_side_depth),
        current_building_height=int(current_building_height),
        rotation_amount=int(rotation_amount),
        word_bits=int(word_bits),
    )
    return RotationStepResult(
        value_after_preflight=int(result.value_after_preflight),
        boundary_quotient_delta=int(result.boundary_quotient_delta),
        wrap_occurred=bool(result.wrap_occurred),
        wrap_direction=str(result.wrap_direction),
        side_depth_increment=int(result.side_depth_increment),
        rotated_value=int(result.rotated_value),
    )


def rotation_right_step(
    domain: Domain,
    *,
    value_before: int,
    current_building_side_depth: int,
    current_building_height: int,
    rotation_amount: int,
    word_bits: int,
) -> RotationStepResult:
    iwt_core = _native_or_raise("rotation_right_step")
    result = iwt_core.rotation_right_step(
        _cpp_domain(iwt_core, domain),
        value_before=int(value_before),
        current_building_side_depth=int(current_building_side_depth),
        current_building_height=int(current_building_height),
        rotation_amount=int(rotation_amount),
        word_bits=int(word_bits),
    )
    return RotationStepResult(
        value_after_preflight=int(result.value_after_preflight),
        boundary_quotient_delta=int(result.boundary_quotient_delta),
        wrap_occurred=bool(result.wrap_occurred),
        wrap_direction=str(result.wrap_direction),
        side_depth_increment=int(result.side_depth_increment),
        rotated_value=int(result.rotated_value),
    )


def cross_domain_step(
    old_domain: Domain,
    new_domain: Domain,
    *,
    value_before: int,
    cross_domain_reencoding_quotient: int,
    current_cross_building_event_count: int,
    cross_step: int,
) -> CrossDomainStepResult:
    iwt_core = _native_or_raise("cross_domain_step")
    result = iwt_core.cross_domain_step(
        _cpp_domain(iwt_core, old_domain),
        _cpp_domain(iwt_core, new_domain),
        value_before=int(value_before),
        cross_domain_reencoding_quotient=int(cross_domain_reencoding_quotient),
        current_cross_building_event_count=int(current_cross_building_event_count),
        cross_step=int(cross_step),
    )
    return CrossDomainStepResult(
        value_after_reduction=int(result.value_after_reduction),
        boundary_quotient_delta=int(result.boundary_quotient_delta),
        wrap_occurred=bool(result.wrap_occurred),
        wrap_direction=str(result.wrap_direction),
        cross_domain_reencoding_quotient_after=int(result.cross_domain_reencoding_quotient_after),
        cross_building_event_count_after=int(result.cross_building_event_count_after),
    )


__all__ = [
    "ArithmeticStepResult",
    "BitPermutationStepResult",
    "CrossDomainStepResult",
    "RotationStepResult",
    "StructuralStepResult",
    "add_step",
    "cross_domain_step",
    "p_box_values_step",
    "permute_bits_step",
    "preflight_reduce",
    "rotation_left_step",
    "rotation_right_step",
    "sbox_step",
    "sub_step",
    "xor_step",
]
