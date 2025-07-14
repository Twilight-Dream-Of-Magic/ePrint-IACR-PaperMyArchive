from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True, slots=True)
class AtomicEvent:
    """
    One atomic step trace record (mechanism-side annotation).

    Notes:
    - wrap is defined at the integer-lift layer: Delta(raw) != 0.
    - delta is the per-step increment applied to information_height.current_building_height in the toy.
      For add/sub/xor/lifted operations this matches Delta(raw); for S-box / P-box style steps it may be
      a structural, policy-defined increment even when wrap=False.
    - carry/borrow are included for 2^w modular add/sub only (when q is power-of-two).
    """

    tc: int
    op: str
    # floor here is a representation label, not a literal "floor inside one building".
    floor: str
    q: int
    w: int
    x0: int
    x1: int
    raw: int
    delta: int
    wrap: bool
    carry: Optional[int] = None
    borrow: Optional[int] = None
    meta: Tuple[Tuple[str, Any], ...] = ()

    def meta_dict(self) -> Dict[str, Any]:
        return dict(self.meta)

