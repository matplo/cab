import math

import numpy as np

from cab_eec.eec import EECAccumulator, denominators_for
from cab_eec.records import ParticleArrays, SplittingRecord


def make_record():
    return SplittingRecord(
        sample="s",
        selection="maxkt",
        event_id=1,
        jet_index=0,
        event_weight=1.0,
        jet_pt=10.0,
        jet_eta=0.0,
        jet_phi=0.0,
        delta_rg=0.2,
        z=0.4,
        kt=2.0,
        lnkt=math.log(2.0),
        pt_a=6.0,
        pt_b=4.0,
        parent_pt=11.0,
        parts_a=ParticleArrays([3.0, 3.0], [0.0, 0.1], [0.0, 0.0]),
        parts_b=ParticleArrays([4.0], [0.0], [0.2]),
    )


def test_denominators():
    r = make_record()
    assert denominators_for(r, "jet_pt2") == {"AA": 100.0, "BB": 100.0, "AB": 100.0}
    assert denominators_for(r, "radiator_pt2") == {"AA": 121.0, "BB": 121.0, "AB": 121.0}
    assert denominators_for(r, "radiator_scalar_sum_pt2") == {"AA": 100.0, "BB": 100.0, "AB": 100.0}
    assert denominators_for(r, "parent_pt2") == {"AA": 121.0, "BB": 121.0, "AB": 121.0}
    assert denominators_for(r, "per_prong") == {"AA": 36.0, "BB": 16.0, "AB": 24.0}


def test_pair_filling_and_cab():
    r = make_record()
    acc = EECAccumulator(np.linspace(-5, 1, 13))
    acc.fill_record(r, "jet_pt2")
    result = acc.result()
    assert result.n_jets == 1
    assert np.isclose(result.density["all"], result.density["AA"] + result.density["BB"] + result.density["AB"]).all()
    assert np.nanmax(result.density["AA"]) > 0
    assert np.nanmax(result.density["AB"]) > 0
    assert np.isnan(result.cab[result.density["BB"] == 0]).all()
