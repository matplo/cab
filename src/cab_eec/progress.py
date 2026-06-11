"""Progress bar wrapper."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TypeVar

T = TypeVar("T")


def progress(iterable: Iterable[T], **kwargs) -> Iterator[T]:
    try:
        from tqdm import tqdm
    except ImportError:
        return iter(iterable)
    return iter(tqdm(iterable, **kwargs))
