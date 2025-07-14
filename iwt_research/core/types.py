from __future__ import annotations

from typing import Any, Mapping, Sequence, TypeAlias

StateValue: TypeAlias = int | tuple[int, ...]
ObservationValue: TypeAlias = int | tuple[int, ...]
StateSnapshot: TypeAlias = Mapping[str, Any]
EventSnapshot: TypeAlias = Mapping[str, Any]
StateTrajectory: TypeAlias = Sequence[StateSnapshot]
EventTrajectory: TypeAlias = Sequence[EventSnapshot]

