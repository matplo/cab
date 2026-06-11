"""Analysis record structures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParticleArrays:
    pt: list[float]
    eta: list[float]
    phi: list[float]

    def __len__(self) -> int:
        return len(self.pt)


@dataclass(frozen=True)
class SplittingRecord:
    sample: str
    selection: str
    event_id: int
    jet_index: int
    event_weight: float
    jet_pt: float
    jet_eta: float
    jet_phi: float
    delta_rg: float
    z: float
    kt: float
    lnkt: float
    pt_a: float
    pt_b: float
    parent_pt: float | None
    parts_a: ParticleArrays
    parts_b: ParticleArrays
