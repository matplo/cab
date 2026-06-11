"""Stage cache keys and filesystem helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .paths import expand_input_paths


ANALYSIS_CONFIG_KEYS = {
    "samples",
    "input",
    "jet",
    "selections",
    "eec",
}

PLOT_CONFIG_KEYS = {"plots", "plot"}


def stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(data: Any, n: int = 16) -> str:
    return hashlib.sha256(stable_json(data).encode("utf-8")).hexdigest()[:n]


def file_identity(path: str | Path) -> dict[str, Any]:
    p = Path(path).expanduser().resolve()
    stat = p.stat()
    return {
        "path": str(p),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def input_identity(sample: dict[str, Any], input_cfg: dict[str, Any]) -> dict[str, Any]:
    paths = sample.get("files") or sample.get("paths") or []
    if isinstance(paths, (str, Path)):
        paths = [paths]
    paths = expand_input_paths(paths)
    return {
        "sample": sample.get("name") or sample.get("label"),
        "files": [file_identity(p) for p in paths],
        "tree": input_cfg.get("tree", "tracks"),
        "branches": input_cfg.get(
            "branches",
            {"event_id": "eventID", "px": "px", "py": "py", "pz": "pz", "energy": "energy"},
        ),
    }


def event_index_key(sample: dict[str, Any], input_cfg: dict[str, Any]) -> str:
    return stable_hash({"stage": "event_index", "input": input_identity(sample, input_cfg)})


def jet_splittings_key(
    sample: dict[str, Any],
    input_cfg: dict[str, Any],
    jet_cfg: dict[str, Any],
    selections: list[dict[str, Any]],
    backend_versions: dict[str, Any] | None = None,
) -> str:
    return stable_hash(
        {
            "stage": "jet_splittings",
            "input": input_identity(sample, input_cfg),
            "jet": jet_cfg,
            "selections": selections,
            "backend": backend_versions or {},
        }
    )


def eec_key(
    splitting_key: str,
    eec_cfg: dict[str, Any],
    normalization: str,
) -> str:
    return stable_hash(
        {
            "stage": "eec_tables",
            "splitting_key": splitting_key,
            "eec": eec_cfg,
            "normalization": normalization,
        }
    )


def cache_path(cache_dir: str | Path, stage: str, sample_name: str, key: str, suffix: str) -> Path:
    path = Path(cache_dir).expanduser() / stage
    path.mkdir(parents=True, exist_ok=True)
    safe_sample = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in sample_name)
    return path / f"{safe_sample}__{key}.{suffix}"


def analysis_fingerprint(config: dict[str, Any]) -> str:
    payload = {k: config.get(k) for k in ANALYSIS_CONFIG_KEYS if k in config}
    return stable_hash(payload)


def plot_fingerprint(config: dict[str, Any]) -> str:
    payload = {k: config.get(k) for k in PLOT_CONFIG_KEYS if k in config}
    return stable_hash(payload)
