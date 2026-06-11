"""Path and glob helpers."""

from __future__ import annotations

import glob
from pathlib import Path


def expand_input_paths(paths: list[str | Path] | str | Path, base: str | Path | None = None) -> list[str]:
    if isinstance(paths, (str, Path)):
        paths = [paths]
    base_path = Path(base).expanduser() if base is not None else None
    expanded: list[str] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if base_path is not None and not path.is_absolute():
            path = base_path / path
        pattern = str(path)
        matches = sorted(glob.glob(pattern))
        if matches:
            expanded.extend(str(Path(match).resolve()) for match in matches)
        else:
            expanded.append(str(path.resolve() if path.exists() else path))
    return expanded
