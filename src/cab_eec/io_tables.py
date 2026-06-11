"""Parquet serialization helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .eec import EECResult
from .records import ParticleArrays, SplittingRecord


def require_pyarrow():
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("pyarrow is required for parquet outputs") from exc
    return pa, pq


def write_splittings(path: str | Path, records: list[SplittingRecord]) -> None:
    pa, pq = require_pyarrow()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table(
        {
            "sample": [r.sample for r in records],
            "selection": [r.selection for r in records],
            "event_id": [r.event_id for r in records],
            "jet_index": [r.jet_index for r in records],
            "event_weight": [r.event_weight for r in records],
            "jet_pt": [r.jet_pt for r in records],
            "jet_eta": [r.jet_eta for r in records],
            "jet_phi": [r.jet_phi for r in records],
            "delta_rg": [r.delta_rg for r in records],
            "z": [r.z for r in records],
            "kt": [r.kt for r in records],
            "lnkt": [r.lnkt for r in records],
            "pt_a": [r.pt_a for r in records],
            "pt_b": [r.pt_b for r in records],
            "parent_pt": [np.nan if r.parent_pt is None else r.parent_pt for r in records],
            "const_a_pt": [r.parts_a.pt for r in records],
            "const_a_eta": [r.parts_a.eta for r in records],
            "const_a_phi": [r.parts_a.phi for r in records],
            "const_b_pt": [r.parts_b.pt for r in records],
            "const_b_eta": [r.parts_b.eta for r in records],
            "const_b_phi": [r.parts_b.phi for r in records],
        }
    )
    pq.write_table(table, path)


def read_splittings(path: str | Path) -> list[SplittingRecord]:
    pa, pq = require_pyarrow()
    table = pq.read_table(path)
    data = table.to_pydict()
    records = []
    for i in range(table.num_rows):
        records.append(
            SplittingRecord(
                sample=data["sample"][i],
                selection=data["selection"][i],
                event_id=int(data["event_id"][i]),
                jet_index=int(data["jet_index"][i]),
                event_weight=float(data["event_weight"][i]),
                jet_pt=float(data["jet_pt"][i]),
                jet_eta=float(data["jet_eta"][i]),
                jet_phi=float(data["jet_phi"][i]),
                delta_rg=float(data["delta_rg"][i]),
                z=float(data["z"][i]),
                kt=float(data["kt"][i]),
                lnkt=float(data["lnkt"][i]),
                pt_a=float(data["pt_a"][i]),
                pt_b=float(data["pt_b"][i]),
                parent_pt=None if data["parent_pt"][i] is None or np.isnan(data["parent_pt"][i]) else float(data["parent_pt"][i]),
                parts_a=ParticleArrays(data["const_a_pt"][i], data["const_a_eta"][i], data["const_a_phi"][i]),
                parts_b=ParticleArrays(data["const_b_pt"][i], data["const_b_eta"][i], data["const_b_phi"][i]),
            )
        )
    return records


def write_eec_table(path: str | Path, rows: list[dict[str, Any]]) -> None:
    pa, pq = require_pyarrow()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)


def eec_rows(sample: str, selection: str, normalization: str, result: EECResult) -> list[dict[str, Any]]:
    rows = []
    for i, center in enumerate(result.centers):
        row = {
            "sample": sample,
            "selection": selection,
            "normalization": normalization,
            "bin_lo_lndr": float(result.edges[i]),
            "bin_hi_lndr": float(result.edges[i + 1]),
            "bin_center_lndr": float(center),
            "eec_AA": float(result.density["AA"][i]),
            "eec_BB": float(result.density["BB"][i]),
            "eec_AB": float(result.density["AB"][i]),
            "eec_all": float(result.density["all"][i]),
            "eec_AA_err": float(result.error["AA"][i]),
            "eec_BB_err": float(result.error["BB"][i]),
            "eec_AB_err": float(result.error["AB"][i]),
            "eec_all_err": float(result.error["all"][i]),
            "cab_eec": float(result.cab[i]) if np.isfinite(result.cab[i]) else np.nan,
            "cab_eec_err": float(result.cab_error[i]) if np.isfinite(result.cab_error[i]) else np.nan,
            "n_jets": int(result.n_jets),
            "sum_event_weight": float(result.sum_event_weight),
        }
        rows.append(row)
    return rows
