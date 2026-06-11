from pathlib import Path

import pytest

from cab_eec.cleanup import remove_directory


def test_remove_directory_removes_existing_directory(tmp_path):
    target = tmp_path / "plots"
    target.mkdir()
    (target / "old.png").write_text("")
    remove_directory(target, "plot_dir")
    assert not target.exists()


def test_remove_directory_rejects_file(tmp_path):
    target = tmp_path / "not_a_dir"
    target.write_text("")
    with pytest.raises(ValueError):
        remove_directory(target, "output_dir")


def test_remove_directory_rejects_cwd():
    with pytest.raises(ValueError):
        remove_directory(Path.cwd(), "output_dir")
