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

JEWEL HepMC event generation lives in `heppyyier-utils`, not in the CAB
analysis package. A typical pre-analysis workflow is:

```bash
jewel_pipeline --tag pt100 --samples both --nevents 10000 --convert
jewel_prepare --tag pbpb_001 --samples medium --job-id 1
jewel_run outputs/jewel_events/pbpb_001
jewel_convert outputs/jewel_events/pbpb_001/jewel_med/events/jewel_med_pbpb_001.hepmc \
  outputs/jewel_events/pbpb_001/jewel_med/roots/jewel_med_pbpb_001.root \
  --subtract-4mom
```

Install/update the utility package through heppyyier once the recipe is
available:

```bash
heppyyier recipe update
heppyyier install heppyyier-utils
module load heppyyier-utils
```

The JEWEL utilities assume `jewel-2.4.0-simple` and `jewel-2.4.0-vac` are in
`PATH`, write each sample into a self-contained run directory under
`outputs/jewel_events/<tag>/`, and convert HepMC to CAB-compatible ROOT TTrees
with `uproot`.
For JEWEL production specifically, install/load `jewel` and `lhapdf` separately:

```bash
heppyyier install jewel lhapdf
module load jewel lhapdf
```

The required LHAPDF sets are `CT14nlo` (`PDFSET 13100`) for pp/vacuum and
`EPPS16nlo_CT14nlo_Pb208` (`PDFSET 901300`) for PbPb/medium.

`plot --clean` removes only the configured plot directory before regenerating figures.
`run --clean` removes the configured analysis `output_dir` before running and defaults
to `--recompute all`, while leaving `cache_dir` itself in place.

The expected local environment is `henv`:

```bash
henv --run python --version
henv --run module avail
```

For local development without installing the package:

```bash
PYTHONPATH=src henv --run python -m cab_eec.cli run config.yaml
PYTHONPATH=src henv --run python -m cab_eec.cli plot config.yaml
```

The Python backend loads FastJet/fjcontrib with `heppyyier.load("fastjet")` and
`heppyyier.load("fjcontrib")`. The shell modulefiles advertise the installed
packages, but the analysis code does not rely on native ROOT or PyROOT.

## Notebooks

The notebooks are post-processing tools for parquet outputs produced by
`cab-eec run`. They expect to be run from the repository root, where
`config.yaml` resolves `output_dir`, `eec.parquet`, and the per-sample
`*_splittings.parquet` files. Notebook-generated CSVs and PNGs are analysis
products and are ignored by git.

[notebooks/ab_most_probable_rl.ipynb](notebooks/ab_most_probable_rl.ipynb)
extracts the most probable `R_L` from the AB EEC component. It fits the stored
`eec_AB` density directly, without multiplying by `R_L`, using a Gaussian-like
shape in `ln(R_L)` plus an optional baseline. The fit is initialized from the
global maximum of the AB histogram, seeded with a local first-stage window, then
refit with up to three wider final windows. If scipy is available, the notebook
uses `scipy.optimize.curve_fit`; otherwise it falls back to a deterministic
numpy grid fit. It writes `ab_most_probable_rl.csv` and `ab_fit_summary.csv`,
where the latter joins fit mean/width columns to selected-splitting kinematics
such as mean selected radiator pT.

[notebooks/cab_ratio_y1_crossing.ipynb](notebooks/cab_ratio_y1_crossing.ipynb)
extracts where the CAB AA/pp ratio crosses `y=1`. It builds the ratio from
`cab_eec` and `cab_eec_err`, using `plot.ratio_pairs` from the YAML when
available. The benchmark crossing is a linear interpolation between the two
bins bracketing `y=1`; an optional local polynomial interpolation around that
same crossing is stored in parallel `poly_*` columns. The notebook writes
`cab_ratio_y1_crossings.csv` and `cab_ratio_y1_crossings_all.csv`, and it
displays/saves diagnostic plots showing the bracketing bins, interpolation
function, and intercept.

The CAB crossing notebook also includes summary studies:

- crossing `R_L` versus Soft Drop `z_cut` for each normalization;
- max-kT crossing `R_L` versus normalization;
- crossing shifts versus the selected radiator mean pT;
- crossing shifts versus the AA-pp difference in selected radiator mean pT;
- a 2D radiator-pT plane with `<pT>_radiator(pp)` on x, `<pT>_radiator(AA)` on
  y, and relative crossing shift in percent as color;
- a split-panel version of that 2D plane with one panel per scale choice.

For these summaries, `SUMMARY_METHOD = "linear"` uses the two-bin benchmark,
while `SUMMARY_METHOD = "poly"` uses the polynomial alternative. The selected
radiator pT is the stored `parent_pt`, filled from
`LundDeclustering.pair().perp()` with scalar prong-sum fallback.

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
- `per_prong`: AA uses `pT_A^2`, BB uses `pT_B^2`, and AB uses `pT_A * pT_B`.

Legacy configs using `parent_pt2` are accepted as an alias for `radiator_pt2`,
but new analyses should use `radiator_pt2`.
