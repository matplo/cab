"""Top-level cacheable analysis pipeline."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from . import __version__
from .cache import cache_path, eec_key, event_index_key, input_identity, jet_splittings_key
from .cleanup import remove_directory
from .eec import EECAccumulator, eec_edges
from .event_io import UprootEventSource
from .fastjet_backend import FastJetBackend, JetSplitter
from .io_tables import eec_rows, read_splittings, write_eec_table, write_splittings
from .progress import progress


def run(config: dict[str, Any], recompute: str | None = None, clean: bool = False) -> dict[str, Any]:
    output_dir = Path(config["output_dir"])
    cache_dir = Path(config["cache_dir"])
    if clean:
        remove_directory(output_dir, "output_dir")
        if recompute is None:
            recompute = "all"
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    backend = FastJetBackend.load()
    backend_versions = backend.versions()
    metadata: dict[str, Any] = {
        "cab_eec_version": __version__,
        "backend_versions": backend_versions,
        "samples": {},
        "outputs": {},
    }
    all_eec_rows: list[dict[str, Any]] = []

    for sample in config["samples"]:
        sample_name = sample["name"]
        event_key = event_index_key(sample, config["input"])
        event_cache = cache_path(cache_dir, "event_index", sample_name, event_key, "json")
        if event_cache.exists() and recompute not in ("all", "event_index"):
            print(f"[cache hit] event_index {sample_name}: {event_cache}")
            event_index = json.loads(event_cache.read_text(encoding="utf-8"))
        else:
            print(f"[compute] event_index {sample_name}")
            event_index = build_event_index(sample, config["input"])
            event_cache.write_text(json.dumps(event_index, indent=2, sort_keys=True), encoding="utf-8")
            print(f"[cache save] event_index {sample_name}: {event_cache}")

        split_key = jet_splittings_key(sample, config["input"], config["jet"], config["selections"], backend_versions)
        split_cache = cache_path(cache_dir, "jet_splittings", sample_name, split_key, "parquet")
        metadata["samples"][sample_name] = {
            "event_index_key": event_key,
            "event_index_cache": str(event_cache),
            "event_index": event_index,
            "splittings_key": split_key,
        }

        if split_cache.exists() and recompute not in ("all", "jet_splittings"):
            print(f"[cache hit] splittings {sample_name}: {split_cache}")
            records = read_splittings(split_cache)
        else:
            print(f"[compute] splittings {sample_name}")
            records = compute_splittings(sample, config, backend, event_index=event_index)
            write_splittings(split_cache, records)
            print(f"[cache save] splittings {sample_name}: {split_cache}")

        sample_split_out = output_dir / f"{sample_name}__splittings.parquet"
        write_splittings(sample_split_out, records)
        metadata["outputs"].setdefault(sample_name, {})["splittings"] = str(sample_split_out)

        for normalization in config["eec"].get("normalizations", ["jet_pt2"]):
            key = eec_key(split_key, config["eec"], normalization)
            eec_cache = cache_path(cache_dir, "eec_tables", sample_name, key, "parquet")
            if eec_cache.exists() and recompute not in ("all", "eec_tables", "jet_splittings"):
                print(f"[cache hit] eec {sample_name} {normalization}: {eec_cache}")
                all_eec_rows.extend(_read_eec_rows(eec_cache))
            else:
                print(f"[compute] eec {sample_name} {normalization}")
                rows = compute_eec_rows(sample_name, records, config["eec"], normalization)
                write_eec_table(eec_cache, rows)
                print(f"[cache save] eec {sample_name} {normalization}: {eec_cache}")
                all_eec_rows.extend(rows)
            metadata["samples"][sample_name].setdefault("eec_keys", {})[normalization] = key

    eec_out = output_dir / "eec.parquet"
    write_eec_table(eec_out, all_eec_rows)
    metadata["outputs"]["eec"] = str(eec_out)

    meta_out = output_dir / "metadata.json"
    meta_out.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    metadata["metadata_path"] = str(meta_out)
    return metadata


def compute_splittings(
    sample: dict[str, Any],
    config: dict[str, Any],
    backend: FastJetBackend,
    event_index: dict[str, Any] | None = None,
):
    source = UprootEventSource(
        sample["files"],
        tree=config["input"].get("tree", "tracks"),
        branches=config["input"].get("branches"),
        batch_entries=config["input"].get("batch_entries", 250_000),
        max_events=config["jet"].get("max_events"),
    )
    splitter = JetSplitter(backend, config["jet"], config["selections"], sample["name"])
    records = []
    total_events = _event_total(event_index, config["jet"].get("max_events"))
    for event in progress(source, total=total_events, desc=f"{sample['name']} events", unit="event"):
        records.extend(splitter.records_from_event(event))
        max_jets = config["jet"].get("max_jets")
        if max_jets is not None and len({(r.event_id, r.jet_index) for r in records}) >= int(max_jets):
            break
    return records


def build_event_index(sample: dict[str, Any], input_cfg: dict[str, Any]) -> dict[str, Any]:
    try:
        import uproot
    except ImportError as exc:
        raise RuntimeError("uproot is required to build the event index cache") from exc

    tree_name = input_cfg.get("tree", "tracks")
    branches = input_cfg.get("branches") or {}
    branch_names = list(branches.values()) if branches else ["eventID", "px", "py", "pz", "energy"]
    files = []
    file_infos = input_identity(sample, input_cfg)["files"]
    for file_info in progress(file_infos, desc=f"{sample['name']} index", unit="file"):
        path = file_info["path"]
        with uproot.open(path) as root_file:
            tree = root_file[tree_name]
            available = set(tree.keys())
            missing = [branch for branch in branch_names if branch not in available]
            files.append(
                {
                    **file_info,
                    "tree": tree_name,
                    "num_entries": int(tree.num_entries),
                    "missing_branches": missing,
                }
            )
    return {"sample": sample["name"], "tree": tree_name, "branches": branches, "files": files}


def compute_eec_rows(sample_name: str, records: list, eec_cfg: dict[str, Any], normalization: str) -> list[dict[str, Any]]:
    edges = eec_edges(eec_cfg.get("lndr_min", -5.0), eec_cfg.get("lndr_max", 1.5), eec_cfg.get("nbins", 60))
    by_selection = defaultdict(lambda: EECAccumulator(edges))
    for record in progress(records, desc=f"{sample_name} EEC {normalization}", unit="split"):
        by_selection[record.selection].fill_record(record, normalization)
    rows = []
    for selection, accum in sorted(by_selection.items()):
        rows.extend(eec_rows(sample_name, selection, normalization, accum.result()))
    return rows


def _event_total(event_index: dict[str, Any] | None, max_events: int | None) -> int | None:
    if not event_index:
        return max_events
    # The event index stores track entries, not unique event count. It still gives
    # tqdm a useful finite scale for file sizes only if max_events is unavailable.
    if max_events is not None:
        return int(max_events)
    return None


def inspect_cache(config: dict[str, Any]) -> dict[str, Any]:
    try:
        backend_versions = FastJetBackend.load().versions()
    except RuntimeError:
        backend_versions = {}
    report = {"cache_dir": config["cache_dir"], "samples": {}}
    for sample in config["samples"]:
        sample_name = sample["name"]
        event_key = event_index_key(sample, config["input"])
        event_cache = cache_path(config["cache_dir"], "event_index", sample_name, event_key, "json")
        split_key = jet_splittings_key(sample, config["input"], config["jet"], config["selections"], backend_versions)
        split_cache = cache_path(config["cache_dir"], "jet_splittings", sample_name, split_key, "parquet")
        report["samples"][sample_name] = {
            "event_index_key": event_key,
            "event_index_cache": str(event_cache),
            "event_index_exists": event_cache.exists(),
            "splittings_key": split_key,
            "splittings_cache": str(split_cache),
            "splittings_exists": split_cache.exists(),
            "eec": {},
        }
        for normalization in config["eec"].get("normalizations", ["jet_pt2"]):
            key = eec_key(split_key, config["eec"], normalization)
            eec_cache = cache_path(config["cache_dir"], "eec_tables", sample_name, key, "parquet")
            report["samples"][sample_name]["eec"][normalization] = {
                "key": key,
                "cache": str(eec_cache),
                "exists": eec_cache.exists(),
            }
    return report


def _read_eec_rows(path: Path) -> list[dict[str, Any]]:
    _, pq = __import__("cab_eec.io_tables", fromlist=["require_pyarrow"]).require_pyarrow()
    return pq.read_table(path).to_pylist()
