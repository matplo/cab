import builtins

from cab_eec.progress import progress


def test_progress_yields_items():
    assert list(progress([1, 2, 3], disable=True)) == [1, 2, 3]


def test_progress_falls_back_without_tqdm(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "tqdm":
            raise ImportError("no tqdm")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert list(progress([1, 2, 3])) == [1, 2, 3]
