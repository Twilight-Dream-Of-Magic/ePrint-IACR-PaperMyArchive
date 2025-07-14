"""
Toy PRG / stream cipher: expansion via mode-of-operation over existing block ciphers.

Counter mode:  keystream[i] = E_k(IV + i mod q)
OFB mode:      s_0 = IV,  s_{i+1} = E_k(s_i),  keystream[i] = s_i

The "expansion" semantics: small seed (key + IV) -> long keystream.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Tuple

from ..ciphers.runner_factory import build_toy_cipher_from_config


@dataclass(frozen=True, slots=True)
class ToyPRGConfig:
    cipher_preset: str = "toy_spn"
    word_bits: int = 8
    rounds: int = 4
    cipher_seed: int = 0
    lane_count: int = 4
    initial_value: int = 0
    mode: str = "counter"
    output_length: int = 256

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _build_cipher(prg_config: ToyPRGConfig) -> Any:
    block_cipher_config_dict: Dict[str, Any] = {
        "cipher_preset": prg_config.cipher_preset,
        "word_bits": prg_config.word_bits,
        "rounds": prg_config.rounds,
        "cipher_seed": prg_config.cipher_seed,
        "lane_count": prg_config.lane_count,
    }
    return build_toy_cipher_from_config(block_cipher_config_dict)


def _state_modulus(cipher: Any) -> int:
    """Determine the state-space size (modulus) or modulus^n for vector ciphers."""
    cipher_config = getattr(cipher, "configuration", None)
    if cipher_config is None:
        raise TypeError("unsupported cipher config interface: need .configuration")
    state_space_modulus = 1 << int(cipher_config.word_bits)
    lane_count = getattr(cipher_config, "lane_count", None)
    if lane_count and int(lane_count) > 1:
        return state_space_modulus ** int(lane_count)
    return state_space_modulus


def _snapshots_to_states_events(state_snapshots: Any, event_snapshots: Any, domain: Any) -> Tuple[List[Any], List[Any]]:
    """Convert C++ state/event snapshots to Python State and AtomicEvent lists."""
    from ..core.enhanced_state import DiscreteHighdimensionalInformationSpace_TrackTrajectoryState, InformationHeight
    from ..core.atomic_trace import AtomicEvent
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


def generate_keystream(
    prg_config: ToyPRGConfig,
    *,
    collect_internal_traces: bool = False,
) -> Tuple[List[int], Dict[str, Any]]:
    """
    Generate a keystream of length prg_config.output_length.

    Returns (keystream, metadata) where keystream is a list of integer values
    and metadata contains configuration and the mode used.

    If collect_internal_traces=True, metadata["internal_traces"] will contain
    a list of (states, events) pairs — one per keystream block — for winding
    trajectory analysis.
    """
    cipher = _build_cipher(prg_config)
    state_space_modulus = _state_modulus(cipher)
    initial_value = int(prg_config.initial_value) % state_space_modulus
    output_length = int(prg_config.output_length)
    keystream_mode = str(prg_config.mode).strip().lower()

    from ..ciphers.toy_spn import ToySubstitutionPermutationNetwork
    from ..ciphers.toy_arx_cipher import ToyARX
    is_scalar_spn = (
        isinstance(cipher, ToySubstitutionPermutationNetwork)
        and getattr(cipher.configuration, "lane_count", 1) <= 1
    )
    is_arx = isinstance(cipher, ToyARX)

    try:
        from ..native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None and is_scalar_spn:
            state_space_modulus = int(cipher.domain.q)
            keystream_cpp, traces_cpp = iwt_core.generate_keystream_spn(
                keystream_mode,
                initial_value,
                output_length,
                collect_internal_traces,
                int(cipher.configuration.rounds),
                [int(k) for k in cipher.round_keys],
                [int(s) for s in cipher.substitution_table],
                [int(p) for p in cipher.bit_permutation],
                int(cipher.domain.modulus),
                int(cipher.domain.representative),
                "R0",
            )
            keystream = [int(x) for x in keystream_cpp]
            internal_traces = []
            if collect_internal_traces and traces_cpp:
                for state_snapshots, event_snapshots in traces_cpp:
                    states, events = _snapshots_to_states_events(
                        state_snapshots, event_snapshots, cipher.domain
                    )
                    internal_traces.append((states, events))
            metadata = {
                "config": prg_config.as_dict(),
                "state_space_size": int(state_space_modulus),
                "mode": keystream_mode,
                "output_length": len(keystream),
            }
            if collect_internal_traces:
                metadata["internal_traces"] = internal_traces
            return keystream, metadata
    except Exception:
        pass

    try:
        from ..native import iwt_core, available as _native_available
        if _native_available and iwt_core is not None and is_arx:
            cross_domain = getattr(cipher, "cross_domain", None)
            cross_modulus = int(cross_domain.modulus) if cross_domain else 0
            cross_every = int(getattr(cipher.configuration, "cross_every_rounds", 0) or 0)
            rot_dir = str(getattr(cipher.configuration, "rot_dir", "l")).strip().lower()
            rotate_left = rot_dir != "r"
            state_space_modulus = int(cipher.domain.q)
            keystream_cpp, traces_cpp = iwt_core.generate_keystream_arx(
                keystream_mode,
                initial_value,
                output_length,
                collect_internal_traces,
                int(cipher.configuration.rounds),
                [int(k) for k in cipher.ks],
                [int(c) for c in cipher.cs],
                [int(r) for r in cipher.rs],
                rotate_left,
                int(cipher.domain.modulus),
                int(cipher.domain.representative),
                cross_modulus,
                cross_every,
                "R0",
                "DomQ",
            )
            keystream = [int(x) for x in keystream_cpp]
            internal_traces = []
            if collect_internal_traces and traces_cpp:
                for state_snapshots, event_snapshots in traces_cpp:
                    states, events = _snapshots_to_states_events(
                        state_snapshots, event_snapshots, cipher.domain
                    )
                    internal_traces.append((states, events))
            metadata = {
                "config": prg_config.as_dict(),
                "state_space_size": int(state_space_modulus),
                "mode": keystream_mode,
                "output_length": len(keystream),
            }
            if collect_internal_traces:
                metadata["internal_traces"] = internal_traces
            return keystream, metadata
    except Exception:
        pass

    if is_scalar_spn:
        raise RuntimeError(
            "iwt_core (C++ extension) is required for scalar SPN keystream generation. "
            "Build the native module from iwt_research/iwt_core or install with native support."
        )
    if is_arx:
        raise RuntimeError(
            "iwt_core (C++ extension) is required for ARX keystream generation. "
            "Build the native module from iwt_research/iwt_core or install with native support."
        )

    keystream: List[int] = []
    internal_traces: List[Tuple[List[Any], List[Any]]] = []

    if keystream_mode == "counter":
        for index in range(output_length):
            initial_state_value = (initial_value + index) % state_space_modulus
            states, events = cipher.run(int(initial_state_value))
            keystream.append(int(states[-1].x))
            if collect_internal_traces:
                internal_traces.append((states, events))
    elif keystream_mode == "ofb":
        current_state = initial_value
        for _ in range(output_length):
            states, events = cipher.run(int(current_state))
            output = int(states[-1].x)
            keystream.append(output)
            current_state = output
            if collect_internal_traces:
                internal_traces.append((states, events))
    else:
        raise ValueError(f"unknown PRG mode: {keystream_mode!r} (expected 'counter' or 'ofb')")

    metadata: Dict[str, Any] = {
        "config": prg_config.as_dict(),
        "state_space_size": int(state_space_modulus),
        "mode": keystream_mode,
        "output_length": len(keystream),
    }
    if collect_internal_traces:
        metadata["internal_traces"] = internal_traces

    return keystream, metadata


def generate_keystream_from_seed(
    prg_config: ToyPRGConfig, seed_override: int
) -> List[int]:
    """Generate keystream with a different cipher seed (for seed-sensitivity analysis)."""
    from dataclasses import replace
    prg_config_with_seed_override = replace(prg_config, cipher_seed=int(seed_override))
    keystream, _ = generate_keystream(prg_config_with_seed_override)
    return keystream
