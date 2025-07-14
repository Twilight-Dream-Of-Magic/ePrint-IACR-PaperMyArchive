from __future__ import annotations

from typing import Any, List, Protocol, Tuple

from ..core.atomic_trace import AtomicEvent
from ..core.enhanced_state import DiscreteHighdimensionalInformationSpace_TrackTrajectoryState


class CipherRunner(Protocol):
    def init_state(self, seed: int) -> Any:
        ...

    def run_from_state(
        self,
        state: Any,
    ) -> Tuple[List[DiscreteHighdimensionalInformationSpace_TrackTrajectoryState], List[AtomicEvent]]:
        ...

    def successor_of_state(self, state: Any) -> Any:
        ...

    def state_to_observation(self, state: Any) -> int | tuple[int, ...]:
        ...

