# CAB EEC

Clean CAB observable study pipeline.

The pipeline reads ROOT-format input files with `uproot` only, clusters jets through FastJet/fjcontrib exposed by heppyyier, selects Lund prongs, caches intermediate analysis products, and writes parquet tables for EEC and CAB observables.

See [docs/CAB_EEC_PIPELINE_PLAN.md](docs/CAB_EEC_PIPELINE_PLAN.md).

## Commands

```bash
cab-eec run config.yaml
cab-eec run --clean config.yaml
cab-eec plot config.yaml
cab-eec plot --clean config.yaml
cab-eec inspect-cache config.yaml
```

`plot --clean` removes only the configured plot directory before regenerating figures.
`run --clean` removes the configured analysis `output_dir` before running and defaults
to `--recompute all`, while leaving `cache_dir` itself in place.

The expected local environment is `henv`:

```bash
/Users/ploskon/.local/bin/henv --run python --version
/Users/ploskon/.local/bin/henv --run module avail
```

For local development without installing the package:

```bash
PYTHONPATH=src /Users/ploskon/.local/bin/henv --run python -m cab_eec.cli run config.yaml
PYTHONPATH=src /Users/ploskon/.local/bin/henv --run python -m cab_eec.cli plot config.yaml
```

The notebook [notebooks/ab_most_probable_rl.ipynb](notebooks/ab_most_probable_rl.ipynb)
extracts the most probable `R_L` from the AB EEC component by fitting a
log-normal-like shape to `eec_AB` from the parquet output. It initializes the
fit from the global maximum of the AB histogram in `ln(R_L)`. It bootstraps the
binned spectrum for the mode uncertainty. The fit is two-stage: first a local
window around the MPV seeds the Gaussian, then up to three wider final windows
are tried from that seed and the lowest-`chi2_ndf` candidate is kept. The default
windows include more high-`R_L` than low-`R_L` bins. If scipy is available, it
uses `scipy.optimize.curve_fit`; otherwise it falls back to a deterministic
numpy grid fit. Full bootstrap refits are available in the notebook with
`BOOTSTRAP_REFIT = True` after narrowing the sample, selection, normalization,
or fit window.

The notebook also builds `summary_df` and writes `ab_fit_summary.csv`, joining
fit mean/width columns to selected-splitting kinematics such as
`radiator_pt_mean`. A configurable summary-plot cell can put radiator pT on the
x-axis and compare max-kT/SoftDrop selections.

The Python backend loads FastJet/fjcontrib with `heppyyier.load("fastjet")` and
`heppyyier.load("fjcontrib")`. The shell modulefiles advertise the installed
packages, but the analysis code does not rely on native ROOT or PyROOT.

Input files in YAML may be literal paths or glob patterns:

```yaml
samples:
  - name: jewel_vac
    files:
      - /path/to/jewel_vac_*.root
```

Ratio plot y-ranges default to `[0, 4]` and can be configured:

```yaml
plot:
  ratio_ylim: [0, 4]
  ratio_eec_ylim: [0, 3]
  ratio_cab_ylim: [0.5, 1.5]
  ratio_rg_ylim: [0, 4]
```

EEC and CAB plots use `ln(delta R)` on the main x-axis and add a top `R_L`
axis with linear tick labels, including the standard ticks such as `0.01`,
`0.2`, `0.3`, and `0.4` when they are inside the plotted range. The x-axis
range is fixed from `eec.lndr_min` to `eec.lndr_max`. EEC component plots use
a linear y-scale by default; override with `plot.eec_yscale` if needed.

EEC normalization modes:

- `jet_pt2`: denominator is the selected jet `pT^2`.
- `radiator_pt2`: denominator is `LundDeclustering.pair().perp()^2`, the vector-summed selected radiator pT from fjcontrib.
- `radiator_scalar_sum_pt2`: denominator is `(pT_A + pT_B)^2`, where `pT_A` and `pT_B` are scalar sums over filtered prong constituents.
- `parent_pt2`: backward-compatible alias for `radiator_pt2`.
- `per_prong`: AA uses `pT_A^2`, BB uses `pT_B^2`, and AB uses `pT_A * pT_B`.
