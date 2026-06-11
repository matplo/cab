from cab_eec.fastjet_backend import split_parent_pt


class Parent:
    def perp(self):
        return 42.0

    def pt(self):
        return 99.0


class SplitWithPair:
    def pair(self):
        return Parent()


class SplitWithoutPair:
    pass


def test_split_parent_pt_prefers_pair_perp():
    assert split_parent_pt(SplitWithPair(), 6.0, 4.0) == 42.0


def test_split_parent_pt_falls_back_to_scalar_prong_sum():
    assert split_parent_pt(SplitWithoutPair(), 6.0, 4.0) == 10.0
