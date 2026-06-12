"""Config loading and normalization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .paths import expand_input_paths


DEFAULT_BRANCHES = {
    "event_id": "eventID",
    "px": "px",
    "py": "py",
    "pz": "pz",
    "energy": "energy",
}


DEFAULT_CONFIG: dict[str, Any] = {
    "input": {
        "tree": "tracks",
        "branches": DEFAULT_BRANCHES,
        "batch_entries": 250_000,
    },
    "jet": {
        "R": 0.4,
        "pt_min": 100.0,
        "pt_max": None,
        "eta_max": 2.5,
        "eta_margin": 0.05,
        "pt_particle_min": 0.1,
        "max_events": None,
        "max_jets": None,
    },
    "selections": [{"name": "maxkt", "mode": "max_kt"}],
    "eec": {
        "lndr_min": -5.0,
        "lndr_max": 1.5,
        "nbins": 60,
        "normalizations": ["jet_pt2", "radiator_pt2", "radiator_scalar_sum_pt2"],
    },
    "output_dir": "outputs",
    "cache_dir": ".cache/cab_eec",
}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: str | Path) -> dict[str, Any]:
    cfg_path = Path(path).expanduser().resolve()
    with cfg_path.open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream) or {}
    cfg = _deep_merge(DEFAULT_CONFIG, raw)
    cfg["_config_path"] = str(cfg_path)
    cfg["_config_dir"] = str(cfg_path.parent)
    cfg["output_dir"] = str(_resolve_path(cfg["output_dir"], cfg_path.parent))
    cfg["cache_dir"] = str(_resolve_path(cfg["cache_dir"], cfg_path.parent))
    cfg["samples"] = [_normalize_sample(s, cfg_path.parent) for s in cfg.get("samples", [])]
    if not cfg["samples"]:
        raise ValueError("config must define at least one sample under 'samples'")
    cfg["selections"] = [_normalize_selection(s) for s in cfg.get("selections", [])]
    cfg["eec"]["normalizations"] = _normalize_eec_normalizations(cfg["eec"].get("normalizations", ["jet_pt2"]))
    return cfg


def _resolve_path(path: str | Path, base: Path) -> Path:
    p = Path(path).expanduser()
    if p.is_absolute():
        return p
    return base / p


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_eec_normalizations(value: Any) -> list[str]:
    aliases = {"parent_pt2": "radiator_pt2"}
    out: list[str] = []
    seen: set[str] = set()
    for item in _as_list(value):
        name = aliases.get(str(item), str(item))
        if name in seen:
            continue
        out.append(name)
        seen.add(name)
    return out


def _normalize_sample(sample: dict[str, Any], base: Path) -> dict[str, Any]:
    out = dict(sample)
    if "name" not in out:
        out["name"] = out.get("label")
    if not out.get("name"):
        raise ValueError("each sample needs a 'name' or 'label'")
    files = out.get("files") or out.get("paths") or out.get("path")
    files = _as_list(files)
    if not files:
        raise ValueError(f"sample {out['name']!r} has no files")
    out["files"] = expand_input_paths(files, base)
    return out


def _normalize_selection(selection: dict[str, Any]) -> dict[str, Any]:
    out = dict(selection)
    mode = out.get("mode", out.get("type", "max_kt"))
    out["mode"] = "max_kt" if mode in ("maxkt", "max_kt") else mode
    if "name" not in out:
        if out["mode"] == "soft_drop":
            z = out.get("z_cut", out.get("z", 0.1))
            out["name"] = f"sd_z{str(z).replace('.', 'p')}"
        else:
            out["name"] = "maxkt"
    return out
