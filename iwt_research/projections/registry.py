from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .projections import parse_projection


@dataclass(frozen=True, slots=True)
class ProjectionRegistration:
    projection_spec: str

    def as_dict(self) -> Dict[str, Any]:
        return {"projection_spec": str(self.projection_spec)}


def parse_projection_set(
    *,
    primary_projection: str,
    additional_projection_specs_csv: str | None,
    word_bits: int,
) -> List[Tuple[str, Any]]:
    """
    Register a primary projection and optional additional projections.
    additional_projection_specs_csv: comma-separated projection specs.
    """
    specs: List[str] = [str(primary_projection)]
    if additional_projection_specs_csv:
        for part in str(additional_projection_specs_csv).split(","):
            spec = part.strip()
            if spec:
                specs.append(spec)

    # Deduplicate while preserving order.
    unique_specs: List[str] = []
    seen: set[str] = set()
    for spec in specs:
        normalized = spec.strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_specs.append(normalized)

    projections: List[Tuple[str, Any]] = []
    for spec in unique_specs:
        _, projection = parse_projection(spec, word_bits=int(word_bits))
        projections.append((spec, projection))
    return projections

