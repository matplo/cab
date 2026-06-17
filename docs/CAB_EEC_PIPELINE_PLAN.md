# CAB EEC Pipeline Plan

Date: 2026-06-09

Status: planning/specification, now used as the implementation guide.

Key decisions:

- Use `uproot` only for ROOT-format file I/O. Do not use PyROOT, ROOT C++, `TFile`, or native ROOT libraries for input.
- Use the `henv` environment and heppyyier-style FastJet/fjcontrib access for jet finding and Lund declustering.
- Use Lund-selected prongs for both `max_kt` and SoftDrop-like selections.
- Use staged caching so plotting changes do not rerun event I/O, jet finding, or EEC accumulation.
- Write parquet analysis outputs as the primary audit trail.

## Summary

Build the CAB analysis package in this repository so it reads ROOT-format JEWEL track files only through `uproot`, clusters jets with FastJet via heppyyier-style imports, selects prongs from Lund declustering, and writes reusable cached analysis products plus final parquet tables and plots.

The pipeline is split into cacheable stages so plot-only changes never rerun jet finding or EEC accumulation.

## Key Changes

- Add a CLI:
  - `cab-eec run config.yaml`: produce or reuse analysis caches and parquet outputs.
  - `cab-eec plot config.yaml`: read parquet outputs only and make figures.
  - `cab-eec inspect-cache config.yaml`: show cache hits/misses and cache keys.
- Use heppyyier-style FastJet setup:
  - `import heppyyier; heppyyier.load("fastjet"); heppyyier.load("fjcontrib")`
  - then `import cppyy, fastjet, fjcontrib`
- Run locally through `henv`, for example `PYTHONPATH=src henv --run python -m cab_eec.cli run config.yaml`.
- Read ROOT-format input with `uproot` only, expecting `tracks/eventID`, `px`, `py`, `pz`, and `energy`.
- Stream events in `uproot` batches grouped by `eventID`; no PyROOT or native ROOT I/O.

## Analysis And Cache Design

Use three cache layers under a configurable `cache_dir`:

- `event_index`: file list, file sizes/mtimes, tree name, branch names, event counts/ranges.
- `jet_splittings`: accepted jets and selected-splitting metadata, including constituents assigned to A/B for each configured selection.
- `eec_tables`: binned AA/BB/AB/all/CAB outputs for each EEC binning and normalization mode.

Cache keys are content/config hashes built from only the parameters that affect that stage:

- Input identity: absolute paths, file sizes, mtimes, tree/branch names.
- Jet stage: `jet_R`, jet pT/eta cuts, constituent pT cut, max events/jets.
- Splitting stage: selection mode, `z_cut`, max-kT settings, Lund/fjcontrib version metadata.
- EEC stage: bin edges, normalization mode, pair convention.
- Plot stage is not cached as analysis; plots are regenerated from parquet.

Changing plot labels, colors, ratio panels, axis limits, output formats, or figure lists must only rerun `cab-eec plot`.

Changing EEC binning or normalization reuses cached `jet_splittings` and recomputes only `eec_tables`.

Changing jet cuts, constituent cuts, input files, or `jet_R` invalidates downstream caches.

Add `--recompute stage` with choices `all`, `event_index`, `jet_splittings`, `eec_tables` for controlled invalidation.

## Observable Implementation

- Use `fjcontrib.LundGenerator()` for selected-splitting prong definitions.
- Implement selection modes:
  - `max_kt`: Lund splitting with maximum `kt()`.
  - `soft_drop`: first Lund splitting with `z() >= z_cut`.
- For each accepted selected splitting, cache:
  - jet `pt`, `eta`, `phi`, event weight.
  - `Delta = Rg = splitting.Delta()`.
  - `z`, `kt`, `lnkt`, `pT_A`, `pT_B`.
  - filtered A and B constituent arrays needed for EEC.
- Fill EEC histograms in `ln(delta_R)` bins:
  - AA/BB: off-diagonal same-prong ordered pairs.
  - AB: all A-B pairs with factor `2`.
  - `all = AA + BB + AB`.
  - density normalized by physical `delta_R` bin width.
- Support YAML-configurable EEC normalization modes:
  - `jet_pt2`
  - `radiator_pt2`, the selected Lund radiator scale `splitting.pair().perp()^2`, falling back to `(pT_A + pT_B)^2` only if unavailable
  - `radiator_scalar_sum_pt2`, the scalar constituent prong scale `(pT_A + pT_B)^2`
  - `per_prong`: AA uses `pT_A^2`, BB uses `pT_B^2`, AB uses `pT_A * pT_B`

## Outputs

Primary analysis outputs are parquet:

- `splittings.parquet`: per-jet selected-splitting records and `Delta`/`Rg`.
- `eec.parquet`: binned `eec_AA`, `eec_BB`, `eec_AB`, `eec_all`, `cab_eec`, uncertainties.
- `metadata.json`: cache keys, package versions, input identity, and full resolved config.

Plotting reads only these parquet/metadata outputs.

Plot products include:

- AA/BB/AB/all EEC panels.
- CAB overlays and medium/vacuum ratios.
- `Delta`/`Rg` distributions for selected splitting modes.

## Test Plan

- Unit-test cache key behavior:
  - plot-only config changes do not change analysis keys.
  - EEC bin changes invalidate only EEC cache.
  - jet cuts/input changes invalidate splitting and EEC caches.
- Unit-test pair filling and normalization modes.
- Unit-test selected-splitting observables, including persisted `Delta`/`Rg`.
- Integration smoke test with a tiny ROOT-format fixture read through `uproot`, verifying cache hit/miss behavior across repeated runs.

## Assumptions

- v1 optimizes for JEWEL ROOT-format `tracks` inputs.
- Default prong definition is Lund-selected.
- Default radiator normalization is configurable. Use `radiator_pt2` for the
  fjcontrib selected-radiator `pair().perp()^2` scale and
  `radiator_scalar_sum_pt2` for the scalar prong-sum `(pT_A + pT_B)^2` scale.
- Cached splitting records may be larger than final EEC tables, but this is the right tradeoff because it avoids rerunning uproot I/O, jet finding, and Lund declustering when changing EEC binning or plots.
