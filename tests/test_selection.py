from cab_eec.fastjet_backend import select_lund_splitting


class Split:
    def __init__(self, kt, z):
        self._kt = kt
        self._z = z

    def kt(self):
        return self._kt

    def z(self):
        return self._z


def test_select_max_kt():
    seq = [Split(1, 0.2), Split(5, 0.05), Split(3, 0.5)]
    assert select_lund_splitting(seq, {"mode": "max_kt"}).kt() == 5
    assert select_lund_splitting(seq, {"mode": "max_kt", "kt_min": 6}) is None


def test_select_soft_drop_first_passing():
    seq = [Split(5, 0.05), Split(3, 0.2), Split(8, 0.3)]
    selected = select_lund_splitting(seq, {"mode": "soft_drop", "z_cut": 0.1})
    assert selected.kt() == 3
    assert select_lund_splitting(seq, {"mode": "soft_drop", "z_cut": 0.4}) is None
