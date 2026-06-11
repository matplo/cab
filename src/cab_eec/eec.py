"""EEC and CAB accumulation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from .records import ParticleArrays, SplittingRecord


PAIR_KEYS = ("AA", "BB", "AB", "all")


@dataclass
class EECResult:
    centers: np.ndarray
    edges: np.ndarray
    density: dict[str, np.ndarray]
    error: dict[str, np.ndarray]
    cab: np.ndarray
    cab_error: np.ndarray
    n_jets: int
    sum_event_weight: float


class EECAccumulator:
    """Binned EEC with AA/BB/AB/all decomposition and per-jet SEM errors."""

    def __init__(self, edges: Iterable[float]):
        self.edges = np.asarray(list(edges), dtype=float)
        if self.edges.ndim != 1 or len(self.edges) < 2:
            raise ValueError("edges must be a 1D array with at least two entries")
        nbins = len(self.edges) - 1
        self.h = {key: np.zeros(nbins, dtype=float) for key in PAIR_KEYS}
        self.h2 = {key: np.zeros(nbins, dtype=float) for key in PAIR_KEYS}
        self.n_jets = 0
        self.sum_event_weight = 0.0

    def fill_record(self, record: SplittingRecord, normalization: str) -> None:
        denominators = denominators_for(record, normalization)
        self.fill(record.parts_a, record.parts_b, denominators, event_weight=record.event_weight)

    def fill(
        self,
        parts_a: ParticleArrays,
        parts_b: ParticleArrays,
        denominators: dict[str, float],
        event_weight: float = 1.0,
    ) -> None:
        nbins = len(self.edges) - 1
        buf = {key: np.zeros(nbins, dtype=float) for key in PAIR_KEYS}
        self._accum_same(buf, "AA", parts_a, denominators["AA"])
        self._accum_same(buf, "BB", parts_b, denominators["BB"])
        self._accum_cross(buf, parts_a, parts_b, denominators["AB"])
        for key in PAIR_KEYS:
            weighted = buf[key] * event_weight
            self.h[key] += weighted
            self.h2[key] += weighted**2
        self.n_jets += 1
        self.sum_event_weight += event_weight

    def _accum_same(self, buf: dict[str, np.ndarray], key: str, parts: ParticleArrays, denom: float) -> None:
        if denom <= 0 or len(parts) < 2:
            return
        pt = np.asarray(parts.pt, dtype=float)
        eta = np.asarray(parts.eta, dtype=float)
        phi = np.asarray(parts.phi, dtype=float)
        deta = eta[:, None] - eta[None, :]
        dphi = wrap_delta_phi(phi[:, None] - phi[None, :])
        dr = np.hypot(deta, dphi)
        weights = (pt[:, None] * pt[None, :]) / denom
        mask = ~np.eye(len(pt), dtype=bool)
        self._add_pairs(buf, key, dr[mask], weights[mask])

    def _accum_cross(
        self,
        buf: dict[str, np.ndarray],
        parts_a: ParticleArrays,
        parts_b: ParticleArrays,
        denom: float,
    ) -> None:
        if denom <= 0 or len(parts_a) == 0 or len(parts_b) == 0:
            return
        pt_a = np.asarray(parts_a.pt, dtype=float)
        eta_a = np.asarray(parts_a.eta, dtype=float)
        phi_a = np.asarray(parts_a.phi, dtype=float)
        pt_b = np.asarray(parts_b.pt, dtype=float)
        eta_b = np.asarray(parts_b.eta, dtype=float)
        phi_b = np.asarray(parts_b.phi, dtype=float)
        deta = eta_a[:, None] - eta_b[None, :]
        dphi = wrap_delta_phi(phi_a[:, None] - phi_b[None, :])
        dr = np.hypot(deta, dphi).ravel()
        weights = (2.0 * pt_a[:, None] * pt_b[None, :] / denom).ravel()
        self._add_pairs(buf, "AB", dr, weights)

    def _add_pairs(self, buf: dict[str, np.ndarray], key: str, dr: np.ndarray, weights: np.ndarray) -> None:
        valid_dr = dr > 0
        if not np.any(valid_dr):
            return
        idx = np.searchsorted(self.edges, np.log(dr[valid_dr]), side="right") - 1
        w = weights[valid_dr]
        valid = (idx >= 0) & (idx < len(buf[key]))
        if not np.any(valid):
            return
        np.add.at(buf[key], idx[valid], w[valid])
        np.add.at(buf["all"], idx[valid], w[valid])

    def result(self) -> EECResult:
        centers = 0.5 * (self.edges[:-1] + self.edges[1:])
        widths = np.exp(self.edges[1:]) - np.exp(self.edges[:-1])
        density = {}
        error = {}
        for key in PAIR_KEYS:
            if self.n_jets == 0:
                mean = np.zeros_like(centers)
                sem = np.zeros_like(centers)
            else:
                mean = self.h[key] / self.n_jets
                var = np.maximum(self.h2[key] / self.n_jets - mean**2, 0.0)
                sem = np.sqrt(var / self.n_jets)
            density[key] = mean / widths
            error[key] = sem / widths
        cab, cab_error = cab_from_components(density, error)
        return EECResult(
            centers=centers,
            edges=self.edges.copy(),
            density=density,
            error=error,
            cab=cab,
            cab_error=cab_error,
            n_jets=self.n_jets,
            sum_event_weight=self.sum_event_weight,
        )


def wrap_delta_phi(dphi: np.ndarray) -> np.ndarray:
    return (dphi + math.pi) % (2.0 * math.pi) - math.pi


def denominators_for(record: SplittingRecord, normalization: str) -> dict[str, float]:
    if normalization == "jet_pt2":
        den = record.jet_pt**2
        return {"AA": den, "BB": den, "AB": den}
    if normalization == "radiator_pt2":
        pt = record.parent_pt if record.parent_pt is not None else record.pt_a + record.pt_b
        den = pt**2
        return {"AA": den, "BB": den, "AB": den}
    if normalization == "radiator_scalar_sum_pt2":
        den = (record.pt_a + record.pt_b) ** 2
        return {"AA": den, "BB": den, "AB": den}
    if normalization == "parent_pt2":
        pt = record.parent_pt if record.parent_pt is not None else record.pt_a + record.pt_b
        den = pt**2
        return {"AA": den, "BB": den, "AB": den}
    if normalization == "per_prong":
        return {"AA": record.pt_a**2, "BB": record.pt_b**2, "AB": record.pt_a * record.pt_b}
    raise ValueError(f"unknown EEC normalization: {normalization!r}")


def cab_from_components(
    density: dict[str, np.ndarray],
    error: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    aa = density["AA"]
    bb = density["BB"]
    ab = density["AB"]
    saa = error["AA"]
    sbb = error["BB"]
    sab = error["AB"]
    denom = np.sqrt(np.maximum(aa * bb, 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        cab = np.where(denom > 0, ab / denom, np.nan)
        rel_ab = np.where(ab > 0, sab / ab, 0.0)
        rel_aa = np.where(aa > 0, saa / aa, 0.0)
        rel_bb = np.where(bb > 0, sbb / bb, 0.0)
        cab_error = np.abs(cab) * np.sqrt(rel_ab**2 + 0.25 * rel_aa**2 + 0.25 * rel_bb**2)
    return cab, cab_error


def eec_edges(lndr_min: float, lndr_max: float, nbins: int) -> np.ndarray:
    return np.linspace(float(lndr_min), float(lndr_max), int(nbins) + 1)
