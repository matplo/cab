"""Controlled cleanup helpers for CLI output directories."""

from __future__ import annotations

import shutil
from pathlib import Path


def remove_directory(path: str | Path, label: str) -> None:
    target = Path(path).expanduser().resolve()
    cwd = Path.cwd().resolve()
    home = Path.home().resolve()
    if target in (Path("/"), cwd, home):
        raise ValueError(f"refusing to clean {label} directory: {target}")
    if target.exists():
        if not target.is_dir():
            raise ValueError(f"refusing to clean {label}: not a directory: {target}")
        shutil.rmtree(target)
        print(f"[clean] removed {label}: {target}")
