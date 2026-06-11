import numpy as np

from cab_eec.plotting import _hist_density_ratio, _ratio_pairs, _ratio_with_uncertainty, _ratio_ylim, _set_lndr_xlim


def test_ratio_with_uncertainty():
    ratio, err = _ratio_with_uncertainty([4.0], [0.4], [2.0], [0.1])
    assert np.allclose(ratio, [2.0])
    assert np.allclose(err, [2.0 * ((0.4 / 4.0) ** 2 + (0.1 / 2.0) ** 2) ** 0.5])


def test_auto_detect_pbpb_over_pp():
    rows = [{"sample": "pp"}, {"sample": "PbPb"}]
    assert _ratio_pairs({}, rows) == [{"numerator": "PbPb", "denominator": "pp", "label": "PbPb/pp"}]


def test_auto_detect_jewel_med_over_vac():
    rows = [{"sample": "jewel_vac"}, {"sample": "jewel_med"}]
    assert _ratio_pairs({}, rows) == [
        {"numerator": "jewel_med", "denominator": "jewel_vac", "label": "jewel_med/jewel_vac"}
    ]


def test_configured_ratio_pairs_override_auto_detection():
    rows = [{"sample": "pp"}, {"sample": "PbPb"}]
    config = {"plot": {"ratio_pairs": [{"numerator": "AA", "denominator": "pp", "label": "AA/pp"}]}}
    assert _ratio_pairs(config, rows) == [{"numerator": "AA", "denominator": "pp", "label": "AA/pp"}]


def test_ratio_ylim_defaults_and_overrides():
    assert _ratio_ylim({}, "ratio_eec_ylim") == (0.0, 4.0)
    assert _ratio_ylim({"plot": {"ratio_ylim": [0.5, 2.0]}}, "ratio_eec_ylim") == (0.5, 2.0)
    assert _ratio_ylim({"plot": {"ratio_ylim": [0.0, 4.0], "ratio_cab_ylim": [0.8, 1.2]}}, "ratio_cab_ylim") == (0.8, 1.2)
    assert _ratio_ylim({"plot": {"ratio_ylim": None}}, "ratio_eec_ylim") is None


def test_hist_density_ratio():
    centers, ratio, err = _hist_density_ratio(
        np.asarray([0.1, 0.1, 0.3, 0.3]),
        np.asarray([0.1, 0.3, 0.3, 0.3]),
        np.asarray([0.0, 0.2, 0.4]),
    )
    assert np.allclose(centers, [0.1, 0.3])
    assert np.allclose(ratio, [2.0, 2.0 / 3.0])
    assert np.all(np.isfinite(err))


def test_set_lndr_xlim_uses_eec_config():
    class Axis:
        def __init__(self):
            self.xlim = None

        def set_xlim(self, lo, hi):
            self.xlim = (lo, hi)

    ax = Axis()
    _set_lndr_xlim(ax, {"eec": {"lndr_min": -5.0, "lndr_max": -0.9}})
    assert ax.xlim == (-5.0, -0.9)
