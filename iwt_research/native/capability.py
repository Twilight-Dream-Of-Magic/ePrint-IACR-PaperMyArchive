from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


REQUIRED_NATIVE_SYMBOLS = (
    "preflight_reduce",
    "add_step",
    "sub_step",
    "xor_step",
    "sbox_step",
    "p_box_values_step",
    "permute_bits_step",
    "rotation_left_step",
    "rotation_right_step",
    "cross_domain_step",
)


@dataclass(frozen=True, slots=True)
class NativeCapability:
    available: bool
    module_name: str | None
    reason: str | None
    symbols: Dict[str, bool]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "available": bool(self.available),
            "module_name": self.module_name,
            "reason": self.reason,
            "symbols": {str(k): bool(v) for k, v in self.symbols.items()},
        }


def build_native_capability(*, iwt_core: Any, available: bool, import_error: Any) -> NativeCapability:
    symbol_map: Dict[str, bool] = {}
    for symbol in REQUIRED_NATIVE_SYMBOLS:
        symbol_map[symbol] = bool(iwt_core is not None and hasattr(iwt_core, symbol))
    module_name = None
    if iwt_core is not None:
        module_name = str(getattr(iwt_core, "__name__", "iwt_core"))
    reason = None
    if not bool(available):
        reason = str(import_error) if import_error is not None else "native_module_unavailable"
    return NativeCapability(
        available=bool(available),
        module_name=module_name,
        reason=reason,
        symbols=symbol_map,
    )

