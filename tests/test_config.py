from pathlib import Path

from cab_eec.config import load_config
from cab_eec.paths import expand_input_paths


def test_expand_input_paths_matches_glob(tmp_path):
    (tmp_path / "a_2.root").write_text("")
    (tmp_path / "a_1.root").write_text("")
    paths = expand_input_paths(str(tmp_path / "a_*.root"))
    assert paths == [str(tmp_path / "a_1.root"), str(tmp_path / "a_2.root")]


def test_expand_input_paths_preserves_unmatched_pattern(tmp_path):
    pattern = tmp_path / "missing_*.root"
    assert expand_input_paths(str(pattern)) == [str(pattern)]


def test_load_config_expands_sample_globs(tmp_path):
    (tmp_path / "jewel_vac_1.root").write_text("")
    (tmp_path / "jewel_vac_2.root").write_text("")
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
samples:
  - name: jewel_vac
    files:
      - jewel_vac_*.root
""",
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)
    assert cfg["samples"][0]["files"] == [
        str(tmp_path / "jewel_vac_1.root"),
        str(tmp_path / "jewel_vac_2.root"),
    ]


def test_default_normalizations_include_scalar_radiator_sum(tmp_path):
    sample = tmp_path / "input.root"
    sample.write_text("")
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
samples:
  - name: s
    files:
      - {sample}
""",
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)
    assert cfg["eec"]["normalizations"] == ["jet_pt2", "radiator_pt2", "radiator_scalar_sum_pt2"]


def test_parent_pt2_config_aliases_to_radiator_pt2(tmp_path):
    sample = tmp_path / "input.root"
    sample.write_text("")
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
samples:
  - name: s
    files:
      - {sample}
eec:
  normalizations:
    - jet_pt2
    - parent_pt2
    - radiator_pt2
    - radiator_scalar_sum_pt2
""",
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)
    assert cfg["eec"]["normalizations"] == ["jet_pt2", "radiator_pt2", "radiator_scalar_sum_pt2"]
