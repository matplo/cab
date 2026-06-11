from cab_eec.cache import analysis_fingerprint, eec_key, jet_splittings_key


def test_plot_only_changes_do_not_change_analysis_fingerprint():
    base = {
        "samples": [{"name": "a", "files": ["x.root"]}],
        "input": {"tree": "tracks"},
        "jet": {"R": 0.4},
        "selections": [{"name": "maxkt", "mode": "max_kt"}],
        "eec": {"nbins": 10},
        "plot": {"color": "red"},
    }
    changed = dict(base)
    changed["plot"] = {"color": "blue", "title": "new"}
    assert analysis_fingerprint(base) == analysis_fingerprint(changed)


def test_eec_key_changes_without_changing_splitting_key():
    sample = {"name": "a", "files": ["pyproject.toml"]}
    input_cfg = {"tree": "tracks"}
    jet_cfg = {"R": 0.4}
    selections = [{"name": "maxkt", "mode": "max_kt"}]
    split_key = jet_splittings_key(sample, input_cfg, jet_cfg, selections, {})
    assert eec_key(split_key, {"nbins": 10}, "jet_pt2") != eec_key(split_key, {"nbins": 20}, "jet_pt2")
    assert eec_key(split_key, {"nbins": 10}, "jet_pt2") != eec_key(split_key, {"nbins": 10}, "radiator_pt2")
