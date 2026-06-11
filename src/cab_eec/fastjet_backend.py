"""FastJet/fjcontrib backend via heppyyier-style imports."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from .event_io import Event
from .records import ParticleArrays, SplittingRecord


@dataclass
class FastJetBackend:
    fastjet: Any
    fjcontrib: Any
    cppyy: Any

    @classmethod
    def load(cls) -> "FastJetBackend":
        try:
            import heppyyier

            heppyyier.load("fastjet")
            heppyyier.load("fjcontrib")
        except ImportError:
            pass
        try:
            import cppyy
            import fastjet
            import fjcontrib
        except ImportError as exc:
            raise RuntimeError(
                "FastJet backend is unavailable. Install/load heppyyier, cppyy, fastjet, and fjcontrib."
            ) from exc
        return cls(fastjet=fastjet, fjcontrib=fjcontrib, cppyy=cppyy)

    def versions(self) -> dict[str, str]:
        versions = {}
        if hasattr(self.fastjet, "fastjet_version_string"):
            versions["fastjet"] = str(self.fastjet.fastjet_version_string())
        versions["fjcontrib"] = str(getattr(self.fjcontrib, "__version__", "unknown"))
        return versions

    @property
    def pseudojet_vector_type(self):
        return self.cppyy.gbl.std.vector[self.fastjet.PseudoJet]

    def particles_from_event(self, event: Event) -> Any:
        vec = self.pseudojet_vector_type()
        for px, py, pz, energy in zip(event.px, event.py, event.pz, event.energy):
            vec.push_back(self.fastjet.PseudoJet(float(px), float(py), float(pz), float(energy)))
        return vec


class JetSplitter:
    def __init__(self, backend: FastJetBackend, jet_cfg: dict[str, Any], selections: list[dict[str, Any]], sample_name: str):
        self.backend = backend
        self.fastjet = backend.fastjet
        self.fjcontrib = backend.fjcontrib
        self.sample_name = sample_name
        self.R = float(jet_cfg.get("R", jet_cfg.get("jet_R", 0.4)))
        self.pt_min = float(jet_cfg.get("pt_min", 0.0))
        self.pt_max = jet_cfg.get("pt_max")
        self.pt_max = float(self.pt_max) if self.pt_max is not None else None
        self.eta_max = float(jet_cfg.get("eta_max", 2.5))
        self.eta_margin = float(jet_cfg.get("eta_margin", 0.05))
        self.pt_particle_min = float(jet_cfg.get("pt_particle_min", 0.1))
        self.max_jets = jet_cfg.get("max_jets")
        self.max_jets = int(self.max_jets) if self.max_jets is not None else None
        self.selections = selections
        self.jet_def = self.fastjet.JetDefinition(self.fastjet.antikt_algorithm, self.R)
        self.lund_gen = self.fjcontrib.LundGenerator()

    def records_from_event(self, event: Event, start_jet_index: int = 0) -> list[SplittingRecord]:
        particles = self.backend.particles_from_event(event)
        if particles.size() == 0:
            return []
        cs = self.fastjet.ClusterSequence(particles, self.jet_def)
        jets = self.fastjet.sorted_by_pt(cs.inclusive_jets())
        out: list[SplittingRecord] = []
        jet_index = start_jet_index
        for jet in jets:
            if not self._accept_jet(jet):
                continue
            seq = list(self.lund_gen.result(jet))
            for selection in self.selections:
                split = select_lund_splitting(seq, selection)
                if split is None:
                    continue
                record = self._record_from_split(event, jet, jet_index, selection["name"], split)
                if record is not None:
                    out.append(record)
            jet_index += 1
            if self.max_jets is not None and jet_index >= self.max_jets:
                break
        return out

    def _accept_jet(self, jet: Any) -> bool:
        if jet.pt() < self.pt_min:
            return False
        if self.pt_max is not None and jet.pt() >= self.pt_max:
            return False
        return abs(jet.eta()) < self.eta_max - self.eta_margin

    def _record_from_split(self, event: Event, jet: Any, jet_index: int, selection_name: str, split: Any) -> SplittingRecord | None:
        parts_a = particles_from_pseudojets(split.harder().constituents(), self.pt_particle_min)
        parts_b = particles_from_pseudojets(split.softer().constituents(), self.pt_particle_min)
        if len(parts_a) == 0 or len(parts_b) == 0:
            return None
        pt_a = float(np.sum(parts_a.pt))
        pt_b = float(np.sum(parts_b.pt))
        kt = float(split.kt())
        parent_pt = split_parent_pt(split, pt_a, pt_b)
        return SplittingRecord(
            sample=self.sample_name,
            selection=selection_name,
            event_id=event.event_id,
            jet_index=jet_index,
            event_weight=event.weight,
            jet_pt=float(jet.pt()),
            jet_eta=float(jet.eta()),
            jet_phi=float(jet.phi_std() if hasattr(jet, "phi_std") else jet.phi()),
            delta_rg=float(split.Delta()),
            z=float(split.z()),
            kt=kt,
            lnkt=math.log(kt) if kt > 0 else float("nan"),
            pt_a=pt_a,
            pt_b=pt_b,
            parent_pt=parent_pt,
            parts_a=parts_a,
            parts_b=parts_b,
        )


def select_lund_splitting(seq: list[Any], selection: dict[str, Any]) -> Any | None:
    if not seq:
        return None
    mode = selection.get("mode", "max_kt")
    if mode == "max_kt":
        kt_min = float(selection.get("kt_min", 0.0))
        candidates = [split for split in seq if float(split.kt()) > kt_min]
        return max(candidates, key=lambda split: split.kt()) if candidates else None
    if mode == "soft_drop":
        z_cut = float(selection.get("z_cut", selection.get("z", 0.1)))
        for split in seq:
            if float(split.z()) >= z_cut:
                return split
        return None
    raise ValueError(f"unknown selection mode: {mode!r}")


def particles_from_pseudojets(parts: Any, pt_min: float) -> ParticleArrays:
    pts: list[float] = []
    etas: list[float] = []
    phis: list[float] = []
    for part in parts:
        pt = float(part.pt())
        if pt <= pt_min:
            continue
        pts.append(pt)
        etas.append(float(part.eta()))
        phis.append(float(part.phi_std() if hasattr(part, "phi_std") else part.phi()))
    return ParticleArrays(pt=pts, eta=etas, phi=phis)


def split_parent_pt(split: Any, pt_a: float, pt_b: float) -> float | None:
    pair = getattr(split, "pair", None)
    if callable(pair):
        try:
            parent = pair()
            if hasattr(parent, "perp"):
                return float(parent.perp())
            if hasattr(parent, "pt"):
                return float(parent.pt())
        except Exception:
            pass
    return pt_a + pt_b
