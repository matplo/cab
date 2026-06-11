"""Plotting from parquet outputs only."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from .cleanup import remove_directory


def plot(config: dict[str, Any], clean: bool = False) -> list[str]:
    output_dir = Path(config["output_dir"])
    plot_dir = Path(config.get("plot", {}).get("output_dir", output_dir / "plots"))
    if clean:
        remove_directory(plot_dir, "plot_dir")
    plot_dir.mkdir(parents=True, exist_ok=True)
    mpl_config_dir = plot_dir / ".matplotlib"
    xdg_cache_dir = plot_dir / ".cache"
    mpl_config_dir.mkdir(parents=True, exist_ok=True)
    xdg_cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_config_dir))
    os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache_dir))

    try:
        import matplotlib.pyplot as plt
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("matplotlib and pyarrow are required for plotting") from exc

    eec_path = output_dir / "eec.parquet"
    if not eec_path.exists():
        raise FileNotFoundError(f"EEC parquet not found: {eec_path}")
    rows = pq.read_table(eec_path).to_pylist()
    saved = []
    saved.extend(_plot_cab(rows, plot_dir, plt, config))
    saved.extend(_plot_components(rows, plot_dir, plt, config))
    saved.extend(_plot_sample_ratios(rows, plot_dir, plt, config))
    saved.extend(_plot_rg(config, plot_dir, plt))
    saved.extend(_plot_rg_ratios(config, plot_dir, plt, _ratio_pairs(config, rows)))
    return saved


def _plot_cab(rows: list[dict[str, Any]], plot_dir: Path, plt: Any, config: dict[str, Any]) -> list[str]:
    saved = []
    groups = _group_rows(rows, ("selection", "normalization"))
    for (selection, normalization), group_rows in groups.items():
        fig, ax = plt.subplots(figsize=(7, 4))
        for sample in sorted({r["sample"] for r in group_rows}):
            sample_rows = sorted([r for r in group_rows if r["sample"] == sample], key=lambda r: r["bin_center_lndr"])
            x = [r["bin_center_lndr"] for r in sample_rows]
            y = [r["cab_eec"] for r in sample_rows]
            e = [r["cab_eec_err"] for r in sample_rows]
            ax.step(x, y, where="mid", label=sample)
            ax.fill_between(x, [a - b for a, b in zip(y, e)], [a + b for a, b in zip(y, e)], alpha=0.15, step="mid")
        ax.axhline(1.0, color="grey", ls=":", lw=1)
        ax.set_xlabel("ln(delta R)")
        ax.set_ylabel("CAB_EEC = AB / sqrt(AA * BB)")
        ax.set_title(f"CAB EEC: {selection}, {normalization}")
        ax.legend(fontsize=8)
        _set_lndr_xlim(ax, config)
        _add_linear_rl_axis(ax)
        out = plot_dir / f"cab__{selection}__{normalization}.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        saved.append(str(out))
    return saved


def _plot_components(rows: list[dict[str, Any]], plot_dir: Path, plt: Any, config: dict[str, Any]) -> list[str]:
    saved = []
    groups = _group_rows(rows, ("sample", "selection", "normalization"))
    for (sample, selection, normalization), group_rows in groups.items():
        group_rows = sorted(group_rows, key=lambda r: r["bin_center_lndr"])
        x = [r["bin_center_lndr"] for r in group_rows]
        fig, ax = plt.subplots(figsize=(7, 4))
        for key, label in [("eec_AA", "AA"), ("eec_BB", "BB"), ("eec_AB", "AB"), ("eec_all", "all")]:
            ax.step(x, [r[key] for r in group_rows], where="mid", label=label)
        ax.set_yscale(config.get("plot", {}).get("eec_yscale", "linear"))
        ax.set_xlabel("ln(delta R)")
        ax.set_ylabel("dSigma_EEC / d(delta R)")
        ax.set_title(f"EEC: {sample}, {selection}, {normalization}")
        ax.legend(fontsize=8)
        _set_lndr_xlim(ax, config)
        _add_linear_rl_axis(ax)
        out = plot_dir / f"eec__{sample}__{selection}__{normalization}.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        saved.append(str(out))
    return saved


def _plot_sample_ratios(rows: list[dict[str, Any]], plot_dir: Path, plt: Any, config: dict[str, Any]) -> list[str]:
    saved = []
    ratio_pairs = _ratio_pairs(config, rows)
    if not ratio_pairs:
        return saved

    groups = _group_rows(rows, ("selection", "normalization"))
    for (selection, normalization), group_rows in groups.items():
        for pair in ratio_pairs:
            numerator = pair["numerator"]
            denominator = pair["denominator"]
            label = pair.get("label", f"{numerator}/{denominator}")
            num_rows = _rows_for_sample(group_rows, numerator)
            den_rows = _rows_for_sample(group_rows, denominator)
            if not num_rows or not den_rows:
                continue
            if not _compatible_bins(num_rows, den_rows):
                print(f"[w] skip ratio {label} {selection} {normalization}: incompatible bins")
                continue
            saved.append(_plot_component_ratio(num_rows, den_rows, label, selection, normalization, plot_dir, plt, config))
            saved.append(_plot_cab_ratio(num_rows, den_rows, label, selection, normalization, plot_dir, plt, config, numerator, denominator))
    saved.extend(_plot_cab_ratio_overlays(rows, ratio_pairs, plot_dir, plt, config))
    return saved


def _plot_component_ratio(
    num_rows: list[dict[str, Any]],
    den_rows: list[dict[str, Any]],
    label: str,
    selection: str,
    normalization: str,
    plot_dir: Path,
    plt: Any,
    config: dict[str, Any],
) -> str:
    x = np.asarray([r["bin_center_lndr"] for r in num_rows], dtype=float)
    fig, ax = plt.subplots(figsize=(7, 4))
    for value_key, error_key, component in [
        ("eec_AA", "eec_AA_err", "AA"),
        ("eec_BB", "eec_BB_err", "BB"),
        ("eec_AB", "eec_AB_err", "AB"),
        ("eec_all", "eec_all_err", "all"),
    ]:
        ratio, ratio_err = _ratio_with_uncertainty(
            [r[value_key] for r in num_rows],
            [r[error_key] for r in num_rows],
            [r[value_key] for r in den_rows],
            [r[error_key] for r in den_rows],
        )
        ax.step(x, ratio, where="mid", label=component)
        ax.fill_between(x, ratio - ratio_err, ratio + ratio_err, alpha=0.15, step="mid")
    ax.axhline(1.0, color="grey", ls=":", lw=1)
    ylim = _ratio_ylim(config, "ratio_eec_ylim")
    if ylim is not None:
        ax.set_ylim(ylim)
    ax.set_xlabel("ln(delta R)")
    ax.set_ylabel(label)
    ax.set_title(f"EEC ratio: {label}, {selection}, {normalization}")
    ax.legend(fontsize=8)
    _set_lndr_xlim(ax, config)
    _add_linear_rl_axis(ax)
    out = plot_dir / f"ratio_eec__{_safe_name(label)}__{selection}__{normalization}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def _plot_cab_ratio(
    num_rows: list[dict[str, Any]],
    den_rows: list[dict[str, Any]],
    label: str,
    selection: str,
    normalization: str,
    plot_dir: Path,
    plt: Any,
    config: dict[str, Any],
    numerator: str,
    denominator: str,
) -> str:
    x = np.asarray([r["bin_center_lndr"] for r in num_rows], dtype=float)
    ratio, ratio_err = _ratio_with_uncertainty(
        [r["cab_eec"] for r in num_rows],
        [r["cab_eec_err"] for r in num_rows],
        [r["cab_eec"] for r in den_rows],
        [r["cab_eec_err"] for r in den_rows],
    )
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.step(x, ratio, where="mid", label="CAB_EEC")
    ax.fill_between(x, ratio - ratio_err, ratio + ratio_err, alpha=0.15, step="mid")
    ax.axhline(1.0, color="grey", ls=":", lw=1)
    ylim = _ratio_ylim(config, "ratio_cab_ylim")
    if ylim is not None:
        ax.set_ylim(ylim)
    ax.set_xlabel("ln(delta R)")
    ax.set_ylabel(label)
    ax.set_title(f"CAB ratio: {label}, {selection}, {normalization}")
    _set_lndr_xlim(ax, config)
    _add_rg_median_markers(ax, config, selection, numerator, denominator)
    ax.legend(fontsize=8)
    _add_linear_rl_axis(ax)
    out = plot_dir / f"ratio_cab__{_safe_name(label)}__{selection}__{normalization}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def _plot_cab_ratio_overlays(
    rows: list[dict[str, Any]],
    ratio_pairs: list[dict[str, str]],
    plot_dir: Path,
    plt: Any,
    config: dict[str, Any],
) -> list[str]:
    saved = []
    by_normalization = _group_rows(rows, ("normalization",))
    for (normalization,), norm_rows in by_normalization.items():
        by_selection = _group_rows(norm_rows, ("selection",))
        for pair in ratio_pairs:
            numerator = pair["numerator"]
            denominator = pair["denominator"]
            label = pair.get("label", f"{numerator}/{denominator}")
            fig, ax = plt.subplots(figsize=(7, 4))
            n_curves = 0
            for (selection,), selection_rows in sorted(by_selection.items()):
                num_rows = _rows_for_sample(selection_rows, numerator)
                den_rows = _rows_for_sample(selection_rows, denominator)
                if not num_rows or not den_rows:
                    continue
                if not _compatible_bins(num_rows, den_rows):
                    print(f"[w] skip CAB overlay ratio {label} {selection} {normalization}: incompatible bins")
                    continue
                x = np.asarray([r["bin_center_lndr"] for r in num_rows], dtype=float)
                ratio, ratio_err = _ratio_with_uncertainty(
                    [r["cab_eec"] for r in num_rows],
                    [r["cab_eec_err"] for r in num_rows],
                    [r["cab_eec"] for r in den_rows],
                    [r["cab_eec_err"] for r in den_rows],
                )
                ax.step(x, ratio, where="mid", label=selection)
                ax.fill_between(x, ratio - ratio_err, ratio + ratio_err, alpha=0.12, step="mid")
                n_curves += 1
            if n_curves == 0:
                plt.close(fig)
                continue
            ax.axhline(1.0, color="grey", ls=":", lw=1)
            ylim = _ratio_ylim(config, "ratio_cab_ylim")
            if ylim is not None:
                ax.set_ylim(ylim)
            ax.set_xlabel("ln(delta R)")
            ax.set_ylabel(label)
            ax.set_title(f"CAB ratio overlay: {label}, {normalization}")
            ax.legend(fontsize=8)
            _set_lndr_xlim(ax, config)
            _add_linear_rl_axis(ax)
            out = plot_dir / f"ratio_cab_overlay__{_safe_name(label)}__{normalization}.png"
            fig.savefig(out, dpi=150, bbox_inches="tight")
            plt.close(fig)
            saved.append(str(out))
    return saved


def _plot_rg(config: dict[str, Any], plot_dir: Path, plt: Any) -> list[str]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("pyarrow is required for plotting") from exc

    saved = []
    for sample in config["samples"]:
        path = Path(config["output_dir"]) / f"{sample['name']}__splittings.parquet"
        if not path.exists():
            continue
        rows = pq.read_table(path, columns=["selection", "delta_rg"]).to_pylist()
        groups = _group_rows(rows, ("selection",))
        fig, ax = plt.subplots(figsize=(7, 4))
        for (selection,), group_rows in groups.items():
            ax.hist([r["delta_rg"] for r in group_rows], bins=50, histtype="step", density=True, label=selection)
        ax.set_xlabel("Delta = Rg")
        ax.set_ylabel("density")
        ax.set_title(f"Selected splitting opening angle: {sample['name']}")
        ax.legend(fontsize=8)
        out = plot_dir / f"rg__{sample['name']}.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        saved.append(str(out))
    return saved


def _plot_rg_ratios(config: dict[str, Any], plot_dir: Path, plt: Any, ratio_pairs: list[dict[str, str]]) -> list[str]:
    if not ratio_pairs:
        return []
    rows_by_sample = _load_splitting_rows_by_sample(config)
    if not rows_by_sample:
        return []
    saved = []
    all_rg = [float(row["delta_rg"]) for rows in rows_by_sample.values() for row in rows if np.isfinite(row["delta_rg"])]
    if not all_rg:
        return []
    plot_cfg = config.get("plot", {})
    rg_range = plot_cfg.get("rg_range")
    if rg_range is None:
        lo, hi = 0.0, max(all_rg)
        hi = hi if hi > 0 else 1.0
    else:
        lo, hi = float(rg_range[0]), float(rg_range[1])
    bins = int(plot_cfg.get("rg_bins", 50))
    edges = np.linspace(lo, hi, bins + 1)
    selections = sorted({row["selection"] for rows in rows_by_sample.values() for row in rows})

    for pair in ratio_pairs:
        numerator = pair["numerator"]
        denominator = pair["denominator"]
        label = pair.get("label", f"{numerator}/{denominator}")
        overlay_fig, overlay_ax = plt.subplots(figsize=(7, 4))
        overlay_curves = 0
        for selection in selections:
            num_values = _rg_values(rows_by_sample.get(numerator, []), selection)
            den_values = _rg_values(rows_by_sample.get(denominator, []), selection)
            if len(num_values) == 0 or len(den_values) == 0:
                continue
            centers, ratio, ratio_err = _hist_density_ratio(num_values, den_values, edges)

            fig, ax = plt.subplots(figsize=(7, 4))
            ax.step(centers, ratio, where="mid", label=selection)
            ax.fill_between(centers, ratio - ratio_err, ratio + ratio_err, alpha=0.15, step="mid")
            _finish_rg_ratio_axis(ax, label, config)
            ax.set_title(f"Rg ratio: {label}, {selection}")
            out = plot_dir / f"ratio_rg__{_safe_name(label)}__{selection}.png"
            fig.savefig(out, dpi=150, bbox_inches="tight")
            plt.close(fig)
            saved.append(str(out))

            overlay_ax.step(centers, ratio, where="mid", label=selection)
            overlay_ax.fill_between(centers, ratio - ratio_err, ratio + ratio_err, alpha=0.10, step="mid")
            overlay_curves += 1

        if overlay_curves:
            _finish_rg_ratio_axis(overlay_ax, label, config)
            overlay_ax.set_title(f"Rg ratio overlay: {label}")
            out = plot_dir / f"ratio_rg_overlay__{_safe_name(label)}.png"
            overlay_fig.savefig(out, dpi=150, bbox_inches="tight")
            saved.append(str(out))
        plt.close(overlay_fig)
    return saved


def _finish_rg_ratio_axis(ax: Any, label: str, config: dict[str, Any]) -> None:
    ax.axhline(1.0, color="grey", ls=":", lw=1)
    ylim = _ratio_ylim(config, "ratio_rg_ylim")
    if ylim is not None:
        ax.set_ylim(ylim)
    ax.set_xlabel("Rg")
    ax.set_ylabel(label)
    ax.legend(fontsize=8)


def _load_splitting_rows_by_sample(config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("pyarrow is required for Rg plotting") from exc

    rows_by_sample = {}
    for sample in config["samples"]:
        path = Path(config["output_dir"]) / f"{sample['name']}__splittings.parquet"
        if not path.exists():
            continue
        rows_by_sample[sample["name"]] = pq.read_table(path, columns=["selection", "delta_rg"]).to_pylist()
    return rows_by_sample


def _rg_values(rows: list[dict[str, Any]], selection: str) -> np.ndarray:
    return np.asarray([row["delta_rg"] for row in rows if row["selection"] == selection and np.isfinite(row["delta_rg"])], dtype=float)


def _hist_density_ratio(num_values: np.ndarray, den_values: np.ndarray, edges: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    num_counts, _ = np.histogram(num_values, bins=edges)
    den_counts, _ = np.histogram(den_values, bins=edges)
    widths = edges[1:] - edges[:-1]
    centers = 0.5 * (edges[:-1] + edges[1:])
    num_density = num_counts / max(len(num_values), 1) / widths
    den_density = den_counts / max(len(den_values), 1) / widths
    num_err = np.sqrt(num_counts) / max(len(num_values), 1) / widths
    den_err = np.sqrt(den_counts) / max(len(den_values), 1) / widths
    ratio, ratio_err = _ratio_with_uncertainty(num_density, num_err, den_density, den_err)
    return centers, ratio, ratio_err


def _group_rows(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    grouped = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        grouped.setdefault(key, []).append(row)
    return grouped


def _ratio_pairs(config: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    configured = config.get("plot", {}).get("ratio_pairs")
    if configured:
        return [
            {
                "numerator": pair["numerator"],
                "denominator": pair["denominator"],
                "label": pair.get("label", f"{pair['numerator']}/{pair['denominator']}"),
            }
            for pair in configured
        ]
    samples = sorted({row["sample"] for row in rows})
    pp = _find_sample(samples, ("pp", "vac", "vacuum", "jewel_vac", "jewel_vacuum"))
    pbpb = _find_sample(samples, ("pbpb", "pbpb_0_10", "pbpb_010", "aa", "med", "medium", "jewel_med", "jewel_medium"))
    if pp and pbpb:
        return [{"numerator": pbpb, "denominator": pp, "label": f"{pbpb}/{pp}"}]
    return []


def _find_sample(samples: list[str], normalized_candidates: tuple[str, ...]) -> str | None:
    normalized_candidates = tuple(_normalize_sample_name(candidate) for candidate in normalized_candidates)
    for sample in samples:
        normalized = _normalize_sample_name(sample)
        if normalized in normalized_candidates:
            return sample
    for sample in samples:
        normalized = _normalize_sample_name(sample)
        tokens = set(normalized.split("_"))
        if any(normalized.startswith(candidate + "_") or normalized.endswith("_" + candidate) or candidate in tokens for candidate in normalized_candidates):
            return sample
    return None


def _normalize_sample_name(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")


def _rows_for_sample(rows: list[dict[str, Any]], sample: str) -> list[dict[str, Any]]:
    return sorted([row for row in rows if row["sample"] == sample], key=lambda row: row["bin_center_lndr"])


def _compatible_bins(num_rows: list[dict[str, Any]], den_rows: list[dict[str, Any]]) -> bool:
    if len(num_rows) != len(den_rows):
        return False
    for num, den in zip(num_rows, den_rows):
        if num["bin_lo_lndr"] != den["bin_lo_lndr"] or num["bin_hi_lndr"] != den["bin_hi_lndr"]:
            return False
    return True


def _ratio_with_uncertainty(
    numerator: list[float] | np.ndarray,
    numerator_err: list[float] | np.ndarray,
    denominator: list[float] | np.ndarray,
    denominator_err: list[float] | np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    n = np.asarray(numerator, dtype=float)
    sn = np.asarray(numerator_err, dtype=float)
    d = np.asarray(denominator, dtype=float)
    sd = np.asarray(denominator_err, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(d != 0, n / d, np.nan)
        rel_n = np.where(n != 0, sn / n, 0.0)
        rel_d = np.where(d != 0, sd / d, 0.0)
        ratio_err = np.abs(ratio) * np.sqrt(rel_n**2 + rel_d**2)
    ratio_err = np.where(np.isfinite(ratio), ratio_err, np.nan)
    return ratio, ratio_err


def _ratio_ylim(config: dict[str, Any], specific_key: str) -> tuple[float, float] | None:
    plot_cfg = config.get("plot", {})
    value = plot_cfg.get(specific_key, plot_cfg.get("ratio_ylim", [0.0, 4.0]))
    if value is None:
        return None
    if len(value) != 2:
        raise ValueError(f"plot.{specific_key} / plot.ratio_ylim must have exactly two values")
    return float(value[0]), float(value[1])


def _set_lndr_xlim(ax: Any, config: dict[str, Any]) -> None:
    eec_cfg = config.get("eec", {})
    if "lndr_min" in eec_cfg and "lndr_max" in eec_cfg:
        ax.set_xlim(float(eec_cfg["lndr_min"]), float(eec_cfg["lndr_max"]))


def _add_linear_rl_axis(ax: Any) -> None:
    lo, hi = ax.get_xlim()
    tick_values = [0.01, 0.02, 0.03, 0.05, 0.1, 0.2, 0.3, 0.4]
    ticks = [tick for tick in tick_values if tick > 0 and lo <= np.log(tick) <= hi]
    if not ticks:
        return
    secax = ax.secondary_xaxis("top", functions=(_rl_forward, _rl_inverse))
    secax.set_xticks(ticks)
    secax.set_xticklabels([f"{tick:g}" for tick in ticks])
    secax.set_xlabel("R_L")


def _rl_forward(value: Any) -> Any:
    return np.exp(value)


def _rl_inverse(value: Any) -> Any:
    return np.log(np.maximum(value, 1e-12))


def _add_rg_median_markers(ax: Any, config: dict[str, Any], selection: str, numerator: str, denominator: str) -> None:
    rows_by_sample = _load_splitting_rows_by_sample(config)
    ylim = ax.get_ylim()
    marker_y = ylim[0] + 0.96 * (ylim[1] - ylim[0])
    for sample, marker, color in [(denominator, "v", "0.45"), (numerator, "^", "black")]:
        values = _rg_values(rows_by_sample.get(sample, []), selection)
        if len(values) == 0:
            continue
        median = float(np.median(values))
        if median <= 0:
            continue
        x = np.log(median)
        lo, hi = ax.get_xlim()
        if lo <= x <= hi:
            ax.plot([x], [marker_y], marker=marker, color=color, ms=5, label=f"median Rg {sample}")


def _safe_name(value: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in value).strip("_")
