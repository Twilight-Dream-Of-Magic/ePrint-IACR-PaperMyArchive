from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Tuple

from .discrete_domain import Domain


@dataclass(frozen=True, slots=True)
class InFloorHistRecord:
    """
    Snapshot of in-building height when leaving a building (floor/domain).

    When crossing domain, we reset current_building_height in the new domain
    but store this snapshot for the old domain (identified by (floor, q, w)).
    """

    floor: str
    q: int
    w: int
    tc: int
    x: int
    building_height_at_exit: int
    state_value_encoding: str = "scalar"
    lane_count: int = 1


def _upsert_last_in_hist(
    hist: Tuple[InFloorHistRecord, ...],
    rec: InFloorHistRecord,
) -> Tuple[InFloorHistRecord, ...]:
    out = [r for r in hist if (r.floor, r.q, r.w) != (rec.floor, rec.q, rec.w)]
    out.append(rec)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class InformationHeight:
    """
    Information height as a single struct: in-building + cross-building.

    - current_building_side_depth cumulative side depth within current building and same floor (当前楼内, 同层累计)
    - current_building_height: cumulative height within current building and different floor (当前楼内, 异层累计)
    - cross_building_event_count: cross-building event count (enc +1, dec -1)
    - cross_domain_reencoding_quotient: quotient for invertible cross-domain re-encoding
    - building_exit_snapshots: per-building snapshots of height when leaving
    """

    current_building_side_depth : int = 0
    current_building_height: int = 0
    cross_building_event_count: int = 0
    cross_domain_reencoding_quotient: int = 0
    building_exit_snapshots: Tuple[InFloorHistRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class DiscreteHighdimensionalInformationSpace_TrackTrajectoryState:
    """
    Minimal Track Trajectory State for Information Winding Theory toy engineering in the Discrete High-dimensional Space.

    - floor: representation/building label (跨楼=跨表示/跨域)
    - x: value-layer state (single component for toy)
    - information_height: struct holding current_building_height, cross_building_event_count,
      cross_domain_reencoding_quotient, building_exit_snapshots
    - tc: time counter
    """

    floor: str
    domain: Domain
    x: int
    information_height: InformationHeight = field(default_factory=InformationHeight)
    tc: int = 0

    def with_updates(self, **kwargs: Any) -> "DiscreteHighdimensionalInformationSpace_TrackTrajectoryState":
        return replace(self, **kwargs)

    @property
    def same_building_floor(self) -> str:
        """
        Backward-compatible alias for older naming.
        """
        return self.floor

    def _value_x_snapshot_for_history(self) -> tuple[int, str, int]:
        x = self.x
        if isinstance(x, (tuple, list)):
            modulus_q = int(self.domain.q)
            packed = 0
            factor = 1
            for lane_value in x:
                packed += (int(lane_value) % modulus_q) * factor
                factor *= modulus_q
            return int(packed), "base_q_lanes", int(len(x))
        return int(x), "scalar", 1

    def stash_in_floor_hist(self) -> "DiscreteHighdimensionalInformationSpace_TrackTrajectoryState":
        ih = self.information_height
        snapshot_x, snapshot_encoding, lane_count = self._value_x_snapshot_for_history()
        rec = InFloorHistRecord(
            floor=self.floor,
            q=self.domain.q,
            w=self.domain.w,
            tc=int(self.tc),
            x=snapshot_x,
            state_value_encoding=str(snapshot_encoding),
            lane_count=int(lane_count),
            building_height_at_exit=int(ih.current_building_height),
        )
        new_ih = InformationHeight(
            current_building_side_depth=ih.current_building_side_depth,
            current_building_height=ih.current_building_height,
            cross_building_event_count=ih.cross_building_event_count,
            cross_domain_reencoding_quotient=ih.cross_domain_reencoding_quotient,
            building_exit_snapshots=_upsert_last_in_hist(ih.building_exit_snapshots, rec),
        )
        return self.with_updates(information_height=new_ih)

    def as_dict(self) -> Dict[str, Any]:
        x = self.x
        value_x: Any
        if isinstance(x, (tuple, list)):
            value_x = [int(v) for v in x]
        else:
            value_x = int(x)
        ih = self.information_height
        return {
            "building_label": self.floor,
            "same_building_floor_label": self.floor,
            "modulus_q": self.domain.q,
            "representative_w": self.domain.w,
            "value_x": value_x,
            "current_building_side_depth": int(ih.current_building_side_depth),
            "current_building_height": int(ih.current_building_height),
            "cross_building_event_count": int(ih.cross_building_event_count),
            "cross_domain_reencoding_quotient": int(ih.cross_domain_reencoding_quotient),
            "time_counter": int(self.tc),
            "building_exit_snapshots": [
                {
                    "building_label": r.floor,
                    "same_building_floor_label": r.floor,
                    "modulus_q": r.q,
                    "representative_w": r.w,
                    "time_counter": r.tc,
                    "value_x": r.x,
                    "state_value_encoding": str(r.state_value_encoding),
                    "lane_count": int(r.lane_count),
                    "building_height_at_exit": r.building_height_at_exit,
                }
                for r in ih.building_exit_snapshots
            ],
            "in_building_information_height": int(ih.current_building_height),
            "cross_domain_event_counter": int(ih.cross_building_event_count),
            "in_building_history": [
                {
                    "building_label": r.floor,
                    "same_building_floor_label": r.floor,
                    "modulus_q": r.q,
                    "representative_w": r.w,
                    "time_counter": r.tc,
                    "value_x": r.x,
                    "state_value_encoding": str(r.state_value_encoding),
                    "lane_count": int(r.lane_count),
                    "in_building_information_height": r.building_height_at_exit,
                }
                for r in ih.building_exit_snapshots
            ],
        }

    def as_public_dict(self) -> Dict[str, Any]:
        x = self.x
        value_x: Any
        if isinstance(x, (tuple, list)):
            value_x = [int(v) for v in x]
        else:
            value_x = int(x)
        ih = self.information_height
        return {
            "building_label": self.floor,
            "same_building_floor_label": self.floor,
            "domain": {"modulus_q": int(self.domain.q), "representative_w": int(self.domain.w)},
            "value_x": value_x,
            "current_building_side_depth": int(ih.current_building_side_depth),
            "current_building_height": int(ih.current_building_height),
            "cross_building_event_count": int(ih.cross_building_event_count),
            "cross_domain_reencoding_quotient": int(ih.cross_domain_reencoding_quotient),
            "time_counter": int(self.tc),
            "building_exit_snapshots": [
                {
                    "building_label": r.floor,
                    "domain": {"modulus_q": int(r.q), "representative_w": int(r.w)},
                    "time_counter": int(r.tc),
                    "value_x": int(r.x),
                    "state_value_encoding": str(r.state_value_encoding),
                    "lane_count": int(r.lane_count),
                    "building_height_at_exit": int(r.building_height_at_exit),
                }
                for r in ih.building_exit_snapshots
            ],
            "in_building_information_height": int(ih.current_building_height),
            "cross_domain_event_counter": int(ih.cross_building_event_count),
            "cross_domain_reencoding_quotient": int(ih.cross_domain_reencoding_quotient),
            "in_building_history": [
                {
                    "building_label": r.floor,
                    "domain": {"modulus_q": int(r.q), "representative_w": int(r.w)},
                    "time_counter": int(r.tc),
                    "value_x": int(r.x),
                    "state_value_encoding": str(r.state_value_encoding),
                    "lane_count": int(r.lane_count),
                    "in_building_information_height": int(r.building_height_at_exit),
                }
                for r in ih.building_exit_snapshots
            ],
        }
